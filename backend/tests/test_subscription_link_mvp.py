from __future__ import annotations

import base64
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService


class SubscriptionLinkMvpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryRepository()
        self.service = ApiService(
            self.repository,
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
            public_base_url="http://203.0.113.10:8080",
            checkout_mode="mock",
        )

    def test_mock_checkout_activates_subscription_and_connect_page(self) -> None:
        checkout = self.service.checkout({"tariff_id": "vpn.1m"})
        token = checkout["token"]

        html = self.service.connect_html(token)

        self.assertEqual(checkout["redirect_url"], f"/connect/{token}")
        self.assertIn("Ваш VPN активен", html)
        self.assertIn(f"http://203.0.113.10:8080/sub/{token}", html)
        self.assertIn("Скопировать ссылку", html)
        self.assertIn("Показать QR", html)

    def test_expired_subscription_connect_page_shows_renewal(self) -> None:
        checkout = self.service.checkout({"tariff_id": "vpn.1m"})
        token = checkout["token"]
        subscription = self.repository.commercial_subscriptions_by_token[token]
        self.repository.commercial_subscriptions_by_token[token] = replace(
            subscription,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        html = self.service.connect_html(token)

        self.assertIn("Подписка закончилась", html)
        self.assertIn("продлить", html)

    def test_active_subscription_gets_base64_v2ray_subscription(self) -> None:
        token = self.service.checkout({"tariff_id": "vpn.1m"})["token"]

        encoded = self.service.v2ray_subscription(token)
        decoded = base64.b64decode(encoded).decode("utf-8")

        self.assertIn("vless://00000000-0000-4000-8000-000000000001@eu1.vpn.example.com:443", decoded)
        self.assertIn("security=reality", decoded)
        self.assertIn("pbk=mvpRealityPublicKey111111111111111111111111111", decoded)
        self.assertIn("#VPN%20Router%201", decoded)
        self.assertNotIn("vless-disabled", decoded)
        self.assertNotIn("ss-eu-2", decoded)

    def test_pending_subscription_connect_page_shows_awaiting_payment(self) -> None:
        crypto_service = ApiService(
            self.repository,
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
            public_base_url="http://203.0.113.10:8080",
            checkout_mode="crypto_manual",
            crypto_wallets={"trc20": "TTestWallet"},
        )
        token = crypto_service.checkout({"tariff_id": "vpn.1m"})["token"]

        html = crypto_service.connect_html(token)

        self.assertIn("Ожидание оплаты", html)
        self.assertIn(f"/invoice/{token}", html)
        self.assertNotIn("Подписка закончилась", html)

    def test_admin_activate_records_paid_tx_and_payer(self) -> None:
        crypto_service = ApiService(
            self.repository,
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
            public_base_url="http://203.0.113.10:8080",
            checkout_mode="crypto_manual",
            crypto_wallets={"trc20": "TTestWallet"},
        )
        token = crypto_service.checkout({"tariff_id": "vpn.1m"})["token"]

        result = crypto_service.admin_activate_commercial_subscription(
            "test-admin",
            token,
            {"duration_days": 30, "paid_tx": "0xabc", "payer": "0xdef", "payment_id": "crypto:eth"},
        )

        self.assertEqual(result["status"], "activated")
        subscription = self.repository.commercial_subscriptions_by_token[token]
        self.assertEqual(subscription.paid_tx, "0xabc")
        self.assertEqual(subscription.payer, "0xdef")
        self.assertEqual(subscription.payment_id, "crypto:eth")

    def test_tls_vless_node_generates_link_without_reality_params(self) -> None:
        from app.domain.models import NodeHealth, NodeStatus, Protocol, VlessOptions, VpnNode
        from app.domain.v2ray_subscription import vless_links

        node = VpnNode(
            id="tls-1",
            tag="TLS Node",
            region="eu",
            provider="3x-ui",
            country_code="DE",
            host="203.0.113.20",
            port=26670,
            protocol=Protocol.VLESS,
            status=NodeStatus.ACTIVE,
            priority=1,
            options=VlessOptions(
                uuid="00000000-0000-4000-8000-0000000000aa",
                server_name="203.0.113.20",
                security="tls",
                fingerprint="safari",
            ),
        )

        (link,) = vless_links([node])

        self.assertIn("security=tls", link)
        self.assertIn("fp=safari", link)
        self.assertIn("sni=203.0.113.20", link)
        self.assertNotIn("pbk=", link)
        self.assertNotIn("sid=", link)

    def test_raw_subscription_returns_plain_vless_lines_sorted_by_priority(self) -> None:
        token = self.service.checkout({"tariff_id": "vpn.1m"})["token"]

        raw = self.service.raw_v2ray_subscription(token)

        self.assertTrue(raw.startswith("vless://00000000-0000-4000-8000-000000000001@"))
        self.assertIn("\nvless://00000000-0000-4000-8000-000000000003@", raw)

    def test_expired_subscription_is_forbidden_on_subscription_endpoint(self) -> None:
        token = self.service.checkout({"tariff_id": "vpn.1m"})["token"]
        subscription = self.repository.commercial_subscriptions_by_token[token]
        self.repository.commercial_subscriptions_by_token[token] = replace(
            subscription,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        with self.assertRaises(ApiError) as context:
            self.service.v2ray_subscription(token)

        self.assertEqual(context.exception.status, HTTPStatus.FORBIDDEN)
        self.assertEqual(context.exception.payload["error"], "subscription expired")

    def test_unknown_subscription_token_returns_404(self) -> None:
        with self.assertRaises(ApiError) as context:
            self.service.raw_v2ray_subscription("missing-token")

        self.assertEqual(context.exception.status, HTTPStatus.NOT_FOUND)

    def test_qr_endpoint_returns_svg_for_subscription_url(self) -> None:
        token = self.service.checkout({"tariff_id": "vpn.1m"})["token"]

        svg = self.service.subscription_qr_svg(token)

        self.assertTrue(svg.startswith("<svg"))
        self.assertIn('role="img"', svg)

    def test_admin_activation_requires_admin_token_and_extends_subscription(self) -> None:
        token = "test-token"
        self.repository.create_commercial_subscription(token, "vpn.1m")

        with self.assertRaises(ApiError) as context:
            self.service.admin_activate_commercial_subscription("wrong", token, {"duration_days": 30})
        activated = self.service.admin_activate_commercial_subscription("test-admin", token, {"duration_days": 30})

        self.assertEqual(context.exception.status, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(activated["status"], "activated")
        self.assertTrue(self.repository.get_commercial_subscription(token).is_active())

    def test_public_base_url_is_used_in_subscription_url(self) -> None:
        token = "token-1"

        self.assertEqual(self.service.subscription_url(token), "http://203.0.113.10:8080/sub/token-1")


if __name__ == "__main__":
    unittest.main()
