from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.models import NodeHealth, NodeStatus, VpnNode


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    latency_ms: int | None
    checked_at: datetime
    error: str | None = None


@dataclass(frozen=True)
class HealthUpdate:
    node_id: str
    health_score: int
    status: NodeStatus | None
    latency_ms: int | None
    success_rate: float
    health: NodeHealth
    last_check_at: datetime
    error: str | None = None


class TcpNodeProbe:
    def __init__(self, timeout_seconds: float = 3.0) -> None:
        self.timeout_seconds = timeout_seconds

    def check(self, node: VpnNode) -> ProbeResult:
        started = time.monotonic()
        checked_at = datetime.now(timezone.utc)
        try:
            with socket.create_connection((node.host, node.port), timeout=self.timeout_seconds):
                latency_ms = int((time.monotonic() - started) * 1000)
                return ProbeResult(ok=True, latency_ms=max(1, latency_ms), checked_at=checked_at)
        except OSError as exc:
            return ProbeResult(ok=False, latency_ms=None, checked_at=checked_at, error=str(exc))


class NodeHealthEvaluator:
    def __init__(self, smoothing: float = 0.35) -> None:
        if not 0 < smoothing <= 1:
            raise ValueError("smoothing must be in (0, 1]")
        self.smoothing = smoothing

    def evaluate(self, node: VpnNode, probe: ProbeResult) -> HealthUpdate:
        observed_success = 1.0 if probe.ok else 0.0
        success_rate = (node.success_rate * (1 - self.smoothing)) + (observed_success * self.smoothing)
        latency_ms = probe.latency_ms if probe.ok else node.latency_ms
        health_score = self._health_score(success_rate, latency_ms, probe.ok)
        health = self._health(success_rate, health_score, probe.ok)
        status = NodeStatus.DISABLED if health == NodeHealth.DISABLED else node.status
        return HealthUpdate(
            node_id=node.id,
            health_score=health_score,
            status=status,
            latency_ms=latency_ms,
            success_rate=round(success_rate, 4),
            health=health,
            last_check_at=probe.checked_at,
            error=probe.error,
        )

    def _health_score(self, success_rate: float, latency_ms: int | None, ok: bool) -> int:
        latency_penalty = min(latency_ms or 1000, 1000) / 12
        base = success_rate * 100
        if not ok:
            base -= 20
        return max(0, min(100, int(base - latency_penalty)))

    def _health(self, success_rate: float, health_score: int, ok: bool) -> NodeHealth:
        if success_rate < 0.35 or health_score < 20:
            return NodeHealth.DISABLED
        if not ok or success_rate < 0.75 or health_score < 55:
            return NodeHealth.DEGRADED
        return NodeHealth.HEALTHY

