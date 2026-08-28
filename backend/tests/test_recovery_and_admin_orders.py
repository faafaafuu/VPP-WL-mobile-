from __future__ import annotations

import unittest
from http import HTTPStatus

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService

_ADMIN = "test-admin-token-xx"


def _service() -> ApiService:
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token=_ADMIN,
        public_base_url="http://127.0.0.1:8080",
        checkout_mode="crypto_manual",
        crypto_wallets={"trc20": "TTestWalletAddress1234567890ABCDE"},
    )


def _paid_order(svc: ApiService, paid_tx: str = "0xAbCdEf1234567890", payer: str = "0xPayerAddress999") -> str:
    token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
    svc.admin_activate_commercial_subscription(
        _ADMIN,
        token,
        {"duration_days": 30, "paid_tx": paid_tx, "payer": payer, "payment_id": "crypto:eth"},
    )
    return token


class RecoverTest(unittest.TestCase):
    def test_recover_by_tx_hash_is_rejected(self) -> None:
        # The tx hash is just as public on-chain as the sender address (both
        # show up in the receiving wallet's transaction history to anyone), so
        # it must not be usable to recover another buyer's subscription link
        # either — only the email the buyer chose to give us proves it's them.
        svc = _service()
        _paid_order(svc)

        with self.assertRaises(ApiError) as ctx:
            svc.recover({"query": "0xAbCdEf1234567890"})

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)

    def test_recover_by_email_works(self) -> None:
        svc = _service()
        token = _paid_order(svc)
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})

        result = svc.recover({"query": "buyer@example.com"})

        self.assertEqual(result["redirect_url"], f"/connect/{token}")

    def test_recover_email_lookup_is_case_insensitive(self) -> None:
        svc = _service()
        token = _paid_order(svc)
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})

        result = svc.recover({"query": "Buyer@Example.com"})

        self.assertEqual(result["token"], token)

    def test_recover_by_payer_address_is_rejected(self) -> None:
        # The sender address is public and enumerable on-chain, so it must not
        # be usable to recover another buyer's subscription link.
        svc = _service()
        _paid_order(svc, payer="TSenderWalletAddr123456")

        with self.assertRaises(ApiError) as ctx:
            svc.recover({"query": "TSenderWalletAddr123456"})

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)

    def test_recover_returns_latest_order_for_repeat_email(self) -> None:
        svc = _service()
        first = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(first, {"email": "repeat@example.com"})
        svc.admin_activate_commercial_subscription(
            _ADMIN, first, {"duration_days": 30, "paid_tx": "0xfirst111111111", "payment_id": "crypto:eth"}
        )
        second = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(second, {"email": "repeat@example.com"})
        svc.admin_activate_commercial_subscription(
            _ADMIN, second, {"duration_days": 30, "paid_tx": "0xsecond22222222", "payment_id": "crypto:eth"}
        )

        result = svc.recover({"query": "repeat@example.com"})

        self.assertEqual(result["token"], second)

    def test_recover_unknown_reference_raises_404(self) -> None:
        svc = _service()
        _paid_order(svc)

        with self.assertRaises(ApiError) as ctx:
            svc.recover({"query": "0xdeadbeefdeadbeef"})

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)

    def test_recover_short_query_raises_400(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.recover({"query": "0xab"})

        self.assertEqual(ctx.exception.status, HTTPStatus.BAD_REQUEST)

    def test_recover_page_contains_form(self) -> None:
        svc = _service()

        html = svc.recover_html()

        self.assertIn('action="/recover"', html)
        self.assertIn('name="query"', html)

    def test_recover_page_shows_error(self) -> None:
        svc = _service()

        html = svc.recover_html(error="Платёж не найден")

        self.assertIn("Платёж не найден", html)


class AdminOrdersTest(unittest.TestCase):
    def test_requires_admin_token(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.admin_orders("wrong-token")

        self.assertEqual(ctx.exception.status, HTTPStatus.UNAUTHORIZED)

    def test_lists_orders_newest_first_with_payment_details(self) -> None:
        svc = _service()
        pending = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        paid = _paid_order(svc, paid_tx="0xtx1234567890")

        orders = svc.admin_orders(_ADMIN)["orders"]

        self.assertEqual(len(orders), 2)
        by_token = {order["token"]: order for order in orders}
        self.assertEqual(by_token[pending]["status"], "pending")
        self.assertEqual(by_token[paid]["status"], "active")
        self.assertEqual(by_token[paid]["paid_tx"], "0xtx1234567890")
        self.assertEqual(by_token[paid]["connect_url"], f"/connect/{paid}")

    def test_html_page_contains_order_ref(self) -> None:
        svc = _service()
        token = _paid_order(svc)

        html = svc.admin_orders_html(_ADMIN)

        self.assertIn(token[:12].upper(), html)
        self.assertIn("Заказы", html)


if __name__ == "__main__":
    unittest.main()


class CancelOrderTest(unittest.TestCase):
    def test_admin_can_cancel_a_pending_order(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        result = svc.admin_cancel_commercial_subscription(_ADMIN, token)

        self.assertEqual(result["status"], "cancelled")
        subscription = svc.repository.get_commercial_subscription(token)
        assert subscription is not None
        self.assertEqual(subscription.status, "cancelled")

    def test_paid_order_cannot_be_cancelled(self) -> None:
        """Cancelling is for clearing abandoned invoices — it must never be
        able to revoke access somebody actually paid for."""
        svc = _service()
        token = _paid_order(svc)

        with self.assertRaises(ApiError) as ctx:
            svc.admin_cancel_commercial_subscription(_ADMIN, token)

        self.assertEqual(ctx.exception.status, HTTPStatus.CONFLICT)
        subscription = svc.repository.get_commercial_subscription(token)
        assert subscription is not None
        self.assertEqual(subscription.status, "active")

    def test_cancel_requires_admin_token(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        with self.assertRaises(ApiError):
            svc.admin_cancel_commercial_subscription("wrong-token", token)

    def test_unknown_token_is_404(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.admin_cancel_commercial_subscription(_ADMIN, "no-such-token")

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)


class StaleOrderSweepTest(unittest.TestCase):
    def _aged_pending(self, svc: ApiService, hours: int) -> str:
        from dataclasses import replace
        from datetime import datetime, timedelta, timezone

        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        subscription = svc.repository.commercial_subscriptions_by_token[token]
        svc.repository.commercial_subscriptions_by_token[token] = replace(
            subscription, created_at=datetime.now(timezone.utc) - timedelta(hours=hours)
        )
        return token

    def test_orders_older_than_the_ttl_are_cancelled(self) -> None:
        svc = _service()
        old = self._aged_pending(svc, hours=48)
        fresh = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        cancelled = svc.cancel_stale_pending_orders(ttl_hours=24)

        self.assertEqual(cancelled, 1)
        self.assertEqual(svc.repository.get_commercial_subscription(old).status, "cancelled")
        self.assertEqual(svc.repository.get_commercial_subscription(fresh).status, "pending")

    def test_paid_orders_survive_the_sweep(self) -> None:
        from dataclasses import replace
        from datetime import datetime, timedelta, timezone

        svc = _service()
        token = _paid_order(svc)
        subscription = svc.repository.commercial_subscriptions_by_token[token]
        svc.repository.commercial_subscriptions_by_token[token] = replace(
            subscription, created_at=datetime.now(timezone.utc) - timedelta(days=30)
        )

        svc.cancel_stale_pending_orders(ttl_hours=24)

        self.assertEqual(svc.repository.get_commercial_subscription(token).status, "active")

    def test_zero_ttl_disables_the_sweep(self) -> None:
        svc = _service()
        old = self._aged_pending(svc, hours=999)

        self.assertEqual(svc.cancel_stale_pending_orders(ttl_hours=0), 0)
        self.assertEqual(svc.repository.get_commercial_subscription(old).status, "pending")

    def test_cancelled_orders_are_hidden_from_the_order_list(self) -> None:
        svc = _service()
        cancelled_token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.admin_cancel_commercial_subscription(_ADMIN, cancelled_token)
        live_token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        visible = svc.admin_orders(_ADMIN)["orders"]
        everything = svc.admin_orders(_ADMIN, include_cancelled=True)["orders"]

        self.assertEqual([o["order_ref"] for o in visible], [live_token[:12].upper()])
        self.assertEqual(len(everything), 2)
