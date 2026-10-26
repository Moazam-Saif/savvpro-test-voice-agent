"""
brain/types.py – All state types and enums for the brain.

These types are the single source of truth for the dialogue manager's
state machine.  Nothing outside brain/ and domain/ should import from here
other than through Ports.

Every datetime stored here is a NAIVE clinic-local wall-clock time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


# ── Enums ─────────────────────────────────────────────────────────────────────

class Phase(str, Enum):
    GREETING = "GREETING"
    COLLECTING = "COLLECTING"
    IDENTIFYING = "IDENTIFYING"
    CHOOSING_OPTION = "CHOOSING_OPTION"
    CONFIRMING = "CONFIRMING"
    AWAITING_MORE = "AWAITING_MORE"
    ENDED = "ENDED"


class Pending(str, Enum):
    NONE = "NONE"
    INTENT = "INTENT"
    SERVICE = "SERVICE"
    DATE = "DATE"
    TIME = "TIME"
    NAME = "NAME"
    VERIFY = "VERIFY"
    CONFIRM_YN = "CONFIRM_YN"
    CANCEL_YN = "CANCEL_YN"
    OPTION = "OPTION"
    CHANGE_WHICH = "CHANGE_WHICH"
    ANYTHING_ELSE = "ANYTHING_ELSE"
    HUMAN_YN = "HUMAN_YN"
    NOW_YN = "NOW_YN"


class EndReason(str, Enum):
    GOODBYE = "GOODBYE"
    SILENCE = "SILENCE"
    TRANSFER_CALLBACK = "TRANSFER_CALLBACK"
    HANGUP = "HANGUP"
    TURN_LIMIT = "TURN_LIMIT"


class Intent(str, Enum):
    BOOK = "BOOK"
    CANCEL = "CANCEL"
    RESCHEDULE = "RESCHEDULE"
    INFO_HOURS = "INFO_HOURS"
    INFO_DURATION = "INFO_DURATION"
    INFO_SERVICES = "INFO_SERVICES"


class Polarity(str, Enum):
    POS = "POS"
    NEG = "NEG"


class OfferKind(str, Enum):
    SLOT = "SLOT"     # Time-slot alternatives
    VALUE = "VALUE"   # Value choices (service, date, intent, etc.)


class Action(str, Enum):
    GREET = "GREET"
    ASK_SLOT = "ASK_SLOT"
    ASK_CONFIRM = "ASK_CONFIRM"
    OFFER_ALTERNATIVES = "OFFER_ALTERNATIVES"
    OFFER_VALUES = "OFFER_VALUES"
    CLARIFY_OPTION = "CLARIFY_OPTION"
    CLARIFY_COMPOUND = "CLARIFY_COMPOUND"
    ASK_VERIFY = "ASK_VERIFY"
    VERIFY_FAILED = "VERIFY_FAILED"
    BOOK = "BOOK"
    CANCEL_BOOKING = "CANCEL_BOOKING"
    ABANDON = "ABANDON"
    RESCHEDULE_FALLBACK = "RESCHEDULE_FALLBACK"
    ANSWER_INFO = "ANSWER_INFO"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    EMERGENCY = "EMERGENCY"
    ASK_NOW_YN = "ASK_NOW_YN"
    ACK_NOTED = "ACK_NOTED"
    REPEAT = "REPEAT"
    HOLD = "HOLD"
    WAIT = "WAIT"
    REJECT_INVALID = "REJECT_INVALID"
    CLARIFY_NOMATCH = "CLARIFY_NOMATCH"
    SILENCE_REPROMPT = "SILENCE_REPROMPT"
    TRANSFER = "TRANSFER"
    GOODBYE = "GOODBYE"
    ERROR_RECOVERY = "ERROR_RECOVERY"


# ── Extracted value ───────────────────────────────────────────────────────────

@dataclass
class Extracted:
    """A single value extracted by an NLU extractor."""
    slot: str          # e.g. "date", "time", "service", "intent", "yesno"
    value: Any         # The extracted value (typed per slot)
    span: str          # Original text span that matched
    extractor: str     # Name of the extractor module
    polarity: Polarity = Polarity.POS
    clause: int = 0    # Which clause in the utterance


# ── Slot options and offers ───────────────────────────────────────────────────

@dataclass
class SlotOption:
    """A concrete availability slot or a value choice."""
    start: datetime | None         # For SLOT offers; None for VALUE offers
    end: datetime | None = None
    slot: str = ""                 # For VALUE offers: the slot name
    value: Any = None              # For VALUE offers: the candidate value
    label: str = ""                # Human-readable label


@dataclass
class OfferSet:
    """A typed set of options presented to the caller (R14)."""
    offer_id: int                  # turn_index at creation
    kind: OfferKind
    value_slot: str = ""           # For VALUE offers
    options: list[SlotOption] = field(default_factory=list)
    created_turn: int = 0


# ── Proposals ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Proposal:
    """
    Frozen snapshot of a booking intent (R13).
    Exists only while pending=CONFIRM_YN and the last reply was its readback.
    """
    service: str                # Service.value
    patient_name: str
    start: datetime             # Naive clinic-local
    end: datetime
    duration_minutes: int
    for_other: bool
    created_turn: int


@dataclass(frozen=True)
class CancelProposal:
    """Frozen snapshot of a cancel intent (X9)."""
    booking_id: str
    service: str
    start: datetime
    created_turn: int


# ── Verify state ──────────────────────────────────────────────────────────────

@dataclass
class VerifyState:
    """Kept separate from booking slots so name lookups are never echoed (R11)."""
    lookup_name: str = ""
    lookup_date: date | None = None
    lookup_code: str = ""
    candidate_ids: list[str] = field(default_factory=list)  # internal only
    verified_id: str = ""


# ── Counters ──────────────────────────────────────────────────────────────────

@dataclass
class Counters:
    silence: int = 0
    nomatch: int = 0
    reject: int = 0
    slot_attempts: dict[str, int] = field(default_factory=dict)
    verify_failures: int = 0    # session-wide, never reset by a new flow
    oos_streak: int = 0
    human_offers: int = 0
    neg_only_streak: int = 0
    lowconf_streak: int = 0
    noprogress: int = 0


# ── Frame ─────────────────────────────────────────────────────────────────────

@dataclass
class Frame:
    """Per-task state (reset after every completed or abandoned task)."""
    intent: Intent | None = None
    service: str | None = None         # Service.value
    date: date | None = None
    time: datetime | None = None       # Stored as datetime for convenience; only .time() matters

    # Date / window preferences
    time_window: str | None = None     # "MORNING" | "AFTERNOON"
    date_hint: str | None = None       # "NEXT_WEEK" | "THIS_WEEKEND"
    week_anchor: date | None = None    # Monday of the hinted week
    pref_mode: str | None = None       # "EARLIEST"

    # Ambiguity flags
    ambiguous_ampm: bool = False
    urgent: bool = False

    # Patient info
    name: str | None = None            # Patient name
    caller_name: str | None = None
    for_other: bool = False

    # Exclusions / rejections
    exclusions: dict = field(default_factory=lambda: {
        "weekdays": set(),   # set[int] (0=Mon)
        "dates": set(),      # set[date]
        "windows": set(),    # set[str] ("MORNING"|"AFTERNOON")
        "services": set(),   # set[str]
    })
    rejected_starts: set[datetime] = field(default_factory=set)

    # Offers and proposals
    offers: OfferSet | None = None
    proposal: Proposal | None = None
    cancel_proposal: CancelProposal | None = None

    # Verification (cancel flow)
    verify: VerifyState = field(default_factory=VerifyState)

    # Prompt tracking
    last_prompt: str = ""
    resume_pending: Pending = Pending.NONE


# ── Session ───────────────────────────────────────────────────────────────────

@dataclass
class Session:
    """Whole-call state (lives for the lifetime of the call)."""
    session_id: str
    turn_index: int = 0
    last_turn_no: int = 0
    last_response: "TurnResult | None" = None

    frame: Frame = field(default_factory=Frame)
    carry_exclusions: dict = field(default_factory=lambda: {
        "weekdays": set(),
        "dates": set(),
        "windows": set(),
        "services": set(),
    })

    counters: Counters = field(default_factory=Counters)

    # Post-booking tracking
    last_booking: dict | None = None   # {"id": str, "summary": str, "code": str}
    verified_booking_ids: set[str] = field(default_factory=set)

    # Call lifecycle
    hold_grace: int = 0
    filler_streak: int = 0
    ended: bool = False
    end_reason: EndReason | None = None

    # Phase / pending
    phase: Phase = Phase.GREETING
    pending: Pending = Pending.NONE


# ── Turn IO ───────────────────────────────────────────────────────────────────

@dataclass
class TurnInput:
    type: str                   # "utterance" | "silence" | "hangup"
    text: str = ""
    confidence: float | None = None
    turn_no: int = 1


@dataclass
class TraceEntry:
    """One entry in the decision trace for a turn."""
    turn: int
    input: dict
    normalized: str
    intent_scores: dict[str, float]
    extracted: list[dict]
    phase_before: str
    phase_after: str
    pending_before: str
    pending_after: str
    rules_fired: list[str]
    counters: dict
    offers: dict | None
    proposal: dict | None
    effect: str | None
    action: str
    reason: str


@dataclass
class TurnResult:
    """Everything the engine returns for one turn."""
    reply_text: str
    action: Action
    ended: bool
    end_reason: EndReason | None
    phase: Phase
    pending: Pending
    frame: dict           # JSON-serializable snapshot of the frame
    counters: dict
    last_booking: dict | None
    trace: TraceEntry
