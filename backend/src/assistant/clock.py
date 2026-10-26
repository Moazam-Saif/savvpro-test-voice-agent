"""
clock.py – Clock protocol and time-zone helpers.

RULE (T1): The only place UTC ↔ local conversion happens is here.
  - Clock.now_utc() → aware UTC datetime.
  - to_local(utc)   → naive clinic-local wall-clock datetime.
  - local_to_utc(naive) → aware UTC datetime (fold=0 for ambiguous times).

Everything outside this module works with naive local datetimes only.
The brain sees the clock exclusively through Ports.now_local().
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    """Minimal clock interface injected into the engine and domain layer."""

    def now_utc(self) -> datetime:
        """Return the current time as an aware UTC datetime."""
        ...


class SystemClock:
    """Uses the real wall clock."""

    def now_utc(self) -> datetime:
        return datetime.now(tz=timezone.utc)


class FixedClock:
    """Pinned clock for tests and demos.

    Args:
        at: An aware datetime (any timezone).  Stored as UTC.
    """

    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock requires an aware datetime")
        self._utc = at.astimezone(timezone.utc)

    def now_utc(self) -> datetime:
        return self._utc


# ── Conversion helpers (T1) ────────────────────────────────────────────────────

def to_local(utc: datetime, tz: ZoneInfo) -> datetime:
    """Convert an aware UTC datetime to a *naive* clinic-local datetime.

    The result is intentionally naive so that the brain never accidentally
    mixes timezone-aware and naive datetimes.
    """
    if utc.tzinfo is None:
        raise TypeError("to_local() requires an aware UTC datetime")
    local_aware = utc.astimezone(tz)
    return local_aware.replace(tzinfo=None)


def local_to_utc(naive: datetime, tz: ZoneInfo) -> datetime:
    """Convert a *naive* clinic-local datetime back to aware UTC (fold=0).

    fold=0 means we always pick the earlier of the two ambiguous times
    during a fall-back transition, which is the safer choice.
    """
    if naive.tzinfo is not None:
        raise TypeError("local_to_utc() requires a naive datetime")
    local_aware = naive.replace(tzinfo=tz, fold=0)
    return local_aware.astimezone(timezone.utc)
