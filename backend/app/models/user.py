import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, Enum as SAEnum, TIMESTAMP, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID]               = uuid_pk()
    firebase_uid: Mapped[str]           = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str | None]           = mapped_column(String)
    display_name: Mapped[str | None]    = mapped_column(String)

    # Authoritative IANA timezone (e.g. 'America/Los_Angeles').
    # All day-boundary logic reads this column — never derives TZ from client.
    timezone: Mapped[str]               = mapped_column(String, nullable=False, default="UTC")
    timezone_updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # Subscription — kept in sync by RevenueCat webhook handler.
    subscription_tier: Mapped[str]      = mapped_column(
        SAEnum("free", "premium", name="subscription_tier"),
        nullable=False,
        default="free",
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    revenuecat_customer_id: Mapped[str | None]       = mapped_column(String, unique=True)

    # Denormalized coin balance. Source of truth is coin_ledger.
    # Kept in sync via application-layer transactions.
    coin_balance: Mapped[int]           = mapped_column(Integer, nullable=False, default=0)

    # Account health
    is_active: Mapped[bool]             = mapped_column(Boolean, nullable=False, default=True)
    is_banned: Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    ban_reason: Mapped[str | None]      = mapped_column(String)
    banned_at: Mapped[datetime | None]  = mapped_column(TIMESTAMP(timezone=True))
    banned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    created_at: Mapped[datetime]        = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime]        = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # ── Relationships ──────────────────────────────────────────────────────────
    goals:               Mapped[list["Goal"]]                        = relationship(back_populates="user", lazy="select")
    coin_ledger_entries: Mapped[list["CoinLedger"]]                  = relationship(back_populates="user", lazy="select")
    notification_prefs:  Mapped["NotificationPreferences | None"]    = relationship(back_populates="user", uselist=False, lazy="select")
    push_tokens:         Mapped[list["PushToken"]]                   = relationship(back_populates="user", lazy="select")
    sweepstakes_entries: Mapped[list["SweepstakesEntry"]]            = relationship(back_populates="user", lazy="select")

    # ── Computed properties ────────────────────────────────────────────────────

    @property
    def is_premium(self) -> bool:
        """
        True only when the user has an active, non-expired premium subscription.
        This is the single authoritative check — always use this, never read
        subscription_tier directly in business logic.
        """
        if self.subscription_tier != "premium":
            return False
        if self.subscription_expires_at is None:
            return False
        return self.subscription_expires_at > datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<User id={self.id} firebase_uid={self.firebase_uid} tier={self.subscription_tier}>"
