"""sing-box client config — the answer to DNS interception on RU carriers.

A plain vless:// list leaves name resolution to the phone, which on mobile
data means a UDP query to 8.8.8.8 that never reaches Google: TSPU answers it
from the national resolver, and blocked names come back nulled or stale. That
is the same mechanism that kept handing this project's own domain the old,
throttled origin IP long after the record had been moved to Cloudflare.

This config closes that hole. Every query is hijacked out of the OS
(`protocol: dns` -> `dns-out`) and answered over DoH *through the tunnel*, so
the carrier sees one more encrypted stream to the entry node and nothing it
can rewrite. The DoH endpoint is addressed by IP literal on purpose: giving
it a hostname would need resolving before the resolver exists.

Entry nodes are dialled by IP too, so nothing in the startup path depends on
DNS working at all.
"""

from __future__ import annotations

import json
from typing import Any

from app.domain.models import VlessOptions, VpnNode
from app.domain.v2ray_subscription import active_vless_nodes

# Cloudflare, then Google as the second opinion. IP literals — see module docstring.
DOH_PRIMARY = "1.1.1.1"
DOH_SECONDARY = "8.8.8.8"

PROXY_TAG = "proxy"
AUTO_TAG = "auto"
DIRECT_TAG = "direct"


def singbox_config(nodes: list[VpnNode], profile_name: str = "Клео") -> dict[str, Any]:
    outbounds, node_tags = _node_outbounds(nodes)
    if not node_tags:
        raise ValueError("no active nodes available")

    return {
        "log": {"level": "warn", "timestamp": True},
        "dns": _dns(),
        "inbounds": [_tun_inbound()],
        "outbounds": [
            {
                "type": "selector",
                "tag": PROXY_TAG,
                "outbounds": [AUTO_TAG, *node_tags],
                "default": AUTO_TAG,
                "interrupt_exist_connections": False,
            },
            {
                "type": "urltest",
                "tag": AUTO_TAG,
                "outbounds": list(node_tags),
                # Plain HTTP 204: a TLS probe would itself be shaped on the
                # carriers this config exists to survive, making every node
                # look dead.
                "url": "http://cp.cloudflare.com/generate_204",
                "interval": "3m",
                "tolerance": 50,
            },
            *outbounds,
            {"type": "direct", "tag": DIRECT_TAG},
        ],
        "route": _route(),
        "experimental": {
            "cache_file": {"enabled": True, "store_fakeip": False},
            "clash_api": {"external_controller": "127.0.0.1:9090"},
        },
        "_profile": profile_name,
    }


def singbox_config_json(nodes: list[VpnNode], profile_name: str = "Клео") -> str:
    config = singbox_config(nodes, profile_name=profile_name)
    config.pop("_profile", None)
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def _dns() -> dict[str, Any]:
    """sing-box 1.12+ DNS schema.

    The pre-1.12 `{"address": "https://..."}` form is not merely deprecated:
    1.12 and later refuse to start on it unless the user sets an environment
    variable, which is not something a phone app can do.
    """
    return {
        "servers": [
            {"type": "https", "tag": "dns-remote", "server": DOH_PRIMARY, "detour": PROXY_TAG},
            {"type": "https", "tag": "dns-remote-alt", "server": DOH_SECONDARY, "detour": PROXY_TAG},
        ],
        "final": "dns-remote",
        # HTTPS/SVCB records carry ECH and alt-endpoints that make clients open
        # connections outside the tunnel's routing assumptions.
        "strategy": "ipv4_only",
        "disable_cache": False,
        "independent_cache": True,
        "reverse_mapping": True,
    }


def _tun_inbound() -> dict[str, Any]:
    return {
        "type": "tun",
        "tag": "tun-in",
        "address": ["172.19.0.1/30"],
        "mtu": 1400,
        "auto_route": True,
        "strict_route": True,
        "stack": "mixed",
        "endpoint_independent_nat": True,
    }


