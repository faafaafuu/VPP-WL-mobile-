"""sing-box profile — the form that takes DNS away from the carrier."""

from __future__ import annotations

import json
import unittest

from app.domain.models import NodeStatus, Protocol, VlessOptions, VpnNode
from app.domain.singbox_config import PROXY_TAG, singbox_config, singbox_config_json


def _reality_node(node_id: str = "msk-1", priority: int = 1, label: str | None = None) -> VpnNode:
    return VpnNode(
        id=node_id,
        tag=f"vless-{node_id}",
        region="ru",
        provider="cloudru",
        country_code="RU",
        host="82.202.158.253",
        port=443,
        protocol=Protocol.VLESS,
        status=NodeStatus.ACTIVE,
        priority=priority,
        options=VlessOptions(
            uuid="e664c9ea-8409-41d2-9205-5d6d815393a8",
            server_name="cl10ru.funvideorus.net",
            flow="xtls-rprx-vision",
            public_key="mwdfNmIXb0oPVZBdNrrwWe_iaDnXAmFAWANiZrXUJgs",
            short_id="8ca2056b80d84239",
            label=label,
        ),
    )


class DnsInsideTunnelTest(unittest.TestCase):
    def test_every_query_resolves_over_doh_through_the_proxy(self) -> None:
        dns = singbox_config([_reality_node()])["dns"]

        remote = next(s for s in dns["servers"] if s["tag"] == "dns-remote")
        self.assertEqual(remote["type"], "https")
        self.assertEqual(remote["detour"], PROXY_TAG)
        self.assertEqual(dns["final"], "dns-remote")

    def test_doh_endpoints_are_ip_literals(self) -> None:
        """A hostname here would need resolving before the resolver exists."""
        dns = singbox_config([_reality_node()])["dns"]

        for server in dns["servers"]:
            octets = server["server"].split(".")
            self.assertEqual(len(octets), 4, f"{server['server']} is not an IPv4 literal")
            self.assertTrue(all(o.isdigit() for o in octets), f"{server['server']} is not an IPv4 literal")

    def test_os_dns_is_hijacked_before_any_traffic_is_routed(self) -> None:
        rules = singbox_config([_reality_node()])["route"]["rules"]

        hijack = next(i for i, r in enumerate(rules) if r.get("action") == "hijack-dns")
        first_routing = next(i for i, r in enumerate(rules) if "outbound" in r)
        self.assertLess(hijack, first_routing)

    def test_sniff_runs_first_so_later_rules_see_the_real_destination(self) -> None:
        rules = singbox_config([_reality_node()])["route"]["rules"]

        self.assertEqual(rules[0], {"action": "sniff"})

    def test_dial_time_resolution_has_a_declared_resolver(self) -> None:
        """Required from 1.12; sing-box refuses to start without it."""
        route = singbox_config([_reality_node()])["route"]

        self.assertEqual(route["default_domain_resolver"], {"server": "dns-remote"})

    def test_every_referenced_outbound_exists(self) -> None:
        config = singbox_config([_reality_node()])
        tags = {o["tag"] for o in config["outbounds"]}

        referenced = {r["outbound"] for r in config["route"]["rules"] if "outbound" in r}
        referenced.add(config["route"]["final"])
        referenced.update(s["detour"] for s in config["dns"]["servers"] if "detour" in s)

        self.assertEqual(referenced - tags, set())

    def test_no_legacy_schema_leaks_back_in(self) -> None:
        """1.12+ hard-fails on any of these, and a phone app cannot set the
        opt-out environment variables that would keep them working."""
        config = singbox_config([_reality_node()])

        self.assertFalse([s for s in config["dns"]["servers"] if "address" in s])
        self.assertNotIn("sniff", config["inbounds"][0])
        self.assertFalse([o for o in config["outbounds"] if o["type"] in {"block", "dns"}])


class NodeOutboundTest(unittest.TestCase):
    def test_reality_node_carries_keys_and_utls(self) -> None:
        config = singbox_config([_reality_node()])

        node = next(o for o in config["outbounds"] if o["type"] == "vless")
        self.assertEqual(node["server"], "82.202.158.253")
        self.assertEqual(node["server_port"], 443)
        self.assertEqual(node["flow"], "xtls-rprx-vision")
        self.assertEqual(node["packet_encoding"], "xudp")
        self.assertTrue(node["tls"]["reality"]["enabled"])
        self.assertEqual(node["tls"]["reality"]["short_id"], "8ca2056b80d84239")
        self.assertEqual(node["tls"]["utls"]["fingerprint"], "chrome")
        self.assertEqual(node["tls"]["server_name"], "cl10ru.funvideorus.net")

    def test_tcp_transport_is_left_implicit(self) -> None:
        node = next(o for o in singbox_config([_reality_node()])["outbounds"] if o["type"] == "vless")

        self.assertNotIn("transport", node)

    def test_selector_and_urltest_cover_every_node(self) -> None:
        nodes = [_reality_node("a", 1, label="A"), _reality_node("b", 2, label="B")]

        config = singbox_config(nodes)

        selector = next(o for o in config["outbounds"] if o["type"] == "selector")
        urltest = next(o for o in config["outbounds"] if o["type"] == "urltest")
        self.assertEqual(urltest["outbounds"], ["A", "B"])
        self.assertEqual(selector["outbounds"], ["auto", "A", "B"])

    def test_urltest_probe_is_plain_http(self) -> None:
        """A TLS probe is itself shaped on the carriers this config exists to
        survive, which would mark every node dead."""
        urltest = next(o for o in singbox_config([_reality_node()])["outbounds"] if o["type"] == "urltest")

        self.assertTrue(urltest["url"].startswith("http://"))

    def test_duplicate_labels_get_distinct_tags(self) -> None:
        nodes = [_reality_node("a", 1, label="Клео"), _reality_node("b", 2, label="Клео")]

        config = singbox_config(nodes)

        tags = [o["tag"] for o in config["outbounds"] if o["type"] == "vless"]
        self.assertEqual(len(set(tags)), 2)

    def test_unusable_nodes_are_skipped(self) -> None:
        from dataclasses import replace

        good = _reality_node("good", 1, label="Good")
        dead = replace(_reality_node("dead", 2, label="Dead"), status=NodeStatus.DISABLED)

        tags = [o["tag"] for o in singbox_config([good, dead])["outbounds"] if o["type"] == "vless"]

        self.assertEqual(tags, ["Good"])

    def test_no_usable_nodes_raises(self) -> None:
        with self.assertRaises(ValueError):
            singbox_config([])

    def test_missing_reality_key_raises(self) -> None:
        from dataclasses import replace

        node = _reality_node()
        broken = replace(node, options=replace(node.options, public_key=""))

        with self.assertRaises(ValueError):
            singbox_config([broken])


class SerialisationTest(unittest.TestCase):
    def test_json_is_valid_and_drops_internal_keys(self) -> None:
        text = singbox_config_json([_reality_node()])

        parsed = json.loads(text)
        self.assertNotIn("_profile", parsed)
        self.assertIn("dns", parsed)
        self.assertIn("inbounds", parsed)

    def test_tun_inbound_routes_the_whole_device(self) -> None:
        inbound = singbox_config([_reality_node()])["inbounds"][0]

        self.assertEqual(inbound["type"], "tun")
        self.assertTrue(inbound["auto_route"])
        self.assertTrue(inbound["strict_route"])


if __name__ == "__main__":
    unittest.main()
