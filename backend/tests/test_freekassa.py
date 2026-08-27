from __future__ import annotations

import unittest

from app.api.service import ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService


def _service() -> ApiService:
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token="test-admin-token-xx",
        public_base_url="http://127.0.0.1:8080",
        checkout_mode="crypto_manual",
        crypto_wallets={"trc20": "TTestWalletAddress1234567890ABCDE"},
    )


class FreekassaNotifyTest(unittest.TestCase):
    def test_notify_does_not_activate_anything(self) -> None:
        """The quick-pay widget carries no order token and we don't yet
        verify FreeKassa's signature — trusting an unverified POST would let
        anyone grant themselves access for free, so this must be a no-op on
        subscriptions regardless of payload content."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        svc.freekassa_notify(
            {"MERCHANT_ID": "75677", "AMOUNT": "200.00", "MERCHANT_ORDER_ID": token, "SIGN": "whatever"}
        )

        subscription = svc.repository.get_commercial_subscription(token)
        self.assertFalse(subscription.is_active())

    def test_notify_returns_yes_acknowledgement(self) -> None:
        svc = _service()

        result = svc.freekassa_notify({"MERCHANT_ID": "75677", "AMOUNT": "200.00", "intid": "123"})

        self.assertEqual(result, "YES")

    def test_notify_is_recorded_in_admin_audit_log(self) -> None:
        svc = _service()

        svc.freekassa_notify({"MERCHANT_ID": "75677", "AMOUNT": "200.00", "intid": "123456"})

        events = svc.repository.list_admin_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, "freekassa.notify_received")
        self.assertEqual(events[0].target_id, "123456")
        self.assertEqual(events[0].result, "unverified")


class FreekassaResultPagesTest(unittest.TestCase):
    def test_success_page_mentions_activation(self) -> None:
        svc = _service()

        html = svc.freekassa_success_html()

        self.assertIn("Оплата получена", html)

    def test_failure_page_offers_retry(self) -> None:
        svc = _service()

        html = svc.freekassa_failure_html()

        self.assertIn("не прошла", html)


if __name__ == "__main__":
    unittest.main()
