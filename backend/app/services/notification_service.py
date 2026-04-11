"""
NotificationService — push notification dispatch.

Tone enforcement:
  - Free users always receive 'normal' tone regardless of their stored preference
  - Premium users receive their chosen tone: 'normal', 'friendly_banter', or 'harsh'
  - Tone selection only affects message body text — never delivery, timing, or content type
"""
import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import NotificationTone, SubscriptionTier
from app.models.notification import NotificationPreferences, PushToken
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Notification copy by tone ──────────────────────────────────────────────────
# Each entry: (title, body)

GOAL_REMINDER_COPY = {
    NotificationTone.NORMAL: (
        "Goal expiring soon",
        "Your goal expires at the end of today. Don't forget to verify it!",
    ),
    NotificationTone.FRIENDLY_BANTER: (
        "Tick tock! ⏰",
        "Hey, your goal's almost out of time. Go crush it before midnight!",
    ),
    NotificationTone.HARSH: (
        "Stop slacking.",
        "You set a goal. It expires tonight. Stop making excuses and go do it.",
    ),
}

VERIFICATION_APPROVED_COPY = {
    NotificationTone.NORMAL: (
        "Verification approved!",
        "Your goal was verified. Coins have been added to your balance.",
    ),
    NotificationTone.FRIENDLY_BANTER: (
        "You did it! 🎉",
        "Goal verified! Your coins are ready. Keep the streak going!",
    ),
    NotificationTone.HARSH: (
        "Fine. You did it.",
        "Verification approved. Coins added. Now do it again tomorrow.",
    ),
}

VERIFICATION_REJECTED_COPY = {
    NotificationTone.NORMAL: (
        "Verification not approved",
        "Your goal verification was not approved. Please review the reason and try again.",
    ),
    NotificationTone.FRIENDLY_BANTER: (
        "Oops, not this time 😬",
        "Your verification didn't make it through. Check the reason and give it another shot!",
    ),
    NotificationTone.HARSH: (
        "Rejected.",
        "Your verification was rejected. No excuses — read the reason and do better.",
    ),
}

SWEEPSTAKES_WIN_COPY = {
    NotificationTone.NORMAL: (
        "You won! 🏆",
        "Congratulations! You've won the sweepstakes. Check the app to claim your prize.",
    ),
    NotificationTone.FRIENDLY_BANTER: (
        "OH WOW YOU WON!! 🎊🎊",
        "The stars aligned! You won the sweepstakes! Open the app to claim your prize!",
    ),
    NotificationTone.HARSH: (
        "You won. Claim it.",
        "You won the sweepstakes. Prize is waiting. Don't let it expire.",
    ),
}


class NotificationService:

    @staticmethod
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

    @staticmethod
    async def send_goal_reminder(db: AsyncSession, user: User, goal_name: str) -> None:
        """Send a goal expiry reminder push to the user."""
        prefs = await NotificationService._get_prefs(db, user.id)

        if prefs and not prefs.goal_reminder_enabled:
            return
        if prefs and not prefs.push_enabled:
            return

        tone = NotificationService._resolve_tone(user, prefs)
        title, body = GOAL_REMINDER_COPY[tone]
        body = body.replace("your goal", f"your '{goal_name}' goal")

        await NotificationService._send_push(db, user.id, title, body)

    @staticmethod
    async def send_verification_approved(db: AsyncSession, user: User, coins_awarded: int) -> None:
        prefs = await NotificationService._get_prefs(db, user.id)
        if prefs and not prefs.push_enabled:
            return

        tone = NotificationService._resolve_tone(user, prefs)
        title, body = VERIFICATION_APPROVED_COPY[tone]
        body = f"{body} (+{coins_awarded} coin{'s' if coins_awarded != 1 else ''})"

        await NotificationService._send_push(db, user.id, title, body)

    @staticmethod
    async def send_verification_rejected(db: AsyncSession, user: User, reason: str | None) -> None:
        prefs = await NotificationService._get_prefs(db, user.id)
        if prefs and not prefs.push_enabled:
            return

        tone = NotificationService._resolve_tone(user, prefs)
        title, body = VERIFICATION_REJECTED_COPY[tone]

        await NotificationService._send_push(db, user.id, title, body, data={"reason": reason})

    @staticmethod
    async def send_sweepstakes_win(db: AsyncSession, user: User, prize: str) -> None:
        prefs = await NotificationService._get_prefs(db, user.id)
        if prefs and not prefs.sweep_result_enabled:
            return
        if prefs and not prefs.push_enabled:
            return

        tone = NotificationService._resolve_tone(user, prefs)
        title, body = SWEEPSTAKES_WIN_COPY[tone]

        await NotificationService._send_push(db, user.id, title, body, data={"prize": prize})

    # ── Internal dispatch ──────────────────────────────────────────────────────

    @staticmethod
    async def _get_prefs(db: AsyncSession, user_id: UUID) -> NotificationPreferences | None:
        result = await db.execute(
            select(NotificationPreferences).where(NotificationPreferences.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
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

            # Deactivate tokens that Expo reports as unregistered
            for token, result in zip(tokens, results):
                if result.get("status") == "error" and result.get("details", {}).get("error") == "DeviceNotRegistered":
                    token.is_active = False
                    logger.info("Deactivated unregistered push token for user=%s", user_id)

        except Exception as exc:
            logger.exception("Failed to send push notification to user=%s: %s", user_id, exc)
