"""
domain/models.py – Core domain value objects and entities.

All datetimes stored here are NAIVE clinic-local wall-clock times
(post-conversion via clock.to_local).  UTC conversion is done only
at the boundary in clock.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


# ── Service ───────────────────────────────────────────────────────────────────

class Service(str, Enum):
    CLEANING = "cleaning"
    CHECKUP = "checkup"
    FILLING = "filling"
    WHITENING = "whitening"
    EXTRACTION = "extraction"
    ROOT_CANAL = "root_canal"

    @property
    def duration_minutes(self) -> int:
        return _SERVICE_DURATIONS[self]

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ")


_SERVICE_DURATIONS: dict[Service, int] = {
    Service.CLEANING: 30,
    Service.CHECKUP: 30,
    Service.FILLING: 60,
    Service.WHITENING: 60,
    Service.EXTRACTION: 60,
    Service.ROOT_CANAL: 90,
}


# ── Booking ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Booking:
    """An immutable confirmed appointment."""

    id: str                    # UUID4 string
    patient_name: str          # Titlecased, normalized
    service: Service
    start: datetime            # Naive clinic-local
    end: datetime              # Naive clinic-local (start + duration)
    code: str                  # 4-digit string, unique among all bookings
    created_at: datetime       # Naive clinic-local at creation time

    @property
    def date(self) -> date:
        return self.start.date()

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


# ── Name-match result ──────────────────────────────────────────────────────────

class NameMatchTier(str, Enum):
    EXACT = "EXACT"   # Normalized full names are equal
    CLOSE = "CLOSE"   # difflib ratio >= 0.85


@dataclass(frozen=True)
class NameMatch:
    booking: Booking
    tier: NameMatchTier


# ── Availability helpers ───────────────────────────────────────────────────────

class DateCheckReason(str, Enum):
    OK = "OK"
    PAST = "PAST"
    BEYOND_HORIZON = "BEYOND_HORIZON"
    CLOSED_DATE = "CLOSED_DATE"
    CLOSED_DAY = "CLOSED_DAY"


class TimeCheckReason(str, Enum):
    OK = "OK"
    PAST = "PAST"
    TOO_SOON = "TOO_SOON"
    OFF_GRID = "OFF_GRID"
    LUNCH = "LUNCH"
    BEFORE_OPEN = "BEFORE_OPEN"
    AFTER_CLOSE = "AFTER_CLOSE"


@dataclass(frozen=True)
class DateCheckResult:
    reason: DateCheckReason
    closed_reason_label: str = ""   # e.g. "Staff training day"

    @property
    def ok(self) -> bool:
        return self.reason == DateCheckReason.OK


@dataclass(frozen=True)
class TimeCheckContext:
    """Carries day-aware details so NLG can build exact error messages (X5)."""
    open_time: str          # e.g. "09:00" or "10:00" on Saturday
    close_time: str         # e.g. "17:00" or "14:00" on Saturday
    last_valid_start: str   # last start that fits duration before close
    last_start_before_lunch: str | None  # None if lunch is not relevant
    duration_minutes: int


@dataclass(frozen=True)
class TimeCheckResult:
    reason: TimeCheckReason
    context: TimeCheckContext | None = None

    @property
    def ok(self) -> bool:
        return self.reason == TimeCheckReason.OK


@dataclass(frozen=True)
class SlotOption:
    """A single availability option surfaced to the brain."""
    start: datetime           # Naive clinic-local
    end: datetime             # Naive clinic-local
    label: str                # Human-readable, e.g. "Friday, October 30th at 3 PM"


# ── Exceptions ────────────────────────────────────────────────────────────────

class SlotTaken(Exception):
    """Raised by the repository when a slot is already occupied."""


class DuplicateBooking(SlotTaken):
    """Raised when the same patient already has an overlapping booking."""


class InvalidSlot(Exception):
    """Raised by BookingService when domain validation fails on commit."""

    def __init__(self, reason: DateCheckReason | TimeCheckReason, context: TimeCheckContext | None = None) -> None:
        self.reason = reason
        self.context = context
        super().__init__(str(reason))
