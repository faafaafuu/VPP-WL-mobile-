from __future__ import annotations

from app.domain.models import NodeHealth, NodeStatus, VpnNode


def node_score(node: VpnNode) -> float:
    if node.status == NodeStatus.DISABLED or node.health != NodeHealth.HEALTHY:
        return 0.0
    if node.success_rate < 0.75:
        return 0.0

    latency_penalty = min(node.latency_ms or 0, 1000) / 10
    priority_penalty = node.priority / 5
    score = (node.health_score * 0.55) + (node.success_rate * 100 * 0.35) + (node.weight * 0.10)
    return max(0.0, score - latency_penalty - priority_penalty)


def sort_nodes_by_score(nodes: list[VpnNode]) -> list[VpnNode]:
    return sorted(
        [node for node in nodes if node.is_usable()],
        key=lambda node: (-node_score(node), node.priority, node.latency_ms or 10_000, node.tag),
    )
