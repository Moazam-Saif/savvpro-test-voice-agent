"""
brain/nlu/times.py – Time parser (5.4 TIME PARSER).

Handles: "5pm", "5 pm", "5:30", "5 30", "17:30", "half past five",
"quarter to six", "quarter past 3", "noon", "midday".

Bare hour ambiguity (no am/pm):
  - Exactly one valid against the day's hours → take it.
  - Neither valid → guess PM for 1–6, AM for 7–11.
  - Both valid → take guess and set ambiguous_ampm=True.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, time


@dataclass
class TimeResult:
    time: time | None = None
    ambiguous_ampm: bool = False
    out_of_hours: bool = False   # "evening" hint
    error: str | None = None


def _make_time(h: int, m: int) -> time | None:
    try:
        return time(h, m)
    except ValueError:
        return None


def _validate_against_hours(t: time, d: date | None) -> bool:
    """Very loose check: is *t* inside the widest possible clinic hours?"""
    from assistant.domain.hours import day_open_time, day_close_time, windows_for_day
    if d is not None:
        open_t = day_open_time(d)
        close_t = day_close_time(d)
    else:
        open_t = time(9, 0)
        close_t = time(17, 0)
    if open_t is None or close_t is None:
        return False
    return open_t <= t < close_t


def parse_time(text: str, d: date | None = None) -> TimeResult:
    """Extract a start time from normalized *text*."""
    t = text.strip().lower()

    # ── Special words ─────────────────────────────────────────────────────────
    if re.search(r"\b(noon|midday)\b", t):
        return TimeResult(time=time(12, 0))
    if re.search(r"\bevening\b", t):
        return TimeResult(out_of_hours=True)

    # ── "half past N" ─────────────────────────────────────────────────────────
    m = re.search(r"\bhalf past (\d{1,2})\b", t)
    if m:
        h = int(m.group(1))
        return TimeResult(time=_make_time(h, 30) or _make_time(h % 12 + 12, 30))

    # ── "quarter past N" ─────────────────────────────────────────────────────
    m = re.search(r"\bquarter past (\d{1,2})\b", t)
    if m:
        h = int(m.group(1))
        return TimeResult(time=_make_time(h, 15) or _make_time(h % 12 + 12, 15))

    # ── "quarter to N" ────────────────────────────────────────────────────────
    m = re.search(r"\bquarter to (\d{1,2})\b", t)
    if m:
        h = int(m.group(1))
        result_h = h - 1 if h > 0 else 23
        return TimeResult(time=_make_time(result_h, 45))

    # ── "HH:MM am/pm" or "HH MM am/pm" or "H am/pm" ─────────────────────────
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t)
    if m:
        h = int(m.group(1))
        mins = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3).lower()
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        return TimeResult(time=_make_time(h, mins))

    # ── 24-hour "17:30" ───────────────────────────────────────────────────────
    m = re.search(r"\b(1[3-9]|2[0-3]):(\d{2})\b", t)
    if m:
        return TimeResult(time=_make_time(int(m.group(1)), int(m.group(2))))

    # ── "H:MM" or "H MM" with no am/pm ───────────────────────────────────────
    m = re.search(r"\b(\d{1,2})[: ](\d{2})\b", t)
    if m:
        h = int(m.group(1))
        mins = int(m.group(2))
        # Try both AM and PM readings
        am_t = _make_time(h % 12, mins)          # 0-11 range
        pm_t = _make_time(h % 12 + 12, mins) if h % 12 != 0 else _make_time(12, mins)
        if h >= 13:
            # Definitely 24-hour
            return TimeResult(time=_make_time(h, mins))
        am_valid = am_t is not None and _validate_against_hours(am_t, d)
        pm_valid = pm_t is not None and _validate_against_hours(pm_t, d)
        if am_valid and not pm_valid:
            return TimeResult(time=am_t)
        if pm_valid and not am_valid:
            return TimeResult(time=pm_t)
        if am_valid and pm_valid:
            # Ambiguous: take PM and flag
            return TimeResult(time=pm_t, ambiguous_ampm=True)
        # Neither valid: guess PM for 1–6, AM for 7–11
        if 1 <= h <= 6:
            return TimeResult(time=_make_time(h + 12, mins), ambiguous_ampm=False)
        return TimeResult(time=am_t)

    # ── Bare hour "at 3" ──────────────────────────────────────────────────────
    m = re.search(r"\b(?:at )?(\d{1,2})\b", t)
    if m:
        h = int(m.group(1))
        if h > 23:
            return TimeResult(error="invalid hour")
        am_t = _make_time(h if h < 12 else h % 12, 0)
        pm_t = _make_time((h % 12) + 12, 0) if h < 12 else _make_time(h, 0)
        am_valid = am_t is not None and _validate_against_hours(am_t, d)
        pm_valid = pm_t is not None and _validate_against_hours(pm_t, d)
        if am_valid and not pm_valid:
            return TimeResult(time=am_t)
        if pm_valid and not am_valid:
            return TimeResult(time=pm_t)
        if am_valid and pm_valid:
            return TimeResult(time=pm_t, ambiguous_ampm=True)
        if 1 <= h <= 6:
            return TimeResult(time=_make_time(h + 12, 0))
        return TimeResult(time=am_t or pm_t)

    return TimeResult(error="no time found")
