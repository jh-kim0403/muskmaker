"""
AIService — premium AI verification.

Combines three signals to produce a pass/fail/uncertain verdict:
  1. EXIF timestamp vs server receipt time (delta check)
  2. Photo content analysis (does the image plausibly show the stated goal?)
  3. GPS location plausibility (premium_ai_location path only)

This implementation uses OpenAI Vision API as the AI backend.
Swap the _call_openai_vision() method to use a different provider (Gemini,
Rekognition, etc.) without changing any calling code.
"""
import logging
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.config import get_settings
from app.constants import AIVerdict

logger = logging.getLogger(__name__)
settings = get_settings()

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


class AIService:

    @staticmethod
    async def run_verification(
        goal_type_name: str,
        goal_type_maps_query_word: str,
        photo_urls: list[str],            # pre-signed S3 URLs, ordered by photo_index
        exif_captured_at: datetime | None,
        server_receipt_at: datetime,
        location_lat: float | None = None,
        location_lng: float | None = None,
    ) -> dict:
        """
        Run the full AI verification pipeline for a premium submission.

        Returns:
            {
                "verdict":          "pass" | "fail" | "uncertain",
                "confidence_score": 0.0–1.0,
                "timestamp_check":  "pass" | "warn" | "fail",
                "content_check":    "pass" | "fail" | "uncertain",
                "location_check":   "pass" | "fail" | "skipped",
                "delta_seconds":    int | None,
                "ai_raw_response":  dict,   # full OpenAI response for audit
            }
        """
        result = {
            "verdict": AIVerdict.UNCERTAIN,
            "confidence_score": 0.0,
            "timestamp_check": "skipped",
            "content_check": "uncertain",
            "location_check": "skipped",
            "delta_seconds": None,
            "ai_raw_response": {},
        }

        # ── Signal 1: Timestamp delta check ──────────────────────────────────
        ts_check, delta_seconds = AIService._check_timestamp(exif_captured_at, server_receipt_at)
        result["timestamp_check"] = ts_check
        result["delta_seconds"] = delta_seconds

        if ts_check == "fail":
            result["verdict"] = AIVerdict.FAIL
            result["confidence_score"] = 0.0
            return result

        # ── Signal 2: Photo content analysis ─────────────────────────────────
        try:
            content_result = await AIService._call_openai_vision(
                goal_type_name=goal_type_name,
                goal_type_maps_query_word=goal_type_maps_query_word,
                photo_urls=photo_urls,
            )
            result["content_check"] = content_result["verdict"]
            result["confidence_score"] = content_result["confidence"]
            result["ai_raw_response"] = content_result["raw"]
        except Exception as exc:
            logger.exception("OpenAI Vision call failed: %s", exc)
            # On AI provider failure, route to manual review rather than auto-approve or auto-reject
            result["verdict"] = AIVerdict.UNCERTAIN
            result["content_check"] = "uncertain"
            return result

        # ── Signal 3: Location plausibility (location path only) ─────────────
        if location_lat is not None and location_lng is not None:
            loc_check = AIService._check_location_plausibility(
                goal_type_maps_query_word=goal_type_maps_query_word,
                lat=location_lat,
                lng=location_lng,
            )
            result["location_check"] = loc_check
            if loc_check == "fail":
                result["verdict"] = AIVerdict.FAIL
                result["confidence_score"] = 0.0
                return result

        # ── Final verdict ─────────────────────────────────────────────────────
        confidence = result["confidence_score"]
        content_verdict = result["content_check"]

        if content_verdict == "pass" and confidence >= settings.ai_confidence_threshold:
            result["verdict"] = AIVerdict.PASS
        elif content_verdict == "fail" or confidence < 0.3:
            result["verdict"] = AIVerdict.FAIL
        else:
            # Uncertain: route to manual review regardless of path
            result["verdict"] = AIVerdict.UNCERTAIN

        return result

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _check_timestamp(
        exif_captured_at: datetime | None,
        server_receipt_at: datetime,
    ) -> tuple[str, int | None]:
        """
        Returns ("pass"|"warn"|"fail", delta_seconds).
        No EXIF → warn (not hard fail — some devices strip EXIF).
        """
        if exif_captured_at is None:
            return "warn", None

        delta = abs(int((server_receipt_at - exif_captured_at).total_seconds()))

        if delta > settings.exif_delta_fail_seconds:
            return "fail", delta
        if delta > settings.exif_delta_premium_warn_seconds:
            return "warn", delta
        return "pass", delta

    @staticmethod
    async def _call_openai_vision(
        goal_type_name: str,
        goal_type_maps_query_word: str,
        photo_urls: list[str],
    ) -> dict:
        """
        Sends photos to OpenAI Vision with a structured prompt.
        Returns {"verdict": "pass"|"fail"|"uncertain", "confidence": float, "raw": dict}.
        """
        image_content = [
            {"type": "image_url", "image_url": {"url": url, "detail": "low"}}
            for url in photo_urls
        ]

        prompt = (
            f"You are a verification assistant for an accountability app. "
            f"The user claims they completed this goal: '{goal_type_name}'. "
            f"Analyze the provided photo(s) and determine if they plausibly show "
            f"evidence of completing this goal.\n\n"
            f"Respond ONLY with valid JSON in this exact format:\n"
            f'{{"verdict": "pass"|"fail"|"uncertain", "confidence": 0.0-1.0, "reason": "brief explanation"}}\n\n'
            f"Guidelines:\n"
            f"- 'pass': clear visual evidence of the goal activity\n"
            f"- 'fail': photo clearly does not show the goal activity\n"
            f"- 'uncertain': ambiguous — cannot confidently determine either way\n"
            f"- Be strict but fair. Benefit of the doubt for 'uncertain'."
        )

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

        import json
        raw_content = response.choices[0].message.content
        parsed = json.loads(raw_content)

        return {
            "verdict": parsed.get("verdict", "uncertain"),
            "confidence": float(parsed.get("confidence", 0.5)),
            "raw": {"model": settings.openai_model, "response": parsed, "usage": response.usage.model_dump()},
        }

    @staticmethod
    def _check_location_plausibility(
        goal_type_maps_query_word: str,
        lat: float,
        lng: float,
    ) -> str:
        """
        Placeholder for GPS plausibility check.
        In production: cross-check coords against known venue types using a
        Places API (e.g. Google Places) to verify gym coords look like a gym,
        or simply verify coords are not (0,0) / obviously spoofed.
        """
        # Basic sanity: (0, 0) is almost certainly a GPS error / spoof
        if abs(lat) < 0.001 and abs(lng) < 0.001:
            return "fail"
        # Coordinates out of valid range
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return "fail"
        return "pass"
