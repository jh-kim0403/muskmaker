from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "muskmaker",
    broker=settings.rabbitmq_url,
    include=["app.tasks.ai_verification", "app.tasks.periodic"],
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
    beat_schedule={
        "expire-stale-goals": {
            "task": "app.tasks.periodic.expire_stale_goals",
            "schedule": crontab(minute=5),  # every hour at :05
        },
        "send-24h-reminders": {
            "task": "app.tasks.periodic.send_24h_reminders",
            "schedule": 300.0,  # every 5 minutes
        },
        
#        "send-2h-reminders": {
#            "task": "app.tasks.periodic.send_2h_reminders",
#            "schedule": 300.0,  # every 5 minutes
#        },
        "generate-notification-templates": {
            "task": "app.tasks.periodic.generate_notification_templates",
            "schedule": crontab(hour=0, minute=5),  # daily at 00:05 UTC
        },
    },
)
