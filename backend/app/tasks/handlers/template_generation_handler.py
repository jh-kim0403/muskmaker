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

from sqlalchemy import nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import NotificationEvent, NotificationTone
from app.database import CelerySessionFactory
from app.models.goal import GoalType
from app.models.notification import NotificationPromptConfig, NotificationTemplate
from app.services.ai_service import openai_client

logger = logging.getLogger(__name__)
settings = get_settings()

_TONES = [NotificationTone.FRIENDLY_BANTER, NotificationTone.HARSH]


async def _fetch_recent_templates(
    db: AsyncSession, goal_type_id, tone: str, event_type: str, limit: int = 30
) -> list[NotificationTemplate]:
    result = await db.execute(
        select(NotificationTemplate)
        .where(
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.goal_type_id == goal_type_id,
            NotificationTemplate.tone == tone,
        )
        .order_by(NotificationTemplate.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def _fetch_prompt_config(
    db: AsyncSession, goal_type_id, tone: str, event_type: str
) -> NotificationPromptConfig | None:
    result = await db.execute(
        select(NotificationPromptConfig)
        .where(
            NotificationPromptConfig.tone == tone,
            NotificationPromptConfig.event_type == event_type,
            (NotificationPromptConfig.goal_type_id == goal_type_id)
            | NotificationPromptConfig.goal_type_id.is_(None),
        )
        .order_by(nulls_last(NotificationPromptConfig.goal_type_id))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _build_messages(goal_type: GoalType, tone: str, prompt_context: str, existing: list[NotificationTemplate]) -> list[dict]:
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
        f"Tone: {tone}\n"
        f"Instruction: {prompt_context}\n\n"
        f"The following {len(existing)} templates already exist for this goal type + tone.\n"
        f"Your new template must NOT duplicate any of these:\n"
        f"{existing_examples}\n\n"
        f'Return JSON only.'
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def _generate_one(
    db: AsyncSession, goal_type: GoalType, tone: str, event_type: str
) -> None:
    config = await _fetch_prompt_config(db, goal_type.id, tone, event_type)
    if config is None:
        logger.warning(
            "[template_gen] No prompt config for goal_type=%s tone=%s event=%s — skipping",
            goal_type.name, tone, event_type,
        )
        return

    existing = await _fetch_recent_templates(db, goal_type.id, tone, event_type)
    existing_bodies = {t.body.strip().lower() for t in existing}

    messages = _build_messages(goal_type, tone, config.prompt_context, existing)

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
            "[template_gen] OpenAI call failed for goal_type=%s tone=%s event=%s: %s",
            goal_type.name, tone, event_type, exc,
        )
        return

    title = parsed.get("title", "").strip()
    body = parsed.get("body", "").strip()

    if not title or not body:
        logger.warning(
            "[template_gen] Empty title or body from OpenAI for goal_type=%s tone=%s event=%s — skipping",
            goal_type.name, tone, event_type,
        )
        return

    if body.lower() in existing_bodies:
        logger.warning(
            "[template_gen] Duplicate body generated for goal_type=%s tone=%s event=%s — skipping",
            goal_type.name, tone, event_type,
        )
        return

    db.add(NotificationTemplate(
        event_type=event_type,
        tone=tone,
        goal_type_id=goal_type.id,
        title=title,
        body=body,
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()
    logger.info(
        "[template_gen] Generated new template for goal_type=%s tone=%s event=%s: %r",
        goal_type.name, tone, event_type, title,
    )


async def generate_notification_templates() -> None:
    async with CelerySessionFactory() as db:
        result = await db.execute(
            select(GoalType).where(GoalType.is_active == True)  # noqa: E712
        )
        goal_types = result.scalars().all()

    _events = [NotificationEvent.GOAL_MISSED, NotificationEvent.GOAL_REMINDER]

    for goal_type in goal_types:
        for tone in _TONES:
            for event_type in _events:
                async with CelerySessionFactory() as db:
                    try:
                        await _generate_one(db, goal_type, tone, event_type)
                    except Exception as exc:
                        logger.exception(
                            "[template_gen] Unexpected error for goal_type=%s tone=%s event=%s: %s",
                            goal_type.name, tone, event_type, exc,
                        )
