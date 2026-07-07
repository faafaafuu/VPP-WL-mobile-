from __future__ import annotations

import unittest
from http import HTTPStatus

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.domain.models import NodeStatus, Protocol, VlessOptions
from app.domain.v2ray_subscription import raw_subscription
from app.domain.vless_parser import VlessParseError, parse_vless_url
from app.repositories.memory import InMemoryRepository
from app.repositories.sqlite import SqliteRepository
from app.security.tokens import TokenService

# Fake config — NOT a real client UUID/key.
FAKE_VLESS = (
    "vless://00000000-0000-4000-8000-000000000001@198.51.100.7:2083"
    "?type=tcp&security=reality&pbk=FakePublicKeyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "&fp=chrome&sni=www.cloudflare.com&sid=0123abcd#Original%20Label"
)


def _service() -> ApiService:
    return ApiService(
        InMemoryRepository(nodes=[]),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token="test-admin-token-xx",
        public_base_url="http://127.0.0.1:8080",
    )


class VlessParserTest(unittest.TestCase):
    def test_parses_core_fields(self) -> None:
        node = parse_vless_url(FAKE_VLESS, label="VPN Router 1", priority=1, country_code="nl")

        self.assertEqual(node.protocol, Protocol.VLESS)
        self.assertEqual(node.host, "198.51.100.7")
        self.assertEqual(node.port, 2083)
        self.assertEqual(node.country_code, "NL")
        self.assertEqual(node.priority, 1)
        assert isinstance(node.options, VlessOptions)
        self.assertEqual(node.options.uuid, "00000000-0000-4000-8000-000000000001")
        self.assertEqual(node.options.public_key, "FakePublicKeyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        self.assertEqual(node.options.short_id, "0123abcd")
        self.assertEqual(node.options.server_name, "www.cloudflare.com")
        self.assertEqual(node.options.label, "VPN Router 1")
        self.assertEqual(node.options.raw_url, FAKE_VLESS)
        self.assertEqual(node.options.source, "3x-ui")

    def test_label_falls_back_to_fragment(self) -> None:
        node = parse_vless_url(FAKE_VLESS)
        assert isinstance(node.options, VlessOptions)
        self.assertEqual(node.options.label, "Original Label")

    def test_rejects_non_vless(self) -> None:
        with self.assertRaises(VlessParseError):
            parse_vless_url("vmess://abc")

    def test_rejects_missing_uuid(self) -> None:
        with self.assertRaises(VlessParseError):
            parse_vless_url("vless://@1.2.3.4:443?type=tcp#x")

    def test_disabled_flag_sets_status(self) -> None:
        node = parse_vless_url(FAKE_VLESS, enabled=False)
        self.assertEqual(node.status, NodeStatus.DISABLED)


class SubscriptionServesRawUrlTest(unittest.TestCase):
    def test_raw_url_served_verbatim_with_relabel(self) -> None:
        node = parse_vless_url(FAKE_VLESS, label="VPN Router 1")
        raw = raw_subscription([node])

        self.assertIn("vless://00000000-0000-4000-8000-000000000001@198.51.100.7:2083", raw)
        self.assertIn("#VPN%20Router%201", raw)
        self.assertNotIn("#Original%20Label", raw)

    def test_xhttp_transport_preserved(self) -> None:
        url = (
            "vless://00000000-0000-4000-8000-000000000002@198.51.100.8:8443"
            "?type=xhttp&security=tls&sni=example.com&fp=safari#X"
        )
        node = parse_vless_url(url, label="gRPC")
        raw = raw_subscription([node])
        self.assertIn("type=xhttp", raw)
        self.assertIn("security=tls", raw)


class AdminImportVlessTest(unittest.TestCase):
    def test_import_creates_node(self) -> None:
        svc = _service()

        result = svc.admin_import_vless(
            "test-admin-token-xx",
            {"vless_url": FAKE_VLESS, "label": "VPN Router 1", "priority": 1},
        )

        self.assertEqual(result["node"]["label"], "VPN Router 1")
        self.assertEqual(result["node"]["source"], "3x-ui")
        self.assertEqual(len(svc.repository.list_nodes()), 1)

    def test_import_requires_admin(self) -> None:
        svc = _service()
        with self.assertRaises(ApiError) as ctx:
            svc.admin_import_vless("wrong", {"vless_url": FAKE_VLESS})
        self.assertEqual(ctx.exception.status, HTTPStatus.UNAUTHORIZED)

    def test_import_rejects_empty_url(self) -> None:
        svc = _service()
        with self.assertRaises(ApiError) as ctx:
            svc.admin_import_vless("test-admin-token-xx", {})
        self.assertEqual(ctx.exception.status, HTTPStatus.BAD_REQUEST)

    def test_import_rejects_garbage_url(self) -> None:
        svc = _service()
        with self.assertRaises(ApiError) as ctx:
            svc.admin_import_vless("test-admin-token-xx", {"vless_url": "not-a-url"})
        self.assertEqual(ctx.exception.status, HTTPStatus.BAD_REQUEST)

    def test_imported_node_appears_in_subscription_after_activation(self) -> None:
        svc = _service()
        svc.admin_import_vless("test-admin-token-xx", {"vless_url": FAKE_VLESS, "label": "VPN Router 1"})
        svc.repository.create_commercial_subscription("tok", "vpn.1m")
        svc.admin_activate_commercial_subscription("test-admin-token-xx", "tok", {"duration_days": 30})

        raw = svc.raw_v2ray_subscription("tok")
        self.assertIn("198.51.100.7:2083", raw)

    def test_audit_event_recorded(self) -> None:
        svc = _service()
        svc.admin_import_vless("test-admin-token-xx", {"vless_url": FAKE_VLESS})
        events = svc.repository.list_admin_audit_events()
        self.assertTrue(any(e.action == "node.import_vless" for e in events))


class AdminPatchNodeTest(unittest.TestCase):
    def _service_with_node(self) -> ApiService:
        svc = _service()
        svc.admin_import_vless("test-admin-token-xx", {"vless_url": FAKE_VLESS, "label": "VPN Router 1", "priority": 5})
        return svc

    def test_disable_then_enable(self) -> None:
        svc = self._service_with_node()
        node_id = svc.repository.list_nodes()[0].id

        svc.admin_patch_node("test-admin-token-xx", node_id, {"enabled": False})
        self.assertEqual(svc.repository.get_node(node_id).status, NodeStatus.DISABLED)

        svc.admin_patch_node("test-admin-token-xx", node_id, {"enabled": True})
        self.assertEqual(svc.repository.get_node(node_id).status, NodeStatus.ACTIVE)

    def test_change_priority_and_label(self) -> None:
        svc = self._service_with_node()
        node_id = svc.repository.list_nodes()[0].id

        result = svc.admin_patch_node("test-admin-token-xx", node_id, {"priority": 1, "label": "Основной"})

        self.assertEqual(result["node"]["priority"], 1)
        self.assertEqual(result["node"]["label"], "Основной")

    def test_disabled_node_excluded_from_subscription(self) -> None:
        svc = self._service_with_node()
        node_id = svc.repository.list_nodes()[0].id
        svc.admin_patch_node("test-admin-token-xx", node_id, {"enabled": False})
        svc.repository.create_commercial_subscription("tok", "vpn.1m")
        svc.admin_activate_commercial_subscription("test-admin-token-xx", "tok", {"duration_days": 30})

        with self.assertRaises(ApiError) as ctx:
            svc.raw_v2ray_subscription("tok")
        self.assertEqual(ctx.exception.status, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_patch_unknown_node_404(self) -> None:
        svc = _service()
        with self.assertRaises(ApiError) as ctx:
            svc.admin_patch_node("test-admin-token-xx", "nope", {"enabled": False})
        self.assertEqual(ctx.exception.status, HTTPStatus.NOT_FOUND)


class SqliteRoundTripTest(unittest.TestCase):
    def test_raw_url_persists(self) -> None:
        repo = SqliteRepository(":memory:", nodes=[])
        node = parse_vless_url(FAKE_VLESS, label="VPN Router 1")
        repo.upsert_node(node)

        loaded = repo.get_node(node.id)
        assert loaded is not None and isinstance(loaded.options, VlessOptions)
        self.assertEqual(loaded.options.raw_url, FAKE_VLESS)
        self.assertEqual(loaded.options.source, "3x-ui")


if __name__ == "__main__":
    unittest.main()
