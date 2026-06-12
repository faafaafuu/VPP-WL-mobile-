from __future__ import annotations

import unittest
from pathlib import Path


NGINX_CONFIG = Path("../deploy/nginx/vpn-router-api.conf")


class TlsDeployAssetsTest(unittest.TestCase):
    def test_nginx_reverse_proxy_template_enforces_https_and_security_headers(self) -> None:
        config = NGINX_CONFIG.read_text(encoding="utf-8")

        self.assertIn("listen 443 ssl http2", config)
        self.assertIn("return 301 https://$host$request_uri", config)
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3", config)
        self.assertIn("Strict-Transport-Security", config)
        self.assertIn("X-Forwarded-Proto https", config)
        self.assertIn("proxy_pass http://127.0.0.1:8080", config)
        self.assertNotIn("ssl_protocols TLSv1 TLSv1.1", config)


if __name__ == "__main__":
    unittest.main()
