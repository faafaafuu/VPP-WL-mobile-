from __future__ import annotations

import unittest

from app.domain.models import NodeHealth, NodeStatus, Protocol, VlessOptions, VpnNode
from app.domain.node_scoring import node_score
from app.domain.node_selection import choose_preferred_nodes


def node(
    tag: str,
    priority: int,
    health_score: int,
    status: NodeStatus = NodeStatus.ACTIVE,
    health: NodeHealth = NodeHealth.HEALTHY,
    latency_ms: int | None = None,
    success_rate: float = 1.0,
) -> VpnNode:
    return VpnNode(
        id=tag,
        tag=tag,
        region="eu",
        provider="test",
        country_code="DE",
        host=f"{tag}.example.com",
        port=443,
        protocol=Protocol.VLESS,
        status=status,
        priority=priority,
        health_score=health_score,
        health=health,
        latency_ms=latency_ms,
        success_rate=success_rate,
        options=VlessOptions(uuid="00000000-0000-4000-8000-000000000001", server_name="cdn.example.com"),
    )


class NodeSelectionTest(unittest.TestCase):
    def test_sorts_by_score_and_ignores_unusable_nodes(self) -> None:
        selected = choose_preferred_nodes(
            [
                node("low-health", priority=1, health_score=20),
                node("p2", priority=2, health_score=100),
                node("p1-good", priority=1, health_score=90),
                node("disabled", priority=1, health_score=100, status=NodeStatus.DISABLED),
                node("degraded", priority=1, health_score=100, health=NodeHealth.DEGRADED),
            ]
        )

        self.assertEqual([item.tag for item in selected], ["p2", "p1-good"])

    def test_latency_and_success_rate_affect_score(self) -> None:
        fast = node("fast", priority=10, health_score=95, latency_ms=40, success_rate=0.99)
        slow = node("slow", priority=10, health_score=95, latency_ms=400, success_rate=0.99)
        flaky = node("flaky", priority=10, health_score=95, latency_ms=40, success_rate=0.50)

        self.assertGreater(node_score(fast), node_score(slow))
        self.assertEqual(node_score(flaky), 0)


if __name__ == "__main__":
    unittest.main()
