from __future__ import annotations

import unittest

from app.domain.models import NodeHealth, NodeStatus, Protocol, VlessOptions
from app.domain.node_config import NodeConfigError, parse_nodes_from_env


def _base_env(n: int = 1) -> dict[str, str]:
    return {
        f"VPN_NODE_{n}_HOST": f"10.0.0.{n}",
        f"VPN_NODE_{n}_PORT": "443",
        f"VPN_NODE_{n}_UUID": f"00000000-0000-4000-8000-00000000000{n}",
        f"VPN_NODE_{n}_PUBLIC_KEY": f"pubkey{n}abc123",
        f"VPN_NODE_{n}_SHORT_ID": f"deadbeef{n:02x}",
        f"VPN_NODE_{n}_SNI": "www.microsoft.com",
    }


class NodeConfigParseTest(unittest.TestCase):
    def test_empty_env_returns_no_nodes(self) -> None:
        self.assertEqual(parse_nodes_from_env({}), [])

    def test_single_node_minimal_config(self) -> None:
        nodes = parse_nodes_from_env(_base_env(1))

        self.assertEqual(len(nodes), 1)
        node = nodes[0]
        self.assertEqual(node.id, "node_env_1")
        self.assertEqual(node.host, "10.0.0.1")
        self.assertEqual(node.port, 443)
        self.assertEqual(node.protocol, Protocol.VLESS)
        self.assertEqual(node.status, NodeStatus.ACTIVE)
        self.assertEqual(node.health, NodeHealth.HEALTHY)
        self.assertEqual(node.priority, 10)
        assert isinstance(node.options, VlessOptions)
        self.assertEqual(node.options.uuid, "00000000-0000-4000-8000-000000000001")
        self.assertEqual(node.options.public_key, "pubkey1abc123")
        self.assertEqual(node.options.short_id, "deadbeef01")
        self.assertEqual(node.options.server_name, "www.microsoft.com")
        self.assertEqual(node.options.flow, "xtls-rprx-vision")
        self.assertEqual(node.options.fingerprint, "chrome")
        self.assertEqual(node.options.label, "VPN Node 1")

    def test_five_nodes_sorted_by_default_priority(self) -> None:
        env: dict[str, str] = {}
        for n in range(1, 6):
            env.update(_base_env(n))

        nodes = parse_nodes_from_env(env)

        self.assertEqual(len(nodes), 5)
        priorities = [node.priority for node in nodes]
        self.assertEqual(priorities, [10, 20, 30, 40, 50])

    def test_gap_in_numbering_skips_missing_index(self) -> None:
        env = {**_base_env(1), **_base_env(3)}

        nodes = parse_nodes_from_env(env)

        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].id, "node_env_1")
        self.assertEqual(nodes[1].id, "node_env_3")

    def test_disabled_node_has_disabled_status(self) -> None:
        env = {**_base_env(1), "VPN_NODE_1_ENABLED": "false"}

        nodes = parse_nodes_from_env(env)

        self.assertEqual(nodes[0].status, NodeStatus.DISABLED)
        self.assertEqual(nodes[0].health, NodeHealth.DISABLED)

    def test_disabled_node_is_not_usable(self) -> None:
        env = {**_base_env(1), "VPN_NODE_1_ENABLED": "false"}

        node = parse_nodes_from_env(env)[0]

        self.assertFalse(node.is_usable())

    def test_active_node_is_usable(self) -> None:
        nodes = parse_nodes_from_env(_base_env(1))

        self.assertTrue(nodes[0].is_usable())

    def test_custom_label_region_country_priority(self) -> None:
        env = {
            **_base_env(1),
            "VPN_NODE_1_LABEL": "Frankfurt #1",
            "VPN_NODE_1_REGION": "eu-central",
            "VPN_NODE_1_COUNTRY_CODE": "DE",
            "VPN_NODE_1_PRIORITY": "5",
        }

        node = parse_nodes_from_env(env)[0]

        assert isinstance(node.options, VlessOptions)
        self.assertEqual(node.options.label, "Frankfurt #1")
        self.assertEqual(node.region, "eu-central")
        self.assertEqual(node.country_code, "DE")
        self.assertEqual(node.priority, 5)

    def test_custom_flow_and_fingerprint(self) -> None:
        env = {
            **_base_env(1),
            "VPN_NODE_1_FLOW": "",
            "VPN_NODE_1_FINGERPRINT": "firefox",
        }

        node = parse_nodes_from_env(env)[0]

        assert isinstance(node.options, VlessOptions)
        self.assertIsNone(node.options.flow)
        self.assertEqual(node.options.fingerprint, "firefox")

    def test_missing_uuid_raises_error(self) -> None:
        env = {k: v for k, v in _base_env(1).items() if "UUID" not in k}

        with self.assertRaises(NodeConfigError) as ctx:
            parse_nodes_from_env(env)

        self.assertIn("UUID", str(ctx.exception))

    def test_missing_public_key_raises_error(self) -> None:
        env = {k: v for k, v in _base_env(1).items() if "PUBLIC_KEY" not in k}

        with self.assertRaises(NodeConfigError) as ctx:
            parse_nodes_from_env(env)

        self.assertIn("PUBLIC_KEY", str(ctx.exception))

    def test_missing_short_id_raises_error(self) -> None:
        env = {k: v for k, v in _base_env(1).items() if "SHORT_ID" not in k}

        with self.assertRaises(NodeConfigError) as ctx:
            parse_nodes_from_env(env)

        self.assertIn("SHORT_ID", str(ctx.exception))

    def test_missing_sni_raises_error(self) -> None:
        env = {k: v for k, v in _base_env(1).items() if "SNI" not in k}

        with self.assertRaises(NodeConfigError) as ctx:
            parse_nodes_from_env(env)

        self.assertIn("SNI", str(ctx.exception))

    def test_invalid_port_raises_error(self) -> None:
        env = {**_base_env(1), "VPN_NODE_1_PORT": "not-a-number"}

        with self.assertRaises(NodeConfigError) as ctx:
            parse_nodes_from_env(env)

        self.assertIn("PORT", str(ctx.exception))

    def test_out_of_range_port_raises_error(self) -> None:
        env = {**_base_env(1), "VPN_NODE_1_PORT": "99999"}

        with self.assertRaises(NodeConfigError):
            parse_nodes_from_env(env)

    def test_invalid_enabled_value_raises_error(self) -> None:
        env = {**_base_env(1), "VPN_NODE_1_ENABLED": "maybe"}

        with self.assertRaises(NodeConfigError) as ctx:
            parse_nodes_from_env(env)

        self.assertIn("ENABLED", str(ctx.exception))

    def test_invalid_priority_raises_error(self) -> None:
        env = {**_base_env(1), "VPN_NODE_1_PRIORITY": "high"}

        with self.assertRaises(NodeConfigError) as ctx:
            parse_nodes_from_env(env)

        self.assertIn("PRIORITY", str(ctx.exception))


