from __future__ import annotations

from app.domain.node_scoring import sort_nodes_by_score
from app.domain.models import VpnNode


def choose_preferred_nodes(nodes: list[VpnNode], limit: int = 8) -> list[VpnNode]:
    return sort_nodes_by_score(nodes)[:limit]
