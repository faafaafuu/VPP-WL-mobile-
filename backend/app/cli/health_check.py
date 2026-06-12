from __future__ import annotations

import argparse
import json
import os

from app.repositories.factory import create_repository
from app.services.health_worker import HealthCheckWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one VPN node health-check pass.")
    parser.add_argument("--include-disabled", action="store_true", help="Probe disabled nodes too.")
    args = parser.parse_args()

    repository = create_repository()
    retention_days = _retention_days(parser)
    worker = HealthCheckWorker(repository, retention_days=retention_days)
    summary = worker.run_once(include_disabled=args.include_disabled)
    print(
        json.dumps(
            {
                "checked": summary.checked,
                "updated": summary.updated,
                "skipped": summary.skipped,
                "failures": summary.failures,
                "events_written": summary.updated,
                "events_pruned": summary.pruned_events,
                "updates": [
                    {
                        "node_id": update.node_id,
                        "health_score": update.health_score,
                        "latency_ms": update.latency_ms,
                        "success_rate": update.success_rate,
                        "health": update.health.value,
                        "status": update.status.value if update.status else None,
                        "last_check_at": update.last_check_at.isoformat(),
                        "error": update.error,
                    }
                    for update in summary.updates
                ],
            },
            separators=(",", ":"),
        )
    )


def _retention_days(parser: argparse.ArgumentParser) -> int:
    raw_value = os.getenv("VPN_ROUTER_AUDIT_RETENTION_DAYS", "30")
    try:
        retention_days = int(raw_value)
    except ValueError:
        parser.error("VPN_ROUTER_AUDIT_RETENTION_DAYS must be an integer")
    if retention_days < 0:
        parser.error("VPN_ROUTER_AUDIT_RETENTION_DAYS must be non-negative")
    return retention_days


if __name__ == "__main__":
    main()
