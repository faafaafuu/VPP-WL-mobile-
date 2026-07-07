from __future__ import annotations

import base64
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

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


def raw_subscription(nodes: list[VpnNode]) -> str:
    links = vless_links(nodes)
    if not links:
        raise ValueError("no active VLESS nodes available")
    return "\n".join(links) + "\n"


def encoded_subscription(nodes: list[VpnNode]) -> str:
    raw = raw_subscription(nodes)
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _vless_link(node: VpnNode, options: VlessOptions) -> str:
    # Imported nodes carry the original vless:// URL — serve it verbatim, only
    # swapping the #label so the client shows our friendly name.
    if options.raw_url:
        return _relabel(options.raw_url, options.label or node.tag)

    reality = options.reality or {}
    public_key = str(options.public_key or reality.get("public_key") or reality.get("pbk") or "").strip()
    short_id = str(options.short_id or reality.get("short_id") or reality.get("sid") or "").strip()
    if not public_key:
        raise ValueError(f"VLESS node {node.id} is missing public_key")
    if not short_id:
        raise ValueError(f"VLESS node {node.id} is missing short_id")

    query = {
        "type": _transport_type(options),
        "security": options.security or str(reality.get("security", "reality")),
        "pbk": public_key,
        "fp": options.fingerprint or str(reality.get("fingerprint", "chrome")),
        "sni": options.server_name,
        "sid": short_id,
    }
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


def _relabel(raw_url: str, label: str) -> str:
    """Return the vless:// URL with its #fragment replaced by label."""
    scheme, netloc, path, query, _ = urlsplit(raw_url)
    return urlunsplit((scheme, netloc, path, query, quote(label)))
