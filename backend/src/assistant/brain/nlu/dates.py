"""
brain/nlu/dates.py – Date parser (5.4 DATE PARSER).

Output is one of:
  - A concrete date
  - A (hint, week_anchor) pair ("next week", "this weekend")
  - pref_mode="EARLIEST"
  - A conflict (weekday + date disagree)
  - An error string
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Union

# ── Weekday name table ────────────────────────────────────────────────────────
_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTH_NAMES = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


@dataclass
class DateResult:
    date: date | None = None
    hint: str | None = None          # "NEXT_WEEK" | "THIS_WEEKEND"
    week_anchor: date | None = None  # Monday of the hinted week
    pref_mode: str | None = None     # "EARLIEST"
    time_window: str | None = None   # "MORNING" | "AFTERNOON" (trailing window)
    conflict: tuple[date, date] | None = None  # (weekday_reading, ordinal_reading)
    error: str | None = None


def _next_weekday(today: date, wd: int, strict: bool = True) -> date:
    """
    Next occurrence of weekday *wd* (0=Mon).
    strict=True: strictly after today (today==wd gives +7).
    strict=False: on or after today.
    """
    days_ahead = wd - today.weekday()
    if strict and days_ahead <= 0:
        days_ahead += 7
    elif not strict and days_ahead < 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def _monday_of_next_week(today: date) -> date:
    """The Monday that starts the next full Mon–Sun week."""
    days_to_next_monday = (7 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_to_next_monday)


def _next_occurrence_of_day(today: date, day_num: int, month: int | None = None) -> date | None:
    """
    Next future occurrence of the given day number (1–31).
    If month is given, use that month; otherwise find the nearest future month.
    """
    from calendar import monthrange
    if month is not None:
        year = today.year
        # If date would be in the past, roll to next year
        try:
            d = date(year, month, day_num)
        except ValueError:
            return None
        if d <= today:
            try:
                d = date(year + 1, month, day_num)
            except ValueError:
                return None
        return d
    # No month: find nearest future month that has this day
    cursor_month = today.month
    cursor_year = today.year
    for _ in range(13):
        _, last_day = monthrange(cursor_year, cursor_month)
        if day_num <= last_day:
            try:
                d = date(cursor_year, cursor_month, day_num)
                if d > today:
                    return d
            except ValueError:
                pass
        cursor_month += 1
        if cursor_month > 12:
            cursor_month = 1
            cursor_year += 1
    return None


# ── Main parser ────────────────────────────────────────────────────────────────

def parse_date(text: str, today: date, week_anchor: date | None = None, for_verification: bool = False) -> DateResult:
    """
    Parse a date reference from normalized *text*.

    for_verification=True: a bare weekday means the nearest upcoming occurrence
    on or after today (used for lookup_date in cancel verification).
    """
    t = text.strip()

    # ── EARLIEST / ASAP ───────────────────────────────────────────────────────
    if re.search(r"\b(asap|as soon as possible|soonest|sometime soon|earliest available|earliest)\b", t, re.I):
        return DateResult(pref_mode="EARLIEST")

    # ── Relative day expressions ──────────────────────────────────────────────
    if re.search(r"\btoday\b", t, re.I):
        return DateResult(date=today)
    if re.search(r"\btomorrow\b", t, re.I):
        if re.search(r"\bday after tomorrow\b", t, re.I):
            return DateResult(date=today + timedelta(days=2))
        return DateResult(date=today + timedelta(days=1))
    if re.search(r"\bday after tomorrow\b", t, re.I):
        return DateResult(date=today + timedelta(days=2))
    m = re.search(r"\bin (\d+) days?\b", t, re.I)
    if m:
        return DateResult(date=today + timedelta(days=int(m.group(1))))

    # ── "next week" / "this weekend" ─────────────────────────────────────────
    if re.search(r"\bnext week\b", t, re.I):
        anchor = _monday_of_next_week(today)
        return DateResult(hint="NEXT_WEEK", week_anchor=anchor)
    if re.search(r"\bthis weekend\b", t, re.I):
        # Saturday of the current week
        days_to_sat = (5 - today.weekday()) % 7
        anchor = today + timedelta(days=days_to_sat)
        return DateResult(hint="THIS_WEEKEND", week_anchor=anchor)

    # ── Trailing time window ("tomorrow morning", "friday afternoon") ─────────
    window_match = re.search(r"\b(morning|afternoon|evening)\b", t, re.I)
    time_window: str | None = None
    if window_match:
        w = window_match.group(1).lower()
        if w == "morning":
            time_window = "MORNING"
        elif w == "afternoon":
            time_window = "AFTERNOON"
        elif w == "evening":
            time_window = None  # OUT_OF_HOURS handled by time parser
        # Remove the window word so it doesn't confuse date parsing
        t_no_window = t[:window_match.start()].strip() + " " + t[window_match.end():].strip()
        t_no_window = t_no_window.strip()
    else:
        t_no_window = t

    # ── "this friday" / "next friday" ────────────────────────────────────────
    m = re.search(r"\bthis (" + "|".join(_WEEKDAYS) + r")\b", t_no_window, re.I)
    if m:
        wd = _WEEKDAYS[m.group(1).lower()]
        d = _next_weekday(today, wd, strict=False)
        return DateResult(date=d, time_window=time_window)

    m = re.search(r"\bnext (" + "|".join(_WEEKDAYS) + r")\b", t_no_window, re.I)
    if m:
        wd = _WEEKDAYS[m.group(1).lower()]
        anchor = _monday_of_next_week(today)
        # Next Mon–Sun week: find that weekday in the next week starting from anchor
        d = anchor + timedelta(days=wd)
        return DateResult(date=d, time_window=time_window)

    # ── Weekday alone (if week_anchor is set, resolve inside that week) ───────
    m = re.search(r"\b(" + "|".join(_WEEKDAYS) + r")\b", t_no_window, re.I)
    if m:
        wd = _WEEKDAYS[m.group(1).lower()]

        # Check for "weekday the Nth" conflict
        ordinal_m = re.search(r"\bthe (\d{1,2})(st|nd|rd|th)?\b", t_no_window, re.I)
        if ordinal_m:
            day_num = int(ordinal_m.group(1))
            weekday_date = (
                week_anchor + timedelta(days=wd) if week_anchor
                else (_next_weekday(today, wd, strict=not for_verification))
            )
            ordinal_date = _next_occurrence_of_day(today, day_num)
            if ordinal_date and weekday_date and weekday_date != ordinal_date:
                return DateResult(conflict=(weekday_date, ordinal_date))
            if ordinal_date:
                return DateResult(date=ordinal_date, time_window=time_window)

        if week_anchor is not None:
            d = week_anchor + timedelta(days=wd)
        elif for_verification:
            d = _next_weekday(today, wd, strict=False)
        else:
            d = _next_weekday(today, wd, strict=True)
        return DateResult(date=d, time_window=time_window)

    # ── "the 3rd", "on the 21st" ──────────────────────────────────────────────
    m = re.search(r"\b(?:the |on the )?(\d{1,2})(st|nd|rd|th)\b", t_no_window, re.I)
    if m:
        day_num = int(m.group(1))
        d = _next_occurrence_of_day(today, day_num)
        if d:
            return DateResult(date=d, time_window=time_window)

    # ── "november 3", "3 november", "11/3", "11-3" ───────────────────────────
    month_word = "|".join(_MONTH_NAMES)
    # "Month Day" or "Day Month"
    m = re.search(rf"\b({month_word})\s+(\d{{1,2}})\b", t_no_window, re.I)
    if not m:
        m = re.search(rf"\b(\d{{1,2}})\s+({month_word})\b", t_no_window, re.I)
        if m:
            # swap groups
            month_str = m.group(2)
            day_num = int(m.group(1))
        else:
            month_str = ""
            day_num = 0
    else:
        month_str = m.group(1)
        day_num = int(m.group(2))

    if month_str:
        month_num = _MONTH_NAMES[month_str.lower()]
        d = _next_occurrence_of_day(today, day_num, month=month_num)
        if d:
            return DateResult(date=d, time_window=time_window)

    # Numeric "10/30" or "10-30"
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})\b", t_no_window)
    if m:
        month_num = int(m.group(1))
        day_num = int(m.group(2))
        if 1 <= month_num <= 12 and 1 <= day_num <= 31:
            d = _next_occurrence_of_day(today, day_num, month=month_num)
            if d:
                return DateResult(date=d, time_window=time_window)

    return DateResult(error="no date found")
