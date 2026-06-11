from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.domain.health_checker import ProbeResult
from app.domain.models import NodeStatus
from app.repositories.memory import InMemoryRepository
from app.services.health_worker import HealthCheckWorker


class FakeProbe:
    def __init__(self, ok: bool, latency_ms: int | None = 42) -> None:
        self.ok = ok
        self.latency_ms = latency_ms

    def check(self, node):  # type: ignore[no-untyped-def]
        return ProbeResult(
            ok=self.ok,
            latency_ms=self.latency_ms if self.ok else None,
            checked_at=datetime.now(timezone.utc),
            error=None if self.ok else "failed",
        )


class HealthCheckWorkerTest(unittest.TestCase):
    def test_updates_enabled_nodes_and_skips_disabled_by_default(self) -> None:
        repo = InMemoryRepository()
        summary = HealthCheckWorker(repo, probe=FakeProbe(ok=True, latency_ms=33)).run_once()

        self.assertEqual(summary.checked, 3)
        self.assertEqual(summary.updated, 3)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.failures, 0)
        self.assertEqual(repo.get_node("node_eu_1").latency_ms, 33)  # type: ignore[union-attr]
        events = repo.list_node_health_events("node_eu_1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].new_latency_ms, 33)
        self.assertIsNone(events[0].error)

    def test_failed_probe_updates_failure_counts(self) -> None:
        repo = InMemoryRepository()
        summary = HealthCheckWorker(repo, probe=FakeProbe(ok=False)).run_once()

        self.assertEqual(summary.failures, 3)
        self.assertEqual(summary.updated, 3)
        self.assertLess(repo.get_node("node_eu_1").success_rate, 0.99)  # type: ignore[union-attr]
        self.assertEqual(repo.list_node_health_events("node_eu_1")[0].error, "failed")

    def test_can_include_disabled_nodes(self) -> None:
        repo = InMemoryRepository()
        summary = HealthCheckWorker(repo, probe=FakeProbe(ok=True, latency_ms=11)).run_once(include_disabled=True)

        self.assertEqual(summary.checked, 4)
        self.assertEqual(summary.skipped, 0)
        self.assertIsNotNone(repo.get_node("node_bad_1").last_check_at)
        self.assertEqual(repo.get_node("node_bad_1").status, NodeStatus.DISABLED)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
