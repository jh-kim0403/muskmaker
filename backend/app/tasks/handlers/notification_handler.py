"""
Notification handler — runs every 5 minutes via Celery Beat.

Three passes per run:
  1. goal_reminder_24h — active goals expiring in 23–25 hours, not yet notified
  2. goal_reminder_2h  — active goals expiring in 1–3 hours, not yet notified
  3. goal_missed       — goals that just expired without an approved verification

Duplicate sends are prevented by the goal_notification_log table.

Tone enforcement:
  - Free users always receive 'normal' tone regardless of their stored preference
  - Premium users receive their chosen tone: 'normal', 'friendly_banter', or 'harsh'
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from sqlalchemy import nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.constants import GoalStatus, NotificationEvent, NotificationTone
from app.database import CelerySessionFactory
from app.models.goal import Goal
from app.models.notification import GoalNotificationLog, NotificationPreferences, NotificationTemplate, PushToken
from app.models.user import User
from app.models.verification import Verification

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Notification dispatch functions ────────────────────────────────────────────

def _resolve_tone(user: User, prefs: NotificationPreferences | None) -> str:
    """
    Returns the effective tone for a notification.
    Free users ALWAYS get 'normal' regardless of their stored preference.
    This is the single enforcement point — no other code should check tier for tone.
    """
    if not user.is_premium:
        return NotificationTone.NORMAL
    if prefs is None:
        return NotificationTone.NORMAL
    return prefs.notification_tone


async def _get_prefs(db: AsyncSession, user_id: UUID) -> NotificationPreferences | None:
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _get_template(
    db: AsyncSession,
    event_type: str,
    tone: str,
    goal_type_id: UUID | None = None,
) -> NotificationTemplate | None:
    """
    Fetch a template for the given event+tone. When goal_type_id is provided,
    a goal-type-specific template is preferred over a generic one (goal_type_id IS NULL).
    Falls back to generic if no specific template exists.
    """
    result = await db.execute(
        select(NotificationTemplate)
        .where(
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.tone == tone,
            (NotificationTemplate.goal_type_id == goal_type_id)
            | NotificationTemplate.goal_type_id.is_(None),
        )
        .order_by(nulls_last(NotificationTemplate.goal_type_id))
        .order_by(NotificationTemplate.created_at.desc())
        .limit(1)
    )
    template = result.scalar_one_or_none()
    if template is None:
        logger.warning("Missing notification template: event=%s tone=%s goal_type=%s", event_type, tone, goal_type_id)
    return template


async def _log(db: AsyncSession, goal_id: UUID, event_type: str) -> None:
    """Insert a GoalNotificationLog row to prevent duplicate sends."""
    db.add(GoalNotificationLog(goal_id=goal_id, event_type=event_type))


async def _send_push(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    """
    Fetch active push tokens for the user and send via Expo Push API.
    Marks tokens inactive if Expo returns DeviceNotRegistered.
    """
    tokens_result = await db.execute(
        select(PushToken).where(
            PushToken.user_id == user_id,
            PushToken.is_active == True,  # noqa: E712
        )
    )
    tokens = tokens_result.scalars().all()

    if not tokens:
        return

    messages = [
        {
            "to": token.expo_push_token,
            "title": title,
            "body": body,
            "data": data or {},
            "sound": "default",
        }
        for token in tokens
    ]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.expo_push_url,
                json=messages,
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )
            response.raise_for_status()
            results = response.json().get("data", [])

        for token, result in zip(tokens, results):
            if result.get("status") == "error" and result.get("details", {}).get("error") == "DeviceNotRegistered":
                token.is_active = False
                logger.info("Deactivated unregistered push token for user=%s", user_id)

    except Exception as exc:
        logger.exception("Failed to send push notification to user=%s: %s", user_id, exc)


# ── Per-event send functions ───────────────────────────────────────────────────

async def send_goal_reminder_24h(db: AsyncSession, user: User, goal_id: UUID, goal_name: str) -> None:
    prefs = await _get_prefs(db, user.id)
    if prefs and not prefs.goal_reminder_enabled:
        return
    if prefs and not prefs.push_enabled:
        return

    tone = _resolve_tone(user, prefs)
    template = await _get_template(db, NotificationEvent.GOAL_REMINDER_24H, tone)
    if template is None:
        return

    body = template.body.replace("{goal_name}", goal_name)
    await _send_push(db, user.id, template.title, body)
    await _log(db, goal_id, NotificationEvent.GOAL_REMINDER_24H)


async def send_goal_reminder_2h(db: AsyncSession, user: User, goal_id: UUID, goal_name: str) -> None:
    prefs = await _get_prefs(db, user.id)
    if prefs and not prefs.goal_reminder_enabled:
        return
    if prefs and not prefs.push_enabled:
        return

    tone = _resolve_tone(user, prefs)
    template = await _get_template(db, NotificationEvent.GOAL_REMINDER_2H, tone)
    if template is None:
        return

    body = template.body.replace("{goal_name}", goal_name)
    await _send_push(db, user.id, template.title, body)
    await _log(db, goal_id, NotificationEvent.GOAL_REMINDER_2H)


async def send_goal_missed(
    db: AsyncSession, user: User, goal_id: UUID, goal_name: str, goal_type_id: UUID | None = None
) -> None:
    prefs = await _get_prefs(db, user.id)
    if prefs and not prefs.goal_reminder_enabled:
        return
    if prefs and not prefs.push_enabled:
        return

    tone = _resolve_tone(user, prefs)
    template = await _get_template(db, NotificationEvent.GOAL_MISSED, tone, goal_type_id)
    if template is None:
        return

    body = template.body.replace("{goal_name}", goal_name)
    await _send_push(db, user.id, template.title, body)
    await _log(db, goal_id, NotificationEvent.GOAL_MISSED)


async def send_sweep_results(db: AsyncSession, user: User) -> None:
    prefs = await _get_prefs(db, user.id)
    if prefs and not prefs.sweep_result_enabled:
        return
    if prefs and not prefs.push_enabled:
        return

    tone = _resolve_tone(user, prefs)
    template = await _get_template(db, NotificationEvent.SWEEP_RESULTS, tone)
    if template is None:
        return

    await _send_push(db, user.id, template.title, template.body)


# ── Celery Beat orchestrators (one per notification type) ─────────────────────

async def send_24h_reminders() -> None:
    async with CelerySessionFactory() as session:
        try:
            now_utc = datetime.now(timezone.utc)
            window_start = now_utc + timedelta(hours=23)
            window_end   = now_utc + timedelta(hours=25)

            already_sent = select(GoalNotificationLog.goal_id).where(
                GoalNotificationLog.event_type == NotificationEvent.GOAL_REMINDER_24H
            )
            result = await session.execute(
                select(Goal)
                .options(
                    selectinload(Goal.user).selectinload(User.notification_prefs),
                    selectinload(Goal.goal_type),
                )
                .where(
                    Goal.status == GoalStatus.ACTIVE,
                    Goal.expires_at > window_start,
                    Goal.expires_at <= window_end,
                    Goal.id.not_in(already_sent),
                )
            )
            sent = 0
            for goal in result.scalars().all():
                await send_goal_reminder_24h(session, goal.user, goal.id, goal.goal_type.name)
                sent += 1

            await session.commit()
            if sent:
                logger.info("[notification:24h] Sent %d notification(s)", sent)

        except Exception as exc:
            await session.rollback()
            logger.exception("[notification:24h] Error: %s", exc)


async def send_2h_reminders() -> None:
    async with CelerySessionFactory() as session:
        try:
            now_utc = datetime.now(timezone.utc)
            window_start = now_utc + timedelta(hours=1)
            window_end   = now_utc + timedelta(hours=3)

            already_sent = select(GoalNotificationLog.goal_id).where(
                GoalNotificationLog.event_type == NotificationEvent.GOAL_REMINDER_2H
            )
            result = await session.execute(
                select(Goal)
                .options(
                    selectinload(Goal.user).selectinload(User.notification_prefs),
                    selectinload(Goal.goal_type),
                )
                .where(
                    Goal.status == GoalStatus.ACTIVE,
                    Goal.expires_at > window_start,
                    Goal.expires_at <= window_end,
                    Goal.id.not_in(already_sent),
                )
            )
            sent = 0
            for goal in result.scalars().all():
                await send_goal_reminder_2h(session, goal.user, goal.id, goal.goal_type.name)
                sent += 1

            await session.commit()
            if sent:
                logger.info("[notification:2h] Sent %d notification(s)", sent)

        except Exception as exc:
            await session.rollback()
            logger.exception("[notification:2h] Error: %s", exc)


async def send_missed_notifications() -> None:
    async with CelerySessionFactory() as session:
        try:
            now_utc = datetime.now(timezone.utc)
            missed_window = now_utc - timedelta(minutes=10)

            already_sent = select(GoalNotificationLog.goal_id).where(
                GoalNotificationLog.event_type == NotificationEvent.GOAL_MISSED
            )
            approved_verifications = select(Verification.goal_id).where(
                Verification.status == "approved"
            )
            result = await session.execute(
                select(Goal)
                .options(
                    selectinload(Goal.user).selectinload(User.notification_prefs),
                    selectinload(Goal.goal_type),
                )
                .where(
                    Goal.status == GoalStatus.EXPIRED,
                    Goal.expires_at > missed_window,
                    Goal.id.not_in(already_sent),
                    Goal.id.not_in(approved_verifications),
                )
            )
            sent = 0
            for goal in result.scalars().all():
                await send_goal_missed(session, goal.user, goal.id, goal.goal_type.name, goal.goal_type_id)
                sent += 1

            await session.commit()
            if sent:
                logger.info("[notification:missed] Sent %d notification(s)", sent)

        except Exception as exc:
            await session.rollback()
            logger.exception("[notification:missed] Error: %s", exc)
