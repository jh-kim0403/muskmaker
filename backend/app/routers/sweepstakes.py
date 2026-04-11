from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.sweepstakes import Sweepstakes, SweepstakesEntry, SweepstakesWinner
from app.models.user import User
from app.schemas.sweepstakes import (
    EnterSweepstakesRequest,
    EnterSweepstakesResponse,
    SweepstakesWithOddsResponse,
    WinnerResponse,
)
from app.services.coin_service import CoinService

router = APIRouter(tags=["sweepstakes"])


@router.get("/active", response_model=list[SweepstakesWithOddsResponse])
async def list_active_sweepstakes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all active sweepstakes with the user's personal odds.
    Odds = user_entries / total_entries (0 if total is 0).
    """
    sweep_result = await db.execute(
        select(Sweepstakes).where(Sweepstakes.status == "active")
    )
    sweepstakes_list = sweep_result.scalars().all()

    response = []
    for sweep in sweepstakes_list:
        user_entries = await _get_user_entries(db, current_user.id, sweep.id)
        odds = (user_entries / sweep.total_entries_count) if sweep.total_entries_count > 0 else None

        response.append(SweepstakesWithOddsResponse(
            **sweep.__dict__,
            user_entries=user_entries,
            estimated_odds=odds,
        ))
    return response


@router.get("/{sweepstakes_id}", response_model=SweepstakesWithOddsResponse)
async def get_sweepstakes(
    sweepstakes_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Sweepstakes).where(Sweepstakes.id == sweepstakes_id))
    sweep = result.scalar_one_or_none()
    if sweep is None:
        raise HTTPException(status_code=404, detail="Sweepstakes not found")

    user_entries = await _get_user_entries(db, current_user.id, sweepstakes_id)
    odds = (user_entries / sweep.total_entries_count) if sweep.total_entries_count > 0 else None

    return SweepstakesWithOddsResponse(
        **sweep.__dict__,
        user_entries=user_entries,
        estimated_odds=odds,
    )


@router.post("/enter", response_model=EnterSweepstakesResponse, status_code=201)
async def enter_sweepstakes(
    body: EnterSweepstakesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Spend coins to enter a sweepstakes. coins_to_spend coins = coins_to_spend entries.
    Atomic: coin debit + entry creation in one transaction.

    Fairness rules enforced here:
      - Coin source is user.coin_balance (earned from goal completions only)
      - No tier-based bonus entries — 1 coin = 1 entry for all users
    """
    ledger_entry, entry = await CoinService.spend_coins_for_entry(
        db=db,
        user=current_user,
        sweepstakes_id=body.sweepstakes_id,
        coins_to_spend=body.coins_to_spend,
    )

    # Fetch updated pool total
    sweep_result = await db.execute(select(Sweepstakes).where(Sweepstakes.id == body.sweepstakes_id))
    sweep = sweep_result.scalar_one()

    user_total = await _get_user_entries(db, current_user.id, body.sweepstakes_id)
    odds = user_total / sweep.total_entries_count if sweep.total_entries_count > 0 else 0.0

    return EnterSweepstakesResponse(
        entry_id=entry.id,
        coins_entered=body.coins_to_spend,
        new_coin_balance=current_user.coin_balance,
        user_total_entries=user_total,
        total_pool_entries=sweep.total_entries_count,
        estimated_odds=odds,
    )


@router.get("/my/wins", response_model=list[WinnerResponse])
async def get_my_wins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all sweepstakes the user has won."""
    result = await db.execute(
        select(SweepstakesWinner)
        .where(SweepstakesWinner.user_id == current_user.id)
        .order_by(SweepstakesWinner.created_at.desc())
    )
    return result.scalars().all()


async def _get_user_entries(db: AsyncSession, user_id, sweepstakes_id) -> int:
    """Sum all coins the user has entered into a specific sweepstakes."""
    result = await db.execute(
        select(func.coalesce(func.sum(SweepstakesEntry.coins_entered), 0))
        .where(
            SweepstakesEntry.user_id == user_id,
            SweepstakesEntry.sweepstakes_id == sweepstakes_id,
        )
    )
    return result.scalar_one()
