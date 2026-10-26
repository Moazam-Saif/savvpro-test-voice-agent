"""
brain/engine.py – Brain.handle(): the main turn processor.

Architecture (section 3):
  1. Works on a deep copy of the session.
  2. Runs the NLU pipeline over the input text.
  3. Runs the policy (pure function).
  4. Executes the requested effect LAST (book or cancel).
  5. Feeds the effect result back to determine the reply text.
  6. Builds the trace.
  7. Swaps in the new state.

If anything raises, the original session state is kept unchanged and the
caller gets an ERROR_RECOVERY reply.  The brain never raises externally.
"""
from __future__ import annotations

import copy
import logging
from datetime import datetime

from assistant.brain.nlg import render, render_confirmation_code, format_date, format_time
from assistant.brain.normalize import normalize
from assistant.brain.nlu.commands import detect_command, detect_emergency, is_filler, is_out_of_scope
from assistant.brain.nlu.dates import parse_date
from assistant.brain.nlu.intents import score_intents
from assistant.brain.nlu.names import extract_name, extract_code
from assistant.brain.nlu.polarity import split_clauses
from assistant.brain.nlu.services import extract_services
from assistant.brain.nlu.times import parse_time
from assistant.brain.nlu.yesno import extract_yesno
from assistant.brain.policy import run_policy
from assistant.brain.ports import Ports
from assistant.brain.types import (
    Action, Extracted, Polarity, Session, TraceEntry, TurnInput, TurnResult,
    EndReason, Phase, Pending,
)
from assistant.domain.models import SlotTaken, DuplicateBooking, InvalidSlot

logger = logging.getLogger(__name__)


