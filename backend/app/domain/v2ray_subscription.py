from __future__ import annotations

import base64
from urllib.parse import quote, urlencode

from app.domain.models import Protocol, VlessOptions, VpnNode


def active_vless_nodes(nodes: list[VpnNode]) -> list[VpnNode]:
    return sorted(
        (
            node
            for node in nodes
            if node.protocol == Protocol.VLESS
            and node.is_usable()
            and isinstance(node.options, VlessOptions)
        ),
        key=lambda node: (node.priority, -node.health_score, node.tag),
    )


def vless_links(nodes: list[VpnNode]) -> list[str]:
    links: list[str] = []
    for node in active_vless_nodes(nodes):
        assert isinstance(node.options, VlessOptions)
        links.append(_vless_link(node, node.options))
    return links


def hysteria2_link(
    host: str,
    port: int,
    password: str,
    sni: str,
    insecure: bool = False,
    obfs_password: str | None = None,
    label: str = "⚡ Клео │ H2",
) -> str:
    """UDP/QUIC node on the German box.

    Salamander obfs (obfs_password) scrambles every packet into random bytes so
    DPI sees no QUIC/TLS/SNI fingerprint at all.

    Measured 2026-08-29: unusable from RU mobile carriers. UDP to a foreign IP
    on a non-standard port is dropped outright, and 84.247.166.53 is separately
    throttled there — anything encrypted to it stalls at ~4 KB while plain HTTP
    carries 64 KB fine. Clients try this node first and hang on it, which is why
    subscriptions felt "flaky" even where the Reality node worked. Kept behind
    HYSTERIA2_IN_SUBSCRIPTION (off) so it returns the day that IP recovers.
    """
    query = f"sni={quote(sni, safe='')}&insecure={'1' if insecure else '0'}"
    if obfs_password:
        query += f"&obfs=salamander&obfs-password={quote(obfs_password, safe='')}"
    return f"hysteria2://{quote(password, safe='')}@{host}:{port}/?{query}#{quote(label)}"


def raw_subscription(nodes: list[VpnNode], extra_links: list[str] | None = None) -> str:
    links = list(extra_links or []) + vless_links(nodes)
    if not links:
        raise ValueError("no active nodes available")
    return "\n".join(links) + "\n"


def encoded_subscription(nodes: list[VpnNode], extra_links: list[str] | None = None) -> str:
    raw = raw_subscription(nodes, extra_links=extra_links)
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _vless_link(node: VpnNode, options: VlessOptions) -> str:
    reality = options.reality or {}
    security = str(options.security or reality.get("security") or "reality").strip().lower() or "reality"

    transport = _transport_type(options)
    query = {
        "type": transport,
        # Required by the VLESS share-link spec. Lenient clients (V2Box)
        # default it to "none" and connect anyway; strict ones (Happ,
        # Hiddify, anything sing-box based) reject the link outright — which
        # is exactly why the same node worked in one app and not the others.
        "encryption": "none",
        "security": security,
    }
    if transport == "tcp":
        query["headerType"] = str((options.transport or {}).get("headerType") or "none")
    if security == "reality":
        public_key = str(options.public_key or reality.get("public_key") or reality.get("pbk") or "").strip()
        short_id = str(options.short_id or reality.get("short_id") or reality.get("sid") or "").strip()
        if not public_key:
            raise ValueError(f"VLESS node {node.id} is missing public_key")
        if not short_id:
            raise ValueError(f"VLESS node {node.id} is missing short_id")
        query["pbk"] = public_key
    query["fp"] = options.fingerprint or str(reality.get("fingerprint", "chrome"))
    query["sni"] = options.server_name
    if security == "reality":
        query["sid"] = short_id
    if options.flow:
        query["flow"] = options.flow

    label = options.label or str(reality.get("label") or node.tag)
    return (
        f"vless://{quote(options.uuid, safe='')}@{node.host}:{node.port}"
        f"?{urlencode(query)}#{quote(label)}"
    )


def _transport_type(options: VlessOptions) -> str:
    if not options.transport:
        return "tcp"
    return str(options.transport.get("type") or "tcp")
