from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TzChangeSource
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationPreferencesResponse,
    RegisterPushTokenRequest,
    UpdateNotificationPreferencesRequest,
)
from app.schemas.user import UpdateProfileRequest, UpdateTimezoneRequest, UserResponse
from app.services.timezone_service import TimezoneService

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.email is not None:
        current_user.email = str(body.email)
    return current_user


@router.patch("/me/timezone", response_model=UserResponse)
async def update_timezone(
    body: UpdateTimezoneRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the user's stored IANA timezone.
    Rate-limited to 1 change per 24-hour window.
    Timezone changes are never retroactive — existing goals keep their original dates.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")

    await TimezoneService.update_user_timezone(
        db=db,
        user=current_user,
        new_timezone=body.timezone,
        ip_address=ip,
        user_agent=ua,
        source=TzChangeSource.SETTINGS,
    )
    return current_user


@router.post("/me/push-token", status_code=204)
async def register_push_token(
    body: RegisterPushTokenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register or refresh an Expo push token for this device."""
    from sqlalchemy import select
    from app.models.notification import PushToken

    result = await db.execute(
        select(PushToken).where(PushToken.expo_push_token == body.expo_push_token)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.user_id = current_user.id  # re-associate if device switched accounts
        existing.is_active = True
    else:
        db.add(PushToken(
            user_id=current_user.id,
            expo_push_token=body.expo_push_token,
            platform=body.platform,
        ))


@router.get("/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from app.models.notification import NotificationPreferences

    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        # Auto-create with defaults on first access
        prefs = NotificationPreferences(user_id=current_user.id)
        db.add(prefs)
        await db.flush()

    return prefs


@router.patch("/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    body: UpdateNotificationPreferencesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update notification preferences. Tone changes to 'friendly_banter' or 'harsh'
    are stored but only applied at send time for premium users.
    """
    from sqlalchemy import select
    from app.models.notification import NotificationPreferences

    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        prefs = NotificationPreferences(user_id=current_user.id)
        db.add(prefs)
        await db.flush()

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(prefs, field, value)

    return prefs
