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


def _service() -> ApiService:
    rate_svc = make_fixed_rate_service({
        "tether": Decimal("100.00"),
        "usd-coin": Decimal("100.00"),
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
        checkout_mode="crypto_manual",
        crypto_usdt_trc20_address=_WALLET,
        exchange_rate_service=rate_svc,
    )


class InvoiceSelectTest(unittest.TestCase):
    def test_select_fixes_unique_amount_above_base(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        result = svc.select_invoice_coin(token, {"coin_id": "usdt_trc20"})

        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["address"], _WALLET)
        # vpn.1m = 200 RUB / 100 RUB per USDT = 2.00 base + micro tail (capped at +0.20)
        self.assertGreater(Decimal(result["amount"]), Decimal("2.00"))
        self.assertLessEqual(Decimal(result["amount"]), Decimal("2.20"))

    def test_select_persists_payment_intent(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        result = svc.select_invoice_coin(token, {"coin_id": "usdt_trc20"})
        subscription = svc.repository.get_commercial_subscription(token)

        assert subscription is not None
        self.assertEqual(subscription.pay_coin_id, "usdt_trc20")
        self.assertEqual(subscription.pay_amount, result["amount"])
        self.assertEqual(subscription.pay_address, _WALLET)

    def test_select_is_idempotent_for_same_coin(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        first = svc.select_invoice_coin(token, {"coin_id": "usdt_trc20"})
        second = svc.select_invoice_coin(token, {"coin_id": "usdt_trc20"})

        self.assertEqual(first["amount"], second["amount"])

    def test_two_pending_orders_get_distinct_amounts(self) -> None:
        svc = _service()
        token_a = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        token_b = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        amount_a = svc.select_invoice_coin(token_a, {"coin_id": "usdt_trc20"})["amount"]
        amount_b = svc.select_invoice_coin(token_b, {"coin_id": "usdt_trc20"})["amount"]

        self.assertNotEqual(amount_a, amount_b)

    def test_select_unknown_coin_raises_400(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        with self.assertRaises(ApiError) as ctx:
            svc.select_invoice_coin(token, {"coin_id": "dogecoin"})

        self.assertEqual(ctx.exception.status, HTTPStatus.BAD_REQUEST)

    def test_select_unconfigured_coin_raises_503(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        with self.assertRaises(ApiError) as ctx:
            svc.select_invoice_coin(token, {"coin_id": "btc"})

        self.assertEqual(ctx.exception.status, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_select_unknown_token_raises_404(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.select_invoice_coin("missing-token", {"coin_id": "usdt_trc20"})

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)

    def test_select_on_active_subscription_reports_active(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.repository.activate_commercial_subscription(token, 30)

        result = svc.select_invoice_coin(token, {"coin_id": "usdt_trc20"})

        self.assertEqual(result["status"], "active")


class InvoiceStatusTest(unittest.TestCase):
    def test_pending_status(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        status = svc.invoice_status(token)

        self.assertEqual(status["status"], "pending")
        self.assertFalse(status["paid"])
        self.assertEqual(status["connect_url"], f"/connect/{token}")

    def test_active_status_after_payment(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.repository.activate_commercial_subscription(token, 30, paid_tx="tx-1", payer="TPayer")

        status = svc.invoice_status(token)

        self.assertEqual(status["status"], "active")
        self.assertTrue(status["paid"])
        self.assertIsNotNone(status["expires_at"])

    def test_unknown_token_raises_404(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.invoice_status("missing-token")

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)


class WatcherSettingsTest(unittest.TestCase):
    def _base_env(self) -> dict[str, str]:
        return {
            "VPN_ROUTER_TOKEN_SECRET": "test-secret-with-enough-len",
            "VPN_ROUTER_ADMIN_TOKEN": "test-admin-with-enough-len",
            "PUBLIC_BASE_URL": "http://127.0.0.1:8080",
        }

    def test_defaults(self) -> None:
        from app.core.settings import load_settings

        settings = load_settings(self._base_env())

        self.assertIsNone(settings.crypto_trongrid_api_key)
        self.assertIsNone(settings.crypto_etherscan_api_key)
        self.assertEqual(settings.crypto_min_confirmations, 1)
        self.assertEqual(settings.crypto_watch_interval_seconds, 60)

    def test_custom_values(self) -> None:
        from app.core.settings import load_settings

        env = {
            **self._base_env(),
            "CRYPTO_TRONGRID_API_KEY": "tron-key",
            "CRYPTO_ETHERSCAN_API_KEY": "ether-key",
            "CRYPTO_MIN_CONFIRMATIONS": "12",
            "CRYPTO_WATCH_INTERVAL_SECONDS": "30",
        }

        settings = load_settings(env)

        self.assertEqual(settings.crypto_trongrid_api_key, "tron-key")
        self.assertEqual(settings.crypto_etherscan_api_key, "ether-key")
        self.assertEqual(settings.crypto_min_confirmations, 12)
        self.assertEqual(settings.crypto_watch_interval_seconds, 30)

    def test_invalid_min_confirmations_raises(self) -> None:
        from app.core.settings import SettingsError, load_settings

        env = {**self._base_env(), "CRYPTO_MIN_CONFIRMATIONS": "-1"}

        with self.assertRaises(SettingsError):
            load_settings(env)


if __name__ == "__main__":
    unittest.main()
