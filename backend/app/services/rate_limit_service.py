"""A small per-client rate limit for uploads.

Processing one upload costs OCR on every page and, when the interpreter is on, several
model requests. Without a limit a single client can exhaust the provider quota for
everybody, which is not a theoretical worry on a shared demo deployment with two API
keys. This is a sliding window held in memory: it is enough for a single process, and a
multi-process deployment would move the same counters to Redis without changing callers.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int = 12, window_seconds: int = 300) -> None:
        self.limit = max(1, limit)
        self.window = max(1, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self.allowed = 0
        self.rejected = 0

    def check(self, client: str) -> tuple[bool, int]:
        """Returns (allowed, seconds until a slot frees up)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[client]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                self.rejected += 1
                return False, int(self.window - (now - hits[0])) + 1
            hits.append(now)
            self.allowed += 1
            # Keep the table from growing without bound on a long-lived process.
            if len(self._hits) > 4096:
                for key in [k for k, v in self._hits.items() if not v][:1024]:
                    self._hits.pop(key, None)
            return True, 0

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "limit_per_window": self.limit,
                "window_seconds": self.window,
                "allowed": self.allowed,
                "rejected": self.rejected,
                "tracked_clients": len(self._hits),
            }
