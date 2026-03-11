"""Token bucket rate limiter for LLM API calls."""

import threading
import time


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter.

    Enforces a maximum request rate across concurrent worker threads.
    Each call to acquire() blocks until a token is available.

    Args:
        rate: Maximum requests per second (0 = unlimited)
        capacity: Bucket capacity (burst size). Defaults to 1 for smooth spacing.
    """

    def __init__(self, rate: float, capacity: int = 1):
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available, then consume it."""
        if self._rate <= 0:
            return

        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._capacity,
                    self._tokens + elapsed * self._rate,
                )
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

            # Sleep for the time needed to generate one token
            time.sleep(1.0 / self._rate)
