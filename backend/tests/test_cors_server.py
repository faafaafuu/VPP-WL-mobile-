from __future__ import annotations

import unittest
from pathlib import Path


SERVER = Path("app/api/server.py")


class CorsServerTest(unittest.TestCase):
    def test_server_supports_allowlisted_cors_preflight(self) -> None:
        server = SERVER.read_text(encoding="utf-8")

        self.assertIn("def do_OPTIONS", server)
        self.assertIn("Access-Control-Allow-Origin", server)
        self.assertIn("Access-Control-Allow-Methods", server)
        self.assertIn("Authorization,Content-Type,X-Admin-Token", server)
        self.assertIn("SETTINGS.cors_origins", server)


if __name__ == "__main__":
    unittest.main()
