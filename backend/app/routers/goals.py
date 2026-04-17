from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.goal import CreateGoalRequest, GoalResponse, GoalTypeResponse
from app.services.goal_service import GoalService

router = APIRouter(tags=["goals"])


@router.get("/types", response_model=list[GoalTypeResponse])
async def list_goal_types(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return all active goal types with their coin rewards and metadata."""
    return await GoalService.get_active_goal_types(db)


@router.get("/today", response_model=list[GoalResponse])
async def get_todays_goals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all goals the user has created today (in their stored timezone),
    across all statuses.
    """
    return await GoalService.get_todays_goals(db, current_user)


@router.post("/new", response_model=GoalResponse, status_code=201)
async def create_goal(
    body: CreateGoalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new goal for today.

    Server enforces:
      - local_goal_date computed from user's stored timezone (not client input)
      - One goal per type per local day (409 if already exists)
      - Goal type must be active
    """
    return await GoalService.create_goal(
        db=db,
        user=current_user,
        goal_type_id=body.goal_type_id,
        title=body.title,
        expire_user_local_date=body.expire_user_local_date,
    )


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await GoalService.get_user_goal(db, current_user, goal_id)
