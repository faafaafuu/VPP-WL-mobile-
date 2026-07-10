from __future__ import annotations

import unittest
from pathlib import Path


SERVER = Path("app/api/server.py")


class ServerHardeningTest(unittest.TestCase):
    def test_request_body_is_capped_before_read(self) -> None:
        server = SERVER.read_text(encoding="utf-8")

        self.assertIn("_MAX_BODY_BYTES", server)
        self.assertIn("REQUEST_ENTITY_TOO_LARGE", server)
        # Both body readers must go through the size-checked helper, not read
        # an unbounded Content-Length straight into memory.
        self.assertIn("def _content_length", server)
        self.assertEqual(server.count("self._content_length()"), 2)

    def test_admin_orders_token_moves_out_of_url_into_cookie(self) -> None:
        server = SERVER.read_text(encoding="utf-8")

        # The admin token must not be rendered straight from the query string;
        # a query token is redirected into an HttpOnly cookie instead.
        self.assertIn("_send_admin_cookie_redirect", server)
        self.assertIn("HttpOnly", server)
        self.assertIn("SameSite=Strict", server)
        self.assertIn('self._cookie_value("admin_token")', server)


if __name__ == "__main__":
    unittest.main()
