from __future__ import annotations

import json
import unittest
from http import HTTPStatus
from typing import Any

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService


class ApiServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ApiService(
            InMemoryRepository(),
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
        )

    def test_receipt_to_config_flow(self) -> None:
        receipt_response = self.service.auth_receipt(
            {"platform": "sandbox", "receipt": "demo", "device_id": "device-1"},
        )
        token = receipt_response["access_token"]
        user_id = self.service.user_id_from_authorization(f"Bearer {token}")

        config = self.service.config(user_id)

        self.assertEqual(config["route"]["final"], "auto")
        outbound_tags = {outbound["tag"] for outbound in config["outbounds"]}
        self.assertIn("auto", outbound_tags)
        self.assertNotIn("vless-disabled", outbound_tags)

    def test_config_requires_token(self) -> None:
        with self.assertRaises(ApiError) as context:
            self.service.user_id_from_authorization("")

        self.assertEqual(context.exception.status, HTTPStatus.UNAUTHORIZED)

    def test_config_rejects_user_without_subscription(self) -> None:
        init_response = self.service.auth_init({"device_id": "device-2"})
        with self.assertRaises(ApiError) as context:
            self.service.config(init_response["user_id"])

        self.assertEqual(context.exception.status, HTTPStatus.FORBIDDEN)

    def test_admin_can_disable_node_and_remove_it_from_config(self) -> None:
        receipt_response = self.service.auth_receipt(
            {"platform": "sandbox", "receipt": "demo", "device_id": "device-1"},
        )
        user_id = self.service.user_id_from_authorization(f"Bearer {receipt_response['access_token']}")

        update = self.service.admin_update_node_health(
            "test-admin",
            "node_eu_1",
            {"health_score": 0, "status": "disabled"},
        )
        config = self.service.config(user_id)
        outbound_tags = {outbound["tag"] for outbound in config["outbounds"]}

        self.assertEqual(update["node"]["status"], "disabled")
        self.assertFalse(update["node"]["usable"])
        self.assertNotIn("vless-eu-1", outbound_tags)

    def test_admin_health_update_accepts_latency_success_rate_and_health(self) -> None:
        receipt_response = self.service.auth_receipt(
            {"platform": "sandbox", "receipt": "demo", "device_id": "device-1"},
        )
        user_id = self.service.user_id_from_authorization(f"Bearer {receipt_response['access_token']}")

        update = self.service.admin_update_node_health(
            "test-admin",
            "node_eu_1",
            {"health_score": 80, "latency_ms": 230, "success_rate": 0.91, "health": "degraded"},
        )
        config = self.service.config(user_id)
        outbound_tags = {outbound["tag"] for outbound in config["outbounds"]}

        self.assertEqual(update["node"]["latency_ms"], 230)
        self.assertEqual(update["node"]["success_rate"], 0.91)
        self.assertEqual(update["node"]["health"], "degraded")
        self.assertFalse(update["node"]["usable"])
        self.assertNotIn("vless-eu-1", outbound_tags)

    def test_admin_token_is_required(self) -> None:
        with self.assertRaises(ApiError) as context:
            self.service.admin_nodes("wrong")

        self.assertEqual(context.exception.status, HTTPStatus.UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
