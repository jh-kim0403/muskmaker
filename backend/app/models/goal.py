import uuid
from datetime import date, datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk


class GoalType(Base):
    """
    Admin-managed catalog of available goal types.
    coin_reward is identical for free and premium users — it is NEVER tier-adjusted.
    """
    __tablename__ = "goal_types"
    __table_args__ = (
        CheckConstraint("coin_reward > 0", name="chk_goal_types_coin_reward_positive"),
    )

    id: Mapped[uuid.UUID]           = uuid_pk()
    name: Mapped[str]               = mapped_column(Text, nullable=False)  # "Go to the gym"
    slug: Mapped[str]               = mapped_column(Text, nullable=False, unique=True)  # "gym"
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str]               = mapped_column(
        SAEnum("photo", "quiz", name="goal_type"),
        nullable=False,
    )
    icon_url: Mapped[str | None]    = mapped_column(Text)
    ai_prompt: Mapped[str | None]   = mapped_column(Text)
    # Coins awarded on successful verification.
    # This value is NEVER modified by the user's subscription tier.
    coin_reward: Mapped[int]        = mapped_column(Integer, nullable=False)
    difficulty: Mapped[str]         = mapped_column(
        SAEnum("easy", "medium", "hard", name="difficulty"),
        nullable=False,
        default="medium",
        server_default="medium",
    )

    # When True, the premium 1-photo AI path for this type requires location.
    # Has absolutely no effect on free users.
    supports_location_path: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    is_active: Mapped[bool]         = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    display_order: Mapped[int]      = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    goals: Mapped[list["Goal"]] = relationship(back_populates="goal_type", lazy="select")

    def __repr__(self) -> str:
        return f"<GoalType slug={self.slug} coins={self.coin_reward}>"


class Goal(Base):
    """
    One instance of a goal created by a user on a given local calendar day.

    The UNIQUE constraint on (user_id, goal_type_id, local_goal_date) is the
    database-level enforcement of the "one goal per type per local day" fairness rule.

    local_goal_date and timezone_at_creation are always set server-side and are
    frozen at creation — they are never modified after insert.
    """
    __tablename__ = "goals"
    __table_args__ = (
        # Core fairness constraint: one goal per type per local calendar day per user.
        # The DB enforces this — the application layer cannot accidentally bypass it.
        UniqueConstraint(
            "user_id", "goal_type_id", "local_goal_date",
            name="uq_goal_per_type_per_day",
        ),
    )

    id: Mapped[uuid.UUID]           = uuid_pk()
    user_id: Mapped[uuid.UUID]      = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goal_types.id"), nullable=False)
    title: Mapped[str]              = mapped_column(Text, nullable=False)
    
    status: Mapped[str]             = mapped_column(
        SAEnum("active", "submitted", "approved", "rejected", "expired", name="goal_status"),
        nullable=False,
        default="active",
        server_default="active",
    )
    notes: Mapped[str | None]       = mapped_column(Text)

    # ── Timezone-safe day fields (computed server-side, never from client) ──────

    # The local calendar date this goal belongs to in the user's stored timezone.
    # Computed as: (NOW() AT TIME ZONE users.timezone)::DATE
    local_goal_date: Mapped[date]   = mapped_column(Date, nullable=False)

    # The timezone in effect when this goal was created. Frozen at insert.
    # A subsequent timezone change on the user does NOT update this column.
    timezone_at_creation: Mapped[str] = mapped_column(Text, nullable=False)

    # Precomputed end-of-local-day in UTC. Set once at creation.
    # Formula: local_day_end_utc(local_goal_date, timezone_at_creation)
    expires_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # ── Relationships ──────────────────────────────────────────────────────────
    user:         Mapped["User"]                    = relationship(back_populates="goals")
    goal_type:    Mapped["GoalType"]                = relationship(back_populates="goals")
    verification: Mapped["Verification | None"]     = relationship(back_populates="goal", uselist=False, lazy="select")

    def __repr__(self) -> str:
        return f"<Goal id={self.id} type={self.goal_type_id} date={self.local_goal_date} status={self.status}>"


Index("idx_goal_types_active", GoalType.is_active, GoalType.display_order)
Index("idx_goal_types_slug", GoalType.slug)
Index("idx_goals_user_date", Goal.user_id, Goal.local_goal_date.desc())
Index("idx_goals_status", Goal.status, postgresql_where=Goal.status.in_(["active", "submitted"]))
Index("idx_goals_expires_at", Goal.expires_at, postgresql_where=Goal.status == "active")
Index("idx_goals_user_type", Goal.user_id, Goal.goal_type_id)
