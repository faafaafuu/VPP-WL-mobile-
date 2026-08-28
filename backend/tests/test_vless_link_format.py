from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from app.domain.models import NodeStatus, Protocol, VlessOptions, VpnNode
from app.domain.v2ray_subscription import vless_links


def _node(**overrides) -> VpnNode:
    options = VlessOptions(
        uuid="e664c9ea-8409-41d2-9205-5d6d815393a8",
        server_name="cl10ru.funvideorus.net",
        flow="xtls-rprx-vision",
        public_key="mwdfNmIXb0oPVZBdNrrwWe_iaDnXAmFAWANiZrXUJgs",
        short_id="8ca2056b80d84239",
        fingerprint="chrome",
        **overrides,
    )
    return VpnNode(
        id="node_ru_1",
        tag="Клео",
        region="ru-moscow",
        provider="cloudru",
        country_code="RU",
        host="82.202.158.253",
        port=443,
        protocol=Protocol.VLESS,
        status=NodeStatus.ACTIVE,
        priority=1,
        options=options,
    )


def _query(link: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(link).query).items()}


class VlessLinkFormatTest(unittest.TestCase):
    def test_link_declares_encryption_none(self) -> None:
        """The VLESS share-link spec requires `encryption`. V2Box defaults it
        to "none" and connects anyway; Happ, Hiddify and other sing-box based
        clients reject the link — the same node then "works in one app only",
        with a healthy server and correct credentials on both sides."""
        self.assertEqual(_query(vless_links([_node()])[0])["encryption"], "none")

    def test_tcp_transport_declares_header_type(self) -> None:
        self.assertEqual(_query(vless_links([_node()])[0])["headerType"], "none")

    def test_reality_parameters_survive(self) -> None:
        query = _query(vless_links([_node()])[0])

        self.assertEqual(query["security"], "reality")
        self.assertEqual(query["type"], "tcp")
        self.assertEqual(query["sni"], "cl10ru.funvideorus.net")
        self.assertEqual(query["pbk"], "mwdfNmIXb0oPVZBdNrrwWe_iaDnXAmFAWANiZrXUJgs")
        self.assertEqual(query["sid"], "8ca2056b80d84239")
        self.assertEqual(query["fp"], "chrome")
        self.assertEqual(query["flow"], "xtls-rprx-vision")

    def test_link_carries_every_field_a_known_good_link_has(self) -> None:
        """Pinned against a link confirmed working against this same server,
        so a future edit can't quietly drop a field again."""
        known_good = {
            "security", "flow", "fp", "encryption", "sni", "pbk", "sid", "type", "headerType",
        }

        self.assertTrue(known_good.issubset(set(_query(vless_links([_node()])[0]))))


if __name__ == "__main__":
    unittest.main()
