from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator
import pytz


class UserResponse(BaseModel):
    id: UUID
    firebase_uid: str
    email: str | None
    display_name: str | None
    timezone: str
    subscription_tier: str
    subscription_expires_at: datetime | None
    has_completed_onboarding: bool
    onboarding_completed_at: datetime | None
    coin_balance: int
    is_premium: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateTimezoneRequest(BaseModel):
    timezone: str

    @field_validator("timezone")
    @classmethod
    def validate_iana_timezone(cls, v: str) -> str:
        if v not in pytz.all_timezones_set:
            raise ValueError(f"'{v}' is not a valid IANA timezone")
        return v


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
