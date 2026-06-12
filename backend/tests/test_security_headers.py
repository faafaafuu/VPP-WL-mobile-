from __future__ import annotations

import unittest
from pathlib import Path


SERVER = Path("app/api/server.py")


class SecurityHeadersTest(unittest.TestCase):
    def test_server_sets_basic_security_headers(self) -> None:
        server = SERVER.read_text(encoding="utf-8")

        self.assertIn("X-Content-Type-Options", server)
        self.assertIn("nosniff", server)
        self.assertIn("Referrer-Policy", server)
        self.assertIn("X-Frame-Options", server)
        self.assertIn("Strict-Transport-Security", server)
        self.assertIn("SETTINGS.hsts_enabled", server)


if __name__ == "__main__":
    unittest.main()
