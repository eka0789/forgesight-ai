"""Simple sliding-window rate limiter with Redis backend and in-memory fallback."""
from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, redis_url: str | None = None):
        self._redis = None
        self._local: dict[str, deque[float]] = defaultdict(deque)
        if redis_url:
            try:
                import redis as redis_lib  # optional dependency

                client = redis_lib.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.5)
                client.ping()
                self._redis = client
            except Exception:
                self._redis = None

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """Returns True when the request is ALLOWED."""
        now = time.time()
        if self._redis is not None:
            try:
                redis_key = f"rl:{key}:{int(now // window_seconds)}"
                count = self._redis.incr(redis_key)
                if count == 1:
                    self._redis.expire(redis_key, window_seconds + 1)
                return count <= limit
            except Exception:
                pass  # fail-open to local limiter
        window = self._local[key]
        while window and now - window[0] > window_seconds:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        # prevent unbounded growth of the local map
        if len(self._local) > 50_000:
            cutoff = now - window_seconds
            for k in [k for k, q in self._local.items() if not q or q[-1] < cutoff]:
                self._local.pop(k, None)
        return True


limiter = RateLimiter()
