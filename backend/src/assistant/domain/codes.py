"""
domain/codes.py – Confirmation-code generator.

Generates unique 4-digit string codes.  The generator is seedable for
deterministic tests.  The brain never generates codes directly; it goes
through BookingService.
"""
from __future__ import annotations

import random


class CodeGenerator:
    """Seedable 4-digit confirmation-code generator.

    Usage:
        gen = CodeGenerator(seed=42)
        code = gen.next_code(existing={"1234", "5678"})
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def next_code(self, existing: set[str]) -> str:
        """Return a 4-digit code (zero-padded) not in *existing*.

        Raises RuntimeError after 10 000 attempts (the space is 10 000 codes,
        so exhaustion is a config/test error).
        """
        for _ in range(10_000):
            code = f"{self._rng.randint(0, 9999):04d}"
            if code not in existing:
                return code
        raise RuntimeError("CodeGenerator: code space exhausted")
