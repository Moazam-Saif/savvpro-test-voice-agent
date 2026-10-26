"""
domain/repository.py – In-memory booking repository behind a Protocol.

All mutations run under a threading.RLock so a single uvicorn worker
handles concurrent requests safely.  The Protocol (BookingRepository) is
what the rest of the code depends on; InMemoryBookingRepository is the
concrete implementation.

Name-matching rules (4.2):
  - Normalization: casefold, strip punctuation, collapse whitespace, drop titles.
  - EXACT: normalized full names equal.
  - CLOSE: difflib.SequenceMatcher ratio >= 0.85 on full names.
  - NO last-name-only matching (X7).
  - Past bookings excluded by default.
"""
from __future__ import annotations

import difflib
import re
import threading
import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from assistant.domain.models import (
    Booking,
    DuplicateBooking,
    NameMatch,
    NameMatchTier,
    SlotTaken,
)


# ── Name normalization ────────────────────────────────────────────────────────

_TITLES = {"mr", "mrs", "ms", "dr", "miss", "prof"}
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")

CLOSE_THRESHOLD = 0.85


def normalize_name(name: str) -> str:
    """Casefold, strip punctuation, drop titles, collapse whitespace."""
    tokens = _PUNCT.sub(" ", name).casefold().split()
    tokens = [t for t in tokens if t not in _TITLES]
    return _WS.sub(" ", " ".join(tokens)).strip()


# ── Protocol ──────────────────────────────────────────────────────────────────

@runtime_checkable
class BookingRepository(Protocol):
    def list_bookings(self, d: "datetime.date") -> list[Booking]: ...  # type: ignore[name-defined]
    def find_by_name(self, name: str, include_past: bool = False) -> list[NameMatch]: ...
    def find_by_code(self, code: str) -> Booking | None: ...
    def book(self, booking: Booking) -> Booking: ...
    def cancel(self, booking_id: str) -> bool: ...
    def get(self, booking_id: str) -> Booking | None: ...
    def all_bookings(self) -> list[Booking]: ...
    def all_codes(self) -> set[str]: ...


# ── In-memory implementation ──────────────────────────────────────────────────

class InMemoryBookingRepository:
    """Thread-safe in-memory repository (single-worker only)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store: dict[str, Booking] = {}   # id → Booking

    # ── Queries ───────────────────────────────────────────────────────────────

    def list_bookings(self, d: "datetime.date") -> list[Booking]:  # type: ignore[override]
        with self._lock:
            return [b for b in self._store.values() if b.date == d]

    def find_by_name(self, name: str, include_past: bool = False) -> list[NameMatch]:
        needle = normalize_name(name)
        now = datetime.now()   # naive; used only for past-filter approximation
        matches: list[NameMatch] = []
        with self._lock:
            for b in self._store.values():
                if not include_past and b.start < now:
                    continue
                hay = normalize_name(b.patient_name)
                if hay == needle:
                    matches.append(NameMatch(booking=b, tier=NameMatchTier.EXACT))
                else:
                    ratio = difflib.SequenceMatcher(None, needle, hay).ratio()
                    if ratio >= CLOSE_THRESHOLD:
                        matches.append(NameMatch(booking=b, tier=NameMatchTier.CLOSE))
        # Sort: EXACT first, then by start time
        matches.sort(key=lambda m: (0 if m.tier == NameMatchTier.EXACT else 1, m.booking.start))
        return matches

    def find_by_code(self, code: str) -> Booking | None:
        with self._lock:
            for b in self._store.values():
                if b.code == code:
                    return b
        return None

    def get(self, booking_id: str) -> Booking | None:
        with self._lock:
            return self._store.get(booking_id)

    def all_bookings(self) -> list[Booking]:
        with self._lock:
            return list(self._store.values())

    def all_codes(self) -> set[str]:
        with self._lock:
            return {b.code for b in self._store.values()}

    # ── Mutations (all under the lock) ────────────────────────────────────────

    def book(self, booking: Booking) -> Booking:
        """
        Store a booking.
        Raises SlotTaken on overlap, DuplicateBooking if the same patient
        already has an overlapping booking.
        """
        with self._lock:
            needle = normalize_name(booking.patient_name)
            for b in self._store.values():
                # Overlap check: [start, end) intervals
                if b.start < booking.end and b.end > booking.start:
                    if normalize_name(b.patient_name) == needle:
                        raise DuplicateBooking(
                            f"Patient {booking.patient_name!r} already has an "
                            f"overlapping booking at {b.start}"
                        )
                    raise SlotTaken(f"Slot at {booking.start} is already taken")
            self._store[booking.id] = booking
            return booking

    def cancel(self, booking_id: str) -> bool:
        """Remove a booking.  Returns True if it existed."""
        with self._lock:
            if booking_id in self._store:
                del self._store[booking_id]
                return True
            return False

    def _insert_raw(self, booking: Booking) -> None:
        """Used by seed data to insert without overlap checking."""
        with self._lock:
            self._store[booking.id] = booking
