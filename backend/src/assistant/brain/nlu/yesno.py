"""
brain/nlu/yesno.py – Yes/No extraction (5.4 YES AND NO).

Interpreted only when pending is in a yes/no state.
A yes or no COMBINED with slot values is a correction, not a confirmation.
"""
from __future__ import annotations

import re

YES_PATTERNS = re.compile(
    r"\b(yes|yeah|yep|sure|correct|right|that'?s right|ok|okay|"
    r"sounds good|that works|go ahead|please do|perfect)\b",
    re.I,
)
NO_PATTERNS = re.compile(
    r"\b(no|nope|nah|not really|wrong|that'?s wrong|incorrect)\b",
    re.I,
)

# Abandon cues – "no, never mind" etc. during a booking readback
ABANDON_CUES = re.compile(
    r"\b(never mind|nevermind|forget it|cancel that)\b",
    re.I,
)


def extract_yesno(text: str) -> str | None:
    """Return 'yes', 'no', or None."""
    has_yes = bool(YES_PATTERNS.search(text))
    has_no = bool(NO_PATTERNS.search(text))
    if has_yes and not has_no:
        return "yes"
    if has_no and not has_yes:
        return "no"
    return None


def has_abandon(text: str) -> bool:
    return bool(ABANDON_CUES.search(text))