class Brain:
    """Stateless processor — the session carries all state."""

    def handle(self, session: Session, turn_input: TurnInput, ports: Ports) -> TurnResult:
        """
        Process one turn.  Returns a TurnResult.  Never raises.
        """
        original_session = session  # kept for rollback

        try:
            return self._handle_inner(session, turn_input, ports)
        except Exception as exc:
            logger.exception("Brain.handle() unhandled exception (class=%s)", type(exc).__name__)
            # Return ERROR_RECOVERY with the original session untouched
            trace = TraceEntry(
                turn=session.turn_index,
                input={"type": turn_input.type, "text": turn_input.text},
                normalized="",
                intent_scores={},
                extracted=[],
                phase_before=session.phase.value,
                phase_after=session.phase.value,
                pending_before=session.pending.value,
                pending_after=session.pending.value,
                rules_fired=["ERROR"],
                counters={},
                offers=None,
                proposal=None,
                effect=None,
                action=Action.ERROR_RECOVERY.value,
                reason=type(exc).__name__,
            )
            return TurnResult(
                reply_text="I'm having trouble, one moment. Could you say that again?",
                action=Action.ERROR_RECOVERY,
                ended=original_session.ended,
                end_reason=original_session.end_reason,
                phase=original_session.phase,
                pending=original_session.pending,
                frame=_frame_to_dict(original_session.frame),
                counters=_counters_to_dict(original_session.counters),
                last_booking=original_session.last_booking,
                trace=trace,
            )

    def _handle_inner(self, session: Session, turn_input: TurnInput, ports: Ports) -> TurnResult:
        # ── Idempotency check (done by the API layer, but defensively here too) ──
        # If same turn_no as last, the API layer replays; we won't see it here.

        phase_before = session.phase
        pending_before = session.pending

        # ── Deep copy session for atomic state swap ───────────────────────────
        new_session = copy.deepcopy(session)
        new_session.turn_index += 1

        # ── NLU pipeline ──────────────────────────────────────────────────────
        raw_text = turn_input.text or ""
        normalized_text = normalize(raw_text) if raw_text else ""

        extracted: list[Extracted] = []
        intent_score_obj = score_intents("")
        yesno: str | None = None
        command = None
        emergency: str | None = None
        oos_group: str | None = None
        filler = False

        if normalized_text:
            clauses = split_clauses(normalized_text)

            # Filler check (whole utterance)
            filler = is_filler(normalized_text)

            if not filler:
                # Gather all extractions per clause
                for ci, clause in enumerate(clauses):
                    extracted += extract_services(clause, ci)

                # Date extraction (whole text for context)
                today = ports.now_local().date()
                date_result = parse_date(normalized_text, today,
                                         week_anchor=new_session.frame.week_anchor)
                if date_result.date:
                    extracted.append(Extracted(
                        slot="date", value=date_result.date,
                        span=normalized_text, extractor="dates", polarity=Polarity.POS,
                    ))
                if date_result.time_window:
                    new_session.frame.time_window = date_result.time_window
                if date_result.pref_mode:
                    new_session.frame.pref_mode = date_result.pref_mode
                if date_result.hint:
                    new_session.frame.date_hint = date_result.hint
                    new_session.frame.week_anchor = date_result.week_anchor

                # Time extraction
                time_result = parse_time(normalized_text,
                                         d=new_session.frame.date)
                if time_result.time:
                    from datetime import time as time_type
                    t = time_result.time
                    start_dt = datetime.combine(today, t)
                    extracted.append(Extracted(
                        slot="time", value=start_dt,
                        span=normalized_text, extractor="times", polarity=Polarity.POS,
                    ))
                    if time_result.ambiguous_ampm:
                        new_session.frame.ambiguous_ampm = True

                # Yes/No
                yesno = extract_yesno(normalized_text)

                # Name (with bare-answer when pending=NAME or VERIFY)
                bare_name_ok = new_session.pending in (Pending.NAME, Pending.VERIFY)
                name, for_other, direct_patient = extract_name(normalized_text, bare_ok=bare_name_ok)
                if name:
                    extracted.append(Extracted(
                        slot="name", value=name,
                        span=normalized_text, extractor="names", polarity=Polarity.POS,
                    ))
                if for_other:
                    new_session.frame.for_other = True

                # Confirmation code
                code_ok = new_session.pending in (Pending.VERIFY, Pending.NAME)
                code = extract_code(normalized_text, pending_allows=code_ok)
                if code:
                    new_session.frame.verify.lookup_code = code

                # Intent scoring (POS text only, per 5.4)
                from assistant.brain.nlu.polarity import NEG_CUES
                pos_clauses = [c for c in clauses if not NEG_CUES.search(c)]
                pos_text = " ".join(pos_clauses) if pos_clauses else normalized_text
                intent_score_obj = score_intents(pos_text)

                # Emergency
                emergency = detect_emergency(normalized_text)

                # Out-of-scope
                oos_group = is_out_of_scope(normalized_text)

                # Command (gated)
                has_content = bool(extracted) or bool(yesno) or intent_score_obj.best() is not None
                command = detect_command(normalized_text, anything_extracted=has_content)

        # ── Run policy ────────────────────────────────────────────────────────
        decision = run_policy(
            session=new_session,
            turn_input=turn_input,
            extracted=extracted,
            intent_score=intent_score_obj,
            command=command,
            yesno=yesno,
            emergency=emergency,
            oos_group=oos_group,
            is_filler=filler,
            ports=ports,
        )

        new_session = decision.new_session
        reply_text = decision.reply_text
        action = decision.action

        # ── Execute effect LAST ───────────────────────────────────────────────
        effect_str: str | None = None

        if decision.effect == "book":
            try:
                booking = ports.bookings.book(decision.effect_payload)
                effect_str = "book"
                reply_text = render_confirmation_code(booking.code, new_session.turn_index)
                new_session.last_booking = {
                    "id": booking.id,
                    "summary": f"{booking.service.value} on {format_date(booking.date)} at {format_time(booking.start)}",
                    "code": booking.code,
                }
                new_session.verified_booking_ids.add(booking.id)
                new_session.frame = type(new_session.frame)()   # reset frame
                new_session.pending = Pending.ANYTHING_ELSE
                new_session.phase = Phase.AWAITING_MORE
                action = Action.BOOK
            except (SlotTaken, DuplicateBooking):
                # Slot was taken between readback and confirm (E1)
                new_session.frame.proposal = None
                new_session.frame.offers = None
                reply_text = "Sorry, that slot was just taken. Let me find you another time."
                action = Action.OFFER_ALTERNATIVES
            except InvalidSlot as exc:
                new_session.frame.proposal = None
                reply_text = f"I'm sorry, there's a problem with that slot. {exc}"
                action = Action.REJECT_INVALID

        elif decision.effect == "cancel":
            try:
                success = ports.bookings.cancel(decision.effect_payload)
                effect_str = "cancel"
                if success:
                    reply_text = render(Action.CANCEL_BOOKING, new_session.turn_index)
                    if new_session.last_booking and new_session.last_booking.get("id") == decision.effect_payload:
                        new_session.last_booking = None
                    new_session.verified_booking_ids.discard(decision.effect_payload)
                else:
                    reply_text = "I couldn't find that appointment to cancel."
                new_session.pending = Pending.ANYTHING_ELSE
                action = Action.CANCEL_BOOKING
            except Exception:
                reply_text = "I had trouble cancelling that. Please try again."
                action = Action.ERROR_RECOVERY

        # ── Build trace ───────────────────────────────────────────────────────
        trace = TraceEntry(
            turn=new_session.turn_index,
            input={"type": turn_input.type, "text": raw_text, "confidence": turn_input.confidence},
            normalized=normalized_text,
            intent_scores={k: v for k, v in intent_score_obj.scores.items()},
            extracted=[{
                "slot": e.slot, "value": str(e.value), "span": e.span,
                "extractor": e.extractor, "polarity": e.polarity.value, "clause": e.clause,
            } for e in extracted],
            phase_before=phase_before.value,
            phase_after=new_session.phase.value,
            pending_before=pending_before.value,
            pending_after=new_session.pending.value,
            rules_fired=decision.rules_fired,
            counters=_counters_to_dict(new_session.counters),
            offers=_offerset_to_dict(new_session.frame.offers),
            proposal=_proposal_to_dict(new_session.frame.proposal),
            effect=effect_str,
            action=action.value,
            reason=" + ".join(decision.rules_fired) if decision.rules_fired else "none",
        )

        # ── Atomic state swap ─────────────────────────────────────────────────
        # Update last_turn_no on original session AFTER a successful turn
        session.turn_index = new_session.turn_index
        session.last_turn_no = turn_input.turn_no
        session.phase = new_session.phase
        session.pending = new_session.pending
        session.frame = new_session.frame
        session.counters = new_session.counters
        session.ended = new_session.ended
        session.end_reason = new_session.end_reason
        session.last_booking = new_session.last_booking
        session.verified_booking_ids = new_session.verified_booking_ids
        session.hold_grace = new_session.hold_grace
        session.filler_streak = new_session.filler_streak
        session.carry_exclusions = new_session.carry_exclusions

        return TurnResult(
            reply_text=reply_text,
            action=action,
            ended=session.ended,
            end_reason=session.end_reason,
            phase=session.phase,
            pending=session.pending,
            frame=_frame_to_dict(session.frame),
            counters=_counters_to_dict(session.counters),
            last_booking=session.last_booking,
            trace=trace,
        )


