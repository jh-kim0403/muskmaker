import asyncio
import logging

from app.celery_app import celery_app
from app.tasks.handlers.ai_verification_handler import openai_verify_photo, run_location

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ai_verification.run_ai_verification_standard",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_ai_verification_standard(self, verification_id: str) -> None:
    try:
        asyncio.run(openai_verify_photo(verification_id))
    except Exception as exc:
        logger.exception("run_ai_verification_standard failed for %s: %s", verification_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.ai_verification.run_ai_verification_location",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_ai_verification_location(self, verification_id: str) -> None:
    try:
        asyncio.run(run_location(verification_id))
    except Exception as exc:
        logger.exception("run_ai_verification_location failed for %s: %s", verification_id, exc)
        raise self.retry(exc=exc)
