from __future__ import annotations

import unittest
from decimal import Decimal
from http import HTTPStatus

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService
from app.services.exchange_rates import make_fixed_rate_service

_WALLET = "TTestWalletAddress1234567890ABCDE"
_STABLECOIN_RATE = Decimal("100.00")  # 1 USDT = 100 RUB for easy math


def _service(
    checkout_mode: str = "crypto_manual",
    crypto_address: str | None = _WALLET,
    rate_rub: str = "100.00",
) -> ApiService:
    rate_svc = make_fixed_rate_service({
        "tether": Decimal(rate_rub),
        "usd-coin": Decimal(rate_rub),
        "the-open-network": Decimal("650.00"),
        "bitcoin": Decimal("9000000.00"),
        "ethereum": Decimal("320000.00"),
    })
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token="test-admin-token-xx",
        public_base_url="http://127.0.0.1:8080",
        checkout_mode=checkout_mode,
        crypto_usdt_trc20_address=crypto_address,
        crypto_usdt_rate_rub=rate_rub,
        exchange_rate_service=rate_svc,
    )


class CryptoManualCheckoutTest(unittest.TestCase):
    def test_checkout_redirects_to_invoice(self) -> None:
        svc = _service()

        result = svc.checkout({"tariff_id": "vpn.1m"})

        self.assertTrue(result["redirect_url"].startswith("/invoice/"))
        self.assertEqual(result["mode"], "crypto_manual")
        self.assertIn("token", result)

    def test_checkout_creates_pending_subscription(self) -> None:
        svc = _service()

        result = svc.checkout({"tariff_id": "vpn.1m"})
        token = result["token"]
        sub = svc.repository.get_commercial_subscription(token)

        self.assertIsNotNone(sub)
        assert sub is not None
        self.assertEqual(sub.status, "pending")

    def test_invoice_html_contains_wallet_address(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn(_WALLET, html)
        self.assertIn("TRC20", html)

    def test_invoice_html_shows_usdt_amount(self) -> None:
        # vpn.1m default = 200 RUB / 100 RUB per USDT = 2.00 USDT
        svc = _service(rate_rub="100.00")
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn("2.00", html)
        self.assertIn("USDT", html)

    def test_invoice_html_contains_order_ref(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn(token[:12].upper(), html)

    def test_invoice_html_contains_connect_status_link(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn(f"/connect/{token}", html)

    def test_invoice_html_unknown_token_raises_404(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.invoice_html("nonexistent-token")

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)

    def test_invoice_html_without_crypto_address_raises_503(self) -> None:
        svc = _service(crypto_address=None)
        svc.repository.create_commercial_subscription("tok", "vpn.1m")

        with self.assertRaises(ApiError) as ctx:
            svc.invoice_html("tok")

        self.assertEqual(ctx.exception.status, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_invoice_wallet_qr_svg_returns_svg(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        svg = svc.invoice_wallet_qr_svg(token)

        self.assertTrue(svg.startswith("<svg"))

    def test_connect_page_shows_pending_state(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.connect_html(token)

        self.assertIn("Ожидание оплаты", html)
        self.assertIn(f"/invoice/{token}", html)

    def test_admin_can_activate_after_crypto_payment(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        result = svc.admin_activate_commercial_subscription("test-admin-token-xx", token, {"duration_days": 30})

        self.assertEqual(result["status"], "activated")
        sub = svc.repository.get_commercial_subscription(token)
        assert sub is not None
        self.assertTrue(sub.is_active())

    def test_connect_page_shows_active_after_admin_activation(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.admin_activate_commercial_subscription("test-admin-token-xx", token, {"duration_days": 30})

        html = svc.connect_html(token)

        self.assertIn("Ваш VPN активен", html)

    def test_v2ray_subscription_works_after_activation(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.admin_activate_commercial_subscription("test-admin-token-xx", token, {"duration_days": 30})

        encoded = svc.v2ray_subscription(token)

        self.assertGreater(len(encoded), 10)

    def test_v2ray_subscription_blocked_while_pending(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        with self.assertRaises(ApiError) as ctx:
            svc.v2ray_subscription(token)

        self.assertEqual(ctx.exception.status, HTTPStatus.FORBIDDEN)


class RubToUsdtTest(unittest.TestCase):
    def test_basic_conversion_rounds_up(self) -> None:
        from app.api.service import _rub_to_usdt

        self.assertEqual(_rub_to_usdt("399.00", "90.00"), "4.44")

    def test_exact_division(self) -> None:
        from app.api.service import _rub_to_usdt

        self.assertEqual(_rub_to_usdt("900.00", "90.00"), "10.00")

    def test_rounds_up_not_down(self) -> None:
        from app.api.service import _rub_to_usdt

        result = _rub_to_usdt("100.00", "90.00")
        self.assertEqual(result, "1.12")


class CryptoSettingsTest(unittest.TestCase):
    def _base_env(self) -> dict[str, str]:
        return {
            "VPN_ROUTER_TOKEN_SECRET": "test-secret-with-enough-len",
            "VPN_ROUTER_ADMIN_TOKEN": "test-admin-with-enough-len",
            "PUBLIC_BASE_URL": "http://127.0.0.1:8080",
        }

    def test_crypto_manual_requires_wallet_address(self) -> None:
        from app.core.settings import SettingsError, load_settings

        env = {**self._base_env(), "CHECKOUT_MODE": "crypto_manual"}

        with self.assertRaises(SettingsError) as ctx:
            load_settings(env)

        self.assertIn("CRYPTO_WALLET", str(ctx.exception))

    def test_crypto_manual_with_address_ok(self) -> None:
        from app.core.settings import load_settings

        env = {
            **self._base_env(),
            "CHECKOUT_MODE": "crypto_manual",
            "CRYPTO_USDT_TRC20_ADDRESS": "TXXXWalletAddressXXX",
        }

        settings = load_settings(env)

        self.assertEqual(settings.checkout_mode, "crypto_manual")
        self.assertEqual(settings.crypto_usdt_trc20_address, "TXXXWalletAddressXXX")

    def test_custom_usdt_rate(self) -> None:
        from app.core.settings import load_settings

        env = {
            **self._base_env(),
            "CRYPTO_USDT_RATE_RUB": "95.50",
        }

        settings = load_settings(env)

        self.assertEqual(settings.crypto_usdt_rate_rub, "95.50")

    def test_invalid_usdt_rate_raises(self) -> None:
        from app.core.settings import SettingsError, load_settings

        env = {**self._base_env(), "CRYPTO_USDT_RATE_RUB": "not-a-number"}

        with self.assertRaises(SettingsError):
            load_settings(env)


if __name__ == "__main__":
    unittest.main()
