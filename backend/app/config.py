from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── App ───────────────────────────────────────────────────────────────
    app_name: str = "MuskMaker API"
    app_env: str = "development"  # development | staging | production
    debug: bool = False

    # ── Database (AWS RDS PostgreSQL) ─────────────────────────────────────
    database_url: str  # e.g. postgresql+asyncpg://user:pass@host:5432/muskmaker

    # ── Firebase Auth ─────────────────────────────────────────────────────
    firebase_project_id: str
    firebase_service_account_path: str = "firebase-service-account.json"

    # ── AWS ───────────────────────────────────────────────────────────────
    aws_region: str = "us-east-1"
    aws_access_key_id: str
    aws_secret_access_key: str
    s3_bucket_photos: str       # e.g. muskmaker-photos-prod
    s3_bucket_assets: str       # e.g. muskmaker-assets-prod
    cloudfront_domain: str      # e.g. d1234abcd.cloudfront.net
    cloudfront_key_pair_id: str
    cloudfront_private_key_path: str = "cloudfront-private-key.pem"

    # Presigned upload URL expiry (seconds)
    s3_upload_url_expiry: int = 300     # 5 minutes
    s3_download_url_expiry: int = 3600  # 1 hour (admin review)

    # ── RevenueCat ────────────────────────────────────────────────────────
    revenuecat_webhook_secret: str

    # ── OpenAI (AI verification) ──────────────────────────────────────────
    openai_api_key: str
    openai_model: str = "gpt-4o"
    ai_confidence_threshold: float = 0.75

    # ── Expo Push Notifications ───────────────────────────────────────────
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"

    # ── Rate Limits ───────────────────────────────────────────────────────
    # Timezone changes: max N per rolling 24-hour window per user
    timezone_change_rate_limit: int = 1
    # Verification submissions: max N per hour per user
    verification_rate_limit: int = 10

    # ── Anti-Cheat Thresholds ─────────────────────────────────────────────
    # Max seconds between EXIF timestamp and server receipt time before warning
    exif_delta_warn_seconds: int = 300      # 5 min
    # Max seconds before hard fail
    exif_delta_fail_seconds: int = 600      # 10 min
    # For premium: stricter warning threshold
    exif_delta_premium_warn_seconds: int = 120

    # Minutes before local day-end to fire a goal-expiry reminder push
    goal_reminder_minutes_before_expiry: int = 60

    # ── Sweepstakes ───────────────────────────────────────────────────────
    sweep_winner_claim_days: int = 30  # days after notification to claim prize

    # ── Serper Maps (location verification) ──────────────────────────────
    serper_api_key: str

    # ── Celery / RabbitMQ ─────────────────────────────────────────────────
    rabbitmq_url: str

    # ── CORS ──────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