# ── Serialization helpers ─────────────────────────────────────────────────────

def _frame_to_dict(frame) -> dict:
    return {
        "intent": frame.intent.value if frame.intent else None,
        "service": frame.service,
        "date": frame.date.isoformat() if frame.date else None,
        "time": frame.time.isoformat() if frame.time else None,
        "time_window": frame.time_window,
        "pref_mode": frame.pref_mode,
        "ambiguous_ampm": frame.ambiguous_ampm,
        "urgent": frame.urgent,
        "name": frame.name,
        "for_other": frame.for_other,
        "proposal": _proposal_to_dict(frame.proposal),
        "offers": _offerset_to_dict(frame.offers),
    }


def _counters_to_dict(c) -> dict:
    return {
        "silence": c.silence,
        "nomatch": c.nomatch,
        "reject": c.reject,
        "slot_attempts": dict(c.slot_attempts),
        "verify_failures": c.verify_failures,
        "oos_streak": c.oos_streak,
        "human_offers": c.human_offers,
        "noprogress": c.noprogress,
    }


def _proposal_to_dict(p) -> dict | None:
    if p is None:
        return None
    return {
        "service": p.service,
        "patient_name": p.patient_name,
        "start": p.start.isoformat(),
        "end": p.end.isoformat(),
        "duration_minutes": p.duration_minutes,
        "for_other": p.for_other,
    }


def _offerset_to_dict(o) -> dict | None:
    if o is None:
        return None
    return {
        "offer_id": o.offer_id,
        "kind": o.kind.value,
        "options": [{"label": opt.label, "start": opt.start.isoformat() if opt.start else None} for opt in o.options],
    }
