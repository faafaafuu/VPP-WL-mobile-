from __future__ import annotations

import unittest

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService
from app.services.yookassa import YooKassaError, YooKassaPayment


class FakeYooKassaProvider:
    def __init__(self) -> None:
        self.payments: dict[str, dict[str, object]] = {}

    def create_payment(self, device_id: str, product_id: str) -> YooKassaPayment:
        payment_id = "yk-payment-1"
        self.payments[payment_id] = {
            "id": payment_id,
            "status": "pending",
            "paid": False,
            "metadata": {"device_id": device_id, "product_id": product_id},
        }
        return YooKassaPayment(
            id=payment_id,
            status="pending",
            paid=False,
            confirmation_url="https://yookassa.example/confirm",
        )

    def fetch_payment(self, payment_id: str) -> dict[str, object]:
        try:
            return self.payments[payment_id]
        except KeyError as exc:
            raise YooKassaError("payment not found") from exc


class YooKassaPaymentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = FakeYooKassaProvider()
        self.service = ApiService(
            InMemoryRepository(),
            TokenService("test-secret-with-length"),
            ConfigBuilder(),
            admin_token="test-admin",
            yookassa_provider=self.provider,
        )

    def test_create_yookassa_payment_returns_confirmation_url_without_token(self) -> None:
        payment = self.service.create_yookassa_payment({"device_id": "device-1", "product_id": "vpn.monthly"})

        self.assertEqual(payment["provider"], "yookassa")
        self.assertEqual(payment["payment_id"], "yk-payment-1")
        self.assertEqual(payment["confirmation_url"], "https://yookassa.example/confirm")
        self.assertNotIn("access_token", payment)

    def test_yookassa_receipt_activates_subscription_after_provider_status_check(self) -> None:
        self.service.create_yookassa_payment({"device_id": "device-1", "product_id": "vpn.monthly"})
        self.provider.payments["yk-payment-1"]["status"] = "succeeded"
        self.provider.payments["yk-payment-1"]["paid"] = True

        response = self.service.auth_receipt(
            {
                "platform": "yookassa",
                "receipt": "yk-payment-1",
                "device_id": "device-1",
                "product_id": "vpn.monthly",
            }
        )
        user_id = self.service.user_id_from_authorization(f"Bearer {response['access_token']}")

        self.assertEqual(response["token_type"], "Bearer")
        self.assertIsNotNone(self.service.me(user_id)["subscription"])

    def test_yookassa_receipt_rejects_unpaid_payment(self) -> None:
        self.service.create_yookassa_payment({"device_id": "device-1", "product_id": "vpn.monthly"})

        with self.assertRaises(ApiError) as context:
            self.service.auth_receipt(
                {
                    "platform": "yookassa",
                    "receipt": "yk-payment-1",
                    "device_id": "device-1",
                    "product_id": "vpn.monthly",
                }
            )

        self.assertIn("not paid", context.exception.payload["error"])

    def test_yookassa_webhook_activates_without_returning_access_token(self) -> None:
        self.service.create_yookassa_payment({"device_id": "device-1", "product_id": "vpn.monthly"})
        self.provider.payments["yk-payment-1"]["status"] = "succeeded"
        self.provider.payments["yk-payment-1"]["paid"] = True

        response = self.service.yookassa_webhook(
            {
                "type": "notification",
                "event": "payment.succeeded",
                "object": {"id": "yk-payment-1", "status": "succeeded", "paid": True},
            }
        )

        self.assertEqual(response["status"], "activated")
        self.assertIn("user_id", response)
        self.assertNotIn("access_token", response)


if __name__ == "__main__":
    unittest.main()
