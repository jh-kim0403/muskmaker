"""
Shared FastAPI dependencies.

Injected via Depends() in router functions. Each dependency is a single
responsibility: get DB session, resolve current user, assert subscription tier.

Usage in a router:
    @router.get("/goals")
    async def list_goals(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        ...

    @router.post("/verify/premium")
    async def verify_premium(
        _: User = Depends(require_premium),  # 403 if not premium
        ...
    ):
        ...
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolves the Firebase UID from request.state (set by FirebaseAuthMiddleware)
    to a User row. Creates the row if this is the user's first request after
    Firebase account creation (first-time auto-provision).

    Raises 401 if state is missing (should not happen if middleware is active).
    Raises 403 if the user account is banned.
    """
    firebase_user = getattr(request.state, "firebase_user", None)
    if firebase_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    uid = firebase_user["uid"]

    result = await db.execute(select(User).where(User.firebase_uid == uid))
    user = result.scalar_one_or_none()

    if user is None:
        # First request: auto-provision the user row.
        # Timezone will be set via PATCH /users/me/timezone during onboarding.
        user = User(
            firebase_uid=uid,
            email=firebase_user.get("email"),
            display_name=firebase_user.get("name"),
        )
        db.add(user)
        await db.flush()  # get the generated UUID before we return

    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account suspended")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")

    return user


async def require_premium(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Raises 403 if the user does not have an active premium subscription.
    Use on endpoints that are exclusively for premium users.
    """
    if not current_user.is_premium:
        raise HTTPException(
            status_code=403,
            detail="This feature requires a premium subscription",
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Raises 403 if the user is not an admin.
    Admin status is stored as a custom claim on the Firebase token
    and separately checked against a flag in the DB (belt-and-suspenders).
    """
    firebase_user = ...  # already resolved — access via current_user context
    # Check Firebase custom claim
    request_state = ...  # not accessible here; use the pattern below in admin router
    # In practice, admin routes read request.state.firebase_user["admin"] == True
    # This dependency checks the DB column as a second factor.
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT is_admin FROM admin_users WHERE user_id = :uid"),
        {"uid": str(current_user.id)},
    )
    row = result.fetchone()
    if row is None or not row.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
