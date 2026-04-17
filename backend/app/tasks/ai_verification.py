from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.ai_verification.run_ai_verification_standard",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_ai_verification_standard(self, verification_id: str) -> None:
    """
    AI verification for premium_ai_standard path (2 photos, no location).
    Loads verification from DB, calls AIService, writes result back.
    Implementation to be filled in.
    """
    pass


@celery_app.task(
    name="app.tasks.ai_verification.run_ai_verification_location",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_ai_verification_location(self, verification_id: str) -> None:
    """
    AI verification for premium_ai_location path (1 photo + GPS).
    Loads verification from DB, calls AIService with location data, writes result back.
    Implementation to be filled in.
    """
    pass
