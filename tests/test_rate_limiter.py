"""Tests for TokenBucketRateLimiter."""

import threading
import time

from kgf.extraction.rate_limiter import TokenBucketRateLimiter


def test_zero_rate_is_noop():
    """acquire() returns immediately when rate=0."""
    limiter = TokenBucketRateLimiter(rate=0)
    start = time.monotonic()
    for _ in range(100):
        limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1, f"Zero-rate limiter should be instant, took {elapsed:.3f}s"


def test_negative_rate_is_noop():
    """acquire() returns immediately when rate is negative."""
    limiter = TokenBucketRateLimiter(rate=-1)
    start = time.monotonic()
    for _ in range(10):
        limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


def test_rate_enforcement():
    """5 acquires at 10 req/s should take ~0.4s (first is free from bucket)."""
    limiter = TokenBucketRateLimiter(rate=10, capacity=1)
    start = time.monotonic()
    for _ in range(5):
        limiter.acquire()
    elapsed = time.monotonic() - start
    # 1st acquire is instant (bucket has 1 token), 4 more at 0.1s each = ~0.4s
    assert 0.3 <= elapsed <= 0.8, f"Expected ~0.4s, got {elapsed:.3f}s"


def test_thread_safety():
    """Multiple threads acquiring tokens should not corrupt state."""
    limiter = TokenBucketRateLimiter(rate=50, capacity=1)
    results = []
    errors = []

    def worker():
        try:
            for _ in range(5):
                limiter.acquire()
                results.append(time.monotonic())
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors, f"Thread errors: {errors}"
    assert len(results) == 20, f"Expected 20 acquires, got {len(results)}"


def test_burst_capacity():
    """Capacity > 1 allows initial burst."""
    limiter = TokenBucketRateLimiter(rate=5, capacity=3)
    start = time.monotonic()
    # First 3 should be nearly instant (bucket starts full)
    for _ in range(3):
        limiter.acquire()
    burst_elapsed = time.monotonic() - start
    assert burst_elapsed < 0.1, f"Burst of 3 should be instant, took {burst_elapsed:.3f}s"
