"""
domain/hours.py – Clinic opening-hours configuration.

RULE (T1 / X1 / X4):
  - Mon–Fri 09:00–17:00 with a lunch closure 13:00–14:00.
  - Saturday 10:00–14:00 (no lunch).
  - Sunday: closed.
  - DAY PARTS: MORNING = start before 12:00, AFTERNOON = start >= 12:00.
    (Not tied to specific open/close windows, so Saturday works correctly.)
"""
from __future__ import annotations

from datetime import date, time
from typing import NamedTuple


# ── Open windows per weekday ──────────────────────────────────────────────────
# Each tuple is (open, close) using naive time objects.
# Monday=0 … Sunday=6

class _Window(NamedTuple):
    open: time
    close: time


_WEEKDAY_WINDOWS: dict[int, list[_Window]] = {
    0: [_Window(time(9, 0), time(13, 0)), _Window(time(14, 0), time(17, 0))],   # Monday
    1: [_Window(time(9, 0), time(13, 0)), _Window(time(14, 0), time(17, 0))],   # Tuesday
    2: [_Window(time(9, 0), time(13, 0)), _Window(time(14, 0), time(17, 0))],   # Wednesday
    3: [_Window(time(9, 0), time(13, 0)), _Window(time(14, 0), time(17, 0))],   # Thursday
    4: [_Window(time(9, 0), time(13, 0)), _Window(time(14, 0), time(17, 0))],   # Friday
    5: [_Window(time(10, 0), time(14, 0))],                                      # Saturday
    6: [],                                                                        # Sunday – closed
}

# Lunch closure for weekdays (not Saturday)
LUNCH_START = time(13, 0)
LUNCH_END = time(14, 0)

# Slot grid
SLOT_GRID_MINUTES = 30

# Booking constraints
MIN_LEAD_TIME_HOURS = 2
BOOKING_HORIZON_DAYS = 60


def windows_for_day(d: date) -> list[_Window]:
    """Return the list of open windows for a given date (may be empty)."""
    return _WEEKDAY_WINDOWS[d.weekday()]


def is_open_day(d: date) -> bool:
    """True if the clinic is open at all on this calendar date (ignoring closed dates)."""
    return bool(windows_for_day(d))


def day_open_time(d: date) -> time | None:
    """Earliest opening time for the day, or None if closed."""
    windows = windows_for_day(d)
    return windows[0].open if windows else None


def day_close_time(d: date) -> time | None:
    """Latest closing time for the day, or None if closed."""
    windows = windows_for_day(d)
    return windows[-1].close if windows else None


def has_lunch(d: date) -> bool:
    """True for Mon–Fri (the days that have a lunch closure)."""
    return d.weekday() < 5


def validate_open_windows() -> None:
    """
    Config-load assertion (T1): no open window may intersect 00:00–04:00,
    so a slot can never fall in a spring-forward gap or fall-back repeat.
    Raises AssertionError if the constraint is violated.
    """
    danger_start = time(0, 0)
    danger_end = time(4, 0)
    for weekday, windows in _WEEKDAY_WINDOWS.items():
        for w in windows:
            # A window intersects [00:00, 04:00) if its open < 04:00
            assert w.open >= danger_end, (
                f"Window {w} on weekday {weekday} intersects the 00:00–04:00 "
                "DST danger zone"
            )


# Run the assertion at import time so misconfiguration is caught early.
validate_open_windows()
