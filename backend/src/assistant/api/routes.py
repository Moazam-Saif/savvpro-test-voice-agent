"""
api/routes.py – FastAPI route definitions.

Endpoints:
  POST /api/sessions           → create a session, return the greeting.
  POST /api/sessions/{id}/turns → process one turn.
  GET  /api/demo/bookings       → list seeded bookings (DEMO_ENDPOINTS_ENABLED only).
  GET  /health
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from assistant.api.schemas import (
    CreateSessionRequest, DemoBookingItem, TraceResponse, TurnRequest, TurnResponse,
)
from assistant.brain.engine import Brain
from assistant.brain.ports import Ports
from assistant.brain.types import TurnInput, Phase, Pending

logger = logging.getLogger(__name__)

router = APIRouter()
brain = Brain()


def _get_store(request: Request):
    return request.app.state.session_store


def _get_booking_service(request: Request):
    return request.app.state.booking_service


def _get_ports(request: Request) -> Ports:
    app = request.app
    return Ports(
        clock=app.state.clock,
        bookings=app.state.booking_service,
        tz=app.state.tz,
    )


def _trace_to_response(trace) -> TraceResponse:
    return TraceResponse(
        turn=trace.turn,
        input=trace.input,
        normalized=trace.normalized,
        intent_scores=trace.intent_scores,
        extracted=trace.extracted,
        phase_before=trace.phase_before,
        phase_after=trace.phase_after,
        pending_before=trace.pending_before,
        pending_after=trace.pending_after,
        rules_fired=trace.rules_fired,
        counters=trace.counters,
        offers=trace.offers,
        proposal=trace.proposal,
        effect=trace.effect,
        action=trace.action,
        reason=trace.reason,
    )


# ── POST /api/sessions ────────────────────────────────────────────────────────

@router.post("/api/sessions", status_code=201)
def create_session(request: Request) -> TurnResponse:
    store = _get_store(request)
    ports = _get_ports(request)
    session = store.create()

    # Process turn 0 (the greeting)
    turn_input = TurnInput(type="utterance", text="", turn_no=0)
    # Force greeting on first turn
    session.phase = Phase.GREETING
    session.pending = Pending.NONE
    result = brain.handle(session, turn_input, ports)
    session.last_turn_no = 0
    session.last_response = result

    return TurnResponse(
        session_id=session.session_id,
        turn_no=0,
        reply_text=result.reply_text,
        ended=result.ended,
        end_reason=result.end_reason.value if result.end_reason else None,
        phase=result.phase.value,
        pending=result.pending.value,
        frame=result.frame,
        counters=result.counters,
        last_booking=result.last_booking,
        trace=_trace_to_response(result.trace),
    )


# ── POST /api/sessions/{session_id}/turns ─────────────────────────────────────

@router.post("/api/sessions/{session_id}/turns")
def process_turn(session_id: str, body: TurnRequest, request: Request) -> TurnResponse:
    store = _get_store(request)
    ports = _get_ports(request)

    entry = store.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    session, lock = entry

    with lock:
        # ── Idempotency (section 6) ───────────────────────────────────────────
        if body.turn_no == session.last_turn_no and session.last_response is not None:
            # Same turn_no → replay stored response
            result = session.last_response
        elif body.turn_no == session.last_turn_no + 1:
            # New turn
            if session.ended:
                raise HTTPException(status_code=409, detail="Session has ended")

            if body.type == "utterance" and body.text is None:
                raise HTTPException(status_code=422, detail="text is required for utterances")

            turn_input = TurnInput(
                type=body.type,
                text=body.text or "",
                confidence=body.confidence,
                turn_no=body.turn_no,
            )
            result = brain.handle(session, turn_input, ports)
            session.last_turn_no = body.turn_no
            session.last_response = result
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Expected turn_no {session.last_turn_no + 1}, got {body.turn_no}",
            )

    return TurnResponse(
        session_id=session_id,
        turn_no=body.turn_no,
        reply_text=result.reply_text,
        ended=result.ended,
        end_reason=result.end_reason.value if result.end_reason else None,
        phase=result.phase.value,
        pending=result.pending.value,
        frame=result.frame,
        counters=result.counters,
        last_booking=result.last_booking,
        trace=_trace_to_response(result.trace),
    )


# ── GET /health ────────────────────────────────────────────────────────────────

@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── GET /api/demo/bookings ─────────────────────────────────────────────────────

demo_router = APIRouter()


@demo_router.get("/api/demo/bookings")
def list_demo_bookings(request: Request) -> list[DemoBookingItem]:
    svc = _get_booking_service(request)
    bookings = svc._repo.all_bookings()
    return [
        DemoBookingItem(
            id=b.id,
            patient_name=b.patient_name,
            service=b.service.value,
            start=b.start.isoformat(),
            code=b.code,
        )
        for b in sorted(bookings, key=lambda b: b.start)[:20]
    ]
