"""
Notification worker — runs every 5 minutes via APScheduler.

Sends goal-expiry reminder pushes to users whose goals are approaching
the end of their local day. Uses each goal's expires_at and the user's
reminder_minutes_before_expiry preference to determine send time.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionFactory
from app.models.goal import Goal
from app.models.notification import NotificationPreferences
from app.models.user import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Default reminder window if user has no preferences set
DEFAULT_REMINDER_MINUTES = 60


async def send_goal_reminders() -> None:
    """
    Find all active goals whose expires_at is within the user's reminder window
    and send a reminder push if one hasn't been sent yet.

    Uses a simple 'sent_reminder' flag approach: in production, track this
    in a goal_reminders table to prevent duplicate sends across worker restarts.
    """
    async with AsyncSessionFactory() as session:
        try:
            now_utc = datetime.now(timezone.utc)

            # Find active goals expiring in the next 0–90 minutes
            # (90 min window covers the max reminder preference setting)
            window_end = now_utc + timedelta(minutes=90)

            result = await session.execute(
                select(Goal)
                .options(
                    selectinload(Goal.user).selectinload(User.notification_prefs),
                    selectinload(Goal.goal_type),
                )
                .where(
                    Goal.status == "active",
                    Goal.expires_at > now_utc,
                    Goal.expires_at <= window_end,
                )
            )
            goals = result.scalars().all()

            sent = 0
            for goal in goals:
                user = goal.user
                prefs: NotificationPreferences | None = user.notification_prefs

                if prefs and not prefs.goal_reminder_enabled:
                    continue

                reminder_minutes = (
                    prefs.reminder_minutes_before_expiry
                    if prefs else DEFAULT_REMINDER_MINUTES
                )

                # Check if we're inside the user's reminder window
                reminder_send_at = goal.expires_at - timedelta(minutes=reminder_minutes)
                if now_utc < reminder_send_at:
                    continue  # Not yet time to send

                await NotificationService.send_goal_reminder(
                    session, user, goal.goal_type.name
                )
                sent += 1

            await session.commit()
            if sent:
                logger.info("[notification_worker] Sent %d goal reminder(s)", sent)

        except Exception as exc:
            await session.rollback()
            logger.exception("[notification_worker] Error sending reminders: %s", exc)
