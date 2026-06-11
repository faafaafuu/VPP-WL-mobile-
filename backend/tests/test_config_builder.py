from __future__ import annotations

import unittest

from app.domain.config_builder import ConfigBuilder
from app.domain.models import NodeStatus, Protocol, VlessOptions, VpnNode


class ConfigBuilderTest(unittest.TestCase):
    def test_builds_config_with_direct_ru_rules_and_auto_proxy(self) -> None:
        config = ConfigBuilder().build_client_config(
            [
                VpnNode(
                    id="node-1",
                    tag="vless-eu-1",
                    region="eu",
                    country_code="DE",
                    host="eu1.example.com",
                    port=443,
                    protocol=Protocol.VLESS,
                    status=NodeStatus.ACTIVE,
                    priority=10,
                    options=VlessOptions(
                        uuid="00000000-0000-4000-8000-000000000001",
                        server_name="cdn.example.com",
                    ),
                )
            ]
        )

        outbound_tags = {outbound["tag"] for outbound in config["outbounds"]}
        self.assertIn("auto", outbound_tags)
        self.assertIn("direct", outbound_tags)
        self.assertEqual(config["route"]["final"], "auto")
        self.assertTrue(
            any(rule.get("domain_suffix") and "ru" in rule["domain_suffix"] for rule in config["route"]["rules"])
        )
        self.assertTrue(any(rule_set["tag"] == "geosite-ru" for rule_set in config["route"]["rule_set"]))

    def test_skips_disabled_nodes(self) -> None:
        config = ConfigBuilder().build_client_config(
            [
                VpnNode(
                    id="disabled",
                    tag="disabled",
                    region="eu",
                    country_code="DE",
                    host="bad.example.com",
                    port=443,
                    protocol=Protocol.VLESS,
                    status=NodeStatus.DISABLED,
                    priority=10,
                    options=VlessOptions(
                        uuid="00000000-0000-4000-8000-000000000001",
                        server_name="cdn.example.com",
                    ),
                ),
                VpnNode(
                    id="active",
                    tag="active",
                    region="eu",
                    country_code="DE",
                    host="ok.example.com",
                    port=443,
                    protocol=Protocol.VLESS,
                    status=NodeStatus.ACTIVE,
                    priority=10,
                    options=VlessOptions(
                        uuid="00000000-0000-4000-8000-000000000002",
                        server_name="cdn.example.com",
                    ),
                ),
            ]
        )

        outbound_tags = {outbound["tag"] for outbound in config["outbounds"]}
        self.assertIn("active", outbound_tags)
        self.assertNotIn("disabled", outbound_tags)

    def test_fails_when_no_nodes_are_usable(self) -> None:
        with self.assertRaises(ValueError):
            ConfigBuilder().build_client_config([])


if __name__ == "__main__":
    unittest.main()

