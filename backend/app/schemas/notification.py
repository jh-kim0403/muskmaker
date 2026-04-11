from uuid import UUID
from pydantic import BaseModel


class NotificationPreferencesResponse(BaseModel):
    id: UUID
    push_enabled: bool
    email_enabled: bool
    goal_reminder_enabled: bool
    reminder_minutes_before_expiry: int
    notification_tone: str      # 'normal' | 'friendly_banter' | 'harsh'
    sweep_result_enabled: bool
    new_sweep_enabled: bool

    model_config = {"from_attributes": True}


class UpdateNotificationPreferencesRequest(BaseModel):
    push_enabled: bool | None = None
    email_enabled: bool | None = None
    goal_reminder_enabled: bool | None = None
    reminder_minutes_before_expiry: int | None = None
    # 'friendly_banter' and 'harsh' are accepted here but silently
    # downgraded to 'normal' at send time for free users.
    notification_tone: str | None = None
    sweep_result_enabled: bool | None = None
    new_sweep_enabled: bool | None = None


class RegisterPushTokenRequest(BaseModel):
    expo_push_token: str
    platform: str               # 'ios' | 'android'
