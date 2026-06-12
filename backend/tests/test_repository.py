from __future__ import annotations

import unittest

from datetime import datetime, timezone

from app.domain.models import NodeHealth, NodeHealthEvent, NodeStatus, Platform, ReceiptClaim, new_id
from app.repositories.memory import InMemoryRepository


class InMemoryRepositoryTest(unittest.TestCase):
    def test_sandbox_receipt_activates_subscription(self) -> None:
        repo = InMemoryRepository()
        subscription = repo.activate_subscription(
            ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-1")
        )

        self.assertIsNotNone(repo.get_user(subscription.user_id))
        self.assertIsNotNone(repo.get_active_subscription(subscription.user_id))

    def test_exports_and_deletes_user_data(self) -> None:
        repo = InMemoryRepository()
        subscription = repo.activate_subscription(
            ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-1")
        )

        exported = repo.export_user_data(subscription.user_id)
        deleted = repo.delete_user(subscription.user_id)

        self.assertEqual(exported["user"]["device_id"], "device-1")
        self.assertEqual(exported["subscription"]["product_id"], "vpn.monthly")
        self.assertTrue(deleted)
        self.assertIsNone(repo.get_user(subscription.user_id))
        self.assertIsNone(repo.get_active_subscription(subscription.user_id))

    def test_short_production_receipt_is_rejected(self) -> None:
        repo = InMemoryRepository()
        with self.assertRaises(ValueError):
            repo.activate_subscription(ReceiptClaim(platform=Platform.APPLE, receipt="short", device_id="device-1"))

    def test_updates_node_health(self) -> None:
        repo = InMemoryRepository()

        node = repo.update_node_health("node_eu_1", health_score=35, status=NodeStatus.DRAINING)

        self.assertIsNotNone(node)
        self.assertEqual(node.health_score, 35)
        self.assertEqual(node.status, NodeStatus.DRAINING)

    def test_stores_node_health_events(self) -> None:
        repo = InMemoryRepository()
        event = NodeHealthEvent(
            id=new_id("nhe"),
            node_id="node_eu_1",
            checked_at=datetime.now(timezone.utc),
            old_health=NodeHealth.HEALTHY,
            new_health=NodeHealth.DEGRADED,
            old_status=NodeStatus.ACTIVE,
            new_status=NodeStatus.ACTIVE,
            old_success_rate=0.99,
            new_success_rate=0.5,
            old_latency_ms=50,
            new_latency_ms=500,
            health_score=30,
            error="timeout",
        )

        repo.add_node_health_event(event)

        self.assertEqual(repo.list_node_health_events("node_eu_1"), [event])


if __name__ == "__main__":
    unittest.main()
