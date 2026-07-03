"""OSIN CHAIN QUEBEC ULTIMATE - Rate Limiter - Ghost1o1"""
import time, threading
from collections import defaultdict
from typing import Dict, Tuple


class RateLimiter:
    def __init__(self, max_requests: int = 30, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self._buckets: Dict[str, Tuple[int, float]] = defaultdict(
            lambda: (0, time.time()))
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        with self._lock:
            count, window_start = self._buckets[key]
            now = time.time()
            if now - window_start > self.window:
                self._buckets[key] = (1, now)
                return True
            if count < self.max_requests:
                self._buckets[key] = (count + 1, window_start)
                return True
            return False

    def wait_if_needed(self, key: str) -> float:
        while not self.check(key):
            time.sleep(2)
        return 0.0

    def reset(self, key: str):
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]

    def get_remaining(self, key: str) -> int:
        with self._lock:
            count, window_start = self._buckets[key]
            now = time.time()
            if now - window_start > self.window:
                return self.max_requests
            return max(0, self.max_requests - count)

    def status(self, key: str) -> Dict:
        with self._lock:
            count, window_start = self._buckets[key]
            now = time.time()
            elapsed = now - window_start
            remaining = max(0, self.max_requests - count)
            reset_in = max(0, self.window - elapsed)
            return {
                "key": key, "max_requests": self.max_requests,
                "window_seconds": self.window, "used": count,
                "remaining": remaining,
                "reset_in_seconds": round(reset_in, 1),
                "rate_limited": remaining == 0,
            }

    def cleanup_expired(self):
        with self._lock:
            now = time.time()
            expired = [k for k, (_, ws) in self._buckets.items()
                        if now - ws > self.window * 2]
            for k in expired:
                del self._buckets[k]