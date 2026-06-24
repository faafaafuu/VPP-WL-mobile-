from __future__ import annotations

from typing import Mapping

from app.domain.models import NodeHealth, NodeStatus, Protocol, VlessOptions, VpnNode


_MAX_NODES = 10


class NodeConfigError(ValueError):
    pass


def parse_nodes_from_env(env: Mapping[str, str]) -> list[VpnNode]:
    """Load VLESS nodes from VPN_NODE_{n}_* env vars. Returns empty list if none configured."""
    nodes: list[VpnNode] = []
    for n in range(1, _MAX_NODES + 1):
        prefix = f"VPN_NODE_{n}_"
        host = env.get(f"{prefix}HOST", "").strip()
        if not host:
            continue

        port_raw = env.get(f"{prefix}PORT", "443").strip()
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise NodeConfigError(f"VPN_NODE_{n}_PORT must be an integer, got {port_raw!r}") from exc
        if not 1 <= port <= 65535:
            raise NodeConfigError(f"VPN_NODE_{n}_PORT must be between 1 and 65535")

        uuid = env.get(f"{prefix}UUID", "").strip()
        if not uuid:
            raise NodeConfigError(f"VPN_NODE_{n}_UUID is required when VPN_NODE_{n}_HOST is set")

        public_key = env.get(f"{prefix}PUBLIC_KEY", "").strip()
        if not public_key:
            raise NodeConfigError(f"VPN_NODE_{n}_PUBLIC_KEY is required when VPN_NODE_{n}_HOST is set")

        short_id = env.get(f"{prefix}SHORT_ID", "").strip()
        if not short_id:
            raise NodeConfigError(f"VPN_NODE_{n}_SHORT_ID is required when VPN_NODE_{n}_HOST is set")

        sni = env.get(f"{prefix}SNI", "").strip()
        if not sni:
            raise NodeConfigError(f"VPN_NODE_{n}_SNI is required when VPN_NODE_{n}_HOST is set")

        flow = env.get(f"{prefix}FLOW", "xtls-rprx-vision").strip() or None
        fingerprint = env.get(f"{prefix}FINGERPRINT", "chrome").strip() or "chrome"
        label = env.get(f"{prefix}LABEL", f"VPN Node {n}").strip() or f"VPN Node {n}"
        region = env.get(f"{prefix}REGION", "unknown").strip() or "unknown"
        country_code = env.get(f"{prefix}COUNTRY_CODE", "XX").strip() or "XX"

        priority_raw = env.get(f"{prefix}PRIORITY", str(n * 10)).strip()
        try:
            priority = int(priority_raw)
        except ValueError as exc:
            raise NodeConfigError(f"VPN_NODE_{n}_PRIORITY must be an integer, got {priority_raw!r}") from exc

        enabled_raw = env.get(f"{prefix}ENABLED", "true").strip().lower()
        if enabled_raw in {"1", "true", "yes", "on"}:
            enabled = True
        elif enabled_raw in {"0", "false", "no", "off"}:
            enabled = False
        else:
            raise NodeConfigError(f"VPN_NODE_{n}_ENABLED must be true or false, got {enabled_raw!r}")

        status = NodeStatus.ACTIVE if enabled else NodeStatus.DISABLED
        health = NodeHealth.HEALTHY if enabled else NodeHealth.DISABLED

        nodes.append(
            VpnNode(
                id=f"node_env_{n}",
                tag=f"vless-env-{n}",
                region=region,
                provider="env",
                country_code=country_code,
                host=host,
                port=port,
                protocol=Protocol.VLESS,
                status=status,
                health=health,
                priority=priority,
                options=VlessOptions(
                    uuid=uuid,
                    server_name=sni,
                    public_key=public_key,
                    short_id=short_id,
                    flow=flow,
                    fingerprint=fingerprint,
                    label=label,
                ),
            )
        )

    return nodes
