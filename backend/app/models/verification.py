import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Integer, SmallInteger, Date, ForeignKey, TIMESTAMP,
    UniqueConstraint, CheckConstraint, Enum as SAEnum, Numeric,
    Boolean, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, uuid_pk


class Verification(Base):
    """
    One verification attempt per goal (1-to-1 with goals after submission).

    Captures all evidence required for both review paths:
      - free_manual:           2 photos → admin review queue → manual approval
      - premium_ai_standard:   2 photos → instant AI review
      - premium_ai_location:   1 photo + GPS → instant AI review with location check

    Location fields are NULL for all paths except premium_ai_location,
    enforced by chk_location_path_only.
    """
    __tablename__ = "verifications"
    __table_args__ = (
        # Location fields: all present or all absent
        CheckConstraint(
            "(location_lat IS NULL AND location_lng IS NULL AND location_accuracy_meters IS NULL) OR "
            "(location_lat IS NOT NULL AND location_lng IS NOT NULL AND location_accuracy_meters IS NOT NULL)",
            name="chk_location_complete",
        ),
        # Location data only allowed on the location-enabled premium path
        CheckConstraint(
            "location_lat IS NULL OR verification_path = 'premium_ai_location'",
            name="chk_location_path_only",
        ),
    )

    id: Mapped[uuid.UUID]       = uuid_pk()
    goal_id: Mapped[uuid.UUID]  = mapped_column(ForeignKey("goals.id"), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID]  = mapped_column(ForeignKey("users.id"), nullable=False)

    status: Mapped[str]         = mapped_column(
        SAEnum("pending_review", "in_review", "approved", "rejected", name="verification_status"),
        nullable=False,
        default="pending_review",
    )
    verification_path: Mapped[str] = mapped_column(
        SAEnum("free_manual", "premium_ai_standard", "premium_ai_location", name="verification_path"),
        nullable=False,
    )

    # ── Submission timestamps ──────────────────────────────────────────────────
    # submitted_at: UTC server clock at time of request receipt. Never from client.
    submitted_at: Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Calendar date of submission in the user's timezone, computed server-side.
    # Application layer enforces: local_submission_date == goal.local_goal_date.
    local_submission_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone_at_submission: Mapped[str] = mapped_column(String, nullable=False)

    # ── Anti-cheat: EXIF timestamp cross-check ────────────────────────────────
    exif_captured_at: Mapped[datetime | None]       = mapped_column(TIMESTAMP(timezone=True))
    server_receipt_at: Mapped[datetime]             = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    # Absolute delta seconds between EXIF and server receipt. Thresholds in config.py.
    timestamp_delta_seconds: Mapped[int | None]     = mapped_column(Integer)

    # ── Location (premium_ai_location path only — NULL for all other paths) ───
    location_lat: Mapped[Decimal | None]            = mapped_column(Numeric(10, 8))
    location_lng: Mapped[Decimal | None]            = mapped_column(Numeric(11, 8))
    location_accuracy_meters: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    location_captured_at: Mapped[datetime | None]   = mapped_column(TIMESTAMP(timezone=True))

    # ── AI result (premium paths only) ────────────────────────────────────────
    ai_confidence_score: Mapped[Decimal | None]     = mapped_column(Numeric(5, 4))  # 0.0000–1.0000
    ai_verdict: Mapped[str | None]                  = mapped_column(String)         # 'pass'|'fail'|'uncertain'
    ai_result_payload: Mapped[dict | None]          = mapped_column(JSONB)          # full AI API response
    ai_processed_at: Mapped[datetime | None]        = mapped_column(TIMESTAMP(timezone=True))

    # ── Review outcome ─────────────────────────────────────────────────────────
    reviewed_at: Mapped[datetime | None]            = mapped_column(TIMESTAMP(timezone=True))
    reviewer_id: Mapped[uuid.UUID | None]           = mapped_column(ForeignKey("users.id"))
    rejection_reason: Mapped[str | None]            = mapped_column(Text)
    internal_notes: Mapped[str | None]              = mapped_column(Text)

    # ── Coin award (set atomically with coin_ledger insert) ───────────────────
    coins_awarded: Mapped[int]                      = mapped_column(Integer, nullable=False, default=0)
    coins_awarded_at: Mapped[datetime | None]       = mapped_column(TIMESTAMP(timezone=True))

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # ── Relationships ──────────────────────────────────────────────────────────
    goal:         Mapped["Goal"]                    = relationship(back_populates="verification")
    user:         Mapped["User"]                    = relationship(foreign_keys=[user_id])
    photos:       Mapped[list["VerificationPhoto"]] = relationship(back_populates="verification", lazy="select", order_by="VerificationPhoto.photo_index")
    admin_review: Mapped["AdminReview | None"]      = relationship(back_populates="verification", uselist=False, lazy="select")

    def __repr__(self) -> str:
        return f"<Verification id={self.id} path={self.verification_path} status={self.status}>"


class VerificationPhoto(Base):
    """
    Individual photo belonging to a verification.

    photo_index 0 = first photo, 1 = second photo.
    - Free path:              always index 0 and 1
    - Premium standard:       always index 0 and 1
    - Premium location path:  only index 0

    s3_key is NEVER returned directly to clients.
    Always generate a time-limited pre-signed URL before serving.
    EXIF fields are extracted server-side after upload; values from the client
    are NEVER trusted for these fields.
    """
    __tablename__ = "verification_photos"
    __table_args__ = (
        UniqueConstraint("verification_id", "photo_index", name="uq_photo_index_per_verification"),
    )

    id: Mapped[uuid.UUID]               = uuid_pk()
    verification_id: Mapped[uuid.UUID]  = mapped_column(ForeignKey("verifications.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID]          = mapped_column(ForeignKey("users.id"), nullable=False)

    # S3 object key (never exposed directly — always use pre-signed URL)
    s3_key: Mapped[str]                 = mapped_column(String, nullable=False, unique=True)
    s3_bucket: Mapped[str]              = mapped_column(String, nullable=False)

    photo_index: Mapped[int]            = mapped_column(SmallInteger, nullable=False)  # 0 or 1

    # EXIF metadata — extracted server-side only, never from client payload
    exif_captured_at: Mapped[datetime | None]   = mapped_column(TIMESTAMP(timezone=True))
    exif_gps_lat: Mapped[Decimal | None]        = mapped_column(Numeric(10, 8))
    exif_gps_lng: Mapped[Decimal | None]        = mapped_column(Numeric(11, 8))
    exif_gps_alt_m: Mapped[Decimal | None]      = mapped_column(Numeric(8, 2))
    exif_device_make: Mapped[str | None]        = mapped_column(String)
    exif_device_model: Mapped[str | None]       = mapped_column(String)

    file_size_bytes: Mapped[int | None]         = mapped_column(Integer)
    width_px: Mapped[int | None]                = mapped_column(Integer)
    height_px: Mapped[int | None]               = mapped_column(Integer)
    mime_type: Mapped[str]                      = mapped_column(String, nullable=False, default="image/jpeg")

    # Soft delete — row kept for audit trail
    is_deleted: Mapped[bool]                    = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None]         = mapped_column(TIMESTAMP(timezone=True))

    created_at: Mapped[datetime]    = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    verification: Mapped["Verification"] = relationship(back_populates="photos")

    def __repr__(self) -> str:
        return f"<VerificationPhoto id={self.id} index={self.photo_index} s3_key={self.s3_key}>"
