"""
brain/policy.py – Policy rules R0–R16 (5.5).

The policy is a pure function: it takes the current session + extracted
NLU results + ports, and returns a Decision (state mutations + optional
effect request).  The engine executes effects AFTER the policy returns.

This module is deliberately long — the spec defines 17 rules and each one
must be auditable.  Every rule that fires writes its ID to rules_fired.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from assistant.brain.nlg import (
    format_date, format_time, render, render_readback, render_confirmation_code
)
from assistant.brain.nlu.commands import Command
from assistant.brain.nlu.intents import IntentScore
from assistant.brain.nlu.yesno import has_abandon
from assistant.brain.types import (
    Action, CancelProposal, Counters, EndReason, Extracted,
    Frame, Intent, OfferKind, OfferSet, Pending, Phase,
    Polarity, Proposal, Session, SlotOption, TurnInput,
)
from assistant.domain.models import Service, SlotTaken, DuplicateBooking, InvalidSlot
from assistant.domain.service import BookingProposal


MAX_TURNS = 200
NOMATCH_HUMAN_THRESHOLD = 3
SLOT_ATTEMPTS_THRESHOLD = 3
REJECT_HUMAN_THRESHOLD = 3
OOS_STREAK_THRESHOLD = 3
VERIFY_FAIL_HUMAN_THRESHOLD = 2
VERIFY_FAIL_LOCK_THRESHOLD = 4
NOPROGRESS_LIMIT = 8
SILENCE_END_THRESHOLD = 3
FILLER_STREAK_THRESHOLD = 3


# ── Decision object ───────────────────────────────────────────────────────────

@dataclass
class Decision:
    """What the policy decided to do this turn."""
    new_session: Session
    reply_text: str
    action: Action
    rules_fired: list[str] = field(default_factory=list)
    effect: str | None = None       # "book" | "cancel" | None
    effect_payload: Any = None      # BookingProposal | booking_id


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ask(session: Session, pending: Pending, prompt: str, action: Action = Action.ASK_SLOT) -> None:
    session.pending = pending
    session.frame.last_prompt = prompt
    session.phase = Phase.COLLECTING


def _end_session(session: Session, reason: EndReason, reply: str, action: Action) -> Decision:
    session.ended = True
    session.end_reason = reason
    session.phase = Phase.ENDED
    session.pending = Pending.NONE
    return Decision(new_session=session, reply_text=reply, action=action)


def _offer_human(session: Session) -> str:
    session.counters.human_offers += 1
    session.pending = Pending.HUMAN_YN
    msg = "Would you like me to ask a staff member to call you back?"
    session.frame.last_prompt = msg
    return msg


def _reset_frame(session: Session) -> None:
    """Discard the current frame, keeping session-level data."""
    session.frame = Frame()
    session.pending = Pending.INTENT
    session.phase = Phase.GREETING
    # Reset per-flow counters (but NOT verify_failures)
    session.counters.nomatch = 0
    session.counters.reject = 0
    session.counters.slot_attempts = {}
    session.counters.oos_streak = 0
    session.counters.neg_only_streak = 0


def _get_service(session: Session) -> Service | None:
    if session.frame.service:
        try:
            return Service(session.frame.service)
        except ValueError:
            return None
    return None


def _duration(session: Session) -> int:
    svc = _get_service(session)
    return svc.duration_minutes if svc else 30


def _destroy_proposal(session: Session) -> None:
    session.frame.proposal = None
    session.frame.cancel_proposal = None
    session.frame.offers = None


def _next_required_slot(session: Session) -> str | None:
    f = session.frame
    if f.intent is None:
        return "intent"
    if f.service is None:
        return "service"
    if f.date is None and f.pref_mode != "EARLIEST":
        return "date"
    if f.time is None and f.pref_mode != "EARLIEST":
        return "time"
    if f.name is None:
        return "name"
    return None


def _build_offer_set_from_slots(session: Session, options: list[SlotOption], turn_idx: int) -> OfferSet:
    return OfferSet(
        offer_id=turn_idx,
        kind=OfferKind.SLOT,
        options=[SlotOption(start=o.start, end=o.end, label=o.label) for o in options],
        created_turn=turn_idx,
    )


def _speak_options(options: list[SlotOption]) -> str:
    if not options:
        return ""
    parts = [f"option {i+1}: {o.label}" for i, o in enumerate(options[:3])]
    return " Or ".join(parts) + ". Which would you prefer?"


# ── Main policy entrypoint ────────────────────────────────────────────────────

def run_policy(
    session: Session,
    turn_input: TurnInput,
    extracted: list[Extracted],
    intent_score: IntentScore,
    command: Command | None,
    yesno: str | None,
    emergency: str | None,
    oos_group: str | None,
    is_filler: bool,
    ports: Any,   # Ports – avoid circular import
) -> Decision:
    """
    Apply rules R0–R16 in order.  Returns a Decision.
    The session passed in is already a deep copy (the engine ensures this).
    """
    rules_fired: list[str] = []
    s = session   # convenience alias

    # ── R0: Session ended ─────────────────────────────────────────────────────
    if s.ended:
        rules_fired.append("R0")
        return Decision(
            new_session=s,
            reply_text="This call has ended.",
            action=Action.ERROR_RECOVERY,
            rules_fired=rules_fired,
        )

    # ── Turn limit (R16 extension) ────────────────────────────────────────────
    if s.turn_index >= MAX_TURNS:
        rules_fired.append("R16.turn_limit")
        return _end_session(s, EndReason.TURN_LIMIT, "I'm sorry, I've reached my turn limit. Goodbye.", Action.GOODBYE)

    # ── Hangup event ──────────────────────────────────────────────────────────
    if turn_input.type == "hangup":
        rules_fired.append("R0.hangup")
        return _end_session(s, EndReason.HANGUP, "", Action.GOODBYE)

    # ── Greeting (turn 0 or initial greeting phase) ───────────────────────────
    if turn_input.turn_no == 0 or (s.phase == Phase.GREETING and s.turn_index <= 1 and not turn_input.text.strip()):
        rules_fired.append("R12.greet")
        reply = render(Action.GREET, 0)
        s.pending = Pending.INTENT
        s.phase = Phase.COLLECTING
        s.frame.last_prompt = reply
        return Decision(new_session=s, reply_text=reply, action=Action.GREET, rules_fired=rules_fired)

    # ── R1: No-input ladder ───────────────────────────────────────────────────
    if turn_input.type == "silence" or not turn_input.text.strip():
        rules_fired.append("R1")
        if s.hold_grace > 0:
            s.hold_grace -= 1
            return Decision(new_session=s, reply_text="", action=Action.HOLD, rules_fired=rules_fired)
        s.counters.silence += 1
        if s.counters.silence == 1:
            reply = f"Are you still there? {s.frame.last_prompt}"
            return Decision(new_session=s, reply_text=reply, action=Action.SILENCE_REPROMPT, rules_fired=rules_fired)
        elif s.counters.silence == 2:
            example = "For example, you could say 'book a cleaning on Friday at 2 PM'."
            reply = f"{example} {s.frame.last_prompt}"
            return Decision(new_session=s, reply_text=reply, action=Action.SILENCE_REPROMPT, rules_fired=rules_fired)
        else:
            _destroy_proposal(s)
            return _end_session(s, EndReason.SILENCE,
                "I'm not hearing anything, so I'll end the call. Please call back any time.",
                Action.GOODBYE)

    # Reset silence counter on real utterance
    s.counters.silence = 0

    # ── R2: Emergency ─────────────────────────────────────────────────────────
    if emergency == "PRESENT":
        rules_fired.append("R2.present")
        _destroy_proposal(s)
        s.frame.resume_pending = s.pending
        s.pending = Pending.HUMAN_YN
        reply = render(Action.EMERGENCY, s.turn_index)
        s.frame.last_prompt = reply
        return Decision(new_session=s, reply_text=reply, action=Action.EMERGENCY, rules_fired=rules_fired)
    if emergency in ("PAST", "AMBIGUOUS"):
        rules_fired.append(f"R2.{emergency.lower()}")
        s.pending = Pending.NOW_YN
        reply = render(Action.ASK_NOW_YN, s.turn_index)
        s.frame.last_prompt = reply
        return Decision(new_session=s, reply_text=reply, action=Action.ASK_NOW_YN, rules_fired=rules_fired)

    # ── R3: Global commands ───────────────────────────────────────────────────
    if command is not None:
        rules_fired.append(f"R3.{command.value}")

        if command == Command.BYE:
            _destroy_proposal(s)
            return _end_session(s, EndReason.GOODBYE,
                render(Action.GOODBYE, s.turn_index), Action.GOODBYE)

        if command == Command.HUMAN:
            reply = _offer_human(s)
            return Decision(new_session=s, reply_text=reply, action=Action.TRANSFER, rules_fired=rules_fired)

        if command == Command.ROBOT:
            reply = ("Yes, I'm an automated assistant. I can book or cancel appointments, "
                     "or ask staff to call you back.")
            if s.frame.last_prompt:
                reply += " " + s.frame.last_prompt
            return Decision(new_session=s, reply_text=reply, action=Action.ANSWER_INFO, rules_fired=rules_fired)

        if command == Command.REPEAT:
            return Decision(new_session=s, reply_text=s.frame.last_prompt,
                            action=Action.REPEAT, rules_fired=rules_fired)

        if command == Command.HOLD:
            s.hold_grace = 2
            reply = render(Action.HOLD, s.turn_index)
            return Decision(new_session=s, reply_text=reply, action=Action.HOLD, rules_fired=rules_fired)

        if command == Command.START_OVER:
            _reset_frame(s)
            reply = "No problem, starting fresh. How can I help?"
            s.frame.last_prompt = reply
            return Decision(new_session=s, reply_text=reply, action=Action.ACK_NOTED, rules_fired=rules_fired)

    # ── R4: Filler ────────────────────────────────────────────────────────────
    if is_filler:
        rules_fired.append("R4")
        s.filler_streak += 1
        if s.filler_streak >= FILLER_STREAK_THRESHOLD:
            # Treat as silence
            s.counters.silence += 1
            s.filler_streak = 0
        return Decision(new_session=s, reply_text="", action=Action.WAIT, rules_fired=rules_fired)
    s.filler_streak = 0

    # ── R5: Out-of-scope ──────────────────────────────────────────────────────
    if oos_group:
        rules_fired.append(f"R5.{oos_group}")
        s.counters.oos_streak += 1
        reply = render(Action.OUT_OF_SCOPE, s.turn_index, _sub_key=oos_group, prompt=s.frame.last_prompt)
        if s.counters.oos_streak >= OOS_STREAK_THRESHOLD:
            reply += " " + _offer_human(s)
        return Decision(new_session=s, reply_text=reply, action=Action.OUT_OF_SCOPE, rules_fired=rules_fired)
    s.counters.oos_streak = 0

    # ── R6: Pending interpretation ────────────────────────────────────────────
    if s.pending == Pending.HUMAN_YN:
        rules_fired.append("R6.human_yn")
        if yesno == "yes":
            return _end_session(s, EndReason.TRANSFER_CALLBACK,
                render(Action.TRANSFER, s.turn_index), Action.TRANSFER)
        elif yesno == "no":
            s.counters.nomatch = 0
            s.counters.reject = 0
            s.counters.oos_streak = 0
            s.counters.human_offers = 0
            s.pending = s.frame.resume_pending or Pending.NONE
            reply = s.frame.last_prompt
            return Decision(new_session=s, reply_text=reply, action=Action.REPEAT, rules_fired=rules_fired)

    if s.pending == Pending.NOW_YN:
        rules_fired.append("R6.now_yn")
        if yesno == "yes":
            _destroy_proposal(s)
            s.frame.resume_pending = s.pending
            s.pending = Pending.HUMAN_YN
            reply = render(Action.EMERGENCY, s.turn_index)
            s.frame.last_prompt = reply
            return Decision(new_session=s, reply_text=reply, action=Action.EMERGENCY, rules_fired=rules_fired)
        elif yesno == "no":
            s.pending = s.frame.resume_pending or Pending.NONE
            return Decision(new_session=s, reply_text=s.frame.last_prompt, action=Action.REPEAT, rules_fired=rules_fired)

    if s.pending == Pending.ANYTHING_ELSE:
        rules_fired.append("R6.anything_else")
        if yesno == "yes":
            _reset_frame(s)
            reply = "Sure, what else can I do?"
            s.frame.last_prompt = reply
            s.pending = Pending.INTENT
            return Decision(new_session=s, reply_text=reply, action=Action.ASK_SLOT, rules_fired=rules_fired)
        elif yesno == "no":
            return _end_session(s, EndReason.GOODBYE, render(Action.GOODBYE, s.turn_index), Action.GOODBYE)

    # ── R13: Confirmation + commit (MUST come before R8 slot fills) ───────────
    if s.pending == Pending.CONFIRM_YN and s.frame.proposal is not None:
        rules_fired.append("R13")
        pos_extractions = [e for e in extracted if e.polarity == Polarity.POS]
        has_slot_values = any(e.slot in ("service", "date", "time", "name") for e in pos_extractions)
        abandon = yesno == "no" and has_abandon(turn_input.text)
        bare_no = yesno == "no" and not has_slot_values

        if yesno == "yes" and not has_slot_values:
            # Pure yes → commit
            rules_fired.append("R13.commit")
            proposal = s.frame.proposal
            bp = BookingProposal(
                patient_name=proposal.patient_name,
                service=Service(proposal.service),
                start=proposal.start,
                for_other=proposal.for_other,
            )
            return Decision(
                new_session=s,
                reply_text="",   # filled after effect execution by engine
                action=Action.BOOK,
                rules_fired=rules_fired,
                effect="book",
                effect_payload=bp,
            )

        if abandon or (bare_no and not has_slot_values):
            _destroy_proposal(s)
            reply = render(Action.ABANDON, s.turn_index)
            s.pending = Pending.ANYTHING_ELSE
            s.frame.last_prompt = reply
            return Decision(new_session=s, reply_text=reply, action=Action.ABANDON, rules_fired=rules_fired)

        if bare_no:
            # "What would you like to change?"
            _destroy_proposal(s)
            reply = "What would you like to change?"
            s.pending = Pending.CHANGE_WHICH
            s.frame.last_prompt = reply
            return Decision(new_session=s, reply_text=reply, action=Action.ASK_SLOT, rules_fired=rules_fired)

        # Yes/no with slot values = correction → fall through to R8

    if s.pending == Pending.CANCEL_YN and s.frame.cancel_proposal is not None:
        rules_fired.append("R13.cancel")
        if yesno == "yes":
            cp = s.frame.cancel_proposal
            return Decision(
                new_session=s,
                reply_text="",
                action=Action.CANCEL_BOOKING,
                rules_fired=rules_fired,
                effect="cancel",
                effect_payload=cp.booking_id,
            )
        elif yesno == "no":
            s.frame.cancel_proposal = None
            reply = "Okay, I've left it as is. Anything else?"
            s.pending = Pending.ANYTHING_ELSE
            s.frame.last_prompt = reply
            return Decision(new_session=s, reply_text=reply, action=Action.ABANDON, rules_fired=rules_fired)

    # ── R8: Slot fill ─────────────────────────────────────────────────────────
    pos_extracted = [e for e in extracted if e.polarity == Polarity.POS]
    neg_extracted = [e for e in extracted if e.polarity == Polarity.NEG]
    changed_slots: set[str] = set()

    for e in pos_extracted:
        if e.slot == "service":
            if s.frame.service != e.value:
                rules_fired.append(f"R8.fill:service")
                _destroy_proposal(s)
                s.frame.service = e.value
                changed_slots.add("service")
        elif e.slot == "date":
            if s.frame.date != e.value:
                rules_fired.append("R8.fill:date")
                _destroy_proposal(s)
                s.frame.date = e.value
                changed_slots.add("date")
        elif e.slot == "time":
            if s.frame.time != e.value:
                rules_fired.append("R8.fill:time")
                _destroy_proposal(s)
                s.frame.time = e.value
                changed_slots.add("time")
        elif e.slot == "name":
            if s.frame.name != e.value:
                rules_fired.append("R8.fill:name")
                _destroy_proposal(s)
                s.frame.name = e.value
                changed_slots.add("name")

    # Handle negations → add to exclusions
    for e in neg_extracted:
        if e.slot == "date" and e.value:
            rules_fired.append("R8.neg:date")
            s.frame.exclusions["dates"].add(e.value)
            if s.frame.date == e.value:
                s.frame.date = None
                _destroy_proposal(s)

    # ── R7: Intent update ─────────────────────────────────────────────────────
    if intent_score.best() is not None and s.frame.intent != intent_score.best():
        best = intent_score.best()
        rules_fired.append(f"R7.intent:{best.value}")
        if best == Intent.RESCHEDULE:
            reply = render(Action.RESCHEDULE_FALLBACK, s.turn_index)
            s.pending = Pending.OPTION
            s.frame.last_prompt = reply
            return Decision(new_session=s, reply_text=reply, action=Action.RESCHEDULE_FALLBACK, rules_fired=rules_fired)
        if best in (Intent.BOOK, Intent.CANCEL):
            if s.frame.intent and s.frame.intent != best:
                _reset_frame(s)
            s.frame.intent = best
            if intent_score.urgent:
                s.frame.urgent = True
        elif best in (Intent.INFO_HOURS, Intent.INFO_DURATION, Intent.INFO_SERVICES):
            reply = _answer_info(best, s, ports)
            if s.frame.last_prompt:
                reply += " " + s.frame.last_prompt
            return Decision(new_session=s, reply_text=reply, action=Action.ANSWER_INFO, rules_fired=rules_fired)
    elif s.frame.intent is None and any(e.polarity == Polarity.POS and e.slot in ("service", "date", "time") for e in extracted):
        rules_fired.append("R7.implicit:BOOK")
        s.frame.intent = Intent.BOOK

    # ── R9: Incremental validation ────────────────────────────────────────────
    if "date" in changed_slots and s.frame.date:
        from assistant.domain.availability import check_date
        now_utc = ports.clock.now_utc()
        closed_dates = ports.bookings._svc._closed_dates if hasattr(ports.bookings, '_svc') else {}
        dr = check_date(s.frame.date, now_utc, ports.tz, closed_dates)
        if not dr.ok:
            rules_fired.append(f"R9.date:{dr.reason.value}")
            s.counters.slot_attempts["date"] = s.counters.slot_attempts.get("date", 0) + 1
            s.frame.date = None
            reply = _date_error_message(dr)
            s.frame.last_prompt = reply
            s.pending = Pending.DATE
            return Decision(new_session=s, reply_text=reply, action=Action.REJECT_INVALID, rules_fired=rules_fired)

    # ── R10: Availability ─────────────────────────────────────────────────────
    if (s.frame.intent == Intent.BOOK and
            s.frame.service and s.frame.date and s.frame.time and s.frame.name):
        svc = _get_service(s)
        if svc:
            start = datetime.combine(s.frame.date, s.frame.time.time() if isinstance(s.frame.time, datetime) else s.frame.time)
            dur = svc.duration_minutes
            free = ports.bookings.is_free(start, dur)
            if not free:
                rules_fired.append("R10.taken")
                alts = ports.bookings.alternatives(
                    s.frame.date,
                    s.frame.time.time() if isinstance(s.frame.time, datetime) else s.frame.time,
                    dur,
                    s.frame.exclusions.get("dates"),
                    s.frame.exclusions.get("weekdays"),
                    s.frame.rejected_starts,
                )
                if alts:
                    offer_set = _build_offer_set_from_slots(s, alts, s.turn_index)
                    s.frame.offers = offer_set
                    s.pending = Pending.OPTION
                    opts_text = _speak_options(alts)
                    reply = f"That slot isn't available. {opts_text}"
                    s.frame.last_prompt = reply
                    return Decision(new_session=s, reply_text=reply, action=Action.OFFER_ALTERNATIVES, rules_fired=rules_fired)
                else:
                    reply = "I can't find an opening in the next 60 days. Shall I ask staff to call you back?"
                    s.pending = Pending.HUMAN_YN
                    s.frame.last_prompt = reply
                    return Decision(new_session=s, reply_text=reply, action=Action.OFFER_ALTERNATIVES, rules_fired=rules_fired)

    # ── R12: Choose next action ───────────────────────────────────────────────
    next_slot = _next_required_slot(s)
    if next_slot is not None:
        rules_fired.append(f"R12.ask:{next_slot}")
        prompt = render(Action.ASK_SLOT, s.turn_index, _sub_key=next_slot)
        _ask(s, Pending(next_slot.upper()), prompt)
        return Decision(new_session=s, reply_text=prompt, action=Action.ASK_SLOT, rules_fired=rules_fired)

    # All slots filled and slot is free → build Proposal
    if s.frame.intent == Intent.BOOK and s.frame.proposal is None:
        svc = _get_service(s)
        if svc and s.frame.date and s.frame.time and s.frame.name:
            rules_fired.append("R12.confirm")
            t = s.frame.time.time() if isinstance(s.frame.time, datetime) else s.frame.time
            start = datetime.combine(s.frame.date, t)
            end = start + timedelta(minutes=svc.duration_minutes)
            proposal = Proposal(
                service=svc.value,
                patient_name=s.frame.name,
                start=start,
                end=end,
                duration_minutes=svc.duration_minutes,
                for_other=s.frame.for_other,
                created_turn=s.turn_index,
            )
            s.frame.proposal = proposal
            s.pending = Pending.CONFIRM_YN
            s.phase = Phase.CONFIRMING
            reply = render_readback(
                service=svc.value,
                patient_name=s.frame.name,
                start=start,
                duration_minutes=svc.duration_minutes,
                turn_index=s.turn_index,
                ambiguous_ampm=s.frame.ambiguous_ampm,
            )
            s.frame.last_prompt = reply
            return Decision(new_session=s, reply_text=reply, action=Action.ASK_CONFIRM, rules_fired=rules_fired)

    # ── Greeting ──────────────────────────────────────────────────────────────
    if s.phase == Phase.GREETING and s.turn_index == 0:
        rules_fired.append("R12.greet")
        reply = render(Action.GREET, 0)
        s.pending = Pending.INTENT
        s.phase = Phase.COLLECTING
        s.frame.last_prompt = reply
        return Decision(new_session=s, reply_text=reply, action=Action.GREET, rules_fired=rules_fired)

    # ── No-match fallback ─────────────────────────────────────────────────────
    rules_fired.append("R16.nomatch")
    s.counters.nomatch += 1
    s.counters.noprogress += 1
    if s.counters.noprogress >= NOPROGRESS_LIMIT:
        return _end_session(s, EndReason.TRANSFER_CALLBACK,
            "I'm sorry, I'm not able to help on this line. Staff will call you back. Goodbye.",
            Action.TRANSFER)
    if s.counters.nomatch >= NOMATCH_HUMAN_THRESHOLD:
        reply = _offer_human(s)
        return Decision(new_session=s, reply_text=reply, action=Action.TRANSFER, rules_fired=rules_fired)
    if s.counters.nomatch == 2:
        reply = (f"I'm having trouble understanding. For example, you could say "
                 f"'book a cleaning on Friday at 2 PM'. {s.frame.last_prompt}")
    else:
        reply = f"Sorry, I didn't catch that. {s.frame.last_prompt}"
    return Decision(new_session=s, reply_text=reply, action=Action.CLARIFY_NOMATCH, rules_fired=rules_fired)


# ── Info answer helper ────────────────────────────────────────────────────────

def _answer_info(intent: Intent, session: Session, ports: Any) -> str:
    if intent == Intent.INFO_HOURS:
        return render(Action.ANSWER_INFO, session.turn_index, _sub_key="hours")
    if intent == Intent.INFO_DURATION:
        if session.frame.service:
            svc = _get_service(session)
            if svc:
                return f"A {svc.display_name} takes {svc.duration_minutes} minutes."
        return render(Action.ANSWER_INFO, session.turn_index, _sub_key="duration")
    return render(Action.ANSWER_INFO, session.turn_index, _sub_key="services")


# ── Validation error messages ─────────────────────────────────────────────────

def _date_error_message(result: Any) -> str:
    from assistant.domain.models import DateCheckReason
    reason = result.reason
    label = getattr(result, "closed_reason_label", "")
    if reason == DateCheckReason.PAST:
        return "That date has passed. Which day instead?"
    if reason == DateCheckReason.BEYOND_HORIZON:
        return "We book up to 60 days ahead. Which day sooner?"
    if reason == DateCheckReason.CLOSED_DATE:
        return f"We're closed that day{' for ' + label if label else ''}. Would another day work?"
    if reason == DateCheckReason.CLOSED_DAY:
        return "We're closed on Sundays. Would Saturday or Monday work?"
    return "I'm sorry, that date isn't available. Which day instead?"
