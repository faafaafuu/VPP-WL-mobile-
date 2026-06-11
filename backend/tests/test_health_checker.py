from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.domain.health_checker import NodeHealthEvaluator, ProbeResult
from app.domain.models import NodeHealth, NodeStatus, Protocol, VlessOptions, VpnNode


class NodeHealthEvaluatorTest(unittest.TestCase):
    def test_success_keeps_node_healthy_and_updates_latency(self) -> None:
        checked_at = datetime.now(timezone.utc)
        update = NodeHealthEvaluator(smoothing=0.5).evaluate(
            _node(success_rate=0.9),
            ProbeResult(ok=True, latency_ms=50, checked_at=checked_at),
        )

        self.assertEqual(update.health, NodeHealth.HEALTHY)
        self.assertEqual(update.latency_ms, 50)
        self.assertGreater(update.success_rate, 0.9)
        self.assertEqual(update.last_check_at, checked_at)

    def test_failure_degrades_node_before_disabling(self) -> None:
        update = NodeHealthEvaluator(smoothing=0.3).evaluate(
            _node(success_rate=0.9, latency_ms=80),
            ProbeResult(ok=False, latency_ms=None, checked_at=datetime.now(timezone.utc), error="timeout"),
        )

        self.assertEqual(update.health, NodeHealth.DEGRADED)
        self.assertEqual(update.latency_ms, 80)
        self.assertLess(update.success_rate, 0.9)
        self.assertEqual(update.error, "timeout")

    def test_repeated_bad_history_disables_node(self) -> None:
        update = NodeHealthEvaluator(smoothing=0.5).evaluate(
            _node(success_rate=0.2, latency_ms=900),
            ProbeResult(ok=False, latency_ms=None, checked_at=datetime.now(timezone.utc), error="timeout"),
        )

        self.assertEqual(update.health, NodeHealth.DISABLED)
        self.assertEqual(update.status, NodeStatus.DISABLED)


def _node(success_rate: float = 1.0, latency_ms: int | None = None) -> VpnNode:
    return VpnNode(
        id="node-1",
        tag="node-1",
        region="eu",
        provider="test",
        country_code="DE",
        host="127.0.0.1",
        port=443,
        protocol=Protocol.VLESS,
        status=NodeStatus.ACTIVE,
        priority=10,
        success_rate=success_rate,
        latency_ms=latency_ms,
        options=VlessOptions(uuid="00000000-0000-4000-8000-000000000001", server_name="cdn.example.com"),
    )


if __name__ == "__main__":
    unittest.main()

