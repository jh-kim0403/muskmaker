-- =============================================================================
-- MuskMaker — PostgreSQL Schema
-- =============================================================================
-- Conventions:
--   • All primary keys are UUID (gen_random_uuid())
--   • All timestamps are TIMESTAMPTZ (UTC stored, timezone-aware)
--   • Soft deletes use is_deleted + deleted_at rather than hard DELETEs
--   • Business rules that must never be violated are enforced at the DB layer
--     via CHECK constraints, UNIQUE constraints, and triggers — not just app code
-- =============================================================================

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "btree_gist";  -- exclusion constraints (future use)

-- =============================================================================
-- SHARED HELPER FUNCTIONS
-- =============================================================================

-- Convert a UTC timestamptz to the user's local DATE.
-- This is the single authoritative function used everywhere a calendar-day
-- boundary must be computed. NEVER derive local date on the client.
CREATE OR REPLACE FUNCTION user_local_date(
    utc_ts  TIMESTAMPTZ,
    iana_tz TEXT
) RETURNS DATE AS $$
    SELECT (utc_ts AT TIME ZONE iana_tz)::DATE;
$$ LANGUAGE SQL IMMUTABLE STRICT;

-- Compute the exact UTC moment a local calendar day ends (23:59:59.999999)
-- for a given IANA timezone and local date.
-- Used to set goals.expires_at at creation time.
CREATE OR REPLACE FUNCTION local_day_end_utc(
    local_date DATE,
    iana_tz    TEXT
) RETURNS TIMESTAMPTZ AS $$
    SELECT (local_date::TIMESTAMP + INTERVAL '1 day - 1 microsecond')
           AT TIME ZONE iana_tz;
$$ LANGUAGE SQL IMMUTABLE STRICT;

-- =============================================================================
-- ENUMS
-- =============================================================================
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

-- =============================================================================
-- USERS
-- =============================================================================
CREATE TABLE users (
    id                      UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid            TEXT              NOT NULL UNIQUE,
    email                   TEXT,
    display_name            TEXT,

    -- Authoritative IANA timezone for all day-boundary logic (e.g. 'America/Los_Angeles').
    -- Set on onboarding; updated via PATCH /users/me/timezone (rate-limited).
    -- NEVER derived from client at query time — always read from this column.
    timezone                TEXT              NOT NULL DEFAULT 'UTC',
    timezone_updated_at     TIMESTAMPTZ,

    -- Subscription state — kept in sync via RevenueCat webhooks.
    subscription_tier       subscription_tier NOT NULL DEFAULT 'free',
    subscription_expires_at TIMESTAMPTZ,
    revenuecat_customer_id  TEXT              UNIQUE,

    -- Denormalized coin balance for fast reads.
    -- Source of truth is coin_ledger. Kept in sync via application transactions.
    -- CHECK ensures it can never go negative at the DB level.
    coin_balance            INTEGER           NOT NULL DEFAULT 0 CHECK (coin_balance >= 0),

    -- Account health
    is_active               BOOLEAN           NOT NULL DEFAULT TRUE,
    is_banned               BOOLEAN           NOT NULL DEFAULT FALSE,
    ban_reason              TEXT,
    banned_at               TIMESTAMPTZ,
    banned_by               UUID              REFERENCES users(id),

    created_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    last_seen_at            TIMESTAMPTZ
);

CREATE INDEX idx_users_firebase_uid  ON users(firebase_uid);
CREATE INDEX idx_users_revenuecat_id ON users(revenuecat_customer_id) WHERE revenuecat_customer_id IS NOT NULL;
CREATE INDEX idx_users_subscription  ON users(subscription_tier, subscription_expires_at);
CREATE INDEX idx_users_coin_balance  ON users(coin_balance) WHERE coin_balance > 0;

