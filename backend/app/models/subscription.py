import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk


class SubscriptionEvent(Base):
    """
    Immutable archive of every RevenueCat webhook event received.

    Serves two purposes:
    1. Idempotency: revenuecat_event_id (UNIQUE) prevents double-processing
       if RevenueCat retries a webhook delivery.
    2. Audit / dispute resolution: raw_payload preserves the full event for
       later inspection.

    user_id is nullable because RevenueCat webhooks may arrive before the
    user row has been created (race condition on first purchase). In that case,
    firebase_uid is used as a fallback lookup key when the user row is created.
    """
    __tablename__ = "subscription_events"

    id: Mapped[uuid.UUID]               = uuid_pk()

    # May be NULL if webhook arrives before user creation
    user_id: Mapped[uuid.UUID | None]   = mapped_column(ForeignKey("users.id"))
    firebase_uid: Mapped[str | None]    = mapped_column(String)  # fallback lookup

    revenuecat_event_type: Mapped[str]  = mapped_column(String, nullable=False)  # 'INITIAL_PURCHASE', 'RENEWAL', etc.
    revenuecat_event_id: Mapped[str]    = mapped_column(String, nullable=False, unique=True)  # idempotency key
    product_id: Mapped[str | None]      = mapped_column(String)
    period_type: Mapped[str | None]     = mapped_column(String)  # 'NORMAL', 'TRIAL', 'INTRO'
    purchased_at: Mapped[datetime | None]   = mapped_column(TIMESTAMP(timezone=True))
    expires_at: Mapped[datetime | None]     = mapped_column(TIMESTAMP(timezone=True))

    # Full webhook payload — never modify this column after insert
    raw_payload: Mapped[dict]           = mapped_column(JSONB, nullable=False)

    processed_at: Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    processing_error: Mapped[str | None] = mapped_column(Text)  # non-null if handler raised an exception

    created_at: Mapped[datetime]        = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<SubscriptionEvent type={self.revenuecat_event_type} rc_id={self.revenuecat_event_id}>"
