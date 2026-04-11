"""
CoinService — all coin credit and debit operations.

Every coin movement is a DB transaction that:
  1. Inserts a coin_ledger row (append-only)
  2. Updates users.coin_balance atomically
  3. Updates the entity that triggered the movement (verification or sweepstakes_entry)

The ledger is the source of truth. users.coin_balance is a denormalized cache.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import CoinRefType, CoinTxType
from app.models.coin import CoinLedger
from app.models.user import User
from app.models.verification import Verification

logger = logging.getLogger(__name__)


class CoinService:

    @staticmethod
    async def award_coins_for_verification(
        db: AsyncSession,
        user: User,
        verification: Verification,
        coin_amount: int,
    ) -> CoinLedger:
        """
        Award coins after a successful verification.
        Called inside a single DB transaction with the verification approval.

        Coin amount is determined by the goal_type.coin_reward —
        NEVER by the user's subscription tier.
        """
        if coin_amount <= 0:
            raise ValueError(f"coin_amount must be positive, got {coin_amount}")

        if verification.coins_awarded > 0:
            raise ValueError(f"Coins already awarded for verification {verification.id}")

        new_balance = user.coin_balance + coin_amount

        # 1. Append to ledger
        ledger_entry = CoinLedger(
            user_id=user.id,
            amount=coin_amount,
            balance_after=new_balance,
            transaction_type=CoinTxType.GOAL_VERIFIED,
            reference_id=verification.goal_id,
            reference_type=CoinRefType.GOAL,
            description=f"Goal verified — awarded {coin_amount} coin(s)",
        )
        db.add(ledger_entry)
        await db.flush()  # get ledger_entry.id

        # 2. Update user balance
        user.coin_balance = new_balance

        # 3. Stamp the verification
        verification.coins_awarded = coin_amount
        verification.coins_awarded_at = datetime.now(timezone.utc)

        logger.info(
            "Awarded %d coins to user=%s for verification=%s (new balance=%d)",
            coin_amount, user.id, verification.id, new_balance,
        )
        return ledger_entry

    @staticmethod
    async def spend_coins_for_entry(
        db: AsyncSession,
        user: User,
        sweepstakes_id: UUID,
        coins_to_spend: int,
    ) -> tuple["CoinLedger", "SweepstakesEntry"]:  # type: ignore[name-defined]
        """
        Spend coins to enter a sweepstakes. Atomic:
          1. Validate sufficient balance
          2. Debit coin_ledger
          3. Update user balance
          4. Create sweepstakes_entry
          5. Increment sweepstakes.total_entries_count
        """
        from app.models.sweepstakes import Sweepstakes, SweepstakesEntry

        if coins_to_spend <= 0:
            raise HTTPException(status_code=422, detail="coins_to_spend must be positive")

        if user.coin_balance < coins_to_spend:
            raise HTTPException(
                status_code=422,
                detail=f"Insufficient coins: have {user.coin_balance}, need {coins_to_spend}",
            )

        # Verify sweepstakes is active
        sweep_result = await db.execute(
            select(Sweepstakes).where(Sweepstakes.id == sweepstakes_id, Sweepstakes.status == "active")
        )
        sweepstakes = sweep_result.scalar_one_or_none()
        if sweepstakes is None:
            raise HTTPException(status_code=404, detail="Sweepstakes not found or not active")

        new_balance = user.coin_balance - coins_to_spend

        # 1 + 2. Ledger debit
        ledger_entry = CoinLedger(
            user_id=user.id,
            amount=-coins_to_spend,
            balance_after=new_balance,
            transaction_type=CoinTxType.SWEEPSTAKES_ENTRY,
            reference_type=CoinRefType.SWEEPSTAKES_ENTRY,
            description=f"Entered sweepstakes with {coins_to_spend} coin(s)",
        )
        db.add(ledger_entry)
        await db.flush()  # get ledger_entry.id before referencing in entry

        # 3. Update user balance
        user.coin_balance = new_balance

        # 4. Create entry row (ledger_id enforces debit ↔ entry integrity)
        entry = SweepstakesEntry(
            sweepstakes_id=sweepstakes_id,
            user_id=user.id,
            coins_entered=coins_to_spend,
            ledger_id=ledger_entry.id,
        )
        db.add(entry)

        # 5. Increment total pool counter atomically
        sweepstakes.total_entries_count += coins_to_spend

        await db.flush()

        logger.info(
            "User=%s spent %d coins on sweepstakes=%s (new balance=%d, pool=%d)",
            user.id, coins_to_spend, sweepstakes_id, new_balance, sweepstakes.total_entries_count,
        )
        return ledger_entry, entry

    @staticmethod
    async def get_balance_from_ledger(db: AsyncSession, user_id: UUID) -> int:
        """
        Recompute the authoritative coin balance from the ledger.
        Use this for auditing — for normal reads, use users.coin_balance.
        """
        result = await db.execute(
            select(CoinLedger.balance_after)
            .where(CoinLedger.user_id == user_id)
            .order_by(CoinLedger.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row if row is not None else 0
