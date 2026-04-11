-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "btree_gist"; -- exclusion constraints

-- ============================================================
-- SHARED HELPERS
-- ============================================================

-- Convert a UTC timestamptz to a user's local DATE using their IANA timezone.
-- Used everywhere a "calendar day" boundary must be computed server-side.
CREATE OR REPLACE FUNCTION user_local_date(
    utc_ts  TIMESTAMPTZ,
    iana_tz TEXT
) RETURNS DATE AS $$
    SELECT (utc_ts AT TIME ZONE iana_tz)::DATE;
$$ LANGUAGE SQL IMMUTABLE STRICT;

-- Compute the exact UTC moment a local calendar day ends (23:59:59.999999)
-- for a given IANA timezone and local date. Used to set goal expires_at.
CREATE OR REPLACE FUNCTION local_day_end_utc(
    local_date DATE,
    iana_tz    TEXT
) RETURNS TIMESTAMPTZ AS $$
    SELECT (local_date::TIMESTAMP + INTERVAL '1 day - 1 microsecond')
           AT TIME ZONE iana_tz;
$$ LANGUAGE SQL IMMUTABLE STRICT;

-- ============================================================
-- ENUMS
-- ============================================================
CREATE TYPE subscription_tier    AS ENUM ('free', 'premium');
CREATE TYPE goal_status          AS ENUM ('active', 'submitted', 'approved', 'rejected', 'expired');
CREATE TYPE verification_path    AS ENUM ('free_manual', 'premium_ai_standard', 'premium_ai_location');
CREATE TYPE verification_status  AS ENUM ('pending_review', 'in_review', 'approved', 'rejected');
CREATE TYPE review_status        AS ENUM ('queued', 'in_review', 'approved', 'rejected');
CREATE TYPE coin_tx_type         AS ENUM ('goal_verified', 'sweepstakes_entry', 'admin_adjustment', 'refund');
CREATE TYPE coin_ref_type        AS ENUM ('goal', 'sweepstakes_entry', 'admin');
CREATE TYPE sweepstakes_status   AS ENUM ('upcoming', 'active', 'drawing', 'completed', 'cancelled');
CREATE TYPE claim_status         AS ENUM ('pending', 'notified', 'claimed', 'expired', 'forfeited');
CREATE TYPE notification_tone    AS ENUM ('normal', 'friendly_banter', 'harsh');
CREATE TYPE cheat_severity       AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE difficulty           AS ENUM ('easy', 'medium', 'hard');
CREATE TYPE tz_change_source     AS ENUM ('onboarding', 'settings', 'auto_detected', 'admin');

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid            TEXT        NOT NULL UNIQUE,
    email                   TEXT,
    display_name            TEXT,

    -- Timezone (IANA format, e.g. 'America/Los_Angeles')
    -- This is the authoritative timezone for all day-boundary logic.
    -- Never derived client-side at query time — stored and versioned here.
    timezone                TEXT        NOT NULL DEFAULT 'UTC',
    timezone_updated_at     TIMESTAMPTZ,

    -- Subscription
    subscription_tier       subscription_tier NOT NULL DEFAULT 'free',
    subscription_expires_at TIMESTAMPTZ,
    revenuecat_customer_id  TEXT        UNIQUE,

    -- Denormalized coin balance — kept in sync with coin_ledger via
    -- application-layer transactions. Source of truth is coin_ledger.
    coin_balance            INTEGER     NOT NULL DEFAULT 0 CHECK (coin_balance >= 0),

    -- Account health
    is_active               BOOLEAN     NOT NULL DEFAULT TRUE,
    is_banned               BOOLEAN     NOT NULL DEFAULT FALSE,
    ban_reason              TEXT,
    banned_at               TIMESTAMPTZ,
    banned_by               UUID        REFERENCES users(id),

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at            TIMESTAMPTZ
);

CREATE INDEX idx_users_firebase_uid    ON users(firebase_uid);
CREATE INDEX idx_users_revenuecat_id   ON users(revenuecat_customer_id) WHERE revenuecat_customer_id IS NOT NULL;
CREATE INDEX idx_users_subscription    ON users(subscription_tier, subscription_expires_at);
CREATE INDEX idx_users_coin_balance    ON users(coin_balance) WHERE coin_balance > 0;

