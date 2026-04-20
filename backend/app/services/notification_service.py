"""
NotificationService — placeholder stubs for admin router.

The actual notification dispatch logic lives in app.tasks.handlers.notification_handler.
These methods will be recreated when the admin notification flow is rebuilt.
"""
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    async def send_verification_approved(db: AsyncSession, user: User, coins_awarded: int) -> None:
        # TODO: recreate
        pass

    @staticmethod
    async def send_verification_rejected(db: AsyncSession, user: User, rejection_reason: str) -> None:
        # TODO: recreate
        pass

    @staticmethod
    async def send_sweepstakes_win(db: AsyncSession, user: User, prize_description: str) -> None:
        # TODO: recreate
        pass