class NodeConfigInMemoryRepoTest(unittest.TestCase):
    def test_env_nodes_replace_demo_seeds(self) -> None:
        from app.repositories.memory import InMemoryRepository

        env_nodes = parse_nodes_from_env(_base_env(1))
        repo = InMemoryRepository(nodes=env_nodes)

        nodes = repo.list_nodes()

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].id, "node_env_1")

    def test_no_env_nodes_uses_demo_seeds(self) -> None:
        from app.repositories.memory import InMemoryRepository

        repo = InMemoryRepository(nodes=None)

        nodes = repo.list_nodes()

        self.assertGreater(len(nodes), 0)
        self.assertTrue(any(node.id.startswith("node_eu") for node in nodes))


class NodeConfigSettingsTest(unittest.TestCase):
    def _base_settings_env(self) -> dict[str, str]:
        return {
            "VPN_ROUTER_TOKEN_SECRET": "test-secret-with-enough-len",
            "VPN_ROUTER_ADMIN_TOKEN": "test-admin-with-enough-len",
            "PUBLIC_BASE_URL": "http://127.0.0.1:8080",
        }

    def test_settings_loads_nodes_from_env(self) -> None:
        from app.core.settings import load_settings

        env = {**self._base_settings_env(), **_base_env(1)}
        settings = load_settings(env)

        self.assertEqual(len(settings.nodes), 1)
        self.assertEqual(settings.nodes[0].host, "10.0.0.1")

    def test_settings_empty_nodes_when_no_env(self) -> None:
        from app.core.settings import load_settings

        settings = load_settings(self._base_settings_env())

        self.assertEqual(settings.nodes, ())

    def test_settings_rejects_node_with_missing_uuid(self) -> None:
        from app.core.settings import SettingsError, load_settings

        env = {
            **self._base_settings_env(),
            "VPN_NODE_1_HOST": "1.2.3.4",
            "VPN_NODE_1_PUBLIC_KEY": "key",
            "VPN_NODE_1_SHORT_ID": "sid",
            "VPN_NODE_1_SNI": "example.com",
        }

        with self.assertRaises(SettingsError):
            load_settings(env)

    def test_settings_accepts_crypto_manual_checkout_mode(self) -> None:
        from app.core.settings import load_settings

        env = {**self._base_settings_env(), "CHECKOUT_MODE": "crypto_manual"}
        settings = load_settings(env)

        self.assertEqual(settings.checkout_mode, "crypto_manual")

    def test_settings_rejects_unknown_checkout_mode(self) -> None:
        from app.core.settings import SettingsError, load_settings

        env = {**self._base_settings_env(), "CHECKOUT_MODE": "stripe"}

        with self.assertRaises(SettingsError):
            load_settings(env)


if __name__ == "__main__":
    unittest.main()
