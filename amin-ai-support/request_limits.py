"""Bound CPU/model usage for scoped customer requests in one Python process.

These limits are per-process, not a distributed quota system. They do not
replace WAF, request-body filtering, server-wide quotas or abuse monitoring.
"""
from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic


class SlidingLimits:
    def __init__(self, clock=monotonic):
        self.clock = clock
        self.lock = Lock()
        self.events = {}

    def allow(self, token_id: str, route: str, cap: int, window_s: int = 60) -> bool:
        if not token_id or route not in {"chat", "ticket"}:
            raise ValueError("Invalid rate limit scope")
        if cap < 1 or window_s < 1:
            raise ValueError("Invalid rate limit parameters")
        now = self.clock()
        key = (token_id, route)
        with self.lock:
            history = self.events.setdefault(key, deque())
            while history and history[0] <= now - window_s:
                history.popleft()
            if len(history) >= cap:
                return False
            history.append(now)
            # Periodically prune unused token IDs to limit state growth.
            if len(self.events) > 1024:
                for item, times in list(self.events.items()):
                    if not times or times[-1] <= now - window_s:
                        del self.events[item]
            return True
