"""
domain/availability.py – Pure availability functions.

All functions are stateless and receive `now_utc` explicitly so they are
fully testable with a FixedClock.  They never touch the system clock.

Precedence for reason reporting (4.4):
  PAST > BEYOND_HORIZON > CLOSED_DATE > CLOSED_DAY > TOO_SOON >
  OFF_GRID > LUNCH > BEFORE_OPEN > AFTER_CLOSE
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from assistant.clock import to_local, local_to_utc
from assistant.domain.hours import (
    BOOKING_HORIZON_DAYS,
    LUNCH_END,
    LUNCH_START,
    MIN_LEAD_TIME_HOURS,
    SLOT_GRID_MINUTES,
    day_close_time,
    day_open_time,
    has_lunch,
    is_open_day,
    windows_for_day,
)
from assistant.domain.models import (
    Booking,
    DateCheckReason,
    DateCheckResult,
    Service,
    SlotOption,
    TimeCheckContext,
    TimeCheckReason,
    TimeCheckResult,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _format_time(t: time) -> str:
    """Format a time object as 'HH:MM' for NLG context."""
    return t.strftime("%H:%M")


def _slot_fits_in_window(start: time, duration_minutes: int, wopen: time, wclose: time) -> bool:
    """True if [start, start+duration) is fully inside [wopen, wclose)."""
    end_minutes = start.hour * 60 + start.minute + duration_minutes
    close_minutes = wclose.hour * 60 + wclose.minute
    start_minutes = start.hour * 60 + start.minute
    open_minutes = wopen.hour * 60 + wopen.minute
    return start_minutes >= open_minutes and end_minutes <= close_minutes


def _on_grid(t: time) -> bool:
    return t.minute % SLOT_GRID_MINUTES == 0 and t.second == 0


def _grid_times_for_day(d: date) -> list[time]:
    """All grid-aligned start times inside all open windows for the day."""
    result: list[time] = []
    for w in windows_for_day(d):
        cur = w.open
        while True:
            cur_minutes = cur.hour * 60 + cur.minute
            close_minutes = w.close.hour * 60 + w.close.minute
            if cur_minutes >= close_minutes:
                break
            result.append(cur)
            cur = time((cur_minutes + SLOT_GRID_MINUTES) // 60,
                       (cur_minutes + SLOT_GRID_MINUTES) % 60)
    return result


# ── check_date ────────────────────────────────────────────────────────────────

def check_date(
    d: date,
    now_utc: datetime,
    tz: ZoneInfo,
    closed_dates: dict[date, str],
) -> DateCheckResult:
    """Validate a calendar date.  Returns the first failing reason or OK."""
    now_local = to_local(now_utc, tz)
    today = now_local.date()
    horizon = today + timedelta(days=BOOKING_HORIZON_DAYS)

    if d < today:
        return DateCheckResult(DateCheckReason.PAST)
    if d > horizon:
        return DateCheckResult(DateCheckReason.BEYOND_HORIZON)
    if d in closed_dates:
        return DateCheckResult(DateCheckReason.CLOSED_DATE, closed_dates[d])
    if not is_open_day(d):
        return DateCheckResult(DateCheckReason.CLOSED_DAY)
    return DateCheckResult(DateCheckReason.OK)


# ── check_time ────────────────────────────────────────────────────────────────

def check_time(
    t: time,
    now_utc: datetime,
    tz: ZoneInfo,
    d: date | None = None,
    duration_minutes: int = SLOT_GRID_MINUTES,
) -> TimeCheckResult:
    """Validate a start time.

    Without a date, checks only against the widest hours and skips the lunch
    test.  Without a duration, assumes 30 minutes.

    Reason precedence: PAST > TOO_SOON > OFF_GRID > LUNCH > BEFORE_OPEN > AFTER_CLOSE.
    """
    now_local = to_local(now_utc, tz)

    # ── Determine reference day hours ────────────────────────────────────────
    if d is not None:
        open_t = day_open_time(d)
        close_t = day_close_time(d)
        if open_t is None or close_t is None:
            # Closed day – caller should have used check_date first
            return TimeCheckResult(TimeCheckReason.BEFORE_OPEN, _make_context(d, duration_minutes))
    else:
        # Use the widest possible hours across all open days
        open_t = time(9, 0)
        close_t = time(17, 0)

    # ── Build the candidate datetime for elapsed-time checks (T1) ────────────
    check_date_val = d if d is not None else now_local.date()
    candidate_naive = datetime.combine(check_date_val, t)
    candidate_utc = local_to_utc(candidate_naive, tz)

    # PAST
    if candidate_utc <= now_utc:
        return TimeCheckResult(TimeCheckReason.PAST, _make_context(d, duration_minutes) if d else None)

    # TOO_SOON
    lead_time_utc = now_utc + timedelta(hours=MIN_LEAD_TIME_HOURS)
    if candidate_utc < lead_time_utc:
        return TimeCheckResult(TimeCheckReason.TOO_SOON, _make_context(d, duration_minutes) if d else None)

    # OFF_GRID
    if not _on_grid(t):
        return TimeCheckResult(TimeCheckReason.OFF_GRID, _make_context(d, duration_minutes) if d else None)

    # BEFORE_OPEN
    assert open_t is not None
    assert close_t is not None
    if t < open_t:
        return TimeCheckResult(TimeCheckReason.BEFORE_OPEN, _make_context(d, duration_minutes) if d else None)

    # AFTER_CLOSE (slot must end before or at close; check vs last valid start)
    close_minutes = close_t.hour * 60 + close_t.minute
    last_valid_start_minutes = close_minutes - duration_minutes
    t_minutes = t.hour * 60 + t.minute
    if t_minutes > last_valid_start_minutes:
        return TimeCheckResult(TimeCheckReason.AFTER_CLOSE, _make_context(d, duration_minutes) if d else None)

    # LUNCH (only when we have a concrete date and that date has lunch)
    if d is not None and has_lunch(d):
        lunch_start_m = LUNCH_START.hour * 60 + LUNCH_START.minute
        lunch_end_m = LUNCH_END.hour * 60 + LUNCH_END.minute
        end_minutes = t_minutes + duration_minutes
        if t_minutes < lunch_end_m and end_minutes > lunch_start_m:
            # Slot overlaps lunch closure
            # Classify: if the offending window ends at lunch → LUNCH, else AFTER_CLOSE (X3)
            # Since we are inside Mon-Fri and the window that ends at 13:00 is the morning
            # window, any overlap with lunch → LUNCH
            return TimeCheckResult(TimeCheckReason.LUNCH, _make_context(d, duration_minutes))

    return TimeCheckResult(TimeCheckReason.OK, _make_context(d, duration_minutes) if d else None)


def _make_context(d: date | None, duration_minutes: int) -> TimeCheckContext:
    if d is None:
        return TimeCheckContext(
            open_time="09:00",
            close_time="17:00",
            last_valid_start=_format_time(time(17 - duration_minutes // 60,
                                               60 - duration_minutes % 60 if duration_minutes % 60 else 0)),
            last_start_before_lunch=None,
            duration_minutes=duration_minutes,
        )
    open_t = day_open_time(d) or time(9, 0)
    close_t = day_close_time(d) or time(17, 0)
    close_minutes = close_t.hour * 60 + close_t.minute
    last_valid_m = close_minutes - duration_minutes
    last_valid = time(last_valid_m // 60, last_valid_m % 60)

    last_before_lunch: str | None = None
    if has_lunch(d):
        lunch_start_m = LUNCH_START.hour * 60 + LUNCH_START.minute
        lbl_m = lunch_start_m - duration_minutes
        if lbl_m >= open_t.hour * 60 + open_t.minute:
            last_before_lunch = _format_time(time(lbl_m // 60, lbl_m % 60))

    return TimeCheckContext(
        open_time=_format_time(open_t),
        close_time=_format_time(close_t),
        last_valid_start=_format_time(last_valid),
        last_start_before_lunch=last_before_lunch,
        duration_minutes=duration_minutes,
    )


# ── is_free ───────────────────────────────────────────────────────────────────

def is_free(
    start: datetime,
    duration_minutes: int,
    bookings: list[Booking],
) -> bool:
    """True if no existing booking overlaps [start, start+duration)."""
    end = start + timedelta(minutes=duration_minutes)
    for b in bookings:
        if b.start < end and b.end > start:
            return False
    return True


# ── alternatives ──────────────────────────────────────────────────────────────

def alternatives(
    d: date,
    t: time,
    duration_minutes: int,
    bookings: list[Booking],
    now_utc: datetime,
    tz: ZoneInfo,
    closed_dates: dict[date, str],
    excluded_dates: set[date] | None = None,
    excluded_weekdays: set[int] | None = None,
    rejected_starts: set[datetime] | None = None,
    n: int = 2,
) -> list[SlotOption]:
    """
    Return up to *n* (max 3) alternative free slots.

    Same-day free starts ordered by distance in minutes from *t*,
    preferring one before and one after.  If the day yields fewer than *n*,
    fill from the next days within the horizon.
    """
    excluded_dates = excluded_dates or set()
    excluded_weekdays = excluded_weekdays or set()
    rejected_starts = rejected_starts or set()
    n = min(n, 3)

    target_minutes = t.hour * 60 + t.minute
    options: list[SlotOption] = []

    def _free_starts_on_day(day: date) -> list[tuple[int, datetime]]:
        """Returns (distance_minutes, start_dt) pairs sorted by distance."""
        if day in excluded_dates:
            return []
        if day.weekday() in excluded_weekdays:
            return []
        if not is_open_day(day) or day in closed_dates:
            return []
        day_bookings = [b for b in bookings if b.date == day]
        grid = _grid_times_for_day(day)
        result: list[tuple[int, datetime]] = []
        for gt in grid:
            start_dt = datetime.combine(day, gt)
            if start_dt in rejected_starts:
                continue
            result_utc = local_to_utc(start_dt, tz)
            lead_cutoff = now_utc + timedelta(hours=MIN_LEAD_TIME_HOURS)
            if result_utc <= now_utc or result_utc < lead_cutoff:
                continue
            end_dt = start_dt + timedelta(minutes=duration_minutes)
            # Verify the slot fits inside a single open window
            fits = False
            for w in windows_for_day(day):
                w_open_dt = datetime.combine(day, w.open)
                w_close_dt = datetime.combine(day, w.close)
                if start_dt >= w_open_dt and end_dt <= w_close_dt:
                    fits = True
                    break
            if not fits:
                continue
            if not is_free(start_dt, duration_minutes, day_bookings):
                continue
            dist = abs((gt.hour * 60 + gt.minute) - target_minutes)
            result.append((dist, start_dt))
        result.sort(key=lambda x: (x[0], x[1]))
        return result

    # ── Same-day candidates ───────────────────────────────────────────────────
    same_day = _free_starts_on_day(d)
    # Try to pick one before and one after the requested time
    before = [(dist, dt) for dist, dt in same_day if dt.time() < t]
    after = [(dist, dt) for dist, dt in same_day if dt.time() >= t]
    picked: list[datetime] = []
    for _, dt in before[-1:]:   # last "before" = closest before
        picked.append(dt)
    for _, dt in after[:1]:     # first "after" = closest after
        if dt not in picked:
            picked.append(dt)
    # If we still need more, use remaining same-day
    for _, dt in same_day:
        if len(picked) >= n:
            break
        if dt not in picked:
            picked.append(dt)

    for dt in picked[:n]:
        options.append(_make_slot_option(dt, duration_minutes))

    # ── Next-day fill ─────────────────────────────────────────────────────────
    if len(options) < n:
        today = to_local(now_utc, tz).date()
        horizon = today + timedelta(days=BOOKING_HORIZON_DAYS)
        cursor = d + timedelta(days=1)
        while cursor <= horizon and len(options) < n:
            day_opts = _free_starts_on_day(cursor)
            if day_opts:
                _, best_dt = day_opts[0]
                options.append(_make_slot_option(best_dt, duration_minutes))
            cursor += timedelta(days=1)

    return options[:n]


def _make_slot_option(start: datetime, duration_minutes: int) -> SlotOption:
    end = start + timedelta(minutes=duration_minutes)
    label = _format_slot_label(start)
    return SlotOption(start=start, end=end, label=label)


def _format_slot_label(dt: datetime) -> str:
    """Human-readable slot label, e.g. 'Friday, October 30th at 3 PM'."""
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    day = dt.strftime("%-d") if hasattr(dt, "strftime") else str(dt.day)
    # ordinal suffix
    d = dt.day
    suffix = "th" if 11 <= d <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
    hour = dt.hour
    minute = dt.minute
    ampm = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    time_str = f"{hour12}:{minute:02d} {ampm}" if minute else f"{hour12} {ampm}"
    return (
        f"{day_names[dt.weekday()]}, {month_names[dt.month]} {d}{suffix} at {time_str}"
    )


# ── find_next_available ───────────────────────────────────────────────────────

def find_next_available(
    duration_minutes: int,
    from_dt: datetime,
    now_utc: datetime,
    tz: ZoneInfo,
    bookings: list[Booking],
    closed_dates: dict[date, str],
    excluded_dates: set[date] | None = None,
    excluded_weekdays: set[int] | None = None,
    rejected_starts: set[datetime] | None = None,
    time_window: str | None = None,   # "MORNING" | "AFTERNOON" | None
    n: int = 1,
) -> list[SlotOption]:
    """
    Find the first *n* free slots on or after *from_dt*, within the 60-day
    horizon.  Respects exclusions and rejected starts.

    For 'earliest available' with no date (U4), pass from_dt = to_local(now_utc, tz).
    """
    excluded_dates = excluded_dates or set()
    excluded_weekdays = excluded_weekdays or set()
    rejected_starts = rejected_starts or set()

    now_local = to_local(now_utc, tz)
    lead_cutoff_local = to_local(
        now_utc + timedelta(hours=MIN_LEAD_TIME_HOURS), tz
    )
    horizon = now_local.date() + timedelta(days=BOOKING_HORIZON_DAYS)

    start_date = from_dt.date() if isinstance(from_dt, datetime) else from_dt
    results: list[SlotOption] = []

    cursor = start_date
    while cursor <= horizon and len(results) < n:
        if cursor in excluded_dates or cursor in closed_dates or not is_open_day(cursor):
            cursor += timedelta(days=1)
            continue
        if cursor.weekday() in excluded_weekdays:
            cursor += timedelta(days=1)
            continue

        day_bookings = [b for b in bookings if b.date == cursor]
        for gt in _grid_times_for_day(cursor):
            start_dt = datetime.combine(cursor, gt)
            if start_dt in rejected_starts:
                continue
            # Lead time check (compare via UTC per T1)
            start_utc = local_to_utc(start_dt, tz)
            if start_utc <= now_utc or start_dt < lead_cutoff_local:
                continue
            # Time window filter (X1/X4 compliant)
            if time_window == "MORNING" and gt.hour >= 12:
                continue
            if time_window == "AFTERNOON" and gt.hour < 12:
                continue
            # Must fit in a single open window
            end_dt = start_dt + timedelta(minutes=duration_minutes)
            fits = any(
                datetime.combine(cursor, w.open) <= start_dt
                and end_dt <= datetime.combine(cursor, w.close)
                for w in windows_for_day(cursor)
            )
            if not fits:
                continue
            if not is_free(start_dt, duration_minutes, day_bookings):
                continue
            results.append(_make_slot_option(start_dt, duration_minutes))
            if len(results) >= n:
                break

        cursor += timedelta(days=1)

    return results
