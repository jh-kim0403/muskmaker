"""
Goal expiry worker — runs every 15 minutes via APScheduler.

Marks all active goals whose expires_at (end-of-local-day in UTC)
has passed as 'expired'. This is a safety net — the API also checks
expiry on every verification submission.
"""
import logging

from app.database import AsyncSessionFactory
from app.services.goal_service import GoalService

logger = logging.getLogger(__name__)


async def expire_stale_goals() -> None:
    """APScheduler entry point."""
    async with AsyncSessionFactory() as session:
        try:
            count = await GoalService.expire_stale_goals(session)
            await session.commit()
            if count:
                logger.info("[expiry_worker] Expired %d goals", count)
        except Exception as exc:
            await session.rollback()
            logger.exception("[expiry_worker] Error expiring goals: %s", exc)
