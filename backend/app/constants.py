# =============================================================================
# MuskMaker — Application-wide constants
# =============================================================================
# These values are referenced across multiple services.
# Thresholds that may need tuning live in config.py (environment-configurable).
# String constants that must be consistent across services live here.
# =============================================================================

# ── Anti-cheat event type codes ───────────────────────────────────────────────
# Used as anti_cheat_log.event_type values. Never use raw strings in services.

class CheatEvent:
    EXIF_MISMATCH               = "exif_mismatch"             # EXIF time vs server time delta too large
    RAPID_RESUBMISSION          = "rapid_resubmission"        # multiple submissions in short window
    LOCATION_MISMATCH           = "location_mismatch"         # GPS coords implausible for goal type
    IMPOSSIBLE_LOCATION         = "impossible_location"       # GPS coords physically impossible (speed, etc.)
    METADATA_STRIPPED           = "metadata_stripped"         # photo has no EXIF (likely library upload attempt)
    ABNORMAL_DELTA              = "abnormal_delta"            # timestamp delta exceeds hard fail threshold
    TZ_CHANGE_NEAR_GOAL         = "tz_change_near_goal"       # TZ change within 30 min of goal creation
    TZ_WINDOW_EXTENSION         = "tz_window_extension"       # TZ change would extend an active goal's day
    REPEATED_FAILURE            = "repeated_failure"          # multiple rejected verifications in short window
    PATTERN_ANOMALY             = "pattern_anomaly"           # generic unusual pattern flagged by audit service


# ── Verification paths ────────────────────────────────────────────────────────
class VerificationPath:
    FREE_MANUAL             = "free_manual"
    PREMIUM_AI_STANDARD     = "premium_ai_standard"
    PREMIUM_AI_LOCATION     = "premium_ai_location"


# ── Goal statuses ─────────────────────────────────────────────────────────────
class GoalStatus:
    ACTIVE      = "active"
    SUBMITTED   = "submitted"
    APPROVED    = "approved"
    REJECTED    = "rejected"
    EXPIRED     = "expired"


# ── Verification statuses ─────────────────────────────────────────────────────
class VerificationStatus:
    PENDING_REVIEW  = "pending_review"
    IN_REVIEW       = "in_review"
    APPROVED        = "approved"
    REJECTED        = "rejected"


# ── Review statuses ───────────────────────────────────────────────────────────
class ReviewStatus:
    QUEUED      = "queued"
    IN_REVIEW   = "in_review"
    APPROVED    = "approved"
    REJECTED    = "rejected"


# ── Coin transaction types ────────────────────────────────────────────────────
class CoinTxType:
    GOAL_VERIFIED       = "goal_verified"
    SWEEPSTAKES_ENTRY   = "sweepstakes_entry"
    ADMIN_ADJUSTMENT    = "admin_adjustment"
    REFUND              = "refund"


class CoinRefType:
    GOAL                = "goal"
    SWEEPSTAKES_ENTRY   = "sweepstakes_entry"
    ADMIN               = "admin"


# ── Sweepstakes statuses ──────────────────────────────────────────────────────
class SweepstakesStatus:
    UPCOMING    = "upcoming"
    ACTIVE      = "active"
    DRAWING     = "drawing"
    COMPLETED   = "completed"
    CANCELLED   = "cancelled"


# ── Claim statuses ────────────────────────────────────────────────────────────
class ClaimStatus:
    PENDING     = "pending"
    NOTIFIED    = "notified"
    CLAIMED     = "claimed"
    EXPIRED     = "expired"
    FORFEITED   = "forfeited"


# ── Notification tones ────────────────────────────────────────────────────────
class NotificationTone:
    NORMAL              = "normal"
    FRIENDLY_BANTER     = "friendly_banter"
    HARSH               = "harsh"


# ── Subscription tiers ────────────────────────────────────────────────────────
class SubscriptionTier:
    FREE    = "free"
    PREMIUM = "premium"


# ── RevenueCat event types ────────────────────────────────────────────────────
class RevenueCatEvent:
    INITIAL_PURCHASE    = "INITIAL_PURCHASE"
    RENEWAL             = "RENEWAL"
    CANCELLATION        = "CANCELLATION"
    EXPIRATION          = "EXPIRATION"
    BILLING_ISSUE       = "BILLING_ISSUE"
    PRODUCT_CHANGE      = "PRODUCT_CHANGE"
    REFUND              = "REFUND"


# ── Timezone change sources ───────────────────────────────────────────────────
class TzChangeSource:
    ONBOARDING      = "onboarding"
    SETTINGS        = "settings"
    AUTO_DETECTED   = "auto_detected"
    ADMIN           = "admin"


# ── Photo limits per verification path ───────────────────────────────────────
PHOTO_COUNT_BY_PATH: dict[str, int] = {
    VerificationPath.FREE_MANUAL:           2,
    VerificationPath.PREMIUM_AI_STANDARD:   2,
    VerificationPath.PREMIUM_AI_LOCATION:   1,
}


# ── AI verdict values ─────────────────────────────────────────────────────────
class AIVerdict:
    PASS        = "pass"
    FAIL        = "fail"
    UNCERTAIN   = "uncertain"
