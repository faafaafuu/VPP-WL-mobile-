from __future__ import annotations

import unittest

from datetime import datetime, timedelta, timezone

from app.domain.models import NodeHealth, NodeHealthEvent, NodeStatus, Platform, ReceiptClaim, new_id
from app.domain.models import AdminAuditEvent
from app.repositories.memory import InMemoryRepository


class InMemoryRepositoryTest(unittest.TestCase):
    def test_sandbox_receipt_activates_subscription(self) -> None:
        repo = InMemoryRepository()
        subscription = repo.activate_subscription(
            ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-1")
        )

        self.assertIsNotNone(repo.get_user(subscription.user_id))
        self.assertIsNotNone(repo.get_active_subscription(subscription.user_id))
        self.assertTrue(subscription.original_transaction_id.startswith("sandbox:sha256:"))
        self.assertNotIn("demo", subscription.original_transaction_id)

    def test_sandbox_receipt_fingerprint_is_deterministic(self) -> None:
        first_repo = InMemoryRepository()
        second_repo = InMemoryRepository()

        first = first_repo.activate_subscription(
            ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-1")
        )
        second = second_repo.activate_subscription(
            ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-2")
        )

        self.assertEqual(first.original_transaction_id, second.original_transaction_id)

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

    def test_prunes_old_node_health_events(self) -> None:
        repo = InMemoryRepository()
        old_event = NodeHealthEvent(
            id=new_id("nhe"),
            node_id="node_eu_1",
            checked_at=datetime.now(timezone.utc) - timedelta(days=10),
            old_health=None,
            new_health=NodeHealth.DEGRADED,
            old_status=None,
            new_status=NodeStatus.ACTIVE,
            old_success_rate=None,
            new_success_rate=0.4,
            old_latency_ms=None,
            new_latency_ms=None,
            health_score=20,
            error="old",
        )
        new_event = NodeHealthEvent(
            id=new_id("nhe"),
            node_id="node_eu_1",
            checked_at=datetime.now(timezone.utc),
            old_health=None,
            new_health=NodeHealth.HEALTHY,
            old_status=None,
            new_status=NodeStatus.ACTIVE,
            old_success_rate=None,
            new_success_rate=0.99,
            old_latency_ms=None,
            new_latency_ms=33,
            health_score=99,
            error=None,
        )

        repo.add_node_health_event(old_event)
        repo.add_node_health_event(new_event)
        deleted = repo.prune_node_health_events(datetime.now(timezone.utc) - timedelta(days=1))

        events = repo.list_node_health_events("node_eu_1", limit=10)
        self.assertEqual(deleted, 1)
        self.assertEqual([event.id for event in events], [new_event.id])

    def test_stores_admin_audit_events(self) -> None:
        repo = InMemoryRepository()
        event = AdminAuditEvent(
            id=new_id("aae"),
            occurred_at=datetime.now(timezone.utc),
            action="node.health.update",
            target_type="node",
            target_id="node_eu_1",
            result="success",
            details={"health_score": 90},
        )

        repo.add_admin_audit_event(event)

        self.assertEqual(repo.list_admin_audit_events(), [event])

    def test_prunes_old_admin_audit_events(self) -> None:
        repo = InMemoryRepository()
        old_event = AdminAuditEvent(
            id=new_id("aae"),
            occurred_at=datetime.now(timezone.utc) - timedelta(days=10),
            action="node.health.update",
            target_type="node",
            target_id="node_eu_1",
            result="success",
            details={"health_score": 10},
        )
        new_event = AdminAuditEvent(
            id=new_id("aae"),
            occurred_at=datetime.now(timezone.utc),
            action="node.health.update",
            target_type="node",
            target_id="node_eu_2",
            result="success",
            details={"health_score": 90},
        )

        repo.add_admin_audit_event(old_event)
        repo.add_admin_audit_event(new_event)
        deleted = repo.prune_admin_audit_events(datetime.now(timezone.utc) - timedelta(days=1))

        self.assertEqual(deleted, 1)
        self.assertEqual(repo.list_admin_audit_events(), [new_event])


if __name__ == "__main__":
    unittest.main()
