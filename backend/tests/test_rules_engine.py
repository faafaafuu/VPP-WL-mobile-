from __future__ import annotations

import unittest

from app.domain.config_builder import ConfigBuilder
from app.domain.models import NodeStatus, Protocol, VlessOptions, VpnNode
from app.domain.rules_engine import RulesEngine


class RulesEngineTest(unittest.TestCase):
    def test_direct_rules_include_ru_government_banks_and_marketplaces(self) -> None:
        rules = RulesEngine().route_rules()
        direct_rules = [rule for rule in rules if rule.get("outbound") == "direct"]

        self.assertTrue(any("ru" in rule.get("domain_suffix", []) for rule in direct_rules))
        self.assertTrue(any("рф" in rule.get("domain_suffix", []) for rule in direct_rules))
        self.assertTrue(any("gosuslugi.ru" in rule.get("domain", []) for rule in direct_rules))
        self.assertTrue(any("sber.ru" in rule.get("domain", []) for rule in direct_rules))
        self.assertTrue(any("yandex.ru" in rule.get("domain", []) for rule in direct_rules))
        self.assertTrue(any("vk.com" in rule.get("domain", []) for rule in direct_rules))
        self.assertTrue(any("ozon.ru" in rule.get("domain", []) for rule in direct_rules))
        self.assertTrue(any("wildberries.ru" in rule.get("domain", []) for rule in direct_rules))
        self.assertTrue(any("avito.ru" in rule.get("domain", []) for rule in direct_rules))
        self.assertTrue(any("geosite-ru" in rule.get("rule_set", []) for rule in direct_rules))

    def test_proxy_rules_include_common_fallback_services(self) -> None:
        rules = RulesEngine().route_rules()
        proxy_rules = [rule for rule in rules if rule.get("outbound") == "auto"]

        self.assertTrue(any("telegram.org" in rule.get("domain", []) for rule in proxy_rules))
        self.assertTrue(any("instagram.com" in rule.get("domain", []) for rule in proxy_rules))
        self.assertTrue(any("youtube.com" in rule.get("domain", []) for rule in proxy_rules))
        self.assertTrue(any("openai.com" in rule.get("domain", []) for rule in proxy_rules))
        self.assertTrue(any("x.com" in rule.get("domain", []) for rule in proxy_rules))
        self.assertTrue(any("discord.com" in rule.get("domain", []) for rule in proxy_rules))
        self.assertTrue(any("github.com" in rule.get("domain", []) for rule in proxy_rules))

    def test_rules_are_emitted_into_sing_box_config(self) -> None:
        config = ConfigBuilder().build_client_config([_node()])
        route_rules = config["route"]["rules"]

        self.assertTrue(any(rule.get("outbound") == "direct" for rule in route_rules))
        self.assertTrue(any(rule.get("outbound") == "auto" for rule in route_rules))
        self.assertTrue(any(rule_set["tag"] == "geoip-ru" for rule_set in config["route"]["rule_set"]))

    def test_remote_rule_sets_are_versioned_and_checksum_addressed(self) -> None:
        rule_sets = RulesEngine().remote_rule_sets

        self.assertTrue(all("example.invalid" not in rule_set["url"] for rule_set in rule_sets))
        self.assertTrue(all("/v2026.06.12/" in rule_set["url"] for rule_set in rule_sets))
        self.assertTrue(all("?sha256=" in rule_set["url"] for rule_set in rule_sets))
        self.assertTrue(all(rule_set["update_interval"] == "24h" for rule_set in rule_sets))


def _node() -> VpnNode:
    return VpnNode(
        id="node-1",
        tag="vless-eu-1",
        region="eu",
        provider="test",
        country_code="DE",
        host="eu1.example.com",
        port=443,
        protocol=Protocol.VLESS,
        status=NodeStatus.ACTIVE,
        priority=10,
        options=VlessOptions(uuid="00000000-0000-4000-8000-000000000001", server_name="cdn.example.com"),
    )


if __name__ == "__main__":
    unittest.main()
