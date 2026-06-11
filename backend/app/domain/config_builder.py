from __future__ import annotations

from typing import Any

from app.domain.models import (
    Hysteria2Options,
    Protocol,
    ShadowsocksOptions,
    VlessOptions,
    VpnNode,
    WireGuardOptions,
)
from app.domain.node_scoring import sort_nodes_by_score
from app.domain.rules_engine import RulesEngine


class ConfigBuilder:
    def __init__(self, rules_engine: RulesEngine | None = None) -> None:
        self.rules_engine = rules_engine or RulesEngine()

    def build_client_config(self, nodes: list[VpnNode]) -> dict[str, Any]:
        usable_nodes = sort_nodes_by_score(nodes)
        if not usable_nodes:
            raise ValueError("no usable VPN nodes available")

        proxy_outbounds = [self._node_to_outbound(node) for node in usable_nodes]
        proxy_tags = [outbound["tag"] for outbound in proxy_outbounds]

        return {
            "log": {"level": "warn", "timestamp": True},
            "dns": self._dns_config(),
            "inbounds": [
                {
                    "type": "tun",
                    "tag": "tun-in",
                    "interface_name": "vpn0",
                    "address": ["172.19.0.1/30", "fdfe:dcba:9876::1/126"],
                    "auto_route": True,
                    "strict_route": True,
                    "sniff": True,
                }
            ],
            "outbounds": [
                {
                    "type": "urltest",
                    "tag": "auto",
                    "outbounds": proxy_tags,
                    "url": "https://www.gstatic.com/generate_204",
                    "interval": "1m",
                    "tolerance": 80,
                },
                *proxy_outbounds,
                {"type": "direct", "tag": "direct"},
                {"type": "block", "tag": "block"},
            ],
            "route": self._route_config(),
        }

    def _dns_config(self) -> dict[str, Any]:
        return {
            "servers": [
                {"tag": "ru-dns", "address": "https://77.88.8.8/dns-query", "detour": "direct"},
                {"tag": "remote-dns", "address": "https://1.1.1.1/dns-query", "detour": "auto"},
            ],
            "rules": [
                *self.rules_engine.dns_rules("ru-dns"),
            ],
            "final": "remote-dns",
            "strategy": "prefer_ipv4",
        }

    def _route_config(self) -> dict[str, Any]:
        return {
            "rules": self.rules_engine.route_rules(),
            "rule_set": self.rules_engine.remote_rule_sets,
            "final": "auto",
            "auto_detect_interface": True,
        }

    def _node_to_outbound(self, node: VpnNode) -> dict[str, Any]:
        if node.protocol == Protocol.VLESS:
            return self._vless_outbound(node)
        if node.protocol == Protocol.SHADOWSOCKS:
            return self._shadowsocks_outbound(node)
        if node.protocol == Protocol.WIREGUARD:
            return self._wireguard_outbound(node)
        if node.protocol == Protocol.HYSTERIA2:
            return self._hysteria2_outbound(node)
        raise ValueError(f"unsupported protocol: {node.protocol}")

    def _vless_outbound(self, node: VpnNode) -> dict[str, Any]:
        if not isinstance(node.options, VlessOptions):
            raise ValueError(f"node {node.id} requires VLESS options")

        outbound: dict[str, Any] = {
            "type": "vless",
            "tag": node.tag,
            "server": node.host,
            "server_port": node.port,
            "uuid": node.options.uuid,
            "packet_encoding": "xudp",
            "tls": {
                "enabled": True,
                "server_name": node.options.server_name,
                "alpn": ["h2", "http/1.1"],
            },
        }
        if node.options.flow:
            outbound["flow"] = node.options.flow
        if node.options.transport:
            outbound["transport"] = node.options.transport
        if node.options.reality:
            outbound["tls"]["reality"] = node.options.reality
        return outbound

    def _shadowsocks_outbound(self, node: VpnNode) -> dict[str, Any]:
        if not isinstance(node.options, ShadowsocksOptions):
            raise ValueError(f"node {node.id} requires Shadowsocks options")
        return {
            "type": "shadowsocks",
            "tag": node.tag,
            "server": node.host,
            "server_port": node.port,
            "method": node.options.method,
            "password": node.options.password,
        }

    def _wireguard_outbound(self, node: VpnNode) -> dict[str, Any]:
        if not isinstance(node.options, WireGuardOptions):
            raise ValueError(f"node {node.id} requires WireGuard options")
        outbound: dict[str, Any] = {
            "type": "wireguard",
            "tag": node.tag,
            "server": node.host,
            "server_port": node.port,
            "private_key": node.options.private_key,
            "peer_public_key": node.options.peer_public_key,
            "local_address": node.options.local_address,
            "mtu": node.options.mtu,
        }
        if node.options.reserved:
            outbound["reserved"] = node.options.reserved
        return outbound

    def _hysteria2_outbound(self, node: VpnNode) -> dict[str, Any]:
        if not isinstance(node.options, Hysteria2Options):
            raise ValueError(f"node {node.id} requires Hysteria2 options")
        return {
            "type": "hysteria2",
            "tag": node.tag,
            "server": node.host,
            "server_port": node.port,
            "password": node.options.password,
            "tls": {"enabled": True, "server_name": node.options.server_name},
        }