-- ============================================================
-- GOAL TYPES  (admin-managed catalog)
-- ============================================================
-- Each type defines: what goal it represents, how many coins it awards,
-- its difficulty, and whether the premium 1-photo location path is supported.
CREATE TABLE goal_types (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT        NOT NULL,          -- "Go to the gym"
    slug                    TEXT        NOT NULL UNIQUE,   -- "gym"
    description             TEXT,
    icon_url                TEXT,

    -- Coins awarded upon successful verification of this goal type.
    -- This value NEVER changes based on user subscription tier.
    coin_reward             INTEGER     NOT NULL CHECK (coin_reward > 0),
    difficulty              difficulty  NOT NULL DEFAULT 'medium',

    -- If TRUE, the premium 1-photo AI path requires location services.
    -- Free users are never affected by this flag.
    supports_location_path  BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Admins can deactivate a type without deleting it.
    is_active               BOOLEAN     NOT NULL DEFAULT TRUE,

    display_order           INTEGER     NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_goal_types_active ON goal_types(is_active, display_order);
CREATE INDEX idx_goal_types_slug   ON goal_types(slug);

-- ============================================================
-- GOALS
-- ============================================================
-- One row per goal instance a user creates on a given local calendar day.
-- The UNIQUE constraint on (user_id, goal_type_id, local_goal_date)
-- is the primary database-level enforcement of the "one per type per day" rule.
CREATE TABLE goals (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_type_id            UUID        NOT NULL REFERENCES goal_types(id),

    status                  goal_status NOT NULL DEFAULT 'active',
    notes                   TEXT,

    -- The local calendar date this goal belongs to, in the user's timezone.
    -- Computed server-side: (NOW() AT TIME ZONE user.timezone)::DATE
    -- NEVER trust the client for this value.
    local_goal_date         DATE        NOT NULL,

    -- The timezone in effect when this goal was created.
    -- Frozen at creation — subsequent timezone changes do NOT alter this.
    timezone_at_creation    TEXT        NOT NULL,

    -- Precomputed expiry: end of local_goal_date in the creation timezone (UTC).
    -- Used by the expiry worker and for display ("expires at 11:59 PM tonight").
    expires_at              TIMESTAMPTZ NOT NULL,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ── Core fairness constraint ──────────────────────────────────────────
    -- A user may only have one goal of each type per local calendar day.
    CONSTRAINT uq_goal_per_type_per_day UNIQUE (user_id, goal_type_id, local_goal_date)
);

CREATE INDEX idx_goals_user_date    ON goals(user_id, local_goal_date DESC);
CREATE INDEX idx_goals_status       ON goals(status) WHERE status IN ('active', 'submitted');
CREATE INDEX idx_goals_expires_at   ON goals(expires_at) WHERE status = 'active';
-- Used by expiry worker: find all active goals whose local day has ended
CREATE INDEX idx_goals_user_type    ON goals(user_id, goal_type_id);

-- ============================================================
-- VERIFICATIONS
-- ============================================================
-- One verification attempt per goal (one-to-one with goals after submission).
-- Captures all evidence: photos, EXIF data, AI result, location (premium only).
CREATE TABLE verifications (
    id                          UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id                     UUID                NOT NULL UNIQUE REFERENCES goals(id),
    user_id                     UUID                NOT NULL REFERENCES users(id),

    status                      verification_status NOT NULL DEFAULT 'pending_review',
    verification_path           verification_path   NOT NULL,

    -- ── Submission timestamps ─────────────────────────────────────────────
    -- submitted_at: UTC server clock when the request was received.
    submitted_at                TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    -- local_submission_date: the calendar date of submission in the user's timezone.
    -- Computed server-side from submitted_at + user.timezone at time of submission.
    -- Must equal goal.local_goal_date — enforced in application layer before insert.
    local_submission_date       DATE                NOT NULL,
    timezone_at_submission      TEXT                NOT NULL,

    -- ── Anti-cheat: timestamp cross-check ────────────────────────────────
    -- EXIF timestamp extracted from the primary photo.
    -- Cross-checked against server receipt time.
    exif_captured_at            TIMESTAMPTZ,
    server_receipt_at           TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    -- Absolute delta in seconds between EXIF and server time.
    -- Thresholds: free < 300s warning, premium < 120s warning, > 600s either = flag.
    timestamp_delta_seconds     INTEGER,

    -- ── Premium location path (NULL for all other paths) ─────────────────
    -- Location data collected ONLY when verification_path = 'premium_ai_location'.
    -- Requires explicit user consent obtained before collection.
    location_lat                NUMERIC(10, 8),
    location_lng                NUMERIC(11, 8),
    location_accuracy_meters    NUMERIC(8, 2),
    location_captured_at        TIMESTAMPTZ,

    -- ── AI result (premium paths only) ───────────────────────────────────
    ai_confidence_score         NUMERIC(5, 4),      -- 0.0000 to 1.0000
    ai_verdict                  TEXT,               -- 'pass' | 'fail' | 'uncertain'
    ai_result_payload           JSONB,              -- full AI response for audit
    ai_processed_at             TIMESTAMPTZ,

    -- ── Review outcome ────────────────────────────────────────────────────
    reviewed_at                 TIMESTAMPTZ,
    reviewer_id                 UUID                REFERENCES users(id),  -- admin user
    rejection_reason            TEXT,
    internal_notes              TEXT,

    -- ── Coin award ────────────────────────────────────────────────────────
    -- 0 until approved. Set atomically with coin_ledger insert in same transaction.
    coins_awarded               INTEGER             NOT NULL DEFAULT 0 CHECK (coins_awarded >= 0),
    coins_awarded_at            TIMESTAMPTZ,

    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    -- Sanity constraint: location fields must all be present or all absent.
    CONSTRAINT chk_location_complete CHECK (
        (location_lat IS NULL AND location_lng IS NULL AND location_accuracy_meters IS NULL)
        OR
        (location_lat IS NOT NULL AND location_lng IS NOT NULL AND location_accuracy_meters IS NOT NULL)
    ),
    -- Location data only allowed on the location verification path.
    CONSTRAINT chk_location_path_only CHECK (
        location_lat IS NULL OR verification_path = 'premium_ai_location'
    )
);

CREATE INDEX idx_verifications_user          ON verifications(user_id, submitted_at DESC);
CREATE INDEX idx_verifications_status        ON verifications(status) WHERE status IN ('pending_review', 'in_review');
CREATE INDEX idx_verifications_goal          ON verifications(goal_id);
CREATE INDEX idx_verifications_submitted     ON verifications(submitted_at DESC);
-- For admin review queue ordering
CREATE INDEX idx_verifications_free_pending  ON verifications(submitted_at ASC)
    WHERE status = 'pending_review' AND verification_path = 'free_manual';

-- ============================================================
-- VERIFICATION PHOTOS
-- ============================================================
-- Each verification has 1 or 2 photos depending on path.
-- photo_index is 0-based (0 = first photo, 1 = second photo).
-- Free path: always photo_index 0 and 1.
-- Premium standard: always photo_index 0 and 1.
-- Premium location (1-photo): only photo_index 0.
CREATE TABLE verification_photos (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_id     UUID        NOT NULL REFERENCES verifications(id) ON DELETE CASCADE,
    user_id             UUID        NOT NULL REFERENCES users(id),

    -- S3 object key. Never expose this directly — always generate pre-signed URLs.
    s3_key              TEXT        NOT NULL UNIQUE,
    s3_bucket           TEXT        NOT NULL,

    -- 0 = first photo, 1 = second photo
    photo_index         SMALLINT    NOT NULL CHECK (photo_index IN (0, 1)),

    -- EXIF metadata extracted server-side after upload (never trusted from client)
    exif_captured_at    TIMESTAMPTZ,
    exif_gps_lat        NUMERIC(10, 8),
    exif_gps_lng        NUMERIC(11, 8),
    exif_gps_alt_m      NUMERIC(8, 2),
    exif_device_make    TEXT,
    exif_device_model   TEXT,

    file_size_bytes     INTEGER,
    width_px            INTEGER,
    height_px           INTEGER,
    mime_type           TEXT        NOT NULL DEFAULT 'image/jpeg',

    -- Soft delete: mark deleted but keep row for audit trail.
    is_deleted          BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_photo_index_per_verification UNIQUE (verification_id, photo_index)
);

CREATE INDEX idx_photos_verification ON verification_photos(verification_id);
CREATE INDEX idx_photos_user         ON verification_photos(user_id, created_at DESC);
CREATE INDEX idx_photos_s3_key       ON verification_photos(s3_key);

-- ============================================================
-- COIN LEDGER  (append-only — never updated or deleted)
-- ============================================================
-- Every coin movement is recorded here. coin_balance on users is a
-- denormalized cache kept in sync via application-layer transactions.
-- If ever out of sync, coin_balance can be recomputed from this table.
CREATE TABLE coin_ledger (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(id),

    -- Positive = credit (coins earned), Negative = debit (coins spent)
    amount              INTEGER         NOT NULL CHECK (amount != 0),

    -- Running balance AFTER this transaction. Allows instant balance lookup
    -- via MAX(created_at) without summing the full history.
    balance_after       INTEGER         NOT NULL CHECK (balance_after >= 0),

    transaction_type    coin_tx_type    NOT NULL,

    -- Polymorphic reference: what caused this transaction?
    reference_id        UUID,           -- goal.id, sweepstakes_entry.id, or NULL for admin
    reference_type      coin_ref_type,

    description         TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- No updated_at — this table is immutable after insert.
    CONSTRAINT chk_ref_consistency CHECK (
        (reference_id IS NULL AND reference_type IS NULL)
        OR
        (reference_id IS NOT NULL AND reference_type IS NOT NULL)
    )
);

CREATE INDEX idx_ledger_user          ON coin_ledger(user_id, created_at DESC);
CREATE INDEX idx_ledger_type          ON coin_ledger(transaction_type);
CREATE INDEX idx_ledger_reference     ON coin_ledger(reference_id, reference_type) WHERE reference_id IS NOT NULL;

-- Trigger: block any UPDATE or DELETE on coin_ledger (immutability enforcement)
CREATE OR REPLACE FUNCTION prevent_ledger_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'coin_ledger is append-only: UPDATE and DELETE are not permitted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ledger_immutable
    BEFORE UPDATE OR DELETE ON coin_ledger
    FOR EACH ROW EXECUTE FUNCTION prevent_ledger_mutation();

-- ============================================================
-- SWEEPSTAKES
-- ============================================================
CREATE TABLE sweepstakes (
    id                      UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    title                   TEXT                NOT NULL,
    description             TEXT,
    prize_description       TEXT                NOT NULL,  -- "$50 Amazon Gift Card"
    rules_url               TEXT,

    status                  sweepstakes_status  NOT NULL DEFAULT 'upcoming',

    starts_at               TIMESTAMPTZ         NOT NULL,
    ends_at                 TIMESTAMPTZ         NOT NULL,
    draw_at                 TIMESTAMPTZ,

    -- Denormalized for fast odds display. Updated on every entry insert.
    total_entries_count     BIGINT              NOT NULL DEFAULT 0,

    winner_count            INTEGER             NOT NULL DEFAULT 1 CHECK (winner_count >= 1),

    -- Legal / compliance fields
    no_purchase_necessary   BOOLEAN             NOT NULL DEFAULT TRUE,
    sponsor_name            TEXT                NOT NULL DEFAULT 'MuskMaker',
    apple_not_sponsor       BOOLEAN             NOT NULL DEFAULT TRUE,

    created_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_dates CHECK (ends_at > starts_at),
    CONSTRAINT chk_draw_after_end CHECK (draw_at IS NULL OR draw_at >= ends_at)
);

CREATE INDEX idx_sweepstakes_status   ON sweepstakes(status, ends_at DESC);
CREATE INDEX idx_sweepstakes_active   ON sweepstakes(starts_at, ends_at) WHERE status = 'active';

-- ============================================================
-- SWEEPSTAKES ENTRIES
-- ============================================================
-- Each row represents one entry event (user spending N coins = N entries).
-- For odds calculation: user's total entries = SUM(coins_entered) WHERE user_id = ?
-- For the draw: expand into individual entry slots numbered 1..total_entries_count.
CREATE TABLE sweepstakes_entries (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    sweepstakes_id      UUID        NOT NULL REFERENCES sweepstakes(id),
    user_id             UUID        NOT NULL REFERENCES users(id),

    -- Number of coins spent = number of entries added in this event.
    coins_entered       INTEGER     NOT NULL CHECK (coins_entered > 0),

    -- The coin_ledger row that debited these coins.
    -- Ensures entry cannot exist without a corresponding debit.
    ledger_id           UUID        NOT NULL UNIQUE REFERENCES coin_ledger(id),

    entered_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_entries_sweepstakes     ON sweepstakes_entries(sweepstakes_id, entered_at);
CREATE INDEX idx_entries_user_sweep      ON sweepstakes_entries(user_id, sweepstakes_id);
CREATE INDEX idx_entries_user_total      ON sweepstakes_entries(sweepstakes_id, user_id);

-- ============================================================
-- SWEEPSTAKES DRAWS
-- ============================================================
-- One draw record per sweepstakes. Records audit trail for the draw execution.
CREATE TABLE sweepstakes_draws (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    sweepstakes_id          UUID        NOT NULL UNIQUE REFERENCES sweepstakes(id),

    drawn_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drawn_by                UUID        NOT NULL REFERENCES users(id),  -- admin user

    -- Snapshot at draw time for audit reproducibility
    total_entries_at_draw   BIGINT      NOT NULL,
    total_participants      INTEGER     NOT NULL,

    -- For cryptographic audit: the random algorithm and seed used.
    algorithm_version       TEXT        NOT NULL DEFAULT 'crypto_random_v1',
    random_seed             TEXT,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- SWEEPSTAKES WINNERS
-- ============================================================
CREATE TABLE sweepstakes_winners (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    draw_id                 UUID            NOT NULL REFERENCES sweepstakes_draws(id),
    sweepstakes_id          UUID            NOT NULL REFERENCES sweepstakes(id),
    user_id                 UUID            NOT NULL REFERENCES users(id),

    -- Which randomly-selected entry number (1-indexed) won.
    -- Allows full audit: re-expand entry list, find entry #N, verify it maps to this user.
    winning_entry_number    BIGINT          NOT NULL,

    prize_description       TEXT            NOT NULL,
    claim_status            claim_status    NOT NULL DEFAULT 'pending',

    notified_at             TIMESTAMPTZ,
    claimed_at              TIMESTAMPTZ,
    claim_deadline          TIMESTAMPTZ,    -- e.g., 30 days after notification

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_winners_user          ON sweepstakes_winners(user_id, created_at DESC);
CREATE INDEX idx_winners_draw          ON sweepstakes_winners(draw_id);
CREATE INDEX idx_winners_claim_status  ON sweepstakes_winners(claim_status) WHERE claim_status IN ('pending', 'notified');

-- ============================================================
-- NOTIFICATION PREFERENCES
-- ============================================================
-- One row per user. tone choices other than 'normal' are only
-- meaningful for premium users — enforced at notification send time,
-- not at the DB level (free users who somehow set 'harsh' get 'normal').
CREATE TABLE notification_preferences (
    id                              UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                         UUID                NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    push_enabled                    BOOLEAN             NOT NULL DEFAULT TRUE,
    email_enabled                   BOOLEAN             NOT NULL DEFAULT FALSE,

    -- Goal expiry reminder
    goal_reminder_enabled           BOOLEAN             NOT NULL DEFAULT TRUE,
    reminder_minutes_before_expiry  INTEGER             NOT NULL DEFAULT 60 CHECK (reminder_minutes_before_expiry > 0),

    -- Premium-only tone (enforced at send time, not stored access control)
    notification_tone               notification_tone   NOT NULL DEFAULT 'normal',

    -- Sweepstakes notifications
    sweep_result_enabled            BOOLEAN             NOT NULL DEFAULT TRUE,
    new_sweep_enabled               BOOLEAN             NOT NULL DEFAULT TRUE,

    created_at                      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

-- ============================================================
-- PUSH TOKENS
-- ============================================================
CREATE TABLE push_tokens (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expo_push_token     TEXT        NOT NULL UNIQUE,
    platform            TEXT        NOT NULL CHECK (platform IN ('ios', 'android')),
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_push_tokens_user   ON push_tokens(user_id) WHERE is_active = TRUE;

-- ============================================================
-- ADMIN REVIEW QUEUE
-- ============================================================
-- Created automatically when a free-tier verification is submitted.
-- Premium verifications never create a row here.
CREATE TABLE admin_reviews (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_id     UUID            NOT NULL UNIQUE REFERENCES verifications(id),
    user_id             UUID            NOT NULL REFERENCES users(id),

    -- Lower number = higher priority
    priority            SMALLINT        NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),

    status              review_status   NOT NULL DEFAULT 'queued',

    queued_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    assigned_to         UUID            REFERENCES users(id),  -- admin reviewer
    assigned_at         TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,

    rejection_reason    TEXT,
    reviewer_notes      TEXT,           -- internal only, never shown to user

    -- SLA tracking: free tier target is 24 hours (set to queued_at + 24h on insert)
    sla_deadline        TIMESTAMPTZ     NOT NULL,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reviews_queued      ON admin_reviews(queued_at ASC) WHERE status = 'queued';
CREATE INDEX idx_reviews_assigned    ON admin_reviews(assigned_to) WHERE status = 'in_review';
CREATE INDEX idx_reviews_sla         ON admin_reviews(sla_deadline) WHERE status IN ('queued', 'in_review');

-- ============================================================
-- SUBSCRIPTION EVENTS  (RevenueCat webhook archive)
-- ============================================================
CREATE TABLE subscription_events (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID        REFERENCES users(id),   -- nullable: webhook may arrive before user row
    firebase_uid            TEXT,                               -- fallback lookup key

    revenuecat_event_type   TEXT        NOT NULL,               -- "INITIAL_PURCHASE", "RENEWAL", etc.
    revenuecat_event_id     TEXT        NOT NULL UNIQUE,        -- idempotency key
    product_id              TEXT,
    period_type             TEXT,                               -- "NORMAL", "TRIAL", "INTRO"
    purchased_at            TIMESTAMPTZ,
    expires_at              TIMESTAMPTZ,

    -- Full webhook payload archived for dispute resolution
    raw_payload             JSONB       NOT NULL,
    processed_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_error        TEXT,       -- non-null if processing failed

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sub_events_user     ON subscription_events(user_id, created_at DESC);
CREATE INDEX idx_sub_events_type     ON subscription_events(revenuecat_event_type, processed_at);
CREATE INDEX idx_sub_events_rc_id    ON subscription_events(revenuecat_event_id);

-- ============================================================
-- TIMEZONE AUDIT LOG
-- ============================================================
-- Immutable record of every timezone change. Used for abuse detection
-- and dispute resolution ("user claims goal was created in wrong timezone").
CREATE TABLE timezone_audit_log (
    id                  UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID                NOT NULL REFERENCES users(id),

    old_timezone        TEXT,               -- NULL on first set (onboarding)
    new_timezone        TEXT                NOT NULL,

    changed_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    ip_address          INET,
    user_agent          TEXT,
    change_source       tz_change_source    NOT NULL,

    -- Abuse flags
    flagged_suspicious  BOOLEAN             NOT NULL DEFAULT FALSE,
    flag_reason         TEXT,               -- e.g., 'change_within_30min_of_goal'

    -- Rate limit metadata
    changes_in_window   INTEGER,            -- how many changes in the last 24h at time of this change
    was_blocked         BOOLEAN             NOT NULL DEFAULT FALSE   -- TRUE if rate limit blocked this
);

CREATE INDEX idx_tz_audit_user       ON timezone_audit_log(user_id, changed_at DESC);
CREATE INDEX idx_tz_audit_flagged    ON timezone_audit_log(flagged_suspicious) WHERE flagged_suspicious = TRUE;
CREATE INDEX idx_tz_audit_time       ON timezone_audit_log(changed_at DESC);

-- ============================================================
-- ANTI-CHEAT LOG
-- ============================================================
-- Append-only log of all suspicious activity signals.
-- Populated by: VerificationService, TimezoneService, AuditService.
CREATE TABLE anti_cheat_log (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(id),

    -- Event type codes (application-defined, kept consistent via constants)
    -- Examples: 'tz_change_near_goal', 'exif_mismatch', 'rapid_resubmission',
    --           'location_mismatch', 'impossible_location', 'repeated_failure',
    --           'metadata_stripped', 'abnormal_delta', 'tz_window_extension'
    event_type          TEXT            NOT NULL,
    severity            cheat_severity  NOT NULL DEFAULT 'low',

    -- Polymorphic reference to the triggering entity
    reference_id        UUID,
    reference_type      TEXT            CHECK (reference_type IN ('goal', 'verification', 'entry', 'timezone_change')),

    -- Structured details for machine processing + human review
    details             JSONB,

    -- What the system automatically did in response
    -- e.g., 'flagged_for_review', 'blocked', 'manual_review_required', 'none'
    auto_action         TEXT            NOT NULL DEFAULT 'none',

    -- Admin review of this flag
    reviewed_by         UUID            REFERENCES users(id),
    reviewed_at         TIMESTAMPTZ,
    resolution          TEXT,           -- 'false_positive', 'confirmed_abuse', 'warning_issued', 'banned'

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cheat_user          ON anti_cheat_log(user_id, created_at DESC);
CREATE INDEX idx_cheat_severity      ON anti_cheat_log(severity, created_at DESC) WHERE reviewed_at IS NULL;
CREATE INDEX idx_cheat_unreviewed    ON anti_cheat_log(created_at DESC) WHERE reviewed_at IS NULL;
CREATE INDEX idx_cheat_event_type    ON anti_cheat_log(event_type, created_at DESC);