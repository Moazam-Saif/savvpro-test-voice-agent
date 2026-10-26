"""
brain/nlu/names.py – Name extraction (5.4 NAMES).

Patterns: "my name is X", "this is X", "it's X", "I'm X", "X speaking".
With pending=NAME or VERIFY accepts a bare answer.
"""
from __future__ import annotations

import re

_STOP_WORDS = {
    "um", "uh", "er", "yeah", "yes", "no", "okay", "ok", "so", "well",
    "the", "a", "an", "and", "or", "but", "for", "at", "on", "in",
}

_SERVICE_WORDS = {
    "cleaning", "checkup", "filling", "whitening", "extraction", "root", "canal",
}

_WEEKDAY_WORDS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}

_RELATION_WORDS = re.compile(
    r"\b(for my (son|daughter|wife|husband|mother|father|friend|kid|partner)|"
    r"my (son|daughter|wife|husband|mother|father|friend|kid|partner)|"
    r"someone else|for him|for her|for them)\b",
    re.I,
)

_NAME_PATTERNS = [
    re.compile(r"\bmy name is ([A-Za-z][A-Za-z' \-]{0,30})", re.I),
    re.compile(r"\bthis is ([A-Za-z][A-Za-z' \-]{0,30})", re.I),
    re.compile(r"\bit'?s ([A-Za-z][A-Za-z' \-]{0,30})", re.I),
    re.compile(r"\bi'?m ([A-Za-z][A-Za-z' \-]{0,30})", re.I),
    re.compile(r"\bfor ([A-Za-z][A-Za-z' \-]{0,30})\b", re.I),
    re.compile(r"([A-Za-z][A-Za-z' \-]{0,30}) speaking\b", re.I),
]

_FOR_PATIENT = re.compile(
    r"\bfor (?:my )?(son|daughter|wife|husband|mother|father|friend|kid|partner) ([A-Za-z][A-Za-z' \-]{0,30})",
    re.I,
)


def _clean_name(raw: str) -> str | None:
    """Strip fillers, validate tokens (no digits, no stop/service/weekday words)."""
    tokens = raw.strip().split()[:3]   # max 3 tokens
    clean = []
    for tok in tokens:
        t = tok.strip(".,;:'\"").lower()
        if not t or any(c.isdigit() for c in t):
            break
        if t in _STOP_WORDS or t in _SERVICE_WORDS or t in _WEEKDAY_WORDS:
            break
        clean.append(tok.strip(".,;:'\""))
    if not clean:
        return None
    return " ".join(clean).title()


def extract_name(text: str, bare_ok: bool = False) -> tuple[str | None, bool, str | None]:
    """
    Returns (name, for_other, direct_patient_name).

    name: the extracted name (caller or patient depending on context)
    for_other: True if a relation phrase was detected
    direct_patient_name: set if "for my son Ali" pattern matches
    """
    # Check "for my son Ali" pattern
    m = _FOR_PATIENT.search(text)
    if m:
        patient = _clean_name(m.group(2))
        return patient, True, patient

    # Check relation words (for_other=True, no name yet)
    if _RELATION_WORDS.search(text):
        # Try to extract a name anyway
        for pat in _NAME_PATTERNS:
            m2 = pat.search(text)
            if m2:
                name = _clean_name(m2.group(1))
                if name:
                    return name, True, None
        return None, True, None

    # Named patterns
    for pat in _NAME_PATTERNS:
        m2 = pat.search(text)
        if m2:
            name = _clean_name(m2.group(1))
            if name:
                return name, False, None

    # Bare answer (only when pending=NAME or VERIFY)
    if bare_ok:
        name = _clean_name(text)
        if name:
            return name, False, None

    return None, False, None


def extract_code(text: str, pending_allows: bool = False) -> str | None:
    """
    Extract a 4-digit confirmation code.
    Only extracted when pending allows or the text contains "code"/"confirmation".
    """
    if not pending_allows and not re.search(r"\b(code|confirmation)\b", text, re.I):
        return None
    # 4 consecutive digits
    m = re.search(r"\b(\d{4})\b", text)
    if m:
        return m.group(1)
    # Four spoken digits: "four seven two nine"
    digit_words = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    }
    tokens = text.lower().split()
    found: list[str] = []
    for tok in tokens:
        if tok in digit_words:
            found.append(digit_words[tok])
            if len(found) == 4:
                return "".join(found)
        else:
            found = []
    return None
