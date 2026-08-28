from __future__ import annotations

import unittest
from http import HTTPStatus
from unittest.mock import patch

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService
from app.services.freekassa_client import FreekassaError


def _service(**freekassa_kwargs) -> ApiService:
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token="test-admin-token-xx",
        public_base_url="http://127.0.0.1:8080",
        checkout_mode="crypto_manual",
        crypto_wallets={"trc20": "TTestWalletAddress1234567890ABCDE"},
        **freekassa_kwargs,
    )


def _order(svc: ApiService, tariff_id: str = "vpn.1m") -> str:
    """An order with a contact on file — card payment is gated on knowing
    who to hand the key to, so every redirect test needs one."""
    token = svc.checkout({"tariff_id": tariff_id})["token"]
    svc.set_invoice_contact(token, {"email": "buyer@example.com"})
    return token


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


class FreekassaPayRedirectTest(unittest.TestCase):
    def test_unavailable_without_api_credentials(self) -> None:
        """There is no static-widget fallback any more: that widget was fixed
        to one amount and carried no order reference, so it charged the wrong
        sum on every tariff but one and left even that one unmatchable."""
        svc = _service()
        token = _order(svc)

        with self.assertRaises(ApiError) as ctx:
            svc.freekassa_pay_redirect_url(token, "1.2.3.4")
        self.assertEqual(ctx.exception.status, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_every_tariff_behaves_identically_without_credentials(self) -> None:
        svc = _service()
        for tariff_id in ("vpn.1m", "vpn.3m", "vpn.6m", "vpn.12m"):
            with self.subTest(tariff_id=tariff_id):
                token = _order(svc, tariff_id)
                with self.assertRaises(ApiError) as ctx:
                    svc.freekassa_pay_redirect_url(token, "1.2.3.4")
                self.assertEqual(ctx.exception.status, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_every_tariff_gets_a_real_order_with_its_own_price(self) -> None:
        svc = _service(freekassa_shop_id="75677", freekassa_api_key="secret-key")
        for tariff_id in ("vpn.1m", "vpn.3m", "vpn.6m", "vpn.12m"):
            with self.subTest(tariff_id=tariff_id):
                token = _order(svc, tariff_id)
                with patch(
                    "app.api.service.freekassa_create_order",
                    return_value={"type": "success", "location": "https://pay.freekassa.net/form/2/def"},
                ) as create_order:
                    url = svc.freekassa_pay_redirect_url(token, "1.2.3.4")
                self.assertEqual(url, "https://pay.freekassa.net/form/2/def")
                _, kwargs = create_order.call_args
                self.assertEqual(kwargs["amount"], svc.tariffs_by_id[tariff_id].price_rub)

    def test_order_create_failure_is_audited_and_reported(self) -> None:
        svc = _service(freekassa_shop_id="75677", freekassa_api_key="secret-key")
        token = _order(svc)

        with patch("app.api.service.freekassa_create_order", side_effect=FreekassaError("Merchant not activated")):
            with self.assertRaises(ApiError) as ctx:
                svc.freekassa_pay_redirect_url(token, "1.2.3.4")

        self.assertEqual(ctx.exception.status, HTTPStatus.SERVICE_UNAVAILABLE)
        events = svc.repository.list_admin_audit_events()
        self.assertEqual(events[-1].action, "freekassa.order_create_failed")
        self.assertEqual(events[-1].result, "unavailable")

    def test_card_payment_requires_a_contact(self) -> None:
        """Paying by card without leaving an email or Telegram would produce
        a paid order with nobody to hand the key to."""
        svc = _service(freekassa_shop_id="75677", freekassa_api_key="secret-key")
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        with self.assertRaises(ApiError) as ctx:
            svc.freekassa_pay_redirect_url(token, "1.2.3.4")
        self.assertEqual(ctx.exception.status, HTTPStatus.CONFLICT)

    def test_returns_real_order_location_when_configured(self) -> None:
        svc = _service(freekassa_shop_id="75677", freekassa_api_key="secret-key")
        token = _order(svc)

        with patch(
            "app.api.service.freekassa_create_order",
            return_value={"type": "success", "location": "https://pay.freekassa.net/form/1/abc"},
        ) as create_order:
            url = svc.freekassa_pay_redirect_url(token, "5.6.7.8")

        self.assertEqual(url, "https://pay.freekassa.net/form/1/abc")
        _, kwargs = create_order.call_args
        self.assertEqual(kwargs["payment_id"], token)
        self.assertEqual(kwargs["ip"], "5.6.7.8")
        self.assertEqual(kwargs["email"], "buyer@example.com")


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