-- =============================================================================
-- GOAL TYPES  (admin-managed catalog)
-- =============================================================================
-- Defines what goals exist, their coin rewards, and their review behavior.
-- coin_reward is NEVER modified by subscription tier — same value for all users.
CREATE TABLE goal_types (
    id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name                   TEXT        NOT NULL,         -- "Go to the gym"
    slug                   TEXT        NOT NULL UNIQUE,  -- "gym"
    description            TEXT,
    icon_url               TEXT,

    -- Coins awarded on successful verification. Identical for free and premium users.
    coin_reward            INTEGER     NOT NULL CHECK (coin_reward > 0),
    difficulty             difficulty  NOT NULL DEFAULT 'medium',

    -- When TRUE, the premium 1-photo AI path for this type requires location services.
    -- Has no effect on free users.
    supports_location_path BOOLEAN     NOT NULL DEFAULT FALSE,

    is_active              BOOLEAN     NOT NULL DEFAULT TRUE,
    display_order          INTEGER     NOT NULL DEFAULT 0,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_goal_types_active ON goal_types(is_active, display_order);
CREATE INDEX idx_goal_types_slug   ON goal_types(slug);

-- =============================================================================
-- GOALS
-- =============================================================================
-- One row per goal instance per user per local calendar day.
-- The UNIQUE constraint on (user_id, goal_type_id, local_goal_date) is the
-- primary database enforcement of the "one goal per type per day" fairness rule.
CREATE TABLE goals (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_type_id     UUID        NOT NULL REFERENCES goal_types(id),

    status           goal_status NOT NULL DEFAULT 'active',
    notes            TEXT,

    -- The local calendar date this goal belongs to, in the user's stored timezone.
    -- Computed server-side: (NOW() AT TIME ZONE users.timezone)::DATE
    -- The client NEVER supplies this value.
    local_goal_date         DATE        NOT NULL,

    -- The timezone in effect when this goal was created.
    -- Frozen at insert time. Subsequent timezone changes do NOT alter this column.
    timezone_at_creation    TEXT        NOT NULL,

    -- Precomputed expiry: end-of-day in timezone_at_creation, expressed as UTC.
    -- Used by the expiry worker query and for "expires at X" display in the app.
    expires_at              TIMESTAMPTZ NOT NULL,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ── Core fairness constraint ──────────────────────────────────────────────
    CONSTRAINT uq_goal_per_type_per_day UNIQUE (user_id, goal_type_id, local_goal_date)
);

CREATE INDEX idx_goals_user_date  ON goals(user_id, local_goal_date DESC);
CREATE INDEX idx_goals_status     ON goals(status) WHERE status IN ('active', 'submitted');
CREATE INDEX idx_goals_expires_at ON goals(expires_at) WHERE status = 'active';
CREATE INDEX idx_goals_user_type  ON goals(user_id, goal_type_id);

-- =============================================================================
-- VERIFICATIONS
-- =============================================================================
-- One verification attempt per goal (1-to-1 after submission).
-- Captures all evidence: photos, EXIF data, AI verdict, location (premium only).
CREATE TABLE verifications (
    id                        UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id                   UUID                NOT NULL UNIQUE REFERENCES goals(id),
    user_id                   UUID                NOT NULL REFERENCES users(id),

    status                    verification_status NOT NULL DEFAULT 'pending_review',
    verification_path         verification_path   NOT NULL,

    -- ── Submission timestamps ─────────────────────────────────────────────────
    -- submitted_at: UTC server clock at time of request receipt.
    submitted_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    -- local_submission_date: calendar date of submission in the user's timezone.
    -- Computed server-side from submitted_at + user.timezone at submission time.
    -- Application layer enforces: local_submission_date = goal.local_goal_date.
    local_submission_date     DATE                NOT NULL,
    timezone_at_submission    TEXT                NOT NULL,

    -- ── Anti-cheat: timestamp cross-check ────────────────────────────────────
    exif_captured_at          TIMESTAMPTZ,
    server_receipt_at         TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    -- Absolute delta in seconds between EXIF and server receipt time.
    -- Thresholds defined in config; values exceeding limits trigger cheat flags.
    timestamp_delta_seconds   INTEGER,

    -- ── Premium location path (NULL unless verification_path = 'premium_ai_location') ──
    -- Collected ONLY with explicit user consent, ONLY for the location AI path.
    location_lat              NUMERIC(10, 8),
    location_lng              NUMERIC(11, 8),
    location_accuracy_meters  NUMERIC(8, 2),
    location_captured_at      TIMESTAMPTZ,

    -- ── AI result (premium paths only) ────────────────────────────────────────
    ai_confidence_score       NUMERIC(5, 4),   -- 0.0000 to 1.0000
    ai_verdict                TEXT,            -- 'pass' | 'fail' | 'uncertain'
    ai_result_payload         JSONB,           -- full AI API response (audit trail)
    ai_processed_at           TIMESTAMPTZ,

    -- ── Review outcome ─────────────────────────────────────────────────────────
    reviewed_at               TIMESTAMPTZ,
    reviewer_id               UUID             REFERENCES users(id),
    rejection_reason          TEXT,
    internal_notes            TEXT,

    -- ── Coin award ─────────────────────────────────────────────────────────────
    -- Set atomically with coin_ledger insert in the same DB transaction.
    coins_awarded             INTEGER          NOT NULL DEFAULT 0 CHECK (coins_awarded >= 0),
    coins_awarded_at          TIMESTAMPTZ,

    created_at                TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ      NOT NULL DEFAULT NOW(),

    -- Location fields: all-or-nothing (never partially filled)
    CONSTRAINT chk_location_complete CHECK (
        (location_lat IS NULL AND location_lng IS NULL AND location_accuracy_meters IS NULL)
        OR
        (location_lat IS NOT NULL AND location_lng IS NOT NULL AND location_accuracy_meters IS NOT NULL)
    ),
    -- Location data is only allowed on the location-enabled premium path
    CONSTRAINT chk_location_path_only CHECK (
        location_lat IS NULL OR verification_path = 'premium_ai_location'
    )
);

CREATE INDEX idx_verifications_user         ON verifications(user_id, submitted_at DESC);
CREATE INDEX idx_verifications_goal         ON verifications(goal_id);
CREATE INDEX idx_verifications_status       ON verifications(status) WHERE status IN ('pending_review', 'in_review');
CREATE INDEX idx_verifications_submitted    ON verifications(submitted_at DESC);
-- Optimized index for the admin free-tier review queue (oldest first)
CREATE INDEX idx_verifications_free_pending ON verifications(submitted_at ASC)
    WHERE status = 'pending_review' AND verification_path = 'free_manual';

-- =============================================================================
-- VERIFICATION PHOTOS
-- =============================================================================
-- Free path: always photo_index 0 and 1 (2 photos required).
-- Premium standard: always photo_index 0 and 1 (2 photos required).
-- Premium location 1-photo path: only photo_index 0 (1 photo required).
CREATE TABLE verification_photos (
    id              UUID     PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_id UUID     NOT NULL REFERENCES verifications(id) ON DELETE CASCADE,
    user_id         UUID     NOT NULL REFERENCES users(id),

    -- S3 object key. Never returned directly to clients.
    -- Always generate a time-limited pre-signed URL before serving.
    s3_key          TEXT     NOT NULL UNIQUE,
    s3_bucket       TEXT     NOT NULL,

    photo_index     SMALLINT NOT NULL CHECK (photo_index IN (0, 1)),

    -- EXIF metadata extracted server-side after upload.
    -- Values from client are NEVER trusted for these fields.
    exif_captured_at   TIMESTAMPTZ,
    exif_gps_lat       NUMERIC(10, 8),
    exif_gps_lng       NUMERIC(11, 8),
    exif_gps_alt_m     NUMERIC(8, 2),
    exif_device_make   TEXT,
    exif_device_model  TEXT,

    file_size_bytes    INTEGER,
    width_px           INTEGER,
    height_px          INTEGER,
    mime_type          TEXT    NOT NULL DEFAULT 'image/jpeg',

    -- Soft delete: row kept for audit trail even after deletion
    is_deleted  BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at  TIMESTAMPTZ,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_photo_index_per_verification UNIQUE (verification_id, photo_index)
);

CREATE INDEX idx_photos_verification ON verification_photos(verification_id);
CREATE INDEX idx_photos_user         ON verification_photos(user_id, created_at DESC);
CREATE INDEX idx_photos_s3_key       ON verification_photos(s3_key);

-- =============================================================================
-- COIN LEDGER  (append-only — immutable after insert)
-- =============================================================================
-- Every coin movement is recorded here. users.coin_balance is a denormalized
-- cache. If ever out of sync, it can be recomputed as:
--   SELECT balance_after FROM coin_ledger WHERE user_id = ?
--   ORDER BY created_at DESC LIMIT 1
CREATE TABLE coin_ledger (
    id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID          NOT NULL REFERENCES users(id),

    -- Positive = credit (earned), Negative = debit (spent)
    amount           INTEGER       NOT NULL CHECK (amount != 0),

    -- Running balance AFTER this transaction. Allows O(1) balance lookup.
    balance_after    INTEGER       NOT NULL CHECK (balance_after >= 0),

    transaction_type coin_tx_type  NOT NULL,

    -- Polymorphic reference to the entity that caused this transaction
    reference_id     UUID,
    reference_type   coin_ref_type,

    description      TEXT,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    -- No updated_at — this table is intentionally immutable
    CONSTRAINT chk_ref_consistency CHECK (
        (reference_id IS NULL AND reference_type IS NULL)
        OR
        (reference_id IS NOT NULL AND reference_type IS NOT NULL)
    )
);

CREATE INDEX idx_ledger_user      ON coin_ledger(user_id, created_at DESC);
CREATE INDEX idx_ledger_type      ON coin_ledger(transaction_type);
CREATE INDEX idx_ledger_reference ON coin_ledger(reference_id, reference_type) WHERE reference_id IS NOT NULL;

-- Trigger: block any UPDATE or DELETE (immutability enforced at DB level)
CREATE OR REPLACE FUNCTION prevent_ledger_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'coin_ledger is append-only: UPDATE and DELETE are not permitted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ledger_immutable
    BEFORE UPDATE OR DELETE ON coin_ledger
    FOR EACH ROW EXECUTE FUNCTION prevent_ledger_mutation();

-- =============================================================================
-- SWEEPSTAKES
-- =============================================================================
CREATE TABLE sweepstakes (
    id                    UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
    title                 TEXT               NOT NULL,
    description           TEXT,
    prize_description     TEXT               NOT NULL,  -- e.g. "$50 Amazon Gift Card"
    rules_url             TEXT,

    status                sweepstakes_status NOT NULL DEFAULT 'upcoming',

    starts_at             TIMESTAMPTZ        NOT NULL,
    ends_at               TIMESTAMPTZ        NOT NULL,
    draw_at               TIMESTAMPTZ,

    -- Denormalized for fast odds display. Incremented on every entry insert.
    total_entries_count   BIGINT             NOT NULL DEFAULT 0,

    winner_count          INTEGER            NOT NULL DEFAULT 1 CHECK (winner_count >= 1),

    -- Apple compliance fields (5.3 sweepstakes guidelines)
    no_purchase_necessary BOOLEAN            NOT NULL DEFAULT TRUE,
    sponsor_name          TEXT               NOT NULL DEFAULT 'MuskMaker',
    apple_not_sponsor     BOOLEAN            NOT NULL DEFAULT TRUE,

    created_at            TIMESTAMPTZ        NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ        NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_dates        CHECK (ends_at > starts_at),
    CONSTRAINT chk_draw_after   CHECK (draw_at IS NULL OR draw_at >= ends_at)
);

CREATE INDEX idx_sweepstakes_status ON sweepstakes(status, ends_at DESC);
CREATE INDEX idx_sweepstakes_active ON sweepstakes(starts_at, ends_at) WHERE status = 'active';

-- =============================================================================
-- SWEEPSTAKES ENTRIES
-- =============================================================================
-- Each row = one entry event (user spends N coins → N entries added).
-- Odds display: user_entries = SUM(coins_entered) WHERE user_id = ? AND sweepstakes_id = ?
-- Draw: conceptually expand all entries into a numbered list 1..total_entries_count.
CREATE TABLE sweepstakes_entries (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    sweepstakes_id UUID        NOT NULL REFERENCES sweepstakes(id),
    user_id        UUID        NOT NULL REFERENCES users(id),

    -- Coins spent = entries added in this event.
    coins_entered  INTEGER     NOT NULL CHECK (coins_entered > 0),

    -- Enforces that an entry cannot exist without a corresponding coin debit.
    ledger_id      UUID        NOT NULL UNIQUE REFERENCES coin_ledger(id),

    entered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_entries_sweepstakes ON sweepstakes_entries(sweepstakes_id, entered_at);
CREATE INDEX idx_entries_user_sweep  ON sweepstakes_entries(user_id, sweepstakes_id);
CREATE INDEX idx_entries_user_total  ON sweepstakes_entries(sweepstakes_id, user_id);

-- =============================================================================
-- SWEEPSTAKES DRAWS
-- =============================================================================
-- One row per sweepstakes. Immutable audit record of how the draw was conducted.
CREATE TABLE sweepstakes_draws (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    sweepstakes_id        UUID        NOT NULL UNIQUE REFERENCES sweepstakes(id),

    drawn_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drawn_by              UUID        NOT NULL REFERENCES users(id),

    -- Snapshot at draw time for reproducible audit
    total_entries_at_draw BIGINT      NOT NULL,
    total_participants    INTEGER     NOT NULL,

    -- Cryptographic audit trail
    algorithm_version     TEXT        NOT NULL DEFAULT 'crypto_random_v1',
    random_seed           TEXT,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- SWEEPSTAKES WINNERS
-- =============================================================================
CREATE TABLE sweepstakes_winners (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    draw_id              UUID         NOT NULL REFERENCES sweepstakes_draws(id),
    sweepstakes_id       UUID         NOT NULL REFERENCES sweepstakes(id),
    user_id              UUID         NOT NULL REFERENCES users(id),

    -- The randomly selected entry number (1-indexed).
    -- Allows full audit: expand entry list, find entry #N, verify it maps to user.
    winning_entry_number BIGINT       NOT NULL,

    prize_description    TEXT         NOT NULL,
    claim_status         claim_status NOT NULL DEFAULT 'pending',

    notified_at          TIMESTAMPTZ,
    claimed_at           TIMESTAMPTZ,
    claim_deadline       TIMESTAMPTZ,  -- N days after notification; set on notify

    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_winners_user         ON sweepstakes_winners(user_id, created_at DESC);
CREATE INDEX idx_winners_draw         ON sweepstakes_winners(draw_id);
CREATE INDEX idx_winners_claim_status ON sweepstakes_winners(claim_status) WHERE claim_status IN ('pending', 'notified');

-- =============================================================================
-- NOTIFICATION PREFERENCES
-- =============================================================================
-- One row per user. notification_tone values other than 'normal' are only
-- applied for premium users — enforced at send time in NotificationService.
CREATE TABLE notification_preferences (
    id                             UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                        UUID              NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    push_enabled                   BOOLEAN           NOT NULL DEFAULT TRUE,
    email_enabled                  BOOLEAN           NOT NULL DEFAULT FALSE,

    goal_reminder_enabled          BOOLEAN           NOT NULL DEFAULT TRUE,
    reminder_minutes_before_expiry INTEGER           NOT NULL DEFAULT 60 CHECK (reminder_minutes_before_expiry > 0),

    -- 'friendly_banter' and 'harsh' are premium-only. Free users always get 'normal'.
    notification_tone              notification_tone NOT NULL DEFAULT 'normal',

    sweep_result_enabled           BOOLEAN           NOT NULL DEFAULT TRUE,
    new_sweep_enabled              BOOLEAN           NOT NULL DEFAULT TRUE,

    created_at                     TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at                     TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- PUSH TOKENS
-- =============================================================================
CREATE TABLE push_tokens (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expo_push_token TEXT        NOT NULL UNIQUE,
    platform        TEXT        NOT NULL CHECK (platform IN ('ios', 'android')),
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_push_tokens_user ON push_tokens(user_id) WHERE is_active = TRUE;

-- =============================================================================
-- ADMIN REVIEW QUEUE
-- =============================================================================
-- Created automatically when a free-tier verification is submitted.
-- Premium verifications never insert a row here.
CREATE TABLE admin_reviews (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_id UUID          NOT NULL UNIQUE REFERENCES verifications(id),
    user_id         UUID          NOT NULL REFERENCES users(id),

    -- Priority 1 (highest) to 10 (lowest). Default 5.
    priority        SMALLINT      NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),

    status          review_status NOT NULL DEFAULT 'queued',

    queued_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    assigned_to     UUID          REFERENCES users(id),
    assigned_at     TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,

    rejection_reason TEXT,
    reviewer_notes   TEXT,   -- internal only, never shown to end user

    -- Generated column: SLA deadline = queued_at + 24h (free tier target)
    sla_deadline    TIMESTAMPTZ GENERATED ALWAYS AS (queued_at + INTERVAL '24 hours') STORED,

    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reviews_queued   ON admin_reviews(queued_at ASC) WHERE status = 'queued';
CREATE INDEX idx_reviews_assigned ON admin_reviews(assigned_to) WHERE status = 'in_review';
CREATE INDEX idx_reviews_sla      ON admin_reviews(sla_deadline) WHERE status IN ('queued', 'in_review');

-- =============================================================================
-- SUBSCRIPTION EVENTS  (RevenueCat webhook archive)
-- =============================================================================
CREATE TABLE subscription_events (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID        REFERENCES users(id),  -- nullable: may arrive before user row
    firebase_uid          TEXT,                              -- fallback lookup key

    revenuecat_event_type TEXT        NOT NULL,  -- 'INITIAL_PURCHASE', 'RENEWAL', 'CANCELLATION', etc.
    revenuecat_event_id   TEXT        NOT NULL UNIQUE,  -- idempotency key
    product_id            TEXT,
    period_type           TEXT,                          -- 'NORMAL', 'TRIAL', 'INTRO'
    purchased_at          TIMESTAMPTZ,
    expires_at            TIMESTAMPTZ,

    -- Full payload archived for dispute resolution / replay
    raw_payload           JSONB       NOT NULL,
    processed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_error      TEXT,  -- non-null if handler failed

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sub_events_user  ON subscription_events(user_id, created_at DESC);
CREATE INDEX idx_sub_events_type  ON subscription_events(revenuecat_event_type, processed_at);
CREATE INDEX idx_sub_events_rc_id ON subscription_events(revenuecat_event_id);

-- =============================================================================
-- TIMEZONE AUDIT LOG  (append-only)
-- =============================================================================
-- Immutable record of every timezone change attempt (successful or blocked).
-- Used for: abuse detection, dispute resolution, admin audit panel.
CREATE TABLE timezone_audit_log (
    id                UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID             NOT NULL REFERENCES users(id),

    old_timezone      TEXT,            -- NULL on first set during onboarding
    new_timezone      TEXT             NOT NULL,

    changed_at        TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    ip_address        INET,
    user_agent        TEXT,
    change_source     tz_change_source NOT NULL,

    -- Abuse signals
    flagged_suspicious  BOOLEAN        NOT NULL DEFAULT FALSE,
    flag_reason         TEXT,          -- e.g. 'change_within_30min_of_goal_creation'

    -- Rate limit metadata at time of change
    changes_in_window   INTEGER,       -- count of changes in last 24h at this moment
    was_blocked         BOOLEAN        NOT NULL DEFAULT FALSE  -- TRUE = rate limit rejected this
);

CREATE INDEX idx_tz_audit_user    ON timezone_audit_log(user_id, changed_at DESC);
CREATE INDEX idx_tz_audit_flagged ON timezone_audit_log(flagged_suspicious) WHERE flagged_suspicious = TRUE;
CREATE INDEX idx_tz_audit_time    ON timezone_audit_log(changed_at DESC);

-- =============================================================================
-- ANTI-CHEAT LOG  (append-only)
-- =============================================================================
-- Structured log of all suspicious activity signals. Populated by multiple
-- services: VerificationService, TimezoneService, AuditService.
-- Event type codes are defined as constants in app/constants.py.
CREATE TABLE anti_cheat_log (
    id             UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID           NOT NULL REFERENCES users(id),

    -- Event type string constants (defined in app/constants.py), e.g.:
    --   'tz_change_near_goal'       'exif_mismatch'
    --   'rapid_resubmission'        'location_mismatch'
    --   'impossible_location'       'repeated_failure'
    --   'metadata_stripped'         'abnormal_delta'
    --   'tz_window_extension'
    event_type     TEXT           NOT NULL,
    severity       cheat_severity NOT NULL DEFAULT 'low',

    -- Polymorphic reference to the triggering entity
    reference_id   UUID,
    reference_type TEXT           CHECK (reference_type IN ('goal', 'verification', 'entry', 'timezone_change')),

    -- Structured payload for machine processing and human review
    details        JSONB,

    -- What the system automatically did in response, e.g.:
    --   'none' | 'flagged_for_review' | 'blocked' | 'manual_review_required'
    auto_action    TEXT           NOT NULL DEFAULT 'none',

    -- Admin disposition of this flag
    reviewed_by    UUID           REFERENCES users(id),
    reviewed_at    TIMESTAMPTZ,
    resolution     TEXT,  -- 'false_positive' | 'confirmed_abuse' | 'warning_issued' | 'banned'

    created_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cheat_user       ON anti_cheat_log(user_id, created_at DESC);
CREATE INDEX idx_cheat_severity   ON anti_cheat_log(severity, created_at DESC) WHERE reviewed_at IS NULL;
CREATE INDEX idx_cheat_unreviewed ON anti_cheat_log(created_at DESC) WHERE reviewed_at IS NULL;
CREATE INDEX idx_cheat_event_type ON anti_cheat_log(event_type, created_at DESC);