def _route() -> dict[str, Any]:
    """sing-box 1.12+ route actions.

    Sniffing, DNS hijacking and rejection are rule *actions* now; the old
    `sniff` inbound flag and the `block`/`dns` outbound types are on their way
    out. Order matters: sniff first so later rules can see the real
    destination, then the DNS hijack that is the whole point of this profile.
    """
    return {
        "rules": [
            {"action": "sniff"},
            # This is what takes DNS away from the carrier.
            {"protocol": "dns", "action": "hijack-dns"},
            {"ip_is_private": True, "outbound": DIRECT_TAG},
            # QUIC to :443 is dropped by RU carriers often enough that letting
            # browsers negotiate HTTP/3 inside the tunnel produces stalls that
            # look like the tunnel is broken. Force the TCP fallback.
            {"protocol": "quic", "action": "reject"},
        ],
        "final": PROXY_TAG,
        "auto_detect_interface": True,
        # Required from 1.12: names that need resolving while dialling are sent
        # here. No loop — both the DoH endpoints and the entry nodes are IP
        # literals, so nothing in the dial path needs DNS to come up.
        "default_domain_resolver": {"server": "dns-remote"},
    }


def _node_outbounds(nodes: list[VpnNode]) -> tuple[list[dict[str, Any]], list[str]]:
    outbounds: list[dict[str, Any]] = []
    tags: list[str] = []
    used: set[str] = set()
    for node in active_vless_nodes(nodes):
        options = node.options
        assert isinstance(options, VlessOptions)
        tag = _unique_tag(options.label or node.tag, used)
        outbounds.append(_vless_outbound(node, options, tag))
        tags.append(tag)
    return outbounds, tags


def _unique_tag(base: str, used: set[str]) -> str:
    tag = (base or "node").strip() or "node"
    candidate = tag
    n = 2
    while candidate in used:
        candidate = f"{tag} {n}"
        n += 1
    used.add(candidate)
    return candidate


def _vless_outbound(node: VpnNode, options: VlessOptions, tag: str) -> dict[str, Any]:
    reality = options.reality or {}
    security = str(options.security or reality.get("security") or "reality").strip().lower() or "reality"

    out: dict[str, Any] = {
        "type": "vless",
        "tag": tag,
        "server": node.host,
        "server_port": node.port,
        "uuid": options.uuid,
        # UDP over VLESS needs xudp; without it DNS-over-UDP fallbacks and
        # anything else UDP silently die inside the tunnel.
        "packet_encoding": "xudp",
    }
    if options.flow:
        out["flow"] = options.flow

    tls: dict[str, Any] = {
        "enabled": True,
        "server_name": options.server_name,
        "utls": {"enabled": True, "fingerprint": options.fingerprint or str(reality.get("fingerprint", "chrome"))},
    }
    if security == "reality":
        public_key = str(options.public_key or reality.get("public_key") or reality.get("pbk") or "").strip()
        short_id = str(options.short_id or reality.get("short_id") or reality.get("sid") or "").strip()
        if not public_key:
            raise ValueError(f"VLESS node {node.id} is missing public_key")
        if not short_id:
            raise ValueError(f"VLESS node {node.id} is missing short_id")
        tls["reality"] = {"enabled": True, "public_key": public_key, "short_id": short_id}
    out["tls"] = tls

    transport = _transport(options)
    if transport:
        out["transport"] = transport
    return out


def _transport(options: VlessOptions) -> dict[str, Any] | None:
    raw = options.transport or {}
    kind = str(raw.get("type") or "tcp").lower()
    if kind in ("tcp", ""):
        return None  # sing-box default; emitting it is an error in some builds
    if kind == "ws":
        ws: dict[str, Any] = {"type": "ws", "path": str(raw.get("path") or "/")}
        host = raw.get("host")
        if host:
            ws["headers"] = {"Host": str(host)}
        if raw.get("max_early_data"):
            ws["max_early_data"] = int(raw["max_early_data"])
            ws["early_data_header_name"] = str(raw.get("early_data_header_name") or "Sec-WebSocket-Protocol")
        return ws
    if kind == "grpc":
        return {"type": "grpc", "service_name": str(raw.get("serviceName") or raw.get("service_name") or "")}
    if kind in ("http", "h2"):
        http: dict[str, Any] = {"type": "http", "path": str(raw.get("path") or "/")}
        host = raw.get("host")
        if host:
            http["host"] = [str(host)] if isinstance(host, str) else [str(h) for h in host]
        return http
    raise ValueError(f"unsupported transport for sing-box: {kind}")
