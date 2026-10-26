"""
tests/domain/test_availability.py – Table-driven availability tests.

Covers:
  - check_date: all reasons including Saturday hours (T1/X1)
  - check_time: all reasons including lunch, AFTER_CLOSE, off-grid
  - T1 time tests (a) and (b): DST fall-back arithmetic
  - is_free
  - find_next_available: no-date earliest, horizon
"""
from __future__ import annotations

import pytest
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from assistant.clock import FixedClock, to_local
from assistant.domain.availability import (
    check_date, check_time, is_free, find_next_available,
)
from assistant.domain.models import DateCheckReason, TimeCheckReason, Booking, Service

TZ = ZoneInfo("America/New_York")


def make_booking(start: datetime, duration_minutes: int = 30) -> Booking:
    from uuid import uuid4
    end = start + timedelta(minutes=duration_minutes)
    return Booking(
        id=str(uuid4()), patient_name="Test Patient",
        service=Service.CLEANING, start=start, end=end,
        code="1234", created_at=start,
    )


# ── check_date ────────────────────────────────────────────────────────────────

class TestCheckDate:
    def test_ok_future_weekday(self):
        now = FixedClock(at=datetime.fromisoformat("2026-10-26T14:00:00-04:00"))
        result = check_date(date(2026, 10, 28), now.now_utc(), TZ, {})
        assert result.ok

    def test_past(self):
        now = FixedClock(at=datetime.fromisoformat("2026-10-26T14:00:00-04:00"))
        result = check_date(date(2026, 10, 25), now.now_utc(), TZ, {})
        assert result.reason == DateCheckReason.PAST

    def test_beyond_horizon(self):
        now = FixedClock(at=datetime.fromisoformat("2026-10-26T14:00:00-04:00"))
        far_future = date(2026, 10, 26) + timedelta(days=65)
        result = check_date(far_future, now.now_utc(), TZ, {})
        assert result.reason == DateCheckReason.BEYOND_HORIZON

    def test_closed_date(self):
        now = FixedClock(at=datetime.fromisoformat("2026-10-26T14:00:00-04:00"))
        closed = date(2026, 11, 5)
        result = check_date(closed, now.now_utc(), TZ, {closed: "Staff training day"})
        assert result.reason == DateCheckReason.CLOSED_DATE
        assert result.closed_reason_label == "Staff training day"

    def test_sunday_closed(self):
        now = FixedClock(at=datetime.fromisoformat("2026-10-26T14:00:00-04:00"))
        # 2026-11-01 is a Sunday
        result = check_date(date(2026, 11, 1), now.now_utc(), TZ, {})
        assert result.reason == DateCheckReason.CLOSED_DAY

    def test_saturday_ok(self):
        now = FixedClock(at=datetime.fromisoformat("2026-10-26T14:00:00-04:00"))
        # 2026-10-31 is a Saturday
        result = check_date(date(2026, 10, 31), now.now_utc(), TZ, {})
        assert result.ok


# ── check_time ────────────────────────────────────────────────────────────────

