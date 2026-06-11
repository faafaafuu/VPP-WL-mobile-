from __future__ import annotations

from app.domain.models import VpnNode


def choose_preferred_nodes(nodes: list[VpnNode], limit: int = 8) -> list[VpnNode]:
    usable_nodes = [node for node in nodes if node.is_usable()]
    return sorted(
        usable_nodes,
        key=lambda node: (node.priority, -node.health_score, -node.weight, node.region, node.tag),
    )[:limit]

