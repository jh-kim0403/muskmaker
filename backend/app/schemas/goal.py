from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, field_validator


class GoalTypeResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    icon_url: str | None
    coin_reward: int
    difficulty: str
    supports_location_path: bool

    model_config = {"from_attributes": True}


class CreateGoalRequest(BaseModel):
    goal_type_id: UUID
    notes: str | None = None


class GoalResponse(BaseModel):
    id: UUID
    goal_type_id: UUID
    goal_type: GoalTypeResponse
    status: str
    notes: str | None
    local_goal_date: date
    timezone_at_creation: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class GoalAvailabilityResponse(BaseModel):
    """
    Returned before goal creation so the UI can show which types
    are already used today and which are still available.
    """
    goal_type_id: UUID
    slug: str
    name: str
    coin_reward: int
    already_created_today: bool
    existing_goal_id: UUID | None  # set when already_created_today is True
    existing_goal_status: str | None
