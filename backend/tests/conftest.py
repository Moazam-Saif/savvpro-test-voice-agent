"""
tests/conftest.py – Shared pytest fixtures.
"""
from __future__ import annotations

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from assistant.clock import FixedClock
from assistant.domain.codes import CodeGenerator
from assistant.domain.repository import InMemoryBookingRepository
from assistant.domain.seed import build_closed_dates, seed_repository
from assistant.domain.service import BookingService


DEMO_NOW = datetime.fromisoformat("2026-10-26T14:00:00-04:00")   # EDT
CLINIC_TZ = ZoneInfo("America/New_York")


@pytest.fixture
def fixed_clock():
    return FixedClock(at=DEMO_NOW)


@pytest.fixture
def tz():
    return CLINIC_TZ


@pytest.fixture
def closed_dates(fixed_clock, tz):
    return build_closed_dates(fixed_clock, tz)


@pytest.fixture
def empty_repo():
    return InMemoryBookingRepository()


@pytest.fixture
def code_gen():
    return CodeGenerator(seed=42)


@pytest.fixture
def booking_service(empty_repo, fixed_clock, tz, closed_dates, code_gen):
    return BookingService(
        repository=empty_repo,
        clock=fixed_clock,
        tz=tz,
        closed_dates=closed_dates,
        code_gen=code_gen,
    )


@pytest.fixture
def seeded_repo(fixed_clock, tz, closed_dates):
    repo = InMemoryBookingRepository()
    gen = CodeGenerator(seed=42)
    seed_repository(repo, fixed_clock, tz, closed_dates, gen)
    return repo
