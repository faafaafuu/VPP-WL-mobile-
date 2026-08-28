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

    def test_admin_cookie_secure_flag_follows_https_base_url(self) -> None:
        """The Secure flag used to be gated on VPN_ROUTER_HSTS_ENABLED — an
        unrelated setting that's off in production even though the site is
        HTTPS-only, so the admin cookie shipped without Secure. It must be
        tied to whether the deployment actually serves over HTTPS instead."""
        server = SERVER.read_text(encoding="utf-8")

        self.assertIn('SETTINGS.public_base_url.startswith("https://")', server)
        self.assertNotIn("if SETTINGS.hsts_enabled:\n            cookie", server)

    def test_body_decoders_handle_malformed_utf8_without_crashing(self) -> None:
        """Regression guard: both request-body readers used to call
        .decode("utf-8") unguarded (or outside the try/except that only
        caught JSONDecodeError), so a malformed-encoding POST body crashed
        the request thread with an unhandled UnicodeDecodeError instead of
        returning a clean 400."""
        server = SERVER.read_text(encoding="utf-8")

        self.assertIn("except (json.JSONDecodeError, UnicodeDecodeError):", server)
        self.assertIn("except UnicodeDecodeError:", server)
        self.assertEqual(server.count("UnicodeDecodeError"), 2)


if __name__ == "__main__":
    unittest.main()
