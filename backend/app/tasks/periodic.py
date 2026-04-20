import asyncio
import logging

from app.celery_app import celery_app
from app.tasks.handlers.goal_expiry_handler import expire_stale_goals
from app.tasks.handlers.notification_handler import (
    send_24h_reminders,
    send_2h_reminders,
    send_missed_notifications,
)
from app.tasks.handlers.template_generation_handler import generate_notification_templates

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.periodic.expire_stale_goals",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def expire_stale_goals_task(self) -> None:
    try:
        asyncio.run(expire_stale_goals())
    except Exception as exc:
        logger.exception("expire_stale_goals_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.periodic.send_24h_reminders",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def send_24h_reminders_task(self) -> None:
    try:
        asyncio.run(send_24h_reminders())
    except Exception as exc:
        logger.exception("send_24h_reminders_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.periodic.send_2h_reminders",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def send_2h_reminders_task(self) -> None:
    try:
        asyncio.run(send_2h_reminders())
    except Exception as exc:
        logger.exception("send_2h_reminders_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.periodic.send_missed_notifications",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def send_missed_notifications_task(self) -> None:
    try:
        asyncio.run(send_missed_notifications())
    except Exception as exc:
        logger.exception("send_missed_notifications_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.periodic.generate_notification_templates",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def generate_notification_templates_task(self) -> None:
    try:
        asyncio.run(generate_notification_templates())
    except Exception as exc:
        logger.exception("generate_notification_templates_task failed: %s", exc)
        raise self.retry(exc=exc)
