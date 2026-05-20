"""
NotificationService — push notifications triggered by admin actions.

These are transactional notifications (verification results, sweep wins) with
dynamic content, so they compose messages inline rather than using DB templates.

Push dispatch and preference fetching are shared with notification_handler.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.tasks.handlers.notification_handler import _get_prefs, _send_push

logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    async def send_verification_approved(db: AsyncSession, user: User, coins_awarded: int) -> None:
        prefs = await _get_prefs(db, user.id)
        if prefs and not prefs.push_enabled:
            return

        await _send_push(
            db,
            user.id,
            title="Verification Approved ✓",
            body=f"Your goal was verified! You earned {coins_awarded} coin{'s' if coins_awarded != 1 else ''}.",
        )

    @staticmethod
    async def send_verification_rejected(db: AsyncSession, user: User, rejection_reason: str | None) -> None:
        prefs = await _get_prefs(db, user.id)
        if prefs and not prefs.push_enabled:
            return

        body = "Your goal verification was rejected."
        if rejection_reason:
            body = f"Verification rejected: {rejection_reason}"

        await _send_push(
            db,
            user.id,
            title="Verification Not Approved",
            body=body,
        )

    @staticmethod
    async def send_sweepstakes_win(db: AsyncSession, user: User, prize_description: str) -> None:
        prefs = await _get_prefs(db, user.id)
        if prefs and not prefs.push_enabled:
            return
        if prefs and not prefs.sweep_result_enabled:
            return

        await _send_push(
            db,
            user.id,
            title="You Won!",
            body=f"Congratulations! You won: {prize_description}",
        )
