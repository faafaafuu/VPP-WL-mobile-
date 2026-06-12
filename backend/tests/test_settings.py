from __future__ import annotations

import unittest

from app.core.settings import SettingsError, load_settings


class SettingsTest(unittest.TestCase):
    def test_loads_required_settings(self) -> None:
        settings = load_settings(
            {
                "VPN_ROUTER_TOKEN_SECRET": "token-secret-with-enough-length",
                "VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length",
                "VPN_ROUTER_HOST": "0.0.0.0",
                "VPN_ROUTER_PORT": "8090",
                "VPN_ROUTER_CORS_ORIGINS": "http://localhost:8081, http://127.0.0.1:19006",
                "VPN_ROUTER_ALLOWED_PRODUCT_IDS": "vpn.monthly,vpn.yearly",
            }
        )

        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 8090)
        self.assertEqual(settings.cors_origins, ("http://localhost:8081", "http://127.0.0.1:19006"))
        self.assertEqual(settings.allowed_product_ids, ("vpn.monthly", "vpn.yearly"))

    def test_rejects_missing_secret(self) -> None:
        with self.assertRaises(SettingsError):
            load_settings({"VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length"})

    def test_rejects_placeholder_secret(self) -> None:
        with self.assertRaises(SettingsError):
            load_settings(
                {
                    "VPN_ROUTER_TOKEN_SECRET": "replace-with-random-32-byte-secret",
                    "VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length",
                }
            )

    def test_rejects_invalid_port(self) -> None:
        with self.assertRaises(SettingsError):
            load_settings(
                {
                    "VPN_ROUTER_TOKEN_SECRET": "token-secret-with-enough-length",
                    "VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length",
                    "VPN_ROUTER_PORT": "99999",
                }
            )


if __name__ == "__main__":
    unittest.main()
