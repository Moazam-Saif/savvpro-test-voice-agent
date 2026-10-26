"""
brain/nlg.py – Natural language generation templates (5.8).

Templates are keyed by Action.  2–3 variants each, selected by
turn_index % n (deterministic, never random).

Word limits (5.1):
  - Normal replies: ~25 words
  - Readbacks and info: ~35 words
  - Compound (R15): ~45 words
"""
from __future__ import annotations

import re
from datetime import datetime, date, time

from assistant.brain.types import Action


# ── Date / time formatters ────────────────────────────────────────────────────

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def format_date(d: date) -> str:
    """'Friday, October 30th'"""
    n = d.day
    suffix = "th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{_DAY_NAMES[d.weekday()]}, {_MONTH_NAMES[d.month]} {n}{suffix}"


def format_time(t: time | datetime) -> str:
    """'3 PM' or '3:30 PM'"""
    if isinstance(t, datetime):
        t = t.time()
    h = t.hour
    m = t.minute
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    if m:
        return f"{h12}:{m:02d} {ampm}"
    return f"{h12} {ampm}"


def format_code(code: str) -> str:
    """'4 7 2 9' – spoken digit by digit"""
    return " ".join(code)


# ── Template registry ─────────────────────────────────────────────────────────

_TEMPLATES: dict[str, list[str]] = {
    Action.GREET.value: [
        "Thanks for calling Bright Smile Dental. This is the automated assistant. "
        "I can book or cancel an appointment. How can I help?",
    ],
    Action.ASK_SLOT.value + ":service": [
        "What service are you looking for? We offer cleanings, checkups, fillings, whitening, extractions, and root canals.",
        "What type of appointment do you need? For example, a cleaning or a checkup.",
    ],
    Action.ASK_SLOT.value + ":date": [
        "What day works for you?",
        "Which day would you like to come in?",
    ],
    Action.ASK_SLOT.value + ":time": [
        "What time would you like?",
        "What time works for you?",
    ],
    Action.ASK_SLOT.value + ":name": [
        "May I have the patient's name?",
        "What name should I put the appointment under?",
    ],
    Action.ASK_SLOT.value + ":intent": [
        "How can I help you today?",
        "What can I do for you?",
    ],
    Action.CLARIFY_NOMATCH.value: [
        "Sorry, I didn't catch that. {prompt}",
        "I'm not sure I understood. {prompt}",
    ],
    Action.CLARIFY_NOMATCH.value + ":2": [
        "I'm having trouble understanding. For example, you could say 'next Tuesday at 10 AM'. {prompt}",
    ],
    Action.ASK_CONFIRM.value: [
        "So that's a {service} for {name} on {date} at {time}, about {duration} minutes. Shall I book it?",
        "Let me confirm: a {service} for {name} on {date} at {time}, about {duration} minutes. Sound good?",
    ],
    Action.BOOK.value: [
        "You're all set! Your confirmation code is {code}. Anything else?",
        "Done! I've booked that for you. Your confirmation code is {code}. Anything else I can help with?",
    ],
    Action.CANCEL_BOOKING.value: [
        "Done. I've cancelled that appointment. Anything else?",
        "Cancelled. Is there anything else I can help with?",
    ],
    Action.ABANDON.value: [
        "Okay, I won't book it. Anything else I can help with?",
        "No problem, I've left that as is. Anything else?",
    ],
    Action.GOODBYE.value: [
        "Goodbye! Have a great day.",
        "Thanks for calling Bright Smile Dental. Goodbye!",
    ],
    Action.TRANSFER.value: [
        "I'll ask our staff to call you back. Goodbye.",
    ],
    Action.HOLD.value: [
        "Sure, take your time.",
        "No problem, I'll wait.",
    ],
    Action.EMERGENCY.value: [
        "If this is a medical emergency, please call emergency services now. Shall I ask our staff to call you?",
    ],
    Action.ASK_NOW_YN.value: [
        "Just checking: is this happening right now?",
    ],
    Action.OUT_OF_SCOPE.value + ":PRICE": [
        "I can't help with pricing or insurance on this line, but our staff can. {prompt}",
    ],
    Action.OUT_OF_SCOPE.value + ":LOCATION": [
        "I can't provide directions or address details here, but you can find that on our website. {prompt}",
    ],
    Action.OUT_OF_SCOPE.value + ":MEDICAL": [
        "I can't give medical advice on this line. Please consult your dentist. {prompt}",
    ],
    Action.ANSWER_INFO.value + ":hours": [
        "We're open Monday to Friday, 9 AM to 5 PM, with a lunch break from 1 to 2 PM. "
        "On Saturdays we're open 10 AM to 2 PM. We're closed Sundays.",
    ],
    Action.ANSWER_INFO.value + ":duration": [
        "A cleaning or checkup takes 30 minutes. A filling, whitening, or extraction takes 60 minutes. "
        "A root canal takes 90 minutes.",
    ],
    Action.ANSWER_INFO.value + ":services": [
        "We offer checkups, cleanings, and whitening. We also do fillings, extractions, and root canals.",
    ],
    Action.RESCHEDULE_FALLBACK.value: [
        "I can't move appointments on this line. I can cancel it and book a new time, "
        "or ask staff to call you. Which would you like?",
    ],
    Action.ACK_NOTED.value: [
        "Okay, noted. What can I help you with?",
        "Got it. How can I help?",
    ],
    Action.REPEAT.value: [
        "{last_prompt}",
    ],
    Action.ERROR_RECOVERY.value: [
        "I'm having trouble, one moment. Could you say that again?",
        "Something went wrong on my end. Could you repeat that?",
    ],
    Action.ASK_VERIFY.value: [
        "May I have your name and the appointment date, or your confirmation code?",
        "Could you give me your name and the date of your appointment, or your confirmation code?",
    ],
    Action.VERIFY_FAILED.value: [
        "I couldn't find a matching appointment. You can also try the confirmation code.",
        "I wasn't able to match that. You can also provide your confirmation code.",
    ],
    Action.OFFER_ALTERNATIVES.value: [
        "That slot isn't available. {options}",
        "I'm afraid that time is taken. {options}",
    ],
}


