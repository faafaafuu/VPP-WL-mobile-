from __future__ import annotations

import json
import unittest
from pathlib import Path


MONITORING_ROOT = Path("../deploy/monitoring")


class MonitoringAssetsTest(unittest.TestCase):
    def test_prometheus_config_uses_blackbox_probe_jobs(self) -> None:
        config = (MONITORING_ROOT / "prometheus.yml").read_text(encoding="utf-8")

        self.assertIn("vpn-router-api", config)
        self.assertIn("vpn-router-api-metrics", config)
        self.assertIn("vpn-router-nodes", config)
        self.assertIn("/metrics", config)
        self.assertIn("blackbox-exporter:9115", config)
        self.assertIn("vpn-router-alerts.yml", config)

    def test_alert_rules_cover_api_node_down_and_latency(self) -> None:
        alerts = (MONITORING_ROOT / "vpn-router-alerts.yml").read_text(encoding="utf-8")

        self.assertIn("VpnRouterApiDown", alerts)
        self.assertIn("VpnRouterNodeDown", alerts)
        self.assertIn("VpnRouterNodeHighLatency", alerts)
        self.assertIn("probe_success", alerts)
        self.assertIn("probe_duration_seconds", alerts)

    def test_grafana_dashboard_is_valid_json_for_probe_metrics(self) -> None:
        dashboard = json.loads((MONITORING_ROOT / "grafana-dashboard.json").read_text(encoding="utf-8"))

        self.assertEqual(dashboard["title"], "VPN Router Operations")
        self.assertIn("panels", dashboard)
        serialized = json.dumps(dashboard)
        self.assertIn("vpn_router_usable_nodes", serialized)
        self.assertIn("vpn_router_node_health_events_retained", serialized)
        self.assertIn("vpn_router_admin_audit_events_retained", serialized)
        self.assertIn("probe_success", serialized)
        self.assertIn("probe_duration_seconds", serialized)


if __name__ == "__main__":
    unittest.main()
