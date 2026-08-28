from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.domain.models import (
    AdminAuditEvent,
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
        self.assertTrue(subscription.original_transaction_id.startswith("sandbox:sha256:"))
        self.assertNotIn("demo", subscription.original_transaction_id)
        self.assertGreaterEqual(len(self.repo.list_nodes()), 3)

    def test_persists_yookassa_subscription(self) -> None:
        subscription = self.repo.activate_subscription(
            ReceiptClaim(platform=Platform.YOOKASSA, receipt="yk-payment-1", device_id="device-1")
        )

        self.assertIsNotNone(self.repo.get_active_subscription(subscription.user_id))
        self.assertTrue(subscription.original_transaction_id.startswith("yookassa:sha256:"))

    def test_persists_and_extends_commercial_subscription(self) -> None:
        created = self.repo.create_commercial_subscription("token-1", "vpn.1m", payment_id="payment-1")
        first = self.repo.activate_commercial_subscription("token-1", 30)
        second = self.repo.activate_commercial_subscription("token-1", 30, payment_id="payment-2")

        reloaded = self.repo.get_commercial_subscription("token-1")
        self.assertEqual(created.status, "pending")
        self.assertTrue(first.is_active())
        self.assertTrue(second.expires_at > first.expires_at + timedelta(days=29))
        self.assertEqual(reloaded.payment_id, "payment-2")
        self.assertIsNone(self.repo.activate_commercial_subscription("missing-token", 30))

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
        self.assertEqual(self.repo.count_node_health_events_by_result(), {"success": 0, "failure": 1})

    def test_prunes_old_node_health_events(self) -> None:
        old_event = NodeHealthEvent(
            id=new_id("nhe"),
            node_id="node_eu_1",
            checked_at=datetime.now(timezone.utc) - timedelta(days=10),
            old_health=None,
            new_health=NodeHealth.DEGRADED,
            old_status=None,
            new_status=NodeStatus.ACTIVE,
            old_success_rate=None,
            new_success_rate=0.3,
            old_latency_ms=None,
            new_latency_ms=None,
            health_score=15,
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
            new_latency_ms=22,
            health_score=95,
            error=None,
        )

        self.repo.add_node_health_event(old_event)
        self.repo.add_node_health_event(new_event)
        deleted = self.repo.prune_node_health_events(datetime.now(timezone.utc) - timedelta(days=1))

        events = self.repo.list_node_health_events("node_eu_1", limit=10)
        self.assertEqual(deleted, 1)
        self.assertEqual([event.id for event in events], [new_event.id])

    def test_persists_admin_audit_events(self) -> None:
        event = AdminAuditEvent(
            id=new_id("aae"),
            occurred_at=datetime.now(timezone.utc),
            action="node.health.update",
            target_type="node",
            target_id="node_eu_1",
            result="success",
            details={"health_score": 90},
        )

        self.repo.add_admin_audit_event(event)
        events = self.repo.list_admin_audit_events()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].id, event.id)
        self.assertEqual(events[0].details, {"health_score": 90})
        self.assertEqual(self.repo.count_admin_audit_events(), 1)

    def test_prunes_old_admin_audit_events(self) -> None:
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

        self.repo.add_admin_audit_event(old_event)
        self.repo.add_admin_audit_event(new_event)
        deleted = self.repo.prune_admin_audit_events(datetime.now(timezone.utc) - timedelta(days=1))

        events = self.repo.list_admin_audit_events()
        self.assertEqual(deleted, 1)
        self.assertEqual([event.id for event in events], [new_event.id])


class SqliteConcurrencyTest(unittest.TestCase):
    """Regression guard: ThreadingHTTPServer runs every request on its own
    thread. A single sqlite3.Connection shared across threads (even with
    check_same_thread=False) intermittently raised "sqlite3.InterfaceError:
    bad parameter or other API misuse" under real concurrent traffic in
    production. Hammering the repository from many threads at once should
    no longer raise anything."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = SqliteRepository(Path(self.tempdir.name) / "test.db")

    def tearDown(self) -> None:
        self.repo.close()
        self.tempdir.cleanup()

    def test_concurrent_reads_and_writes_do_not_raise(self) -> None:
        import threading

        errors: list[BaseException] = []

        def worker(i: int) -> None:
            try:
                token = f"tok-{i}"
                self.repo.create_commercial_subscription(token, "vpn.1m")
                for _ in range(20):
                    self.repo.get_commercial_subscription(token)
            except BaseException as exc:  # noqa: BLE001 - captured for the assertion below
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])

    def test_each_thread_gets_its_own_connection(self) -> None:
        import threading

        connections: list[int] = []
        lock = threading.Lock()

        def worker() -> None:
            conn_id = id(self.repo.connection)
            with lock:
                connections.append(conn_id)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(set(connections)), 5)


if __name__ == "__main__":
    unittest.main()