def render(action: Action, turn_index: int = 0, **kwargs) -> str:
    """
    Render the NLG template for *action* at *turn_index*.

    Extra keyword arguments are substituted into the template string.
    Falls back to a generic message if the key is not found.
    """
    # Try action + sub-key, then plain action
    sub_key = kwargs.pop("_sub_key", None)
    templates = None
    if sub_key:
        templates = _TEMPLATES.get(action.value + ":" + sub_key)
    if templates is None:
        templates = _TEMPLATES.get(action.value)
    if templates is None:
        return f"[missing template: {action.value}]"

    template = templates[turn_index % len(templates)]

    # Substitute known kwargs
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def render_readback(
    service: str,
    patient_name: str,
    start: datetime,
    duration_minutes: int,
    turn_index: int = 0,
    ambiguous_ampm: bool = False,
) -> str:
    """Render the booking readback (R12)."""
    time_str = format_time(start)
    if ambiguous_ampm:
        ampm = "in the afternoon" if start.hour >= 12 else "in the morning"
        time_str = f"{time_str}, {ampm}"
    templates = _TEMPLATES.get(Action.ASK_CONFIRM.value, [])
    template = templates[turn_index % len(templates)] if templates else ""
    return template.format(
        service=service.replace("_", " "),
        name=patient_name,
        date=format_date(start.date()),
        time=time_str,
        duration=duration_minutes,
    )


def render_confirmation_code(code: str, turn_index: int = 0) -> str:
    """'You're all set! Your confirmation code is 4 7 2 9. Anything else?'"""
    templates = _TEMPLATES.get(Action.BOOK.value, [])
    template = templates[turn_index % len(templates)] if templates else ""
    return template.format(code=format_code(code))
