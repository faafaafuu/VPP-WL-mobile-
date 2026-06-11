from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.domain.models import NodeHealth, NodeStatus, Platform, Protocol, ReceiptClaim, VlessOptions, VpnNode
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


if __name__ == "__main__":
    unittest.main()
