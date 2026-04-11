"""
VerificationService — the core of the anti-cheat and review system.

Two completely separate paths:
  FREE:
    - 2 photos required (always)
    - No AI — manual admin review only
    - Creates admin_review queue entry
    - Coins awarded ONLY after admin approves

  PREMIUM (standard):
    - 2 photos required
    - Instant AI verification
    - Coins awarded immediately on AI pass
    - Routed to manual review on AI uncertain

  PREMIUM (location):
    - 1 photo required
    - Location data required (explicit consent obtained client-side)
    - Instant AI verification with GPS cross-check
    - Coins awarded immediately on AI pass
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.constants import (
    AIVerdict, CheatEvent, GoalStatus, PHOTO_COUNT_BY_PATH,
    VerificationPath, VerificationStatus,
)
from app.models.audit import AdminReview, AntiCheatLog
from app.models.goal import Goal, GoalType
from app.models.user import User
from app.models.verification import Verification, VerificationPhoto
from app.services.ai_service import AIService
from app.services.coin_service import CoinService
from app.services.storage_service import StorageService
from app.services.timezone_service import TimezoneService

logger = logging.getLogger(__name__)
settings = get_settings()


class VerificationService:

    @staticmethod
    async def request_upload_url(
        db: AsyncSession,
        user: User,
        goal_id: UUID,
        photo_index: int,
        mime_type: str,
    ) -> dict:
        """
        Validate the goal is eligible for verification and generate a pre-signed
        S3 PUT URL the client will upload directly to.
        """
        goal = await VerificationService._get_eligible_goal(db, user, goal_id)

        if photo_index not in (0, 1):
            raise HTTPException(status_code=422, detail="photo_index must be 0 or 1")

        s3_key = StorageService.generate_photo_s3_key(str(user.id), str(goal_id), photo_index)
        upload_url, expires_at = StorageService.generate_upload_url(s3_key, mime_type)

        return {"upload_url": upload_url, "s3_key": s3_key, "expires_at": expires_at}

    @staticmethod
    async def submit_verification(
        db: AsyncSession,
        user: User,
        goal_id: UUID,
        verification_path: str,
        photo_s3_keys: list[str],
        location_lat=None,
        location_lng=None,
        location_accuracy_meters=None,
        location_captured_at=None,
    ) -> Verification:
        """
        Full verification submission pipeline:
          1. Validate goal eligibility (same-day check)
          2. Validate path authorization (free vs premium)
          3. Validate photo count for path
          4. Validate S3 keys exist
          5. Extract EXIF server-side
          6. Anti-cheat checks
          7. Create verification + photo rows
          8. Route: free → admin queue | premium → AI
          9. Award coins if immediately approved
        """
        # ── 1. Goal eligibility ───────────────────────────────────────────────
        goal = await VerificationService._get_eligible_goal(db, user, goal_id)

        # Same-day check: submission must be on the same local date as goal creation
        now_utc = datetime.now(timezone.utc)
        local_submission_date = TimezoneService.user_local_date(now_utc, user.timezone)

        if local_submission_date != goal.local_goal_date:
            raise HTTPException(
                status_code=422,
                detail="Goal has expired — verification must be submitted on the same local day it was created",
            )

        # ── 2. Path authorization ─────────────────────────────────────────────
        if verification_path in (VerificationPath.PREMIUM_AI_STANDARD, VerificationPath.PREMIUM_AI_LOCATION):
            if not user.is_premium:
                raise HTTPException(status_code=403, detail="Premium subscription required for AI verification")

        if verification_path == VerificationPath.PREMIUM_AI_LOCATION:
            if location_lat is None or location_lng is None:
                raise HTTPException(status_code=422, detail="Location data required for the 1-photo AI path")

        # Free users may only use free_manual
        if not user.is_premium and verification_path != VerificationPath.FREE_MANUAL:
            raise HTTPException(status_code=403, detail="Free users must use the free_manual path")

        # ── 3. Photo count validation ─────────────────────────────────────────
        required_photos = PHOTO_COUNT_BY_PATH[verification_path]
        if len(photo_s3_keys) != required_photos:
            raise HTTPException(
                status_code=422,
                detail=f"This path requires exactly {required_photos} photo(s), got {len(photo_s3_keys)}",
            )

        # ── 4. Verify S3 keys exist ───────────────────────────────────────────
        for key in photo_s3_keys:
            if not StorageService.verify_s3_key_exists(key):
                raise HTTPException(status_code=422, detail=f"Photo not found in storage: {key}")

        # ── 5. Extract EXIF server-side (never trust client) ──────────────────
        exif_data_list = [StorageService.extract_exif(key) for key in photo_s3_keys]
        primary_exif = exif_data_list[0]  # use first photo as primary timestamp reference

        # ── 6. Anti-cheat checks ──────────────────────────────────────────────
        server_receipt_at = now_utc
        exif_captured_at = primary_exif.get("captured_at")
        delta_seconds = None

        if exif_captured_at:
            delta_seconds = abs(int((server_receipt_at - exif_captured_at).total_seconds()))

            if delta_seconds > settings.exif_delta_fail_seconds:
                # Hard fail: timestamp too far off
                db.add(AntiCheatLog(
                    user_id=user.id,
                    event_type=CheatEvent.ABNORMAL_DELTA,
                    severity="high",
                    reference_type="verification",
                    details={"delta_seconds": delta_seconds, "goal_id": str(goal_id)},
                    auto_action="blocked",
                ))
                await db.flush()
                raise HTTPException(
                    status_code=422,
                    detail="Photo timestamp is too far from submission time — please retake the photo",
                )
        else:
            # No EXIF at all — likely library upload attempt or stripped metadata
            db.add(AntiCheatLog(
                user_id=user.id,
                event_type=CheatEvent.METADATA_STRIPPED,
                severity="medium",
                reference_type="verification",
                details={"goal_id": str(goal_id), "s3_key": photo_s3_keys[0]},
                auto_action="flagged_for_review",
            ))

        # ── 7. Create verification and photo rows ─────────────────────────────
        # Load goal_type for coin_reward
        gt_result = await db.execute(select(GoalType).where(GoalType.id == goal.goal_type_id))
        goal_type = gt_result.scalar_one()

        verification = Verification(
            goal_id=goal_id,
            user_id=user.id,
            verification_path=verification_path,
            submitted_at=now_utc,
            local_submission_date=local_submission_date,
            timezone_at_submission=user.timezone,
            exif_captured_at=exif_captured_at,
            server_receipt_at=server_receipt_at,
            timestamp_delta_seconds=delta_seconds,
            # Location — only set for location path
            location_lat=location_lat if verification_path == VerificationPath.PREMIUM_AI_LOCATION else None,
            location_lng=location_lng if verification_path == VerificationPath.PREMIUM_AI_LOCATION else None,
            location_accuracy_meters=location_accuracy_meters if verification_path == VerificationPath.PREMIUM_AI_LOCATION else None,
            location_captured_at=location_captured_at if verification_path == VerificationPath.PREMIUM_AI_LOCATION else None,
        )
        db.add(verification)
        await db.flush()  # get verification.id

        # Create photo rows
        for idx, (s3_key, exif) in enumerate(zip(photo_s3_keys, exif_data_list)):
            photo = VerificationPhoto(
                verification_id=verification.id,
                user_id=user.id,
                s3_key=s3_key,
                s3_bucket=settings.s3_bucket_photos,
                photo_index=idx,
                exif_captured_at=exif.get("captured_at"),
                exif_gps_lat=exif.get("gps_lat"),
                exif_gps_lng=exif.get("gps_lng"),
                exif_gps_alt_m=exif.get("gps_alt_m"),
                exif_device_make=exif.get("device_make"),
                exif_device_model=exif.get("device_model"),
                file_size_bytes=exif.get("file_size_bytes"),
                width_px=exif.get("width_px"),
                height_px=exif.get("height_px"),
            )
            db.add(photo)

        # Mark goal as submitted
        goal.status = GoalStatus.SUBMITTED
        await db.flush()

        # ── 8. Route to review path ───────────────────────────────────────────
        if verification_path == VerificationPath.FREE_MANUAL:
            await VerificationService._route_to_manual_review(db, verification)

        else:
            # Premium: run AI verification
            photo_urls = [StorageService.get_photo_url(key) for key in photo_s3_keys]
            ai_result = await AIService.run_verification(
                goal_type_name=goal_type.name,
                goal_type_slug=goal_type.slug,
                photo_urls=photo_urls,
                exif_captured_at=exif_captured_at,
                server_receipt_at=server_receipt_at,
                location_lat=float(location_lat) if location_lat else None,
                location_lng=float(location_lng) if location_lng else None,
            )

            # Store AI result on verification
            verification.ai_confidence_score = ai_result["confidence_score"]
            verification.ai_verdict = ai_result["verdict"]
            verification.ai_result_payload = ai_result
            verification.ai_processed_at = datetime.now(timezone.utc)

            if ai_result["verdict"] == AIVerdict.PASS:
                # Instant approval + coin award
                await VerificationService._approve_verification(
                    db, user, verification, goal, goal_type.coin_reward
                )
            elif ai_result["verdict"] == AIVerdict.FAIL:
                verification.status = VerificationStatus.REJECTED
                verification.rejection_reason = "Automated review: photo does not show the stated goal"
                goal.status = GoalStatus.REJECTED
            else:
                # Uncertain: escalate to manual review
                await VerificationService._route_to_manual_review(db, verification, priority=3)

        await db.flush()
        await db.refresh(verification, ["photos"])
        return verification

    # ── Admin review workflow ──────────────────────────────────────────────────

    @staticmethod
    async def process_admin_decision(
        db: AsyncSession,
        admin_user: User,
        review_id: UUID,
        decision: str,
        rejection_reason: str | None,
        reviewer_notes: str | None,
    ) -> Verification:
        """
        Admin approves or rejects a free-tier verification.
        On approval: awards coins atomically.
        """
        from app.models.audit import AdminReview

        review_result = await db.execute(
            select(AdminReview)
            .options(
                selectinload(AdminReview.verification)
                .selectinload(Verification.goal)
                .selectinload(Goal.goal_type)
            )
            .where(AdminReview.id == review_id, AdminReview.status == "in_review")
        )
        review = review_result.scalar_one_or_none()
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found or not in 'in_review' state")

        verification = review.verification
        goal = verification.goal
        goal_type = goal.goal_type

        # Load user for coin award
        user_result = await db.execute(select(User).where(User.id == verification.user_id))
        user = user_result.scalar_one()

        now_utc = datetime.now(timezone.utc)

        if decision == "approved":
            await VerificationService._approve_verification(
                db, user, verification, goal, goal_type.coin_reward
            )
            review.status = "approved"
        elif decision == "rejected":
            verification.status = VerificationStatus.REJECTED
            verification.rejection_reason = rejection_reason
            verification.reviewed_at = now_utc
            verification.reviewer_id = admin_user.id
            verification.internal_notes = reviewer_notes
            goal.status = GoalStatus.REJECTED
            review.status = "rejected"
            review.rejection_reason = rejection_reason
        else:
            raise HTTPException(status_code=422, detail="decision must be 'approved' or 'rejected'")

        review.completed_at = now_utc
        review.reviewer_notes = reviewer_notes
        return verification

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    async def _get_eligible_goal(db: AsyncSession, user: User, goal_id: UUID) -> Goal:
        """Fetch a goal and verify it belongs to the user and is still active."""
        result = await db.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id)
        )
        goal = result.scalar_one_or_none()
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")

        if goal.status == GoalStatus.EXPIRED:
            raise HTTPException(status_code=422, detail="Goal has expired and can no longer be verified")

        if goal.status not in (GoalStatus.ACTIVE,):
            raise HTTPException(
                status_code=422,
                detail=f"Goal cannot be verified in its current state: {goal.status}",
            )

        # Check expiry by clock (in case worker hasn't run yet)
        if datetime.now(timezone.utc) > goal.expires_at:
            goal.status = GoalStatus.EXPIRED
            raise HTTPException(status_code=422, detail="Goal has expired — the local day has ended")

        return goal

    @staticmethod
    async def _approve_verification(
        db: AsyncSession,
        user: User,
        verification: Verification,
        goal: Goal,
        coin_reward: int,
    ) -> None:
        now_utc = datetime.now(timezone.utc)
        verification.status = VerificationStatus.APPROVED
        verification.reviewed_at = now_utc
        goal.status = GoalStatus.APPROVED

        await CoinService.award_coins_for_verification(db, user, verification, coin_reward)

    @staticmethod
    async def _route_to_manual_review(
        db: AsyncSession,
        verification: Verification,
        priority: int = 5,
    ) -> None:
        """Create an admin_review queue entry for this verification."""
        verification.status = VerificationStatus.PENDING_REVIEW

        now = datetime.now(timezone.utc)
        review = AdminReview(
            verification_id=verification.id,
            user_id=verification.user_id,
            priority=priority,
            queued_at=now,
            sla_deadline=now + timedelta(hours=24),
        )
        db.add(review)
