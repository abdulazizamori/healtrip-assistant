"""In-memory session store and rate limiter.

Prototype choice: a single process keeps state in memory. For horizontal scaling these move to
Redis (sessions with TTL, rate-limit counters) so any instance can serve any request.
Only the minimum is stored: the conversation needed for context, nothing that identifies the patient.
"""

import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field

from .llm import Message


@dataclass
class Session:
    id: str
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    history: list[Message] = field(default_factory=list)
    user_texts: list[str] = field(default_factory=list)
    user_turns: int = 0
    questions_asked: int = 0
    seen_doctor_ids: set[int] = field(default_factory=set)    # grounding: IDs returned by tools in THIS session
    seen_hospital_ids: set[int] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)  # one turn at a time per session


class SessionStore:
    def __init__(self, ttl_minutes: int):
        self._ttl = ttl_minutes * 60
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        s = Session(id=str(uuid.uuid4()))  # server-generated, unguessable
        with self._lock:
            self._evict()
            self._sessions[s.id] = s
        return s

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            self._evict()
            s = self._sessions.get(session_id)
            if s:
                s.last_seen = time.time()
            return s

    def _evict(self) -> None:
        now = time.time()
        for sid in [k for k, v in self._sessions.items() if now - v.last_seen > self._ttl]:
            del self._sessions[sid]


class RateLimiter:
    """Sliding window per key (client IP). Protects cost and availability of the LLM."""

    def __init__(self, per_minute: int):
        self._limit = per_minute
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self._limit:
                return False
            q.append(now)
            return True
