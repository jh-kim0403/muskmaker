"""
Goal expiry handler — runs every 15 minutes via Celery Beat.

Marks all active goals whose expires_at (end-of-local-day in UTC)
has passed as 'expired'. This is a safety net — the API also checks
expiry on every verification submission.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import update

from app.database import CelerySessionFactory
from app.models.goal import Goal
from app.tasks.handlers.notification_handler import send_missed_notifications

logger = logging.getLogger(__name__)


async def expire_stale_goals() -> None:
    async with CelerySessionFactory() as session:
        try:
            now_utc = datetime.now(timezone.utc)
            result = await session.execute(
                update(Goal)
                .where(
                    Goal.status == "active",
                    Goal.expires_at < now_utc,
                )
                .values(status="expired")
                .returning(Goal.id)
            )
            expired_ids = result.fetchall()
            count = len(expired_ids)
            await session.commit()
            if count:
                logger.info("[goal_expiry] Expired %d goals", count)
        except Exception as exc:
            await session.rollback()
            logger.exception("[goal_expiry] Error expiring goals: %s", exc)
            return

    await send_missed_notifications()
