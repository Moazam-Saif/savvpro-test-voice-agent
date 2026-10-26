"""
sessions.py – SessionStore: per-session state with TTL and per-session lock.

Rules:
  - 30-minute idle TTL with lazy cleanup.
  - 200-turn cap (TURN_LIMIT).
  - Per-session threading.Lock to serialize concurrent requests.
  - Session IDs are unguessable (secrets.token_urlsafe(16)).
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

from assistant.brain.types import Frame, Session, Phase, Pending, Counters


SESSION_TTL_SECONDS = 30 * 60   # 30 minutes
MAX_TURNS = 200


@dataclass
class _Entry:
    session: Session
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_access: float = field(default_factory=time.monotonic)


class SessionStore:
    """Thread-safe in-memory session registry."""

    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}
        self._global_lock = threading.Lock()

    def create(self) -> Session:
        """Create a new session and return it."""
        session_id = secrets.token_urlsafe(16)
        session = Session(session_id=session_id)
        entry = _Entry(session=session)
        with self._global_lock:
            self._store[session_id] = entry
            self._lazy_cleanup()
        return session

    def get(self, session_id: str) -> tuple[Session, threading.Lock] | None:
        """Return (session, lock) or None if not found / expired."""
        with self._global_lock:
            entry = self._store.get(session_id)
            if entry is None:
                return None
            if self._is_expired(entry):
                del self._store[session_id]
                return None
            entry.last_access = time.monotonic()
        return entry.session, entry.lock

    def _is_expired(self, entry: _Entry) -> bool:
        return (time.monotonic() - entry.last_access) > SESSION_TTL_SECONDS

    def _lazy_cleanup(self) -> None:
        """Remove expired sessions (called under the global lock)."""
        expired = [sid for sid, e in self._store.items() if self._is_expired(e)]
        for sid in expired:
            del self._store[sid]
