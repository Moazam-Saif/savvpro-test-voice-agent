"""
brain/nlu/services.py – Service extraction (5.4 SERVICE EXTRACTION).

Whole-word synonym lexicon.  Negative phrases ("fill out", "fill in",
"fill up") are excluded.  No fuzzy fallback in P0/P1.
"""
from __future__ import annotations

import re

from assistant.brain.types import Extracted, Polarity
from assistant.brain.nlu.polarity import has_negation_before
from assistant.domain.models import Service

# ── Negative phrases that must never match ────────────────────────────────────
_NEG_PHRASES = re.compile(r"\bfill (out|in|up)\b", re.I)

# ── Synonym → Service map (whole-word patterns) ───────────────────────────────
_SYNONYMS: list[tuple[re.Pattern, Service]] = [
    (re.compile(r"\b(clean(?:ing)?|scale and polish|hygiene)\b", re.I), Service.CLEANING),
    (re.compile(r"\b(check[ -]?up|exam|checkup|consultation)\b", re.I), Service.CHECKUP),
    # "fill" must not match "fill out" etc.
    (re.compile(r"\b(filling|cavity|fill)\b(?!\s+(out|in|up))", re.I), Service.FILLING),
    (re.compile(r"\b(whiten(?:ing)?|bleach(?:ing)?)\b", re.I), Service.WHITENING),
    (re.compile(r"\b(extraction|pull(?:ing)?|pulled|tooth out|remove a tooth)\b", re.I), Service.EXTRACTION),
    (re.compile(r"\broot canal\b", re.I), Service.ROOT_CANAL),
]


def extract_services(clause: str, clause_idx: int = 0) -> list[Extracted]:
    """Return Extracted entries for every service mention in *clause*."""
    # Mask negative phrases so "fill out" never yields FILLING
    masked = _NEG_PHRASES.sub(lambda m: " " * len(m.group()), clause)
    results: list[Extracted] = []
    for pat, service in _SYNONYMS:
        for m in pat.finditer(masked):
            neg = has_negation_before(m.start(), clause)
            results.append(Extracted(
                slot="service",
                value=service.value,
                span=m.group(),
                extractor="services",
                polarity=Polarity.NEG if neg else Polarity.POS,
                clause=clause_idx,
            ))
    return results
