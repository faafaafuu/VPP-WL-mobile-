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
                "VPN_ROUTER_RATE_LIMIT_PER_MINUTE": "60",
                "VPN_ROUTER_AUDIT_RETENTION_DAYS": "14",
                "VPN_ROUTER_HSTS_ENABLED": "true",
                "VPN_ROUTER_YOOKASSA_SHOP_ID": "123456",
                "VPN_ROUTER_YOOKASSA_SECRET_KEY": "yookassa-secret-with-length",
                "VPN_ROUTER_YOOKASSA_RETURN_URL": "https://vpn.example/payments/return",
                "VPN_ROUTER_PRODUCT_PRICES_RUB": "vpn.monthly:399.00,vpn.yearly:2599.00",
                "PUBLIC_BASE_URL": "http://203.0.113.10:8080",
                "CHECKOUT_MODE": "mock",
                "VPN_ROUTER_TARIFFS": "vpn.1m:1 месяц:30:399.00,vpn.3m:3 месяца:90:999.00:выгоднее",
            }
        )

        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 8090)
        self.assertEqual(settings.cors_origins, ("http://localhost:8081", "http://127.0.0.1:19006"))
        self.assertEqual(settings.allowed_product_ids, ("vpn.monthly", "vpn.yearly"))
        self.assertEqual(settings.rate_limit_per_minute, 60)
        self.assertEqual(settings.audit_retention_days, 14)
        self.assertTrue(settings.hsts_enabled)
        self.assertEqual(settings.yookassa_shop_id, "123456")
        self.assertEqual(settings.yookassa_secret_key, "yookassa-secret-with-length")
        self.assertEqual(settings.yookassa_return_url, "https://vpn.example/payments/return")
        self.assertEqual(settings.product_prices_rub["vpn.yearly"], "2599.00")
        self.assertEqual(settings.public_base_url, "http://203.0.113.10:8080")
        self.assertEqual(settings.checkout_mode, "mock")
        self.assertEqual(settings.tariffs[1].id, "vpn.3m")
        self.assertEqual(settings.tariffs[1].duration_days, 90)

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

    def test_rejects_invalid_bool(self) -> None:
        with self.assertRaises(SettingsError):
            load_settings(
                {
                    "VPN_ROUTER_TOKEN_SECRET": "token-secret-with-enough-length",
                    "VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length",
                    "VPN_ROUTER_HSTS_ENABLED": "maybe",
                }
            )

    def test_rejects_partial_yookassa_credentials(self) -> None:
        with self.assertRaises(SettingsError):
            load_settings(
                {
                    "VPN_ROUTER_TOKEN_SECRET": "token-secret-with-enough-length",
                    "VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length",
                    "VPN_ROUTER_YOOKASSA_SHOP_ID": "123456",
                }
            )

    def test_rejects_yookassa_credentials_without_return_url(self) -> None:
        with self.assertRaises(SettingsError):
            load_settings(
                {
                    "VPN_ROUTER_TOKEN_SECRET": "token-secret-with-enough-length",
                    "VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length",
                    "VPN_ROUTER_YOOKASSA_SHOP_ID": "123456",
                    "VPN_ROUTER_YOOKASSA_SECRET_KEY": "yookassa-secret-with-length",
                }
            )

    def test_rejects_invalid_product_price(self) -> None:
        with self.assertRaises(SettingsError):
            load_settings(
                {
                    "VPN_ROUTER_TOKEN_SECRET": "token-secret-with-enough-length",
                    "VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length",
                    "VPN_ROUTER_PRODUCT_PRICES_RUB": "vpn.monthly:not-a-price",
                }
            )

    def test_rejects_invalid_checkout_mode(self) -> None:
        with self.assertRaises(SettingsError):
            load_settings(
                {
                    "VPN_ROUTER_TOKEN_SECRET": "token-secret-with-enough-length",
                    "VPN_ROUTER_ADMIN_TOKEN": "admin-token-with-enough-length",
                    "CHECKOUT_MODE": "crypto",
                }
            )


if __name__ == "__main__":
    unittest.main()
