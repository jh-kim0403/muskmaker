"""
GoalService — goal creation, availability checks, and expiry.

Enforces:
  - One goal per type per local calendar day (backed by DB UNIQUE constraint)
  - local_goal_date and expires_at computed server-side from user's stored timezone
  - timezone_at_creation frozen at insert
"""
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.goal import Goal, GoalType
from app.models.user import User
from app.services.timezone_service import TimezoneService

logger = logging.getLogger(__name__)


class GoalService:

    @staticmethod
    async def get_active_goal_types(db: AsyncSession) -> list[GoalType]:
        result = await db.execute(
            select(GoalType)
            .where(GoalType.is_active == True)  # noqa: E712
            .order_by(GoalType.display_order)
        )
        return result.scalars().all()

    @staticmethod
    async def get_todays_goals(
        db: AsyncSession, user: User
    ) -> list[Goal]:
        """
        Returns all goals the user has created today (in their stored timezone),
        across all statuses. Used by the UI to display today's goal list.
        """
        now_utc = datetime.now(timezone.utc)
        local_today = TimezoneService.user_local_date(now_utc, user.timezone)

        result = await db.execute(
            select(Goal)
            .options(selectinload(Goal.goal_type))
            .where(
                Goal.user_id == user.id,
                Goal.local_goal_date == local_today,
            )
        )
        return result.scalars().all()

    @staticmethod
    async def create_goal(
        db: AsyncSession,
        user: User,
        goal_type_id: UUID,
        expire_user_local_date: date,
        notes: str | None = None,
        title: str | None = None,
    ) -> Goal:
        """
        Create a new goal for the user.

        Server-side:
          - Recomputes local_goal_date from NOW() + user.timezone
          - Sets timezone_at_creation = user.timezone (frozen)
          - Sets expires_at = end-of-local-day in UTC

        The DB UNIQUE constraint on (user_id, goal_type_id, local_goal_date)
        is the last line of defense and will raise IntegrityError if the
        application-layer check is somehow bypassed.
        """
        # Verify goal type exists and is active
        gt_result = await db.execute(
            select(GoalType).where(GoalType.id == goal_type_id, GoalType.is_active == True)  # noqa: E712
        )
        goal_type = gt_result.scalar_one_or_none()
        if goal_type is None:
            raise HTTPException(status_code=404, detail="Goal type not found or inactive")

        expires_at = TimezoneService.local_day_end_utc(expire_user_local_date, user.timezone)

        # Application-layer duplicate check (gives a clean error before hitting the constraint)
        existing = await db.execute(
            select(Goal).where(
                Goal.user_id == user.id,
                Goal.goal_type_id == goal_type_id,
                Goal.local_goal_date == expire_user_local_date,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"You have already created a '{goal_type.name}' goal for day {expire_user_local_date}",
            )

        goal = Goal(
            user_id=user.id,
            goal_type_id=goal_type_id,
            title=title or goal_type.name,
            local_goal_date=expire_user_local_date,
            timezone_at_creation=user.timezone,  # frozen at creation
            expires_at=expires_at,
        )
        db.add(goal)

        try:
            await db.flush()  # surface IntegrityError before commit
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"You have already created a '{goal_type.name}' goal for day {expire_user_local_date}",
            )

        # Reload with relationship for response
        await db.refresh(goal, ["goal_type"])
        return goal

    @staticmethod
    async def get_user_goal(db: AsyncSession, user: User, goal_id: UUID) -> Goal:
        result = await db.execute(
            select(Goal)
            .options(selectinload(Goal.goal_type), selectinload(Goal.verification))
            .where(Goal.id == goal_id, Goal.user_id == user.id)
        )
        goal = result.scalar_one_or_none()
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")
        return goal

