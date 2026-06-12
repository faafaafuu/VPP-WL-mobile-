from __future__ import annotations

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

    def test_server_uses_rate_limiter_for_non_health_requests(self) -> None:
        server = Path("app/api/server.py").read_text(encoding="utf-8")

        self.assertIn("RateLimiter", server)
        self.assertIn("HTTPStatus.TOO_MANY_REQUESTS", server)
        self.assertIn("path == \"/health\"", server)


if __name__ == "__main__":
    unittest.main()
