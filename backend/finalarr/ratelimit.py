"""Small in-process sliding-window rate limiter (single worker, see PLAN.md 4.5)."""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Record a hit for ``key``; False when the limit is already reached."""
        with self._lock:
            hits = self._recent(key)
            if len(hits) >= self._limit:
                return False
            hits.append(self._clock())
            return True

    def forgive(self, key: str) -> None:
        """Give back the most recent hit, e.g. after a successful login."""
        with self._lock:
            hits = self._hits.get(key)
            if hits:
                hits.pop()

    def _recent(self, key: str) -> deque[float]:
        hits = self._hits[key]
        cutoff = self._clock() - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return hits
