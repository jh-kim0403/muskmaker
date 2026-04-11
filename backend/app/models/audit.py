import uuid
from datetime import datetime
from sqlalchemy import (
    String, SmallInteger, Boolean, Integer, ForeignKey, TIMESTAMP,
    Enum as SAEnum, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk


class TimezoneAuditLog(Base):
    """
    Append-only record of every timezone change attempt (successful or blocked).

    Used for:
    - Abuse detection (rate limit enforcement)
    - Dispute resolution ("user claims goal was in wrong timezone")
    - Admin audit panel

    was_blocked=True rows represent changes that were REJECTED by the rate limiter
    and had no effect on users.timezone.
    """
    __tablename__ = "timezone_audit_log"

    id: Mapped[uuid.UUID]       = uuid_pk()
    user_id: Mapped[uuid.UUID]  = mapped_column(ForeignKey("users.id"), nullable=False)

    old_timezone: Mapped[str | None]    = mapped_column(String)  # NULL on first set (onboarding)
    new_timezone: Mapped[str]           = mapped_column(String, nullable=False)

    changed_at: Mapped[datetime]        = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    ip_address: Mapped[str | None]      = mapped_column(INET)
    user_agent: Mapped[str | None]      = mapped_column(String)
    change_source: Mapped[str]          = mapped_column(
        SAEnum("onboarding", "settings", "auto_detected", "admin", name="tz_change_source"),
        nullable=False,
    )

    # Abuse signals
    flagged_suspicious: Mapped[bool]    = mapped_column(Boolean, nullable=False, default=False)
    flag_reason: Mapped[str | None]     = mapped_column(String)  # e.g. 'change_within_30min_of_goal_creation'

    # Rate limit context at time of this change
    changes_in_window: Mapped[int | None]   = mapped_column(Integer)  # count in last 24h
    was_blocked: Mapped[bool]               = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<TimezoneAuditLog user={self.user_id} {self.old_timezone}→{self.new_timezone} blocked={self.was_blocked}>"


class AntiCheatLog(Base):
    """
    Structured, append-only log of all suspicious activity signals.

    Populated by multiple services:
      VerificationService  → exif_mismatch, rapid_resubmission, location_mismatch,
                             impossible_location, metadata_stripped, abnormal_delta
      TimezoneService      → tz_change_near_goal, tz_window_extension
      AuditService         → repeated_failure, pattern_anomaly

    Event type constants are defined in app/constants.py (CHEAT_EVENT_*).

    auto_action represents what the system did immediately:
      'none'                  → logged only
      'flagged_for_review'    → verification sent to manual review regardless of path
      'blocked'               → request was rejected
      'manual_review_required' → added to admin queue with elevated priority
    """
    __tablename__ = "anti_cheat_log"

    id: Mapped[uuid.UUID]           = uuid_pk()
    user_id: Mapped[uuid.UUID]      = mapped_column(ForeignKey("users.id"), nullable=False)

    event_type: Mapped[str]         = mapped_column(String, nullable=False)
    severity: Mapped[str]           = mapped_column(
        SAEnum("low", "medium", "high", "critical", name="cheat_severity"),
        nullable=False,
        default="low",
    )

    # Polymorphic reference to the triggering entity
    reference_id: Mapped[uuid.UUID | None]  = mapped_column()
    reference_type: Mapped[str | None]      = mapped_column(String)  # 'goal'|'verification'|'entry'|'timezone_change'

    # Structured details for machine processing and human review
    details: Mapped[dict | None]    = mapped_column(JSONB)

    # What the system did automatically in response
    auto_action: Mapped[str]        = mapped_column(String, nullable=False, default="none")

    # Admin disposition
    reviewed_by: Mapped[uuid.UUID | None]   = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]    = mapped_column(TIMESTAMP(timezone=True))
    resolution: Mapped[str | None]          = mapped_column(String)  # 'false_positive'|'confirmed_abuse'|'warning_issued'|'banned'

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    user:     Mapped["User"]            = relationship(foreign_keys=[user_id])
    reviewer: Mapped["User | None"]     = relationship(foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return f"<AntiCheatLog user={self.user_id} event={self.event_type} severity={self.severity}>"


class AdminReview(Base):
    """
    Manual review queue entry for free-tier verifications.

    Created automatically by VerificationService when a free user submits.
    Premium verifications NEVER create a row here.

    sla_deadline is a generated column (queued_at + 24h) for SLA monitoring.
    Admins target completion before this deadline.
    """
    __tablename__ = "admin_reviews"

    id: Mapped[uuid.UUID]               = uuid_pk()
    verification_id: Mapped[uuid.UUID]  = mapped_column(ForeignKey("verifications.id"), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID]          = mapped_column(ForeignKey("users.id"), nullable=False)

    # Priority 1 (urgent) to 10 (low). Default 5.
    # Set higher when anti_cheat_log flags the verification.
    priority: Mapped[int]               = mapped_column(SmallInteger, nullable=False, default=5)

    status: Mapped[str]                 = mapped_column(
        SAEnum("queued", "in_review", "approved", "rejected", name="review_status"),
        nullable=False,
        default="queued",
    )

    queued_at: Mapped[datetime]             = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    assigned_to: Mapped[uuid.UUID | None]   = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime | None]    = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None]   = mapped_column(TIMESTAMP(timezone=True))

    rejection_reason: Mapped[str | None]    = mapped_column(Text)
    reviewer_notes: Mapped[str | None]      = mapped_column(Text)  # internal only

    sla_deadline: Mapped[datetime]          = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    verification: Mapped["Verification"]    = relationship(back_populates="admin_review")
    user: Mapped["User"]                    = relationship(foreign_keys=[user_id])
    assignee: Mapped["User | None"]         = relationship(foreign_keys=[assigned_to])

    def __repr__(self) -> str:
        return f"<AdminReview id={self.id} verification={self.verification_id} status={self.status}>"
