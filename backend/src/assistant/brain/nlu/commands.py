"""
brain/nlu/commands.py – Global command detection (5.4 GLOBAL COMMANDS).

Gating: a command fires only if it is the whole utterance (after removing
fillers/politeness words) OR nothing else was extracted.
HUMAN is the exception: it always fires.
"""
from __future__ import annotations

import re
from enum import Enum


class Command(str, Enum):
    ROBOT = "ROBOT"
    REPEAT = "REPEAT"
    HOLD = "HOLD"
    START_OVER = "START_OVER"
    HUMAN = "HUMAN"
    BYE = "BYE"


_FILLER_POLITE = re.compile(
    r"\b(please|ok|okay|so|um|uh|er|ah|well|hmm|right)\b", re.I
)

_PATTERNS: list[tuple[re.Pattern, Command]] = [
    (re.compile(r"\b(are you a (robot|machine)|real person|human\b|automated|is this a robot)\b", re.I), Command.ROBOT),
    (re.compile(r"\b(repeat|say that again|pardon|come again|what was that)\b|^what$", re.I), Command.REPEAT),
    (re.compile(r"\b(hold on|wait|one second|one moment|give me a minute|hang on|let me check|let me look)\b", re.I), Command.HOLD),
    (re.compile(r"\b(start over|start again|forget it|never mind)\b", re.I), Command.START_OVER),
    # HUMAN – always fires (checked separately)
    (re.compile(r"\b(human|agent|operator|speak to someone|talk to someone|receptionist|a person)\b", re.I), Command.HUMAN),
    (re.compile(r"\b(bye|goodbye|that'?s all|hang up)\b", re.I), Command.BYE),
]


def detect_command(text: str, anything_extracted: bool = False) -> Command | None:
    """
    Return the matched Command or None.
    HUMAN always fires; other commands only when the utterance is pure command.
    """
    stripped = _FILLER_POLITE.sub("", text).strip()

    for pat, cmd in _PATTERNS:
        if pat.search(text):
            if cmd == Command.HUMAN:
                return Command.HUMAN   # always fires
            # Gate: fires only if whole utterance or nothing else extracted
            if not anything_extracted or not stripped.replace(pat.search(stripped).group() if pat.search(stripped) else "", "").strip():  # noqa: E501
                return cmd
    return None


def is_filler(text: str) -> bool:
    """True if the utterance is entirely filler tokens."""
    filler = re.compile(
        r"^(um|uh|er|ah|hmm|mm-hmm|mhm|uh-huh|well|let me think)[\s,]*$", re.I
    )
    return bool(filler.match(text.strip()))


def is_out_of_scope(text: str) -> str | None:
    """Return the OOS group name or None."""
    groups = {
        "PRICE": re.compile(r"\b(price|cost|how much|insurance|pay|payment|fee|discount)\b", re.I),
        "LOCATION": re.compile(r"\b(address|where are you|location|directions|parking)\b", re.I),
        "MEDICAL": re.compile(r"\b(should i take|antibiotic|painkiller|medicine|is it normal|is it safe)\b", re.I),
    }
    for group, pat in groups.items():
        if pat.search(text):
            return group
    return None


def detect_emergency(text: str) -> str | None:
    """
    Return emergency classification or None.
    PRESENT | PAST | AMBIGUOUS (see 5.4 EMERGENCY)
    """
    emergency_phrases = re.compile(
        r"\b(severe pain|bleeding|swollen face|knocked out|can'?t breathe|"
        r"cannot breathe|trouble breathing)\b",
        re.I,
    )
    neg_in_scope = re.compile(
        r"\b(isn'?t|is not|no |not |n'?t)\b",
        re.I,
    )
    past_cues = re.compile(
        r"\b(was|were|had|used to|last week|yesterday|earlier|ago)\b",
        re.I,
    )
    present_cues = re.compile(
        r"\b(is|am|are|have|right now|currently|still)\b",
        re.I,
    )

    m = emergency_phrases.search(text)
    if not m:
        return None

    # Check negation in scope of the match
    span_start = m.start()
    prefix = text[:span_start]
    if neg_in_scope.search(prefix[-30:] if len(prefix) > 30 else prefix):
        return None   # NEGATED – ignore

    # Classify tense
    if past_cues.search(text) and not present_cues.search(text):
        return "PAST"
    if present_cues.search(text):
        return "PRESENT"
    return "AMBIGUOUS"
