"""
GoalService — goal creation, availability checks, and expiry.

Enforces:
  - One goal per type per local calendar day (backed by DB UNIQUE constraint)
  - local_goal_date and expires_at computed server-side from user's stored timezone
  - timezone_at_creation frozen at insert
"""
import logging
from datetime import datetime, timezone
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
    async def get_daily_availability(
        db: AsyncSession, user: User
    ) -> list[dict]:
        """
        Returns all active goal types annotated with whether the user has
        already created a goal of that type today (in their stored timezone).
        Used by the UI to show available vs. already-used slots for the day.
        """
        now_utc = datetime.now(timezone.utc)
        local_today = TimezoneService.user_local_date(now_utc, user.timezone)

        # Fetch all active types
        types_result = await db.execute(
            select(GoalType)
            .where(GoalType.is_active == True)  # noqa: E712
            .order_by(GoalType.display_order)
        )
        goal_types = types_result.scalars().all()

        # Fetch today's goals for this user in one query
        goals_result = await db.execute(
            select(Goal).where(
                Goal.user_id == user.id,
                Goal.local_goal_date == local_today,
            )
        )
        todays_goals = {g.goal_type_id: g for g in goals_result.scalars().all()}

        availability = []
        for gt in goal_types:
            existing = todays_goals.get(gt.id)
            availability.append({
                "goal_type_id": gt.id,
                "slug": gt.slug,
                "name": gt.name,
                "coin_reward": gt.coin_reward,
                "already_created_today": existing is not None,
                "existing_goal_id": existing.id if existing else None,
                "existing_goal_status": existing.status if existing else None,
            })
        return availability

    @staticmethod
    async def create_goal(
        db: AsyncSession,
        user: User,
        goal_type_id: UUID,
        notes: str | None,
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

        now_utc = datetime.now(timezone.utc)
        local_today = TimezoneService.user_local_date(now_utc, user.timezone)
        expires_at = TimezoneService.local_day_end_utc(local_today, user.timezone)

        # Application-layer duplicate check (gives a clean error before hitting the constraint)
        existing = await db.execute(
            select(Goal).where(
                Goal.user_id == user.id,
                Goal.goal_type_id == goal_type_id,
                Goal.local_goal_date == local_today,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"You have already created a '{goal_type.name}' goal today",
            )

        goal = Goal(
            user_id=user.id,
            goal_type_id=goal_type_id,
            notes=notes,
            local_goal_date=local_today,
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
                detail=f"You have already created a '{goal_type.name}' goal today",
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

    @staticmethod
    async def expire_stale_goals(db: AsyncSession) -> int:
        """
        Called by the background worker every 15 minutes.
        Marks as 'expired' any active goal whose expires_at has passed.
        Returns the count of goals expired.
        """
        from sqlalchemy import update
        now_utc = datetime.now(timezone.utc)
        result = await db.execute(
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
        if count:
            logger.info("Expired %d stale goals", count)
        return count
