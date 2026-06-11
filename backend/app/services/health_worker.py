from __future__ import annotations

from dataclasses import dataclass

from app.domain.health_checker import HealthUpdate, NodeHealthEvaluator, TcpNodeProbe
from app.domain.models import NodeHealthEvent, NodeStatus, new_id
from app.repositories.factory import Repository


@dataclass(frozen=True)
class HealthCheckSummary:
    checked: int
    updated: int
    skipped: int
    failures: int
    updates: list[HealthUpdate]


class HealthCheckWorker:
    def __init__(
        self,
        repository: Repository,
        probe: TcpNodeProbe | None = None,
        evaluator: NodeHealthEvaluator | None = None,
    ) -> None:
        self.repository = repository
        self.probe = probe or TcpNodeProbe()
        self.evaluator = evaluator or NodeHealthEvaluator()

    def run_once(self, include_disabled: bool = False) -> HealthCheckSummary:
        checked = 0
        updated = 0
        skipped = 0
        failures = 0
        updates: list[HealthUpdate] = []

        for node in self.repository.list_nodes():
            if not include_disabled and node.status == NodeStatus.DISABLED:
                skipped += 1
                continue

            checked += 1
            probe_result = self.probe.check(node)
            health_update = self.evaluator.evaluate(node, probe_result)
            updates.append(health_update)
            if not probe_result.ok:
                failures += 1
            saved = self.repository.update_node_health(
                node.id,
                health_score=health_update.health_score,
                status=health_update.status,
                latency_ms=health_update.latency_ms,
                success_rate=health_update.success_rate,
                health=health_update.health,
                last_check_at=health_update.last_check_at,
            )
            if saved is not None:
                self.repository.add_node_health_event(
                    NodeHealthEvent(
                        id=new_id("nhe"),
                        node_id=node.id,
                        checked_at=health_update.last_check_at,
                        old_health=node.health,
                        new_health=health_update.health,
                        old_status=node.status,
                        new_status=health_update.status or node.status,
                        old_success_rate=node.success_rate,
                        new_success_rate=health_update.success_rate,
                        old_latency_ms=node.latency_ms,
                        new_latency_ms=health_update.latency_ms,
                        health_score=health_update.health_score,
                        error=health_update.error,
                    )
                )
                updated += 1

        return HealthCheckSummary(
            checked=checked,
            updated=updated,
            skipped=skipped,
            failures=failures,
            updates=updates,
        )
