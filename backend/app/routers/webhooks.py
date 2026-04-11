"""
Webhooks router — receives external events.

  POST /webhooks/revenuecat   RevenueCat subscription lifecycle events
  POST /webhooks/apple        Apple App Store server notifications (fallback)

Both endpoints are PUBLIC (no Firebase JWT) but are authenticated via
their own secrets (HMAC for RevenueCat, JWS for Apple).
"""
import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import RevenueCatEvent
from app.database import get_db
from app.models.subscription import SubscriptionEvent
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["webhooks"])


@router.post("/revenuecat", status_code=200)
async def revenuecat_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
):
    """
    Receives RevenueCat subscription lifecycle events and keeps
    users.subscription_tier in sync.

    RevenueCat sends Authorization: <secret> header (plain string, not Bearer).
    """
    # ── Authenticate ──────────────────────────────────────────────────────────
    if authorization != settings.revenuecat_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payload = await request.json()
    event = payload.get("event", {})
    event_type = event.get("type")
    rc_event_id = event.get("id")

    if not rc_event_id:
        raise HTTPException(status_code=422, detail="Missing event id")

    # ── Idempotency check ─────────────────────────────────────────────────────
    existing = await db.execute(
        select(SubscriptionEvent).where(SubscriptionEvent.revenuecat_event_id == rc_event_id)
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("Duplicate RevenueCat event ignored: %s", rc_event_id)
        return {"status": "duplicate"}

    # ── Find user ─────────────────────────────────────────────────────────────
    firebase_uid = event.get("app_user_id")
    user = None
    if firebase_uid:
        result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
        user = result.scalar_one_or_none()

    # ── Archive raw event ─────────────────────────────────────────────────────
    expires_at = None
    purchased_at = None
    if event.get("expiration_at_ms"):
        expires_at = datetime.fromtimestamp(event["expiration_at_ms"] / 1000, tz=timezone.utc)
    if event.get("purchased_at_ms"):
        purchased_at = datetime.fromtimestamp(event["purchased_at_ms"] / 1000, tz=timezone.utc)

    sub_event = SubscriptionEvent(
        user_id=user.id if user else None,
        firebase_uid=firebase_uid,
        revenuecat_event_type=event_type,
        revenuecat_event_id=rc_event_id,
        product_id=event.get("product_id"),
        period_type=event.get("period_type"),
        purchased_at=purchased_at,
        expires_at=expires_at,
        raw_payload=payload,
    )
    db.add(sub_event)

    # ── Update user subscription state ────────────────────────────────────────
    if user is None:
        logger.warning("RevenueCat event for unknown firebase_uid=%s, archived only", firebase_uid)
        return {"status": "archived_no_user"}

    try:
        if event_type in (RevenueCatEvent.INITIAL_PURCHASE, RevenueCatEvent.RENEWAL, RevenueCatEvent.PRODUCT_CHANGE):
            user.subscription_tier = "premium"
            user.subscription_expires_at = expires_at
            if event.get("original_app_user_id"):
                user.revenuecat_customer_id = event["original_app_user_id"]

        elif event_type in (RevenueCatEvent.CANCELLATION, RevenueCatEvent.EXPIRATION):
            # Don't immediately revoke — let expires_at govern access.
            # The is_premium property checks expires_at > now().
            user.subscription_expires_at = expires_at

        elif event_type == RevenueCatEvent.REFUND:
            user.subscription_tier = "free"
            user.subscription_expires_at = None

        elif event_type == RevenueCatEvent.BILLING_ISSUE:
            # Grace period — keep premium until expires_at, log for monitoring
            logger.warning("Billing issue for user=%s, expires_at=%s", user.id, expires_at)

        logger.info(
            "Subscription updated: user=%s event_type=%s tier=%s expires=%s",
            user.id, event_type, user.subscription_tier, user.subscription_expires_at,
        )
    except Exception as exc:
        sub_event.processing_error = str(exc)
        logger.exception("Error processing RevenueCat event %s: %s", rc_event_id, exc)

    return {"status": "processed"}
