"""
brain/nlu/polarity.py – Clause splitting and polarity detection (5.4).

Every extraction is tagged POS or NEG based on negation cues in its clause.
Repair cues ("no wait", "actually") produce a replacement rather than an
exclusion when a positive value follows in the same utterance.
"""
from __future__ import annotations

import re

# ── Clause splitters ───────────────────────────────────────────────────────────
# "Friday or Saturday" must NOT be split (multi-value), so "or" is not a splitter.
_CLAUSE_SPLIT = re.compile(
    r"[;.]|(?<!\bFriday\b),(?!\s+\bor\b)"   # commas (rough; refine if needed)
    r"|\bbut\b|\band then\b|\bactually\b|\binstead\b|\bwait\b",
    re.I,
)

# ── Repair cues ────────────────────────────────────────────────────────────────
REPAIR_CUES = re.compile(
    r"\bno wait\b|\bactually\b|\bi mean\b|\bsorry\b|\bscratch that\b"
    r"|\bmake that\b|\brather\b",
    re.I,
)

# ── Negation cues ─────────────────────────────────────────────────────────────
NEG_CUES = re.compile(
    r"\bnot\b|\bno\b(?!\s+wait)|\bnever\b|\bwithout\b"
    r"|\bdon'?t\b|\bdoesn'?t\b|\bisn'?t\b|\bcan'?t\b|\bwon'?t\b"
    r"|\bcannot\b|\bcannot do\b|\bcan'?t do\b|\bdon'?t want to\b"
    r"|\banything but\b|\bother than\b|\bexcept\b|\binstead of\b",
    re.I,
)

# Tokens covered by a single negation cue (up to 4 tokens after the cue)
NEG_SCOPE_TOKENS = 4


def split_clauses(text: str) -> list[str]:
    """Split *text* into clauses.  Each clause is a stripped non-empty string."""
    parts = _CLAUSE_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def has_negation_before(span_start: int, clause: str) -> bool:
    """
    True if a negation cue appears in *clause* before *span_start* and
    the span is within NEG_SCOPE_TOKENS tokens of it, without crossing clause boundaries.
    """
    for m in NEG_CUES.finditer(clause):
        if m.end() <= span_start:
            # Count tokens between end of cue and start of span
            between = clause[m.end():span_start]
            if any(p in between for p in (",", ";", ".")):
                continue
            tokens_between = len(between.split())
            if tokens_between <= NEG_SCOPE_TOKENS:
                return True
    return False


def has_repair_cue(text: str) -> bool:
    return bool(REPAIR_CUES.search(text))
