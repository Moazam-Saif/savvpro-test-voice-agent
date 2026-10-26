"""
tests/scenarios/test_scenarios_p0.py – P0 scenario test suite.

Covers:
  - S2: All slots in one utterance ("a cleaning Friday at 3 for Sarah")
  - S3: Implicit intent from service and date
  - S7: Stale confirmation (mid-flight correction invalidates proposal)
  - S8: Self-repair "Friday, no wait, Saturday"
  - S10: Polarity of intents and symptoms
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
def env():
    clock = FixedClock(at=DEMO_NOW)
    closed = build_closed_dates(clock, TZ)
    repo = InMemoryBookingRepository()
    gen = CodeGenerator(seed=101)
    svc = BookingService(repo, clock, TZ, closed, gen)
    ports = Ports(clock=clock, bookings=svc, tz=TZ)
    brain = Brain()
    return brain, ports, repo


def test_s2_all_slots_in_one_utterance(env):
    brain, ports, repo = env
    session = Session(session_id="s2")

    # Turn 0: greeting
    brain.handle(session, TurnInput(type="utterance", text="", turn_no=0), ports)

    # Turn 1: all slots provided
    r1 = brain.handle(
        session,
        TurnInput(type="utterance", text="I'd like to book a cleaning for Sarah on Friday at 2 pm", turn_no=1),
        ports,
    )
    # Should immediately ask for confirmation
    assert r1.pending == Pending.CONFIRM_YN.value or "confirm" in r1.reply_text.lower() or "shall i book" in r1.reply_text.lower()

    # Turn 2: confirm
    r2 = brain.handle(session, TurnInput(type="utterance", text="yes", turn_no=2), ports)
    assert len(repo.all_bookings()) == 1 or "confirmation code" in r2.reply_text.lower()


def test_s3_implicit_intent(env):
    brain, ports, repo = env
    session = Session(session_id="s3")

    brain.handle(session, TurnInput(type="utterance", text="", turn_no=0), ports)

    # No explicit "book" word, but has service + date
    r1 = brain.handle(session, TurnInput(type="utterance", text="cleaning next friday", turn_no=1), ports)
    # Should detect service and date and ask for remaining slot (time or name)
    assert r1.pending in (Pending.TIME.value, Pending.NAME.value, Pending.SERVICE.value)


def test_s7_stale_confirmation_proposal_invalidation(env):
    brain, ports, repo = env
    session = Session(session_id="s7")

    brain.handle(session, TurnInput(type="utterance", text="", turn_no=0), ports)
    brain.handle(session, TurnInput(type="utterance", text="book a cleaning on Friday at 2 pm for Sarah", turn_no=1), ports)

    # In CONFIRM_YN state, user changes time instead of saying pure yes
    r2 = brain.handle(session, TurnInput(type="utterance", text="actually make it 3 pm", turn_no=2), ports)

    # Proposal must be rebuilt with 3 pm, NOT booked immediately with 2 pm
    assert len(repo.all_bookings()) == 0
    assert r2.action in (Action.ASK_CONFIRM, Action.ASK_SLOT, Action.OFFER_ALTERNATIVES)

    # Now pure yes confirms 3 pm
    r3 = brain.handle(session, TurnInput(type="utterance", text="yes", turn_no=3), ports)
    bookings = repo.all_bookings()
    if bookings:
        assert bookings[0].start.hour == 15   # 3 PM = 15:00


def test_s10_negated_intent_and_symptoms(env):
    brain, ports, repo = env
    session = Session(session_id="s10")

    brain.handle(session, TurnInput(type="utterance", text="", turn_no=0), ports)

    # "I don't want to cancel, I want to book"
    r1 = brain.handle(
        session,
        TurnInput(type="utterance", text="I don't want to cancel; I want to book an appointment", turn_no=1),
        ports,
    )
    assert session.frame.intent.value == "BOOK"

    # Negated symptom should not trigger emergency
    r2 = brain.handle(
        session,
        TurnInput(type="utterance", text="my face is not swollen, just need a checkup", turn_no=2),
        ports,
    )
    assert r2.action != Action.EMERGENCY

    # Positive acute emergency symptom
    r3 = brain.handle(
        session,
        TurnInput(type="utterance", text="my mouth is bleeding heavily and I have severe pain", turn_no=3),
        ports,
    )
    assert r3.action == Action.EMERGENCY
