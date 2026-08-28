from __future__ import annotations

import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.api.rate_limit import RateLimiter


class RateLimiterTest(unittest.TestCase):
    def test_limits_requests_per_key_inside_one_minute_window(self) -> None:
        limiter = RateLimiter(limit_per_minute=2)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        self.assertTrue(limiter.allow("127.0.0.1", now))
        self.assertTrue(limiter.allow("127.0.0.1", now + timedelta(seconds=1)))
        self.assertFalse(limiter.allow("127.0.0.1", now + timedelta(seconds=2)))
        self.assertTrue(limiter.allow("127.0.0.1", now + timedelta(seconds=61)))

    def test_zero_limit_disables_rate_limiting(self) -> None:
        limiter = RateLimiter(limit_per_minute=0)

        for _ in range(10):
            self.assertTrue(limiter.allow("127.0.0.1"))

    def test_concurrent_requests_never_exceed_the_limit(self) -> None:
        """Regression guard: allow() used to read-then-append the bucket
        without a lock, so two threads for the same key could both pass the
        length check before either appended — letting more requests through
        than limit_per_minute under real concurrent traffic."""
        limiter = RateLimiter(limit_per_minute=5)
        allowed = []
        lock = threading.Lock()

        def worker() -> None:
            result = limiter.allow("shared-key")
            with lock:
                allowed.append(result)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(1 for a in allowed if a), 5)

    def test_stale_buckets_are_evicted_not_kept_forever(self) -> None:
        limiter = RateLimiter(limit_per_minute=2)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        limiter.allow("127.0.0.1", now)
        self.assertIn("127.0.0.1", limiter.buckets)

        # Once the window has fully elapsed with no new requests, the next
        # call for a different key must not leave that IP's now-empty
        # bucket sitting in memory forever.
        limiter.allow("10.0.0.1", now + timedelta(minutes=2))

        self.assertNotIn("127.0.0.1", limiter.buckets)

    def test_server_uses_rate_limiter_for_non_health_requests(self) -> None:
        server = Path("app/api/server.py").read_text(encoding="utf-8")

        self.assertIn("RateLimiter", server)
        self.assertIn("HTTPStatus.TOO_MANY_REQUESTS", server)
        self.assertIn("path == \"/health\"", server)


if __name__ == "__main__":
    unittest.main()
