"""
brain/normalize.py – Text normalization pipeline (5.4 NORMALIZE).

Produces a canonical string suitable for all downstream extractors.
The original text is always preserved for name extraction and tracing.
"""
from __future__ import annotations

import re
import unicodedata


# ── Substitution tables ────────────────────────────────────────────────────────

_CURLY_QUOTES = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
})

_WORD_SUBST: list[tuple[re.Pattern, str]] = [
    # a.m. / p.m. → am / pm
    (re.compile(r"\ba\.m\.(?!\w)", re.I), "am"),
    (re.compile(r"\bp\.m\.(?!\w)", re.I), "pm"),
    # o'clock → (dropped)
    (re.compile(r"\bo'clock\b", re.I), ""),
    # Spoken number words for times: "five thirty" → "5 30", etc.
    # Only the most common ones; the time parser handles the rest.
    (re.compile(r"\btwenty[ -]?one\b", re.I), "21"),
    (re.compile(r"\btwenty[ -]?two\b", re.I), "22"),
    (re.compile(r"\btwenty[ -]?three\b", re.I), "23"),
    (re.compile(r"\btwenty[ -]?four\b", re.I), "24"),
    (re.compile(r"\btwenty[ -]?five\b", re.I), "25"),
    (re.compile(r"\btwenty[ -]?six\b", re.I), "26"),
    (re.compile(r"\btwenty[ -]?seven\b", re.I), "27"),
    (re.compile(r"\btwenty[ -]?eight\b", re.I), "28"),
    (re.compile(r"\btwenty[ -]?nine\b", re.I), "29"),
    (re.compile(r"\bthirty\b", re.I), "30"),
    (re.compile(r"\btwenty\b", re.I), "20"),
    (re.compile(r"\beleven\b", re.I), "11"),
    (re.compile(r"\btwelve\b", re.I), "12"),
    (re.compile(r"\bthirteen\b", re.I), "13"),
    (re.compile(r"\bfourteen\b", re.I), "14"),
    (re.compile(r"\bfifteen\b", re.I), "15"),
    (re.compile(r"\bsixteen\b", re.I), "16"),
    (re.compile(r"\bseventeen\b", re.I), "17"),
    (re.compile(r"\beighteen\b", re.I), "18"),
    (re.compile(r"\bnineteen\b", re.I), "19"),
    (re.compile(r"\bone\b", re.I), "1"),
    (re.compile(r"\btwo\b", re.I), "2"),
    (re.compile(r"\bthree\b", re.I), "3"),
    (re.compile(r"\bfour\b", re.I), "4"),
    (re.compile(r"\bfive\b", re.I), "5"),
    (re.compile(r"\bsix\b", re.I), "6"),
    (re.compile(r"\bseven\b", re.I), "7"),
    (re.compile(r"\beight\b", re.I), "8"),
    (re.compile(r"\bnine\b", re.I), "9"),
    (re.compile(r"\bten\b", re.I), "10"),
    # Ordinal words
    (re.compile(r"\bfirst\b", re.I), "1st"),
    (re.compile(r"\bsecond\b", re.I), "2nd"),
    (re.compile(r"\bthird\b", re.I), "3rd"),
    (re.compile(r"\bfourth\b", re.I), "4th"),
    (re.compile(r"\bfifth\b", re.I), "5th"),
    (re.compile(r"\btwenty-first\b", re.I), "21st"),
    (re.compile(r"\btwenty-second\b", re.I), "22nd"),
    (re.compile(r"\btwenty-third\b", re.I), "23rd"),
    (re.compile(r"\btwenty-fourth\b", re.I), "24th"),
    (re.compile(r"\btwenty-fifth\b", re.I), "25th"),
    (re.compile(r"\bthirtieth\b", re.I), "30th"),
    (re.compile(r"\bthirty-first\b", re.I), "31st"),
]

# Punctuation to strip (keep : , ' - / ;)
_STRIP_PUNCT = re.compile(r"[^\w\s:,'\-;/]")
_COLLAPSE_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """
    Full normalization pipeline (5.4):
      1. Unicode NFKC
      2. Curly quotes → straight
      3. Lowercase
      4. Word substitutions (a.m.→am, number words, ordinals)
      5. Strip punctuation except : , ' - /
      6. Collapse whitespace
    """
    # 1. NFKC + curly quotes
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_CURLY_QUOTES)
    # 2. Lowercase
    text = text.lower()
    # 3. Word substitutions
    for pattern, replacement in _WORD_SUBST:
        text = pattern.sub(replacement, text)
    # 4. Strip punctuation (preserve : , ' - /)
    text = _STRIP_PUNCT.sub(" ", text)
    # 5. Collapse whitespace
    text = _COLLAPSE_WS.sub(" ", text).strip()
    return text
