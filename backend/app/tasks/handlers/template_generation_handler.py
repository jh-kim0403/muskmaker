"""
Template generation handler — runs daily at 00:05 UTC via Celery Beat.

For every active GoalType × every notification tone, generates one new
goal_missed notification template using OpenAI, ensuring it is not a
duplicate of the 30 most recent templates for that (goal_type, tone) slot.

Failures are isolated per (goal_type, tone) combination so one bad OpenAI
response never prevents the other combinations from being generated.
"""
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import NotificationEvent, NotificationTone
from app.database import CelerySessionFactory
from app.models.goal import GoalType
from app.models.notification import NotificationTemplate
from app.services.ai_service import openai_client

logger = logging.getLogger(__name__)
settings = get_settings()

_TONES = [NotificationTone.NORMAL, NotificationTone.FRIENDLY_BANTER, NotificationTone.HARSH]

_TONE_DESCRIPTIONS = {
    NotificationTone.NORMAL: (
        "Neutral, direct, and factual. No jokes, no emojis, no profanity. "
        "Acknowledge the missed goal plainly and encourage the user to try again tomorrow."
    ),
    NotificationTone.FRIENDLY_BANTER: (
        "Funny and light-hearted teasing, like a close friend giving you a hard time. "
        "Emojis are welcome. Playful and warm — never mean-spirited. "
        "Think: the friend who ribs you but is always rooting for you."
    ),
    NotificationTone.HARSH: (
        "Brutal, blunt, friend-style roasting. No-holds-barred accountability. "
        "Strong language is acceptable. Think: the drill-sergeant friend who genuinely "
        "wants you to succeed but has zero tolerance for excuses."
    ),
}


async def _fetch_recent_templates(
    db: AsyncSession, goal_type_id, tone: str, limit: int = 30
) -> list[NotificationTemplate]:
    result = await db.execute(
        select(NotificationTemplate)
        .where(
            NotificationTemplate.event_type == NotificationEvent.GOAL_MISSED,
            NotificationTemplate.goal_type_id == goal_type_id,
            NotificationTemplate.tone == tone,
        )
        .order_by(NotificationTemplate.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


def _build_messages(goal_type: GoalType, tone: str, existing: list[NotificationTemplate]) -> list[dict]:
    existing_examples = "\n".join(
        f'  - Title: "{t.title}" | Body: "{t.body}"'
        for t in existing
    ) or "  (none yet)"

    system_prompt = (
        "You are a copywriter for a mobile accountability app called MuskMaker. "
        "Your job is to write push notification copy that is sent to users who missed a goal. "
        "You must respond with valid JSON only, in exactly this format:\n"
        '{"title": "<short title, max 60 chars>", "body": "<notification body, max 150 chars>"}\n\n'
        "Rules:\n"
        "- The title must be short and punchy (ideally under 8 words)\n"
        "- The body must be original — do NOT copy or closely paraphrase any example below\n"
        "- Stay within the tone specified — do not mix tones\n"
        "- Do not use placeholder text like {goal_name}\n"
        "- Reference the specific goal type naturally in the copy\n"
        "- Output ONLY the JSON object, nothing else"
    )

    user_prompt = (
        f"Goal type: {goal_type.name}\n"
        f"Goal description: {goal_type.description or goal_type.name}\n\n"
        f"Tone: {tone}\n"
        f"Tone guidance: {_TONE_DESCRIPTIONS[tone]}\n\n"
        f"The following {len(existing)} templates already exist for this goal type + tone.\n"
        f"Your new template must NOT duplicate any of these:\n"
        f"{existing_examples}\n\n"
        f"Write one new push notification (title + body) for a user who missed their "
        f'"{goal_type.name}" goal today. Return JSON only.'
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def _generate_one(
    db: AsyncSession, goal_type: GoalType, tone: str
) -> None:
    existing = await _fetch_recent_templates(db, goal_type.id, tone)
    existing_bodies = {t.body.strip().lower() for t in existing}

    messages = _build_messages(goal_type, tone, existing)

    try:
        response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=200,
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
    except Exception as exc:
        logger.warning(
            "[template_gen] OpenAI call failed for goal_type=%s tone=%s: %s",
            goal_type.name, tone, exc,
        )
        return

    title = parsed.get("title", "").strip()
    body = parsed.get("body", "").strip()

    if not title or not body:
        logger.warning(
            "[template_gen] Empty title or body from OpenAI for goal_type=%s tone=%s — skipping",
            goal_type.name, tone,
        )
        return

    if body.lower() in existing_bodies:
        logger.warning(
            "[template_gen] Duplicate body generated for goal_type=%s tone=%s — skipping",
            goal_type.name, tone,
        )
        return

    db.add(NotificationTemplate(
        event_type=NotificationEvent.GOAL_MISSED,
        tone=tone,
        goal_type_id=goal_type.id,
        title=title,
        body=body,
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()
    logger.info(
        "[template_gen] Generated new template for goal_type=%s tone=%s: %r",
        goal_type.name, tone, title,
    )


async def generate_notification_templates() -> None:
    async with CelerySessionFactory() as db:
        result = await db.execute(
            select(GoalType).where(GoalType.is_active == True)  # noqa: E712
        )
        goal_types = result.scalars().all()

    for goal_type in goal_types:
        for tone in _TONES:
            async with CelerySessionFactory() as db:
                try:
                    await _generate_one(db, goal_type, tone)
                except Exception as exc:
                    logger.exception(
                        "[template_gen] Unexpected error for goal_type=%s tone=%s: %s",
                        goal_type.name, tone, exc,
                    )
