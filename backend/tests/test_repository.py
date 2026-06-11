from __future__ import annotations

import unittest

from app.domain.models import Platform, ReceiptClaim
from app.domain.models import NodeStatus
from app.repositories.memory import InMemoryRepository


class InMemoryRepositoryTest(unittest.TestCase):
    def test_sandbox_receipt_activates_subscription(self) -> None:
        repo = InMemoryRepository()
        subscription = repo.activate_subscription(
            ReceiptClaim(platform=Platform.SANDBOX, receipt="demo", device_id="device-1")
        )

        self.assertIsNotNone(repo.get_user(subscription.user_id))
        self.assertIsNotNone(repo.get_active_subscription(subscription.user_id))

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


if __name__ == "__main__":
    unittest.main()
