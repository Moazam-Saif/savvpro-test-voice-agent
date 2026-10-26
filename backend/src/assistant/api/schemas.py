"""
api/schemas.py – Pydantic v2 request/response schemas.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    pass   # No body required


class TurnRequest(BaseModel):
    turn_no: int = Field(..., ge=1)
    type: str = Field(..., pattern=r"^(utterance|silence|hangup)$")
    text: str | None = Field(None, max_length=500)
    confidence: float | None = Field(None, ge=0.0, le=1.0)


# ── Response schemas ──────────────────────────────────────────────────────────

class TraceResponse(BaseModel):
    turn: int
    input: dict[str, Any]
    normalized: str
    intent_scores: dict[str, float]
    extracted: list[dict[str, Any]]
    phase_before: str
    phase_after: str
    pending_before: str
    pending_after: str
    rules_fired: list[str]
    counters: dict[str, Any]
    offers: dict[str, Any] | None
    proposal: dict[str, Any] | None
    effect: str | None
    action: str
    reason: str


class TurnResponse(BaseModel):
    session_id: str
    turn_no: int
    reply_text: str
    ended: bool
    end_reason: str | None
    phase: str
    pending: str
    frame: dict[str, Any]
    counters: dict[str, Any]
    last_booking: dict[str, Any] | None
    trace: TraceResponse


class DemoBookingItem(BaseModel):
    id: str
    patient_name: str
    service: str
    start: str
    code: str
