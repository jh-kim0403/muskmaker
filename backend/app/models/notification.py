import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    TIMESTAMP,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk


class NotificationPreferences(Base):
    """
    One row per user. Stores all notification settings.

    notification_tone: 'friendly_banter' and 'harsh' are premium-only options.
    If a free user somehow has a non-'normal' tone stored, NotificationService
    enforces 'normal' at send time — never at the DB layer.
    """
    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint(
            "reminder_minutes_before_expiry > 0",
            name="chk_notification_preferences_reminder_positive",
        ),
    )

    id: Mapped[uuid.UUID]       = uuid_pk()
    user_id: Mapped[uuid.UUID]  = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    push_enabled: Mapped[bool]  = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # Goal expiry reminder
    goal_reminder_enabled: Mapped[bool]             = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    reminder_minutes_before_expiry: Mapped[int]     = mapped_column(
        Integer, nullable=False, default=60, server_default=text("60")
    )

    # Premium-only: notification tone preference.
    # Enforced at send time: free users always receive 'normal' tone regardless of this value.
    notification_tone: Mapped[str]                  = mapped_column(
        SAEnum("normal", "friendly_banter", "harsh", name="notification_tone"),
        nullable=False,
        default="normal",
        server_default="normal",
    )

    # Sweepstakes notifications
    sweep_result_enabled: Mapped[bool]  = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    new_sweep_enabled: Mapped[bool]     = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="notification_prefs")

    def __repr__(self) -> str:
        return f"<NotificationPreferences user={self.user_id} tone={self.notification_tone}>"


class PushToken(Base):
    __tablename__ = "push_tokens"
    __table_args__ = (
        CheckConstraint("platform IN ('ios', 'android')", name="chk_push_tokens_platform"),
    )

    id: Mapped[uuid.UUID]           = uuid_pk()
    user_id: Mapped[uuid.UUID]      = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expo_push_token: Mapped[str]    = mapped_column(Text, nullable=False, unique=True)
    platform: Mapped[str]           = mapped_column(Text, nullable=False)  # 'ios' | 'android'
    is_active: Mapped[bool]         = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="push_tokens")

    def __repr__(self) -> str:
        return f"<PushToken user={self.user_id} platform={self.platform}>"


Index("idx_push_tokens_user", PushToken.user_id, postgresql_where=PushToken.is_active.is_(True))