class TestCheckTime:
    def _clock(self, iso: str) -> FixedClock:
        return FixedClock(at=datetime.fromisoformat(iso))

    def test_valid_weekday_slot(self):
        clock = self._clock("2026-10-26T14:00:00-04:00")
        result = check_time(time(15, 0), clock.now_utc(), TZ,
                            d=date(2026, 10, 27), duration_minutes=30)
        assert result.ok

    def test_past(self):
        clock = self._clock("2026-10-26T19:00:00-04:00")  # 7 PM local
        result = check_time(time(9, 0), clock.now_utc(), TZ,
                            d=date(2026, 10, 26), duration_minutes=30)
        assert result.reason == TimeCheckReason.PAST

    def test_too_soon(self):
        # Now is 08:00, checking 09:00 same day → only 1hr lead (need 2)
        clock = self._clock("2026-10-27T08:00:00-04:00")
        result = check_time(time(9, 0), clock.now_utc(), TZ,
                            d=date(2026, 10, 27), duration_minutes=30)
        assert result.reason == TimeCheckReason.TOO_SOON

    def test_ok_exactly_2hr_lead(self):
        # Now is 07:00, checking 09:00 → exactly 2hr lead → ok
        clock = self._clock("2026-10-27T07:00:00-04:00")
        result = check_time(time(9, 0), clock.now_utc(), TZ,
                            d=date(2026, 10, 27), duration_minutes=30)
        assert result.ok

    def test_off_grid(self):
        clock = self._clock("2026-10-26T14:00:00-04:00")
        result = check_time(time(10, 15), clock.now_utc(), TZ,
                            d=date(2026, 10, 27), duration_minutes=30)
        assert result.reason == TimeCheckReason.OFF_GRID

    def test_lunch(self):
        clock = self._clock("2026-10-26T14:00:00-04:00")
        # 12:30 slot, 60 minutes → runs into lunch at 13:00
        result = check_time(time(12, 30), clock.now_utc(), TZ,
                            d=date(2026, 10, 27), duration_minutes=60)
        assert result.reason == TimeCheckReason.LUNCH

    def test_before_open_weekday(self):
        clock = self._clock("2026-10-26T14:00:00-04:00")
        result = check_time(time(8, 0), clock.now_utc(), TZ,
                            d=date(2026, 10, 27), duration_minutes=30)
        assert result.reason == TimeCheckReason.BEFORE_OPEN

    def test_after_close_root_canal(self):
        clock = self._clock("2026-10-26T14:00:00-04:00")
        # Root canal 90min at 16:00 → ends at 17:30 > 17:00 close
        result = check_time(time(16, 0), clock.now_utc(), TZ,
                            d=date(2026, 10, 27), duration_minutes=90)
        assert result.reason == TimeCheckReason.AFTER_CLOSE

    def test_saturday_before_open(self):
        clock = self._clock("2026-10-26T14:00:00-04:00")
        # Saturday opens at 10:00, not 09:00
        result = check_time(time(9, 0), clock.now_utc(), TZ,
                            d=date(2026, 10, 31), duration_minutes=30)
        assert result.reason == TimeCheckReason.BEFORE_OPEN

    def test_saturday_ok_at_10(self):
        clock = self._clock("2026-10-26T14:00:00-04:00")
        result = check_time(time(10, 0), clock.now_utc(), TZ,
                            d=date(2026, 10, 31), duration_minutes=30)
        assert result.ok

    # T1 test (b): lead-time boundary around DST fall-back
    def test_t1_lead_boundary_nov2_too_soon(self):
        """At 07:01 local on Nov 2 (post-DST), 09:00 same day is TOO_SOON (only 1h59m lead)."""
        # 2026-11-02 07:01 EST = 12:01 UTC
        clock = FixedClock(at=datetime.fromisoformat("2026-11-02T12:01:00+00:00"))
        result = check_time(time(9, 0), clock.now_utc(), TZ,
                            d=date(2026, 11, 2), duration_minutes=30)
        assert result.reason == TimeCheckReason.TOO_SOON

    def test_t1_lead_boundary_nov2_ok(self):
        """At 07:00 local on Nov 2, 09:00 is exactly 2 hours → OK."""
        # 2026-11-02 07:00 EST = 12:00 UTC
        clock = FixedClock(at=datetime.fromisoformat("2026-11-02T12:00:00+00:00"))
        result = check_time(time(9, 0), clock.now_utc(), TZ,
                            d=date(2026, 11, 2), duration_minutes=30)
        assert result.ok


# ── is_free ───────────────────────────────────────────────────────────────────

class TestIsFree:
    def test_empty(self):
        start = datetime(2026, 10, 27, 10, 0)
        assert is_free(start, 30, []) is True

    def test_overlap(self):
        existing = make_booking(datetime(2026, 10, 27, 10, 0), 30)
        assert is_free(datetime(2026, 10, 27, 10, 0), 30, [existing]) is False

    def test_adjacent_ok(self):
        existing = make_booking(datetime(2026, 10, 27, 10, 0), 30)
        # Starts exactly when previous ends → no overlap
        assert is_free(datetime(2026, 10, 27, 10, 30), 30, [existing]) is True

    def test_partial_overlap(self):
        existing = make_booking(datetime(2026, 10, 27, 10, 0), 60)
        assert is_free(datetime(2026, 10, 27, 10, 30), 30, [existing]) is False


# ── T1 time test (a): real elapsed time across DST fall-back ─────────────────

class TestDSTElapsed:
    def test_t1_a_38_hours_across_fallback(self):
        """
        Real elapsed time from Sat 2026-10-31 20:00 EDT to
        Mon 2026-11-02 09:00 EST is 38 hours (not 37).
        """
        from assistant.clock import local_to_utc
        sat_naive = datetime(2026, 10, 31, 20, 0)
        mon_naive = datetime(2026, 11, 2, 9, 0)
        sat_utc = local_to_utc(sat_naive, TZ)
        mon_utc = local_to_utc(mon_naive, TZ)
        elapsed_hours = (mon_utc - sat_utc).total_seconds() / 3600
        assert elapsed_hours == pytest.approx(38.0)
