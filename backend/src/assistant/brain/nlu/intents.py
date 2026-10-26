"""
brain/nlu/intents.py – Intent extraction and scoring (5.4 INTENT SCORING).

Only POS clauses contribute to scoring.  CANCEL and RESCHEDULE beat BOOK
when both match.  Implicit BOOK fires when no intent scores >= 1.0 but a
POS service, date, or time was extracted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from assistant.brain.types import Intent, Polarity

# ── Keyword tables ────────────────────────────────────────────────────────────
# Each entry is (whole-word pattern, score)
_BOOK_KEYWORDS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bbook\b", re.I), 2.0),
    (re.compile(r"\bschedule\b", re.I), 2.0),
    (re.compile(r"\bmake an appointment\b", re.I), 2.0),
    (re.compile(r"\bappointment\b", re.I), 1.0),
    (re.compile(r"\bcome in\b", re.I), 1.0),
    (re.compile(r"\bfit me in\b", re.I), 1.5),
    (re.compile(r"\bsee the dentist\b", re.I), 1.5),
    (re.compile(r"\bset up\b", re.I), 1.0),
    (re.compile(r"\bavailability\b", re.I), 1.0),
    (re.compile(r"\bany openings\b", re.I), 1.0),
    (re.compile(r"\bearliest available\b", re.I), 1.5),
    (re.compile(r"\bnext available\b", re.I), 1.5),
    (re.compile(r"\bfirst available\b", re.I), 1.5),
    (re.compile(r"\bsoonest\b", re.I), 1.5),
    (re.compile(r"\bas soon as possible\b", re.I), 1.5),
]

# Urgent symptoms – set Frame.urgent=True and add BOOK score
_URGENT_KEYWORDS: list[re.Pattern] = [
    re.compile(r"\btoothache\b", re.I),
    re.compile(r"\btooth hurts\b", re.I),
    re.compile(r"\btooth pain\b", re.I),
    re.compile(r"\bchipped tooth\b", re.I),
    re.compile(r"\bbroken tooth\b", re.I),
]

_CANCEL_KEYWORDS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bcancel\b", re.I), 3.0),
    (re.compile(r"\bcall off\b", re.I), 2.5),
    (re.compile(r"\bdelete\b", re.I), 2.0),
    (re.compile(r"\bdon'?t need\b", re.I), 1.5),
    (re.compile(r"\bcan'?t make it\b", re.I), 2.5),
    (re.compile(r"\bcan'?t make my appointment\b", re.I), 2.5),
    (re.compile(r"\bcannot make it\b", re.I), 2.5),
    (re.compile(r"\bwon'?t be able to come\b", re.I), 2.5),
]

_RESCHEDULE_KEYWORDS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\breschedule\b", re.I), 3.0),
    (re.compile(r"\bchange my appointment\b", re.I), 2.5),
    (re.compile(r"\bcancel and rebook\b", re.I), 2.5),
    (re.compile(r"\bmove\b", re.I), 2.0),
    (re.compile(r"\bpush back\b", re.I), 2.0),
    (re.compile(r"\bdifferent day\b", re.I), 1.5),
]

_INFO_HOURS_KEYWORDS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bhours\b", re.I), 2.0),
    (re.compile(r"\bopen\b", re.I), 1.5),
    (re.compile(r"\bclose\b(?!st)", re.I), 1.5),
    (re.compile(r"\bwhat time do you\b", re.I), 2.0),
]

_INFO_DURATION_KEYWORDS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bhow long\b", re.I), 2.5),
]

_INFO_SERVICES_KEYWORDS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bwhat do you offer\b", re.I), 2.5),
    (re.compile(r"\bwhat treatments do you offer\b", re.I), 2.5),
    (re.compile(r"\bwhat do you do\b", re.I), 2.0),
    (re.compile(r"\bservices\b", re.I), 2.0),
]

INTENT_THRESHOLD = 1.0


@dataclass
class IntentScore:
    scores: dict[str, float] = field(default_factory=dict)
    urgent: bool = False

    def best(self) -> Intent | None:
        """Return the highest-scoring intent at or above threshold.
        Precedence: CANCEL/RESCHEDULE beat BOOK."""
        if not self.scores:
            return None
        best_intent = max(self.scores, key=lambda k: self.scores[k])
        if self.scores[best_intent] < INTENT_THRESHOLD:
            return None
        return Intent(best_intent)


def score_intents(pos_text: str) -> IntentScore:
    """
    Score all intents against POS text (positive clauses joined).
    Returns an IntentScore with per-intent totals and the urgent flag.
    """
    result = IntentScore()

    def _tally(keywords: list[tuple[re.Pattern, float]], intent_name: str) -> None:
        total = 0.0
        for pat, weight in keywords:
            if pat.search(pos_text):
                total += weight
        if total > 0:
            result.scores[intent_name] = total

    # Urgent check
    for pat in _URGENT_KEYWORDS:
        if pat.search(pos_text):
            result.urgent = True
            result.scores[Intent.BOOK.value] = (
                result.scores.get(Intent.BOOK.value, 0.0) + 1.5
            )

    _tally(_BOOK_KEYWORDS, Intent.BOOK.value)
    _tally(_CANCEL_KEYWORDS, Intent.CANCEL.value)
    _tally(_RESCHEDULE_KEYWORDS, Intent.RESCHEDULE.value)
    _tally(_INFO_HOURS_KEYWORDS, Intent.INFO_HOURS.value)
    _tally(_INFO_DURATION_KEYWORDS, Intent.INFO_DURATION.value)
    _tally(_INFO_SERVICES_KEYWORDS, Intent.INFO_SERVICES.value)

    # CANCEL and RESCHEDULE beat BOOK when both match (precedence rule)
    if Intent.CANCEL.value in result.scores or Intent.RESCHEDULE.value in result.scores:
        result.scores.pop(Intent.BOOK.value, None)

    return result
