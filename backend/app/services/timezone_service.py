"""
TimezoneService — authoritative timezone operations.

All calendar-day boundary computations flow through this service.
No other service should perform timezone math directly.
"""
import logging
from datetime import date, datetime, timezone
from typing import Optional

import pytz
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import CheatEvent, TzChangeSource
from app.models.audit import AntiCheatLog, TimezoneAuditLog
from app.models.goal import Goal
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()


class TimezoneService:

    @staticmethod
    def user_local_date(utc_ts: datetime, iana_tz: str) -> date:
        """
        Convert a UTC datetime to the user's local DATE.
        This is the single authoritative function for all day-boundary math.
        NEVER derive a local date from client input.
        """
        tz = pytz.timezone(iana_tz)
        return utc_ts.astimezone(tz).date()

    @staticmethod
    def local_day_end_utc(local_date: date, iana_tz: str) -> datetime:
        """
        Return the exact UTC moment when a local calendar day ends (23:59:59.999999).
        Used to set goals.expires_at at creation time.
        """
        tz = pytz.timezone(iana_tz)
        # Build naive end-of-day, then localize to the target tz, then convert to UTC.
        naive_end = datetime(local_date.year, local_date.month, local_date.day, 23, 59, 59, 999999)
        local_end = tz.localize(naive_end)
        return local_end.astimezone(pytz.utc)

    @staticmethod
    def now_in_timezone(iana_tz: str) -> datetime:
        """Return the current moment expressed in the given IANA timezone."""
        tz = pytz.timezone(iana_tz)
        return datetime.now(timezone.utc).astimezone(tz)

    # ── Timezone update with rate-limiting and abuse detection ────────────────

    @staticmethod
    async def update_user_timezone(
        db: AsyncSession,
        user: User,
        new_timezone: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        source: str = TzChangeSource.SETTINGS,
    ) -> User:
        """
        Update a user's stored timezone with full abuse-protection:
          1. Validate IANA timezone string
          2. Enforce rate limit (max 1 change per 24-hour rolling window)
          3. Check for day-window-extension abuse (change would extend an active goal's day)
          4. Write immutable audit log entry
          5. Update users.timezone (never retroactively modifies existing goals)

        Raises HTTPException on rate limit or window-extension block.
        """
        # Step 1: Validate
        if new_timezone not in pytz.all_timezones_set:
            raise HTTPException(status_code=422, detail=f"'{new_timezone}' is not a valid IANA timezone")

        if new_timezone == user.timezone:
            return user  # No-op

        # Step 2: Rate limit check
        changes_in_window = await TimezoneService._count_changes_in_window(db, user.id)
        rate_limit = settings.timezone_change_rate_limit

        if changes_in_window >= rate_limit:
            # Log the blocked attempt
            await TimezoneService._write_audit_log(
                db, user, new_timezone, ip_address, user_agent, source,
                was_blocked=True, changes_in_window=changes_in_window,
                flagged=True, flag_reason="rate_limit_exceeded",
            )
            raise HTTPException(
                status_code=429,
                detail=f"Timezone can only be changed {rate_limit} time(s) per 24 hours",
            )

        # Step 3: Window-extension abuse check
        # If the user has active goals today and the new TZ would make "today" extend
        # further than the current TZ's day end, block the change.
        is_abusive, flag_reason = await TimezoneService._check_window_extension(
            db, user, new_timezone
        )

        if is_abusive:
            await TimezoneService._write_audit_log(
                db, user, new_timezone, ip_address, user_agent, source,
                was_blocked=True, changes_in_window=changes_in_window,
                flagged=True, flag_reason=flag_reason,
            )
            # Also write an anti-cheat log entry
            db.add(AntiCheatLog(
                user_id=user.id,
                event_type=CheatEvent.TZ_WINDOW_EXTENSION,
                severity="high",
                reference_type="timezone_change",
                details={"old_tz": user.timezone, "new_tz": new_timezone, "reason": flag_reason},
                auto_action="blocked",
            ))
            raise HTTPException(
                status_code=429,
                detail="Timezone change not allowed: it would extend an active goal's valid window",
            )

        # Step 4: Write successful audit log
        # Check proximity to recent goal creation (flag but allow)
        flagged, flag_reason_allow = await TimezoneService._check_near_goal_creation(db, user)

        await TimezoneService._write_audit_log(
            db, user, new_timezone, ip_address, user_agent, source,
            was_blocked=False, changes_in_window=changes_in_window,
            flagged=flagged, flag_reason=flag_reason_allow,
        )

        if flagged:
            db.add(AntiCheatLog(
                user_id=user.id,
                event_type=CheatEvent.TZ_CHANGE_NEAR_GOAL,
                severity="medium",
                reference_type="timezone_change",
                details={"old_tz": user.timezone, "new_tz": new_timezone},
                auto_action="flagged_for_review",
            ))

        # Step 5: Apply the change
        # CRITICAL: existing goals are NOT touched — they keep timezone_at_creation
        user.timezone = new_timezone
        user.timezone_updated_at = datetime.now(timezone.utc)

        return user

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    async def _count_changes_in_window(db: AsyncSession, user_id) -> int:
        """Count successful (not blocked) timezone changes in the last 24 hours."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(func.count())
            .select_from(TimezoneAuditLog)
            .where(
                TimezoneAuditLog.user_id == user_id,
                TimezoneAuditLog.changed_at >= cutoff,
                TimezoneAuditLog.was_blocked == False,  # noqa: E712
            )
        )
        return result.scalar_one()

    @staticmethod
    async def _check_window_extension(
        db: AsyncSession, user: User, new_timezone: str
    ) -> tuple[bool, str]:
        """
        Returns (is_abusive, reason).
        A timezone change is abusive if the user has active goals whose
        local_goal_date equals TODAY in new_tz, but that date's day-end in new_tz
        is later than the day-end in the current timezone.
        This would effectively extend the verification window for those goals.
        """
        now_utc = datetime.now(timezone.utc)
        new_local_today = TimezoneService.user_local_date(now_utc, new_timezone)
        old_local_today = TimezoneService.user_local_date(now_utc, user.timezone)

        # Check for active goals
        result = await db.execute(
            select(Goal).where(
                Goal.user_id == user.id,
                Goal.status.in_(["active", "submitted"]),
            )
        )
        active_goals = result.scalars().all()

        if not active_goals:
            return False, ""

        new_day_end = TimezoneService.local_day_end_utc(new_local_today, new_timezone)
        old_day_end = TimezoneService.local_day_end_utc(old_local_today, user.timezone)

        if new_day_end > old_day_end:
            return True, f"new_tz_day_end={new_day_end.isoformat()} > current_tz_day_end={old_day_end.isoformat()}"

        return False, ""

    @staticmethod
    async def _check_near_goal_creation(
        db: AsyncSession, user: User, window_minutes: int = 30
    ) -> tuple[bool, str]:
        """
        Returns (flagged, reason) if the user created or verified a goal
        within the last `window_minutes` minutes.
        """
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        result = await db.execute(
            select(Goal).where(
                Goal.user_id == user.id,
                Goal.created_at >= cutoff,
            )
        )
        recent_goal = result.scalars().first()
        if recent_goal:
            return True, f"goal_created_at={recent_goal.created_at.isoformat()}"
        return False, ""

    @staticmethod
    async def _write_audit_log(
        db: AsyncSession,
        user: User,
        new_timezone: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        source: str,
        was_blocked: bool,
        changes_in_window: int,
        flagged: bool,
        flag_reason: Optional[str],
    ) -> None:
        log = TimezoneAuditLog(
            user_id=user.id,
            old_timezone=user.timezone,
            new_timezone=new_timezone,
            ip_address=ip_address,
            user_agent=user_agent,
            change_source=source,
            was_blocked=was_blocked,
            changes_in_window=changes_in_window,
            flagged_suspicious=flagged,
            flag_reason=flag_reason,
        )
        db.add(log)
