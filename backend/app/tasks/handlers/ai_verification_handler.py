import json
import logging
import math
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.constants import AIVerdict, GoalStatus, VerificationPath, VerificationStatus
from app.database import CelerySessionFactory as AsyncSessionFactory
from app.models.goal import Goal
from app.models.verification import Verification
from app.services.ai_service import openai_client
from app.services.storage_service import StorageService
from app.services.verification_service import VerificationService

logger = logging.getLogger(__name__)
settings = get_settings()

# 500 feet in meters
_LOCATION_RADIUS_METERS = 152.4

_SERPER_MAPS_URL = "https://google.serper.dev/maps"


async def openai_verify_photo(verification_id: str) -> None:
    async with AsyncSessionFactory() as session:
        # ── 1. Load verification + photos + goal + goal_type + user ──────────
        result = await session.execute(
            select(Verification)
            .options(
                selectinload(Verification.photos),
                selectinload(Verification.goal)
                    .selectinload(Goal.goal_type),
                selectinload(Verification.goal)
                    .selectinload(Goal.user),
            )
            .where(Verification.id == verification_id)
        )
        verification = result.scalar_one_or_none()
        if verification is None:
            logger.error("Verification %s not found", verification_id)
            return

        goal = verification.goal
        goal_type = goal.goal_type
        user = goal.user

        # ── 2. Pick prompt based on verification path ─────────────────────────
        if verification.verification_path == VerificationPath.PREMIUM_AI_LOCATION:
            prompt = goal_type.ai_prompt_location
        else:
            prompt = goal_type.ai_prompt_standard

        # ── 3. Generate fresh download URLs for each photo ───────────────────
        photos = sorted(verification.photos, key=lambda p: p.photo_index)
        photo_urls = [StorageService.get_photo_url(p.s3_key) for p in photos]

        # ── 4. Call OpenAI Vision ─────────────────────────────────────────────
        image_content = [
            {"type": "image_url", "image_url": {"url": url, "detail": "low"}}
            for url in photo_urls
        ]

        response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}, *image_content],
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
        )

        parsed = json.loads(response.choices[0].message.content)
        verdict = parsed.get("verdict", AIVerdict.UNCERTAIN)
        confidence = float(parsed.get("confidence", 0.5))

        # ── 5. Store AI result on verification ───────────────────────────────
        now_utc = datetime.now(timezone.utc)
        verification.ai_verdict = verdict
        verification.ai_confidence_score = confidence
        verification.ai_processed_at = now_utc
        verification.ai_result_payload = {
            "model": settings.openai_model,
            "response": parsed,
            "usage": response.usage.model_dump(),
        }

        # ── 6. Update status based on verdict ────────────────────────────────
        if verdict == AIVerdict.PASS and confidence >= settings.ai_confidence_threshold:
            await VerificationService._approve_verification(
                session, user, verification, goal, goal_type.coin_reward
            )
        elif verdict == AIVerdict.FAIL or confidence < 0.3:
            verification.status = VerificationStatus.REJECTED
            verification.rejection_reason = "Automated review: photo does not show the stated goal"
            goal.status = GoalStatus.REJECTED
        else:
            await VerificationService._route_to_manual_review(session, verification, priority=3)

        await session.commit()


async def run_location(verification_id: str) -> None:
    async with AsyncSessionFactory() as session:
        # ── 1. Load verification + photo + goal + goal_type ───────────────────
        result = await session.execute(
            select(Verification)
            .options(
                selectinload(Verification.photos),
                selectinload(Verification.goal)
                    .selectinload(Goal.goal_type),
                selectinload(Verification.goal)
                    .selectinload(Goal.user),
            )
            .where(Verification.id == verification_id)
        )
        verification = result.scalar_one_or_none()
        if verification is None:
            logger.error("Verification %s not found", verification_id)
            return

        goal = verification.goal
        goal_type = goal.goal_type

        # ── 2. Use submitted GPS coordinates ─────────────────────────────────────
        lat = verification.location_lat
        lng = verification.location_lng

        if lat is None or lng is None:
            logger.error(
                "No location data for verification %s — location check cannot run",
                verification_id,
            )
            return

        # ── 3. Search Serper Maps for goal type near photo location ───────────
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _SERPER_MAPS_URL,
                headers={
                    "X-API-KEY": settings.serper_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "q": goal_type.maps_query_word,
                    "ll": f"@{lat},{lng},19z",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            places = response.json().get("places", [])

        # ── 4. Check if any place is within 500ft ─────────────────────────────
        nearby = any(
            _haversine_meters(float(lat), float(lng), p["latitude"], p["longitude"])
            <= _LOCATION_RADIUS_METERS
            for p in places
            if p.get("latitude") and p.get("longitude")
        )

        if not nearby:
            logger.warning(
                "No %s found within 500ft for verification %s",
                goal_type.maps_query_word, verification_id,
            )
            verification.status = VerificationStatus.REJECTED
            verification.rejection_reason = (
                f"No {goal_type.name} found within 500ft of your photo location"
            )
            goal.status = GoalStatus.REJECTED
            await session.commit()
            return

    # ── 5. Location passed — proceed to OpenAI photo verification ────────────
    await openai_verify_photo(verification_id)


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the distance in meters between two GPS coordinates."""
    r = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
