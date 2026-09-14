import time
from collections import defaultdict, deque
from threading import Lock


class FixedWindowRateLimiter:
    def __init__(self, limit_per_minute: int):
        self._limit = max(1, int(limit_per_minute))
        self._window_sec = 60.0
        self._lock = Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int, int]:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - self._window_sec
            while q and q[0] <= cutoff:
                q.popleft()

            used = len(q)
            if used >= self._limit:
                retry_after = max(1, int(self._window_sec - (now - q[0])))
                return False, 0, retry_after

            q.append(now)
            remaining = max(0, self._limit - len(q))
            return True, remaining, 0
