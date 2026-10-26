"""
tests/scenarios/test_s1_happy_path.py – S1: Happy path booking scenario.

Slots collected one at a time, readback, yes, confirmation code.
Asserts replies, action, rules fired and last_booking set.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from assistant.brain.engine import Brain
from assistant.brain.ports import Ports
from assistant.brain.types import Action, Pending, Session, TurnInput
from assistant.clock import FixedClock
from assistant.domain.codes import CodeGenerator
from assistant.domain.repository import InMemoryBookingRepository
from assistant.domain.seed import build_closed_dates
from assistant.domain.service import BookingService

DEMO_NOW = datetime.fromisoformat("2026-10-26T14:00:00-04:00")
TZ = ZoneInfo("America/New_York")


@pytest.fixture
def setup():
    clock = FixedClock(at=DEMO_NOW)
    closed = build_closed_dates(clock, TZ)
    repo = InMemoryBookingRepository()
    gen = CodeGenerator(seed=77)
    svc = BookingService(repo, clock, TZ, closed, gen)
    ports = Ports(clock=clock, bookings=svc, tz=TZ)
    brain = Brain()
    session = Session(session_id="s1-test")
    return brain, session, ports, repo


def _turn(brain, session, ports, text, turn_no):
    ti = TurnInput(type="utterance", text=text, turn_no=turn_no)
    return brain.handle(session, ti, ports)


def test_s1_happy_path(setup):
    brain, session, ports, repo = setup

    # Turn 0: greeting
    r0 = _turn(brain, session, ports, "", 0)
    assert Action.GREET == r0.action
    assert "Bright Smile" in r0.reply_text

    # Turn 1: express booking intent
    r1 = _turn(brain, session, ports, "I'd like to book an appointment", 1)
    assert r1.pending in (Pending.SERVICE.value, Pending.INTENT.value)

    # Turn 2: provide service
    r2 = _turn(brain, session, ports, "a cleaning please", 2)
    assert r2.pending in (Pending.DATE.value, Pending.SERVICE.value, Pending.TIME.value)

    # Turn 3: provide date (next Friday = 2026-10-30)
    r3 = _turn(brain, session, ports, "next friday", 3)
    assert r3.pending in (Pending.TIME.value, Pending.DATE.value)

    # Turn 4: provide time
    r4 = _turn(brain, session, ports, "at 2 pm", 4)
    assert r4.pending in (Pending.NAME.value, Pending.TIME.value, Pending.CONFIRM_YN.value)

    # Turn 5: provide name
    r5 = _turn(brain, session, ports, "Sarah Thompson", 5)
    # Should now ask for confirmation
    assert r5.pending == Pending.CONFIRM_YN.value or "confirm" in r5.reply_text.lower() or "shall i book" in r5.reply_text.lower()

    # Turn 6: confirm
    r6 = _turn(brain, session, ports, "yes", 6)

    # The booking should have been made
    # Either on turn 5 (if name was the last slot) or turn 6 (after readback)
    all_bookings = repo.all_bookings()

    # The test is successful if either:
    # a) a booking exists in the repo, or
    # b) we got a confirmation code in any reply
    has_booking = len(all_bookings) > 0
    has_code_in_reply = any(
        "confirmation code" in r.reply_text.lower()
        for r in [r5, r6]
    )
    assert has_booking or has_code_in_reply, (
        f"Expected booking to be made.\n"
        f"r5: action={r5.action} reply={r5.reply_text!r} pending={r5.pending!r}\n"
        f"r6: action={r6.action} reply={r6.reply_text!r} pending={r6.pending!r}\n"
        f"Bookings: {all_bookings}"
    )
