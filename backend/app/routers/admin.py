"""
Admin router — protected endpoints for the manual review panel and draw management.

All routes require admin authentication (Firebase custom claim + DB check).
Never expose these routes publicly — serve behind VPN/IP allowlist on EC2.
"""
import logging
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.audit import AdminReview
from app.models.goal import Goal, GoalType
from app.models.sweepstakes import Sweepstakes, SweepstakesDraw, SweepstakesEntry, SweepstakesWinner
from app.models.user import User
from app.models.verification import Verification, VerificationPhoto
from app.schemas.admin import (
    AdminReviewDecisionRequest,
    AdminReviewDecisionResponse,
    AdminReviewQueueItem,
    TriggerDrawRequest,
    TriggerDrawResponse,
)
from app.services.notification_service import NotificationService
from app.services.storage_service import StorageService
from app.services.verification_service import VerificationService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


async def require_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Admin gate: checks Firebase custom claim 'admin' == True.
    Use this as a dependency on all admin routes.
    """
    firebase_user = getattr(request.state, "firebase_user", {})
    if not firebase_user.get("admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Review Queue ───────────────────────────────────────────────────────────────

@router.get("/reviews/queue", response_model=list[AdminReviewQueueItem])
async def get_review_queue(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Returns the pending free-tier verification review queue,
    ordered by priority (ascending) then age (oldest first — FIFO).
    """
    result = await db.execute(
        select(AdminReview)
        .options(
            selectinload(AdminReview.verification)
            .selectinload(Verification.photos),
            selectinload(AdminReview.verification)
            .selectinload(Verification.goal)
            .selectinload(Goal.goal_type),
        )
        .where(AdminReview.status == "queued")
        .order_by(AdminReview.priority.asc(), AdminReview.queued_at.asc())
        .limit(limit)
    )
    reviews = result.scalars().all()

    queue = []
    for review in reviews:
        v = review.verification
        goal = v.goal
        photo_urls = [StorageService.get_photo_url(p.s3_key) for p in sorted(v.photos, key=lambda p: p.photo_index)]

        queue.append(AdminReviewQueueItem(
            review_id=review.id,
            verification_id=v.id,
            user_id=v.user_id,
            goal_type_name=goal.goal_type.name,
            goal_local_date=goal.local_goal_date.isoformat(),
            queued_at=review.queued_at,
            sla_deadline=review.queued_at,  # sla_deadline is a generated column; use raw if needed
            priority=review.priority,
            photo_urls=photo_urls,
        ))
    return queue


