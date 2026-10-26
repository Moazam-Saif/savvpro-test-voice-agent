"""
domain/seed.py – Fake seed data for demos and development.

ALL data is invented.  No real people's names or details.

Rules (4.5 / X2):
  - Uses a fixed-seed generator so the demo is reproducible.
  - Never places bookings in the past, on Sundays, or on closed dates.
  - Fixed bookings are placed first; the random fill avoids them.
  - Fixed bookings sit at least 3 hours in the future.
  - Random fill covers about 35% of available slots over the next 14 days.
"""
from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from assistant.clock import Clock, to_local
from assistant.domain.availability import _grid_times_for_day, is_free
from assistant.domain.codes import CodeGenerator
from assistant.domain.hours import is_open_day
from assistant.domain.models import Booking, Service
from assistant.domain.repository import InMemoryBookingRepository


# ── Fixed bookings (always present for demos) ─────────────────────────────────
# Placed relative to now.  The exact days are computed at seed time.
_FIXED: list[dict] = [
    # Sarah Thompson – two bookings on different days (to test date disambiguation)
    {"name": "Sarah Thompson", "service": Service.CLEANING,  "day_offset": 2, "hour": 10, "minute": 0},
    {"name": "Sarah Thompson", "service": Service.CHECKUP,   "day_offset": 5, "hour": 14, "minute": 0},
    # Other demo patients
    {"name": "Ali Raza",       "service": Service.FILLING,   "day_offset": 3, "hour": 9,  "minute": 0},
    {"name": "Maria Gonzalez", "service": Service.WHITENING, "day_offset": 4, "hour": 14, "minute": 0},
]

SEED_RANDOM_SEED = 20261026   # reproducible
SEED_FILL_RATIO = 0.35
SEED_WINDOW_DAYS = 14
FIXED_LEAD_HOURS = 3


def _next_open_day(from_date: date, closed_dates: dict[date, str], offset: int) -> date:
    """Return the *offset*-th open weekday on or after *from_date*."""
    d = from_date
    count = 0
    while True:
        if is_open_day(d) and d not in closed_dates:
            if count == offset:
                return d
            count += 1
        d += timedelta(days=1)


def seed_repository(
    repo: InMemoryBookingRepository,
    clock: Clock,
    tz: ZoneInfo,
    closed_dates: dict[date, str],
    code_gen: CodeGenerator,
) -> list[Booking]:
    """
    Populate *repo* with fake seed data.  Returns the list of all inserted
    bookings (fixed + random fill) in chronological order.
    """
    now_utc = clock.now_utc()
    now_local = to_local(now_utc, tz)
    today = now_local.date()
    lead_cutoff = now_local + timedelta(hours=FIXED_LEAD_HOURS)

    inserted: list[Booking] = []

    # ── Fixed bookings ────────────────────────────────────────────────────────
    for spec in _FIXED:
        target_date = _next_open_day(today, closed_dates, spec["day_offset"])
        start = datetime.combine(target_date, datetime.min.time()).replace(
            hour=spec["hour"], minute=spec["minute"]
        )
        if start <= lead_cutoff:
            # Push to the next open day if too soon
            target_date = _next_open_day(target_date + timedelta(days=1), closed_dates, 0)
            start = start.replace(year=target_date.year, month=target_date.month, day=target_date.day)

        svc: Service = spec["service"]
        end = start + timedelta(minutes=svc.duration_minutes)
        code = code_gen.next_code({b.code for b in inserted})
        b = Booking(
            id=str(uuid.uuid4()),
            patient_name=spec["name"],
            service=svc,
            start=start,
            end=end,
            code=code,
            created_at=now_local,
        )
        repo._insert_raw(b)
        inserted.append(b)

    # ── Random fill (~35% of 14-day window) ──────────────────────────────────
    rng = random.Random(SEED_RANDOM_SEED)
    horizon = today + timedelta(days=SEED_WINDOW_DAYS)

    fake_names = [
        "James Carter", "Emily Nguyen", "David Kim", "Priya Patel",
        "Omar Hassan", "Sofia Reyes", "Liam O'Brien", "Nina Walsh",
        "Chen Wei", "Fatima Al-Amin",
    ]

    cursor = today
    while cursor <= horizon:
        if not is_open_day(cursor) or cursor in closed_dates:
            cursor += timedelta(days=1)
            continue
        existing_day = [b for b in inserted if b.date == cursor]
        for gt in _grid_times_for_day(cursor):
            if rng.random() > SEED_FILL_RATIO:
                continue
            start_dt = datetime.combine(cursor, gt)
            if start_dt <= lead_cutoff:
                continue
            svc = rng.choice(list(Service))
            end_dt = start_dt + timedelta(minutes=svc.duration_minutes)
            # Verify fits in a window and doesn't overlap existing
            if not is_free(start_dt, svc.duration_minutes, existing_day):
                continue
            name = rng.choice(fake_names)
            code = code_gen.next_code({b.code for b in inserted})
            b = Booking(
                id=str(uuid.uuid4()),
                patient_name=name,
                service=svc,
                start=start_dt,
                end=end_dt,
                code=code,
                created_at=now_local,
            )
            repo._insert_raw(b)
            inserted.append(b)
            existing_day.append(b)
        cursor += timedelta(days=1)

    inserted.sort(key=lambda b: b.start)
    return inserted


def build_closed_dates(clock: Clock, tz: ZoneInfo) -> dict[date, str]:
    """
    Build the CLOSED_DATES dict (X11).
    The first non-Sunday date at least 9 days ahead is closed for staff training.
    """
    now_local = to_local(clock.now_utc(), tz)
    today = now_local.date()
    d = today + timedelta(days=9)
    while d.weekday() == 6:   # Skip Sundays
        d += timedelta(days=1)
    return {d: "Staff training day"}
