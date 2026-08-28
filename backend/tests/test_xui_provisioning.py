from __future__ import annotations

import unittest

from app.api.service import ApiService
from app.domain.config_builder import ConfigBuilder
from app.domain.models import NodeHealth, NodeStatus, Protocol, VlessOptions, VpnNode
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService
from app.services.xui_client import XuiClientError


class FakeXuiClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.added: list[tuple[str, str, int, int, int]] = []
        self.updated: list[tuple[str, str, int, int, int]] = []
        self.deleted: list[str] = []

    def add_client(
        self, client_uuid: str, email: str, expiry_time_ms: int = 0, limit_ip: int = 0, total_gb: int = 0
    ) -> None:
        if self.fail:
            raise XuiClientError("panel unreachable")
        self.added.append((client_uuid, email, expiry_time_ms, limit_ip, total_gb))

    def update_client(
        self, client_uuid: str, email: str, expiry_time_ms: int = 0, limit_ip: int = 0, total_gb: int = 0
    ) -> None:
        if self.fail:
            raise XuiClientError("panel unreachable")
        self.updated.append((client_uuid, email, expiry_time_ms, limit_ip, total_gb))

    def delete_client(self, email: str) -> None:
        if self.fail:
            raise XuiClientError("panel unreachable")
        self.deleted.append(email)


def _xui_template() -> VpnNode:
    return VpnNode(
        id="node_xui_managed",
        tag="vless-xui-managed",
        region="eu",
        provider="3x-ui",
        country_code="NL",
        host="203.0.113.50",
        port=443,
        protocol=Protocol.VLESS,
        status=NodeStatus.ACTIVE,
        health=NodeHealth.HEALTHY,
        priority=0,
        options=VlessOptions(
            uuid="",
            server_name="example.test",
            public_key="pbk-test",
            short_id="sid-test",
            flow="xtls-rprx-vision",
            fingerprint="chrome",
            label="VPN Router",
        ),
    )


class XuiProvisioningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryRepository()
        self.xui_client = FakeXuiClient()

    def _service(self, xui_client=None) -> ApiService:
        return ApiService(
            self.repository,
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
            public_base_url="http://203.0.113.10:8080",
            checkout_mode="mock",
            xui_client=xui_client if xui_client is not None else self.xui_client,
            xui_node_template=_xui_template(),
        )

    def test_mock_checkout_provisions_xui_client_with_per_user_uuid(self) -> None:
        service = self._service()

        token = service.checkout({"tariff_id": "vpn.1m"})["token"]

        self.assertEqual(len(self.xui_client.added), 1)
        client_uuid, email, _expiry, limit_ip, total_gb = self.xui_client.added[0]
        subscription = self.repository.commercial_subscriptions_by_token[token]
        self.assertEqual(subscription.xui_uuid, client_uuid)
        self.assertEqual(subscription.xui_email, email)
        self.assertEqual(limit_ip, 3)  # vpn.1m default max_devices
        self.assertEqual(total_gb, 150)  # vpn.1m default traffic_gb

        raw = service.raw_v2ray_subscription(token)
        self.assertIn(f"vless://{client_uuid}@203.0.113.50:443", raw)

    def test_crypto_payment_activation_provisions_a_client(self) -> None:
        """The payment watcher activates orders straight through the
        repository, bypassing checkout. Without provisioning wired into that
        path a paid crypto order went "active" with no xui_uuid, so the
        customer's subscription link was empty and they got nothing."""
        service = self._service()
        self.repository.create_commercial_subscription("paid-token", "vpn.1m")
        self.repository.activate_commercial_subscription("paid-token", 30, paid_tx="0xabc")
        self.assertEqual(self.xui_client.added, [])

        service.provision_paid_subscription("paid-token")

        self.assertEqual(len(self.xui_client.added), 1)
        subscription = self.repository.commercial_subscriptions_by_token["paid-token"]
        self.assertTrue(subscription.xui_uuid)
        self.assertIn(f"vless://{subscription.xui_uuid}@", service.raw_v2ray_subscription("paid-token"))

    def test_provisioning_a_paid_subscription_twice_reuses_the_client(self) -> None:
        service = self._service()
        self.repository.create_commercial_subscription("paid-token", "vpn.1m")
        self.repository.activate_commercial_subscription("paid-token", 30)

        service.provision_paid_subscription("paid-token")
        service.provision_paid_subscription("paid-token")

        self.assertEqual(len(self.xui_client.added), 1)
        self.assertEqual(len(self.xui_client.updated), 1)

    def test_admin_activate_renews_expiry_on_existing_xui_client(self) -> None:
        service = self._service()
        token = service.checkout({"tariff_id": "vpn.1m"})["token"]
        self.assertEqual(len(self.xui_client.added), 1)
        client_uuid = self.xui_client.added[0][0]

        service.admin_activate_commercial_subscription("test-admin", token, {"duration_days": 30})

        self.assertEqual(len(self.xui_client.added), 1)  # no second client created
        self.assertEqual(len(self.xui_client.updated), 1)  # expiry resynced instead
        self.assertEqual(self.xui_client.updated[0][0], client_uuid)

    def test_panel_outage_does_not_block_activation(self) -> None:
        service = self._service(xui_client=FakeXuiClient(fail=True))

        result = service.checkout({"tariff_id": "vpn.1m"})
        token = result["token"]

        subscription = self.repository.commercial_subscriptions_by_token[token]
        self.assertIsNone(subscription.xui_uuid)
        self.assertTrue(subscription.is_active())

    def test_revoke_clears_xui_client_state(self) -> None:
        service = self._service()
        token = service.checkout({"tariff_id": "vpn.1m"})["token"]
        xui_email = self.repository.commercial_subscriptions_by_token[token].xui_email
        assert xui_email is not None

        service._revoke_xui_client(token)

        self.assertIn(xui_email, self.xui_client.deleted)
        subscription = self.repository.commercial_subscriptions_by_token[token]
        self.assertIsNone(subscription.xui_uuid)
        self.assertIsNone(subscription.xui_email)

    def test_without_xui_configured_falls_back_to_shared_nodes(self) -> None:
        node = VpnNode(
            id="node1",
            tag="vless-1",
            region="eu",
            provider="env",
            country_code="NL",
            host="203.0.113.20",
            port=443,
            protocol=Protocol.VLESS,
            status=NodeStatus.ACTIVE,
            health=NodeHealth.HEALTHY,
            priority=1,
            options=VlessOptions(
                uuid="00000000-0000-4000-8000-0000000000aa",
                server_name="shared.test",
                public_key="pbk-shared",
                short_id="sid-shared",
            ),
        )
        repository = InMemoryRepository(nodes=[node])
        service = ApiService(
            repository,
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
            public_base_url="http://203.0.113.10:8080",
            checkout_mode="mock",
        )

        token = service.checkout({"tariff_id": "vpn.1m"})["token"]
        raw = service.raw_v2ray_subscription(token)

        self.assertIn("00000000-0000-4000-8000-0000000000aa", raw)


if __name__ == "__main__":
    unittest.main()