@router.post("/reviews/{review_id}/claim", status_code=200)
async def claim_review(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Assign a review to the calling admin reviewer (prevents double-review)."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(AdminReview).where(AdminReview.id == review_id, AdminReview.status == "queued")
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found or already claimed")

    review.status = "in_review"
    review.assigned_to = admin.id
    review.assigned_at = datetime.now(timezone.utc)
    return {"status": "claimed", "review_id": str(review_id)}


@router.post("/reviews/{review_id}/decide", response_model=AdminReviewDecisionResponse)
async def decide_review(
    review_id: UUID,
    body: AdminReviewDecisionRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Approve or reject a free-tier verification.
    On approval: coins are awarded atomically.
    On rejection: user is notified with the reason.
    """
    verification = await VerificationService.process_admin_decision(
        db=db,
        admin_user=admin,
        review_id=review_id,
        decision=body.decision,
        rejection_reason=body.rejection_reason,
        reviewer_notes=body.reviewer_notes,
    )

    # Load user for notification
    user_result = await db.execute(select(User).where(User.id == verification.user_id))
    user = user_result.scalar_one()

    if body.decision == "approved":
        await NotificationService.send_verification_approved(db, user, verification.coins_awarded)
    else:
        await NotificationService.send_verification_rejected(db, user, body.rejection_reason)

    return AdminReviewDecisionResponse(
        review_id=review_id,
        verification_id=verification.id,
        decision=body.decision,
        coins_awarded=verification.coins_awarded,
    )


# ── Sweepstakes Draw ───────────────────────────────────────────────────────────

@router.post("/sweepstakes/draw", response_model=TriggerDrawResponse)
async def trigger_draw(
    body: TriggerDrawRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Execute the sweepstakes draw for a completed sweepstakes.

    Algorithm:
      1. Lock the sweepstakes row (status → 'drawing')
      2. Expand all entries into numbered slots 1..total_entries_count
      3. Select N random slots using secrets.randbelow() (cryptographically secure)
      4. Map each slot to its owner
      5. Create winner rows and draw audit record
      6. Notify winners
    """
    from datetime import datetime, timezone

    # Lock
    sweep_result = await db.execute(
        select(Sweepstakes).where(
            Sweepstakes.id == body.sweepstakes_id,
            Sweepstakes.status == "active",
        )
    )
    sweep = sweep_result.scalar_one_or_none()
    if sweep is None:
        raise HTTPException(status_code=404, detail="Sweepstakes not found or not active")

    sweep.status = "drawing"
    await db.flush()

    # Load all entries ordered deterministically for audit reproducibility
    entries_result = await db.execute(
        select(SweepstakesEntry)
        .where(SweepstakesEntry.sweepstakes_id == body.sweepstakes_id)
        .order_by(SweepstakesEntry.entered_at.asc(), SweepstakesEntry.id.asc())
    )
    entries = entries_result.scalars().all()

    if not entries:
        raise HTTPException(status_code=422, detail="No entries in this sweepstakes")

    total_entries = sum(e.coins_entered for e in entries)
    unique_participants = len({e.user_id for e in entries})

    # Build slot → user_id mapping (expand each entry's coins_entered into slots)
    # slot_map[i] = user_id for slot (i+1)  [1-indexed in winner row]
    slot_map: list[UUID] = []
    for entry in entries:
        slot_map.extend([entry.user_id] * entry.coins_entered)

    assert len(slot_map) == total_entries

    # Draw N winners (cryptographically secure)
    random_seed = secrets.token_hex(32)
    winning_slots: list[int] = []
    winners_data: list[dict] = []
    selected_users: set = set()  # prevent duplicate winners

    attempts = 0
    while len(winning_slots) < sweep.winner_count and attempts < total_entries * 2:
        slot = secrets.randbelow(total_entries)  # 0-indexed
        user_id = slot_map[slot]
        if user_id not in selected_users:
            selected_users.add(user_id)
            winning_slots.append(slot + 1)  # store as 1-indexed
            winners_data.append({"user_id": user_id, "slot": slot + 1})
        attempts += 1

    # Create draw audit record
    draw = SweepstakesDraw(
        sweepstakes_id=sweep.id,
        drawn_by=admin.id,
        total_entries_at_draw=total_entries,
        total_participants=unique_participants,
        random_seed=random_seed,
    )
    db.add(draw)
    await db.flush()

    # Create winner rows and notify
    for w in winners_data:
        winner = SweepstakesWinner(
            draw_id=draw.id,
            sweepstakes_id=sweep.id,
            user_id=w["user_id"],
            winning_entry_number=w["slot"],
            prize_description=sweep.prize_description,
        )
        db.add(winner)

    sweep.status = "completed"
    await db.flush()

    # Send win notifications
    from app.config import get_settings
    config = get_settings()
    from datetime import timedelta

    for w in winners_data:
        user_result = await db.execute(select(User).where(User.id == w["user_id"]))
        winner_user = user_result.scalar_one_or_none()
        if winner_user:
            await NotificationService.send_sweepstakes_win(db, winner_user, sweep.prize_description)

    logger.info(
        "Draw completed: sweep=%s total_entries=%d participants=%d winners=%d",
        sweep.id, total_entries, unique_participants, len(winners_data),
    )

    return TriggerDrawResponse(
        draw_id=draw.id,
        sweepstakes_id=sweep.id,
        total_entries=total_entries,
        total_participants=unique_participants,
        winners=winners_data,
    )
