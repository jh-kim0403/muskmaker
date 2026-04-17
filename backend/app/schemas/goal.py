from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, field_validator


class GoalTypeResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    type: str
    icon_url: str | None
    coin_reward: int
    difficulty: str
    supports_location_path: bool

    model_config = {"from_attributes": True}


class CreateGoalRequest(BaseModel):
    goal_type_id: UUID
    title: str
    expire_user_local_date: date


class GoalResponse(BaseModel):
    id: UUID
    goal_type_id: UUID
    goal_type: GoalTypeResponse
    title: str
    status: str
    notes: str | None
    local_goal_date: date
    timezone_at_creation: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


