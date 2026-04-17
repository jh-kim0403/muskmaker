import uuid
from datetime import datetime
from sqlalchemy import (
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    TIMESTAMP,
    Text,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk


class CoinLedger(Base):
    """
    Append-only ledger of every coin movement for every user.

    Rules:
      - Rows are NEVER updated or deleted (enforced by DB trigger + ORM event below).
      - Positive amount = credit (coins earned).
      - Negative amount = debit (coins spent on sweepstakes entries).
      - balance_after = running balance after this transaction, for O(1) balance lookup.
      - users.coin_balance is a denormalized cache kept in sync via application
        transactions. If ever inconsistent, recompute from:
          SELECT balance_after FROM coin_ledger
          WHERE user_id = ? ORDER BY created_at DESC LIMIT 1

    Coin award flow (single DB transaction):
      1. INSERT INTO coin_ledger (amount=+N, transaction_type='goal_verified', ...)
      2. UPDATE users SET coin_balance = coin_balance + N WHERE id = ?
      3. UPDATE verifications SET coins_awarded = N, coins_awarded_at = NOW()

    Entry spend flow (single DB transaction):
      1. INSERT INTO coin_ledger (amount=-N, transaction_type='sweepstakes_entry', ...)
      2. UPDATE users SET coin_balance = coin_balance - N WHERE id = ?
      3. INSERT INTO sweepstakes_entries (coins_entered=N, ledger_id=<new ledger row id>)
      4. UPDATE sweepstakes SET total_entries_count = total_entries_count + N
    """
    __tablename__ = "coin_ledger"
    __table_args__ = (
        CheckConstraint("amount != 0",        name="chk_amount_nonzero"),
        CheckConstraint("balance_after >= 0", name="chk_balance_nonneg"),
        CheckConstraint(
            "(reference_id IS NULL AND reference_type IS NULL) OR "
            "(reference_id IS NOT NULL AND reference_type IS NOT NULL)",
            name="chk_ref_consistency",
        ),
    )

    id: Mapped[uuid.UUID]           = uuid_pk()
    user_id: Mapped[uuid.UUID]      = mapped_column(ForeignKey("users.id"), nullable=False)

    # Positive = earned, Negative = spent
    amount: Mapped[int]             = mapped_column(Integer, nullable=False)

    # Running balance AFTER this transaction. Never compute from SUM() — read this.
    balance_after: Mapped[int]      = mapped_column(Integer, nullable=False)

    transaction_type: Mapped[str]   = mapped_column(
        SAEnum("goal_verified", "sweepstakes_entry", "admin_adjustment", "refund",
               name="coin_tx_type"),
        nullable=False,
    )

    # Polymorphic reference: what caused this transaction?
    reference_id: Mapped[uuid.UUID | None]  = mapped_column()
    reference_type: Mapped[str | None]      = mapped_column(
        SAEnum("goal", "sweepstakes_entry", "admin", name="coin_ref_type")
    )

    description: Mapped[str | None] = mapped_column(Text)

    # No updated_at — this table is intentionally immutable after insert.
    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="coin_ledger_entries")

    def __repr__(self) -> str:
        return f"<CoinLedger id={self.id} user={self.user_id} amount={self.amount} balance_after={self.balance_after}>"


Index("idx_ledger_user", CoinLedger.user_id, CoinLedger.created_at.desc())
Index("idx_ledger_type", CoinLedger.transaction_type)
Index(
    "idx_ledger_reference",
    CoinLedger.reference_id,
    CoinLedger.reference_type,
    postgresql_where=CoinLedger.reference_id.is_not(None),
)


# ── ORM-level immutability guard ──────────────────────────────────────────────
# The DB trigger (trg_ledger_immutable) is the primary enforcement.
# This event listener catches any accidental mutation from within the ORM
# before it even reaches the database.
@event.listens_for(CoinLedger, "before_update")
def _prevent_ledger_update(mapper, connection, target: CoinLedger) -> None:
    raise RuntimeError(
        f"coin_ledger rows are immutable. "
        f"Attempted UPDATE on row id={target.id}. "
        f"To correct an error, insert a reversing entry instead."
    )


@event.listens_for(CoinLedger, "before_delete")
def _prevent_ledger_delete(mapper, connection, target: CoinLedger) -> None:
    raise RuntimeError(
        f"coin_ledger rows are immutable. "
        f"Attempted DELETE on row id={target.id}. "
        f"To correct an error, insert a reversing entry instead."
    )
