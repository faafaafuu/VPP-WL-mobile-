from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import (
    NodeHealth,
    NodeHealthEvent,
    NodeStatus,
    Platform,
    Protocol,
    ReceiptClaim,
    VlessOptions,
    VpnNode,
    new_id,
)
from app.repositories.sqlite import SqliteRepository


class SqliteRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = SqliteRepository(Path(self.tempdir.name) / "test.db")

    def tearDown(self) -> None:
        self.repo.close()
        self.tempdir.cleanup()

    def test_persists_user_subscription_and_seeded_nodes(self) -> None:
        subscription = self.repo.activate_subscription(
            ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-1")
        )

        self.assertIsNotNone(self.repo.get_user(subscription.user_id))
        self.assertIsNotNone(self.repo.get_active_subscription(subscription.user_id))
        self.assertGreaterEqual(len(self.repo.list_nodes()), 3)

    def test_exports_and_deletes_user_data(self) -> None:
        subscription = self.repo.activate_subscription(
            ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-1")
        )

        exported = self.repo.export_user_data(subscription.user_id)
        deleted = self.repo.delete_user(subscription.user_id)

        self.assertEqual(exported["user"]["device_id"], "device-1")
        self.assertEqual(exported["subscription"]["product_id"], "vpn.monthly")
        self.assertTrue(deleted)
        self.assertIsNone(self.repo.get_user(subscription.user_id))
        self.assertIsNone(self.repo.get_active_subscription(subscription.user_id))

    def test_upserts_node_options(self) -> None:
        self.repo.upsert_node(
            VpnNode(
                id="node-test",
                tag="node-test",
                region="eu-test",
                provider="test",
                country_code="DE",
                host="node.example.com",
                port=443,
                protocol=Protocol.VLESS,
                status=NodeStatus.ACTIVE,
                priority=1,
                health_score=99,
                options=VlessOptions(
                    uuid="00000000-0000-4000-8000-000000000099",
                    server_name="cdn.example.com",
                    transport={"type": "ws", "path": "/ws"},
                ),
            )
        )

        node = next(item for item in self.repo.list_nodes() if item.id == "node-test")
        self.assertIsInstance(node.options, VlessOptions)
        self.assertEqual(node.options.transport, {"type": "ws", "path": "/ws"})

    def test_updates_node_health(self) -> None:
        updated = self.repo.update_node_health(
            "node_eu_1",
            health_score=10,
            status=NodeStatus.DISABLED,
            latency_ms=500,
            success_rate=0.2,
            health=NodeHealth.DISABLED,
        )
        reloaded = self.repo.get_node("node_eu_1")

        self.assertIsNotNone(updated)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.health_score, 10)
        self.assertEqual(reloaded.status, NodeStatus.DISABLED)
        self.assertEqual(reloaded.latency_ms, 500)
        self.assertEqual(reloaded.success_rate, 0.2)
        self.assertEqual(reloaded.health, NodeHealth.DISABLED)

    def test_persists_node_health_events(self) -> None:
        event = NodeHealthEvent(
            id=new_id("nhe"),
            node_id="node_eu_1",
            checked_at=datetime.now(timezone.utc),
            old_health=NodeHealth.HEALTHY,
            new_health=NodeHealth.DEGRADED,
            old_status=NodeStatus.ACTIVE,
            new_status=NodeStatus.ACTIVE,
            old_success_rate=0.99,
            new_success_rate=0.44,
            old_latency_ms=55,
            new_latency_ms=300,
            health_score=42,
            error="timeout",
        )

        self.repo.add_node_health_event(event)
        events = self.repo.list_node_health_events("node_eu_1")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].id, event.id)
        self.assertEqual(events[0].new_health, NodeHealth.DEGRADED)
        self.assertEqual(events[0].error, "timeout")


if __name__ == "__main__":
    unittest.main()
