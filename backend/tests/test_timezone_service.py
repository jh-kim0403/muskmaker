"""
Tests for TimezoneService — the most critical correctness requirement.
Every day-boundary rule flows through this service.
"""
import pytest
from datetime import datetime, timezone, date
from unittest.mock import AsyncMock, MagicMock
from app.services.timezone_service import TimezoneService


class TestUserLocalDate:
    def test_converts_utc_to_local_date(self):
        # 2026-04-10 02:00 UTC = 2026-04-09 in Los Angeles (UTC-7 during PDT)
        utc_ts = datetime(2026, 4, 10, 2, 0, 0, tzinfo=timezone.utc)
        result = TimezoneService.user_local_date(utc_ts, "America/Los_Angeles")
        assert result == date(2026, 4, 9)

    def test_utc_user_gets_utc_date(self):
        utc_ts = datetime(2026, 4, 10, 0, 30, 0, tzinfo=timezone.utc)
        result = TimezoneService.user_local_date(utc_ts, "UTC")
        assert result == date(2026, 4, 10)

    def test_near_midnight_east_vs_west(self):
        # 2026-04-10 23:59 UTC
        # = 2026-04-10 in London (UTC+1 BST)
        # = 2026-04-10 16:59 in Los Angeles (still April 10)
        utc_ts = datetime(2026, 4, 10, 23, 59, 0, tzinfo=timezone.utc)
        assert TimezoneService.user_local_date(utc_ts, "Europe/London") == date(2026, 4, 10)
        assert TimezoneService.user_local_date(utc_ts, "America/Los_Angeles") == date(2026, 4, 10)

    def test_dst_spring_forward(self):
        # US DST spring forward: 2026-03-08 02:00 -> 03:00 in America/New_York
        # 2026-03-08 06:59 UTC = 2026-03-08 01:59 EST (before spring forward)
        before_dst = datetime(2026, 3, 8, 6, 59, tzinfo=timezone.utc)
        assert TimezoneService.user_local_date(before_dst, "America/New_York") == date(2026, 3, 8)


class TestLocalDayEndUtc:
    def test_end_of_day_is_23_59_59(self):
        result = TimezoneService.local_day_end_utc(date(2026, 4, 10), "UTC")
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 10
        assert result.hour == 23
        assert result.minute == 59

    def test_la_midnight_is_correct_utc(self):
        # LA is UTC-7 (PDT in April). End of day 23:59:59 PDT = 06:59:59 UTC next day
        result = TimezoneService.local_day_end_utc(date(2026, 4, 10), "America/Los_Angeles")
        assert result.day == 11
        assert result.hour == 6

    def test_expires_at_after_created_at(self):
        # expires_at must always be in the future relative to any time during that local day
        now_la = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        local_date = TimezoneService.user_local_date(now_la, "America/Los_Angeles")
        expires_at = TimezoneService.local_day_end_utc(local_date, "America/Los_Angeles")
        assert expires_at > now_la


class TestGoalOneDayRule:
    """Verify the uniqueness constraint logic works correctly across timezones."""

    def test_same_type_same_local_day_rejected(self):
        # Two goals created at UTC times that map to the same local date
        # should have the same local_goal_date and be blocked by the UNIQUE constraint
        morning_utc = datetime(2026, 4, 10, 15, 0, tzinfo=timezone.utc)  # 8 AM LA
        evening_utc = datetime(2026, 4, 10, 23, 0, tzinfo=timezone.utc)  # 4 PM LA
        tz = "America/Los_Angeles"

        date_morning = TimezoneService.user_local_date(morning_utc, tz)
        date_evening = TimezoneService.user_local_date(evening_utc, tz)

        # Same local date — constraint should reject second goal
        assert date_morning == date_evening

    def test_different_local_days_allowed(self):
        # A goal created just before midnight and one just after are different local days
        before_midnight_utc = datetime(2026, 4, 11, 6, 58, tzinfo=timezone.utc)  # 11:58 PM LA Apr 10
        after_midnight_utc = datetime(2026, 4, 11, 7, 1, tzinfo=timezone.utc)   # 12:01 AM LA Apr 11
        tz = "America/Los_Angeles"

        date_before = TimezoneService.user_local_date(before_midnight_utc, tz)
        date_after = TimezoneService.user_local_date(after_midnight_utc, tz)

        assert date_before != date_after
        assert date_before == date(2026, 4, 10)
        assert date_after == date(2026, 4, 11)
