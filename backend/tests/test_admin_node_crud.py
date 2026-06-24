from __future__ import annotations

import unittest
from http import HTTPStatus

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.domain.models import NodeHealth, NodeStatus, Protocol
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService


def _service() -> ApiService:
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token="test-admin-token-xx",
        public_base_url="http://127.0.0.1:8080",
    )


def _vless_payload(node_id: str = "node_test_1", priority: int = 10) -> dict:
    return {
        "id": node_id,
        "tag": node_id,
        "host": "1.2.3.4",
        "port": 443,
        "protocol": "vless",
        "region": "eu-west",
        "country_code": "NL",
        "provider": "hetzner",
        "priority": priority,
        "status": "active",
        "options": {
            "uuid": "00000000-0000-4000-8000-000000000099",
            "server_name": "www.microsoft.com",
            "public_key": "realPublicKeyXYZ",
            "short_id": "aabbccdd",
            "flow": "xtls-rprx-vision",
            "fingerprint": "chrome",
            "label": "NL Test Node",
        },
    }


class AdminUpsertNodeTest(unittest.TestCase):
    def test_upsert_creates_new_node(self) -> None:
        svc = _service()

        result = svc.admin_upsert_node("test-admin-token-xx", _vless_payload())

        self.assertEqual(result["node"]["id"], "node_test_1")
        self.assertEqual(result["node"]["host"], "1.2.3.4")
        node = svc.repository.get_node("node_test_1")
        self.assertIsNotNone(node)

    def test_upsert_updates_existing_node(self) -> None:
        svc = _service()
        svc.admin_upsert_node("test-admin-token-xx", _vless_payload("node_eu_1", priority=5))

        updated = svc.repository.get_node("node_eu_1")

        assert updated is not None
        self.assertEqual(updated.priority, 5)
        self.assertEqual(updated.host, "1.2.3.4")

    def test_upsert_requires_admin_token(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.admin_upsert_node("wrong-token", _vless_payload())

        self.assertEqual(ctx.exception.status, HTTPStatus.UNAUTHORIZED)

    def test_upsert_rejects_missing_host(self) -> None:
        svc = _service()
        payload = {**_vless_payload(), "host": ""}

        with self.assertRaises(ApiError) as ctx:
            svc.admin_upsert_node("test-admin-token-xx", payload)

        self.assertEqual(ctx.exception.status, HTTPStatus.BAD_REQUEST)
        self.assertIn("host", ctx.exception.payload["error"])

    def test_upsert_rejects_missing_uuid(self) -> None:
        svc = _service()
        payload = _vless_payload()
        payload["options"]["uuid"] = ""

        with self.assertRaises(ApiError) as ctx:
            svc.admin_upsert_node("test-admin-token-xx", payload)

        self.assertEqual(ctx.exception.status, HTTPStatus.BAD_REQUEST)

    def test_upsert_rejects_unknown_protocol(self) -> None:
        svc = _service()
        payload = {**_vless_payload(), "protocol": "fakevpn"}

        with self.assertRaises(ApiError) as ctx:
            svc.admin_upsert_node("test-admin-token-xx", payload)

        self.assertIn("protocol", ctx.exception.payload["error"])

    def test_upserted_node_appears_in_subscription(self) -> None:
        svc = _service()
        svc.admin_upsert_node("test-admin-token-xx", _vless_payload("node_new_sub", priority=1))
        svc.repository.create_commercial_subscription("tok", "vpn.1m")
        svc.admin_activate_commercial_subscription("test-admin-token-xx", "tok", {"duration_days": 30})

        raw = svc.raw_v2ray_subscription("tok")

        self.assertIn("1.2.3.4", raw)

    def test_upsert_audit_event_recorded(self) -> None:
        svc = _service()
        svc.admin_upsert_node("test-admin-token-xx", _vless_payload())

        events = svc.repository.list_admin_audit_events()

        self.assertTrue(any(e.action == "node.upsert" for e in events))


class AdminDisableNodeTest(unittest.TestCase):
    def test_disable_existing_node(self) -> None:
        svc = _service()

        result = svc.admin_disable_node("test-admin-token-xx", "node_eu_1")

        self.assertEqual(result["node"]["status"], "disabled")
        node = svc.repository.get_node("node_eu_1")
        assert node is not None
        self.assertEqual(node.status, NodeStatus.DISABLED)
        self.assertEqual(node.health, NodeHealth.DISABLED)

    def test_disable_requires_admin_token(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.admin_disable_node("bad-token", "node_eu_1")

        self.assertEqual(ctx.exception.status, HTTPStatus.UNAUTHORIZED)

    def test_disable_unknown_node_returns_404(self) -> None:
        svc = _service()

        with self.assertRaises(ApiError) as ctx:
            svc.admin_disable_node("test-admin-token-xx", "nonexistent_node")

        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)

    def test_disabled_node_not_in_subscription(self) -> None:
        svc = _service()
        svc.admin_disable_node("test-admin-token-xx", "node_eu_1")
        svc.repository.create_commercial_subscription("tok", "vpn.1m")
        svc.admin_activate_commercial_subscription("test-admin-token-xx", "tok", {"duration_days": 30})

        raw = svc.raw_v2ray_subscription("tok")

        self.assertNotIn("eu1.vpn.example.com", raw)

    def test_disable_audit_event_recorded(self) -> None:
        svc = _service()
        svc.admin_disable_node("test-admin-token-xx", "node_eu_1")

        events = svc.repository.list_admin_audit_events()

        self.assertTrue(any(e.action == "node.disable" for e in events))


if __name__ == "__main__":
    unittest.main()
