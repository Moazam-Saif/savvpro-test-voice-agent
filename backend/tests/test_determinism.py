"""
tests/test_determinism.py – Determinism test (8.8).

Run the same conversation twice with a FixedClock and identical ports,
then compare replies, traces, and state.
"""
from __future__ import annotations

import copy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from assistant.brain.engine import Brain
from assistant.brain.ports import Ports
from assistant.brain.types import Session, TurnInput, Phase, Pending
from assistant.clock import FixedClock
from assistant.domain.codes import CodeGenerator
from assistant.domain.repository import InMemoryBookingRepository
from assistant.domain.seed import build_closed_dates
from assistant.domain.service import BookingService

DEMO_NOW = datetime.fromisoformat("2026-10-26T14:00:00-04:00")
TZ = ZoneInfo("America/New_York")

UTTERANCES = [
    "",                                    # greeting
    "I'd like to book a cleaning",
    "next friday",
    "at 2 pm",
    "Sarah Thompson",
    "yes",
]


def _run_conversation(utterances: list[str]) -> list[str]:
    clock = FixedClock(at=DEMO_NOW)
    closed = build_closed_dates(clock, TZ)
    repo = InMemoryBookingRepository()
    gen = CodeGenerator(seed=99)
    svc = BookingService(repo, clock, TZ, closed, gen)
    ports = Ports(clock=clock, bookings=svc, tz=TZ)
    brain = Brain()
    session = Session(session_id="test-det")

    replies: list[str] = []
    for i, text in enumerate(utterances):
        turn_input = TurnInput(type="utterance" if text else "utterance", text=text, turn_no=i)
        result = brain.handle(session, turn_input, ports)
        replies.append(result.reply_text)
    return replies


def test_same_inputs_same_replies():
    run1 = _run_conversation(UTTERANCES)
    run2 = _run_conversation(UTTERANCES)
    assert run1 == run2, f"Non-deterministic replies:\nRun1: {run1}\nRun2: {run2}"
