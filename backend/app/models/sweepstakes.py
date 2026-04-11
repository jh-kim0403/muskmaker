import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, BigInteger, Boolean, ForeignKey, TIMESTAMP,
    CheckConstraint, Enum as SAEnum, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk


class Sweepstakes(Base):
    """
    One sweepstakes cycle (typically weekly).

    total_entries_count is a denormalized counter incremented atomically
    on each entry insert. Used for real-time odds display without aggregation.

    Apple compliance fields (5.3): no_purchase_necessary and apple_not_sponsor
    are stored and surfaced in the in-app rules display.
    """
    __tablename__ = "sweepstakes"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at",                     name="chk_dates"),
        CheckConstraint("draw_at IS NULL OR draw_at >= ends_at",   name="chk_draw_after"),
        CheckConstraint("winner_count >= 1",                       name="chk_winner_count"),
    )

    id: Mapped[uuid.UUID]           = uuid_pk()
    title: Mapped[str]              = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    prize_description: Mapped[str]  = mapped_column(String, nullable=False)  # "$50 Amazon Gift Card"
    rules_url: Mapped[str | None]   = mapped_column(String)

    status: Mapped[str]             = mapped_column(
        SAEnum("upcoming", "active", "drawing", "completed", "cancelled", name="sweepstakes_status"),
        nullable=False,
        default="upcoming",
    )

    starts_at: Mapped[datetime]     = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    draw_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # Denormalized for fast odds display. Updated atomically on each entry insert.
    total_entries_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    winner_count: Mapped[int]        = mapped_column(Integer, nullable=False, default=1)

    # Apple guideline 5.3 compliance fields
    no_purchase_necessary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sponsor_name: Mapped[str]           = mapped_column(String, nullable=False, default="MuskMaker")
    apple_not_sponsor: Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    entries: Mapped[list["SweepstakesEntry"]] = relationship(back_populates="sweepstakes", lazy="select")
    draw:    Mapped["SweepstakesDraw | None"] = relationship(back_populates="sweepstakes", uselist=False, lazy="select")
    winners: Mapped[list["SweepstakesWinner"]] = relationship(back_populates="sweepstakes", lazy="select")

    def __repr__(self) -> str:
        return f"<Sweepstakes id={self.id} title={self.title!r} status={self.status}>"


class SweepstakesEntry(Base):
    """
    Records one entry event: user spends N coins → N entries added.

    ledger_id enforces that an entry cannot exist without a corresponding
    coin debit in coin_ledger (FK + UNIQUE).

    Odds calculation:
      user_entries  = SUM(coins_entered) WHERE user_id=? AND sweepstakes_id=?
      total_entries = sweepstakes.total_entries_count
      probability   = user_entries / total_entries
    """
    __tablename__ = "sweepstakes_entries"

    id: Mapped[uuid.UUID]               = uuid_pk()
    sweepstakes_id: Mapped[uuid.UUID]   = mapped_column(ForeignKey("sweepstakes.id"), nullable=False)
    user_id: Mapped[uuid.UUID]          = mapped_column(ForeignKey("users.id"), nullable=False)

    coins_entered: Mapped[int]          = mapped_column(Integer, nullable=False)

    # Enforces entry ↔ debit integrity: entry cannot exist without its ledger row.
    ledger_id: Mapped[uuid.UUID]        = mapped_column(ForeignKey("coin_ledger.id"), nullable=False, unique=True)

    entered_at: Mapped[datetime]        = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    sweepstakes: Mapped["Sweepstakes"]  = relationship(back_populates="entries")
    user: Mapped["User"]                = relationship(back_populates="sweepstakes_entries")
    ledger_entry: Mapped["CoinLedger"]  = relationship(foreign_keys=[ledger_id])

    def __repr__(self) -> str:
        return f"<SweepstakesEntry id={self.id} user={self.user_id} coins={self.coins_entered}>"


class SweepstakesDraw(Base):
    """
    Immutable audit record of how a draw was conducted.
    One row per sweepstakes (UNIQUE on sweepstakes_id).

    winning_entry_number in SweepstakesWinner is auditable:
    re-expand all SweepstakesEntry rows (each coins_entered = N entry slots),
    find slot #winning_entry_number, verify it maps to the winner's user_id.
    """
    __tablename__ = "sweepstakes_draws"

    id: Mapped[uuid.UUID]                   = uuid_pk()
    sweepstakes_id: Mapped[uuid.UUID]       = mapped_column(ForeignKey("sweepstakes.id"), nullable=False, unique=True)

    drawn_at: Mapped[datetime]              = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    drawn_by: Mapped[uuid.UUID]             = mapped_column(ForeignKey("users.id"), nullable=False)

    # Snapshot at draw time for reproducible audit
    total_entries_at_draw: Mapped[int]      = mapped_column(BigInteger, nullable=False)
    total_participants: Mapped[int]         = mapped_column(Integer, nullable=False)

    # Cryptographic audit trail
    algorithm_version: Mapped[str]          = mapped_column(String, nullable=False, default="crypto_random_v1")
    random_seed: Mapped[str | None]         = mapped_column(String)

    created_at: Mapped[datetime]            = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    sweepstakes: Mapped["Sweepstakes"]      = relationship(back_populates="draw")
    winners: Mapped[list["SweepstakesWinner"]] = relationship(back_populates="draw", lazy="select")

    def __repr__(self) -> str:
        return f"<SweepstakesDraw id={self.id} drawn_at={self.drawn_at}>"


class SweepstakesWinner(Base):
    __tablename__ = "sweepstakes_winners"

    id: Mapped[uuid.UUID]               = uuid_pk()
    draw_id: Mapped[uuid.UUID]          = mapped_column(ForeignKey("sweepstakes_draws.id"), nullable=False)
    sweepstakes_id: Mapped[uuid.UUID]   = mapped_column(ForeignKey("sweepstakes.id"), nullable=False)
    user_id: Mapped[uuid.UUID]          = mapped_column(ForeignKey("users.id"), nullable=False)

    # 1-indexed entry slot number that was randomly selected.
    # Allows full audit: expand entry list → find slot N → verify user_id matches.
    winning_entry_number: Mapped[int]   = mapped_column(BigInteger, nullable=False)

    prize_description: Mapped[str]      = mapped_column(String, nullable=False)
    claim_status: Mapped[str]           = mapped_column(
        SAEnum("pending", "notified", "claimed", "expired", "forfeited", name="claim_status"),
        nullable=False,
        default="pending",
    )

    notified_at: Mapped[datetime | None]    = mapped_column(TIMESTAMP(timezone=True))
    claimed_at: Mapped[datetime | None]     = mapped_column(TIMESTAMP(timezone=True))
    claim_deadline: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    draw:        Mapped["SweepstakesDraw"] = relationship(back_populates="winners")
    sweepstakes: Mapped["Sweepstakes"]     = relationship(back_populates="winners")
    user:        Mapped["User"]            = relationship()

    def __repr__(self) -> str:
        return f"<SweepstakesWinner id={self.id} user={self.user_id} status={self.claim_status}>"
