from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "muskmaker",
    broker=settings.rabbitmq_url,
    include=["app.tasks.ai_verification"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.tasks.ai_verification.run_ai_verification_standard": {
            "queue": "ai_verification_standard",
        },
        "app.tasks.ai_verification.run_ai_verification_location": {
            "queue": "ai_verification_location",
        },
    },
)
