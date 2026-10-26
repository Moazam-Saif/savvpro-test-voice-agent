"""
brain/ports.py – Ports: the only way the brain touches the outside world.

The brain receives a Ports object on every turn.  All I/O (clock, bookings)
passes through this boundary.  Tests inject fakes that implement the same
interface.

Architecture rule: nothing in brain/ imports from api/ or does raw I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from assistant.clock import Clock, to_local
from assistant.domain.service import BookingPort, BookingService


@dataclass
class Ports:
    """
    Container for all external capabilities injected into the brain.

    clock: Clock  – the time source (SystemClock or FixedClock).
    bookings: BookingPort – read/write access to appointments.
    tz: ZoneInfo – the clinic's local timezone.
    """
    clock: Clock
    bookings: BookingPort
    tz: ZoneInfo

    def now_local(self) -> datetime:
        """Return the current clinic-local naive datetime (used by the brain)."""
        return to_local(self.clock.now_utc(), self.tz)
