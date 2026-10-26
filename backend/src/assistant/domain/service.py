"""
domain/service.py – BookingService and BookingPort.

BookingService is the ONLY writer of bookings (decision 9).
It re-validates every domain rule under the repository lock before
creating or cancelling a booking, so invalid or occupied slots can never
be committed even if the brain sends a bad Proposal (I3).

BookingPort is the interface the brain sees (via Ports).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from assistant.clock import Clock, local_to_utc, to_local
from assistant.domain.availability import (
    alternatives,
    check_date,
    check_time,
    find_next_available,
    is_free,
)
from assistant.domain.codes import CodeGenerator
from assistant.domain.hours import SLOT_GRID_MINUTES
from assistant.domain.models import (
    Booking,
    DateCheckReason,
    DuplicateBooking,
    InvalidSlot,
    NameMatch,
    Service,
    SlotOption,
    SlotTaken,
    TimeCheckReason,
)
from assistant.domain.repository import InMemoryBookingRepository


# ── BookingPort ───────────────────────────────────────────────────────────────

class BookingPort(Protocol):
    """The only view of the repository the brain is allowed to use."""

    def is_free(self, start: datetime, duration_minutes: int) -> bool: ...
    def alternatives(
        self,
        d: date,
        t: "datetime.time",  # type: ignore[name-defined]
        duration_minutes: int,
        excluded_dates: set[date] | None,
        excluded_weekdays: set[int] | None,
        rejected_starts: set[datetime] | None,
    ) -> list[SlotOption]: ...
    def find_next_available(
        self,
        duration_minutes: int,
        from_dt: datetime,
        time_window: str | None,
        excluded_dates: set[date] | None,
        excluded_weekdays: set[int] | None,
        rejected_starts: set[datetime] | None,
        n: int,
    ) -> list[SlotOption]: ...
    def find_by_name(self, name: str, include_past: bool = False) -> list[NameMatch]: ...
    def find_by_code(self, code: str) -> Booking | None: ...
    def get(self, booking_id: str) -> Booking | None: ...
    def book(self, proposal: "BookingProposal") -> Booking: ...
    def cancel(self, booking_id: str) -> bool: ...


@dataclass(frozen=True)
class BookingProposal:
    """Thin value object passed from the brain to BookingService.book()."""
    patient_name: str
    service: Service
    start: datetime        # Naive clinic-local
    for_other: bool = False


# ── BookingService ────────────────────────────────────────────────────────────

class BookingService:
    """
    The only writer of bookings.  book() runs under the repository lock
    and re-validates all domain rules (I3).
    """

    def __init__(
        self,
        repository: InMemoryBookingRepository,
        clock: Clock,
        tz: ZoneInfo,
        closed_dates: dict[date, str],
        code_gen: CodeGenerator,
    ) -> None:
        self._repo = repository
        self._clock = clock
        self._tz = tz
        self._closed_dates = closed_dates
        self._code_gen = code_gen

    # ── Read-side helpers (delegated to availability module) ──────────────────

    def is_free(self, start: datetime, duration_minutes: int) -> bool:
        bookings = self._repo.list_bookings(start.date())
        return is_free(start, duration_minutes, bookings)

    def alternatives(
        self,
        d: date,
        t: "datetime.time",
        duration_minutes: int,
        excluded_dates: set[date] | None = None,
        excluded_weekdays: set[int] | None = None,
        rejected_starts: set[datetime] | None = None,
    ) -> list[SlotOption]:
        return alternatives(
            d=d,
            t=t,
            duration_minutes=duration_minutes,
            bookings=self._repo.all_bookings(),
            now_utc=self._clock.now_utc(),
            tz=self._tz,
            closed_dates=self._closed_dates,
            excluded_dates=excluded_dates,
            excluded_weekdays=excluded_weekdays,
            rejected_starts=rejected_starts,
        )

    def find_next_available(
        self,
        duration_minutes: int,
        from_dt: datetime,
        time_window: str | None = None,
        excluded_dates: set[date] | None = None,
        excluded_weekdays: set[int] | None = None,
        rejected_starts: set[datetime] | None = None,
        n: int = 1,
    ) -> list[SlotOption]:
        return find_next_available(
            duration_minutes=duration_minutes,
            from_dt=from_dt,
            now_utc=self._clock.now_utc(),
            tz=self._tz,
            bookings=self._repo.all_bookings(),
            closed_dates=self._closed_dates,
            excluded_dates=excluded_dates,
            excluded_weekdays=excluded_weekdays,
            rejected_starts=rejected_starts,
            time_window=time_window,
            n=n,
        )

    def find_by_name(self, name: str, include_past: bool = False) -> list[NameMatch]:
        return self._repo.find_by_name(name, include_past=include_past)

    def find_by_code(self, code: str) -> Booking | None:
        return self._repo.find_by_code(code)

    def get(self, booking_id: str) -> Booking | None:
        return self._repo.get(booking_id)

    # ── Write-side ────────────────────────────────────────────────────────────

    def book(self, proposal: BookingProposal) -> Booking:
        """
        Create a booking from a Proposal.
        Re-validates all domain rules under the repository lock (I3).
        Raises InvalidSlot or SlotTaken on failure.
        """
        now_utc = self._clock.now_utc()
        duration_minutes = proposal.service.duration_minutes

        # ── Re-validate date ─────────────────────────────────────────────────
        date_result = check_date(
            proposal.start.date(), now_utc, self._tz, self._closed_dates
        )
        if not date_result.ok:
            raise InvalidSlot(date_result.reason)

        # ── Re-validate time ─────────────────────────────────────────────────
        time_result = check_time(
            proposal.start.time(), now_utc, self._tz,
            d=proposal.start.date(), duration_minutes=duration_minutes,
        )
        if not time_result.ok:
            raise InvalidSlot(time_result.reason, time_result.context)

        # ── Build Booking object ─────────────────────────────────────────────
        end = proposal.start + timedelta(minutes=duration_minutes)
        now_local = to_local(now_utc, self._tz)
        code = self._code_gen.next_code(self._repo.all_codes())

        booking = Booking(
            id=str(uuid.uuid4()),
            patient_name=proposal.patient_name,
            service=proposal.service,
            start=proposal.start,
            end=end,
            code=code,
            created_at=now_local,
        )

        # ── Attempt atomic insert (raises SlotTaken / DuplicateBooking) ──────
        return self._repo.book(booking)

    def cancel(self, booking_id: str) -> bool:
        """Cancel a booking by id.  Returns True if found and cancelled."""
        return self._repo.cancel(booking_id)
