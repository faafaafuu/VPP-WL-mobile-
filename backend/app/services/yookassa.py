from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import request


class YooKassaError(ValueError):
    pass


@dataclass(frozen=True)
class YooKassaConfig:
    shop_id: str
    secret_key: str
    return_url: str
    product_prices_rub: dict[str, str]

    @property
    def is_configured(self) -> bool:
        return bool(self.shop_id and self.secret_key and self.return_url)


@dataclass(frozen=True)
class YooKassaPayment:
    id: str
    status: str
    paid: bool
    confirmation_url: str | None


class YooKassaProvider(Protocol):
    def create_payment(self, device_id: str, product_id: str) -> YooKassaPayment:
        ...

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        ...


class DisabledYooKassaProvider:
    def create_payment(self, device_id: str, product_id: str) -> YooKassaPayment:
        raise YooKassaError("yookassa is not configured")

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        raise YooKassaError("yookassa is not configured")


class HttpYooKassaProvider:
    base_url = "https://api.yookassa.ru/v3"

    def __init__(self, config: YooKassaConfig) -> None:
        self.config = config

    def create_payment(self, device_id: str, product_id: str) -> YooKassaPayment:
        amount = self.config.product_prices_rub.get(product_id)
        if amount is None:
            raise YooKassaError("unknown product_id")
        payload = {
            "amount": {"value": amount, "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": self.config.return_url},
            "description": f"VPN Router subscription {product_id}",
            "metadata": {"device_id": device_id, "product_id": product_id},
        }
        response = self._send_json("POST", "/payments", payload, idempotence_key=str(uuid.uuid4()))
        return _payment_from_payload(response)

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        if not payment_id.strip():
            raise YooKassaError("payment_id is required")
        return self._send_json("GET", f"/payments/{payment_id}", None)

    def _send_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        idempotence_key: str | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        http_request = request.Request(f"{self.base_url}{path}", data=body, method=method)
        http_request.add_header("Authorization", _basic_auth(self.config.shop_id, self.config.secret_key))
        http_request.add_header("Accept", "application/json")
        if payload is not None:
            http_request.add_header("Content-Type", "application/json")
        if idempotence_key is not None:
            http_request.add_header("Idempotence-Key", idempotence_key)
        with request.urlopen(http_request, timeout=20) as response:
            response_body = response.read().decode("utf-8")
        decoded = json.loads(response_body or "{}")
        if not isinstance(decoded, dict):
            raise YooKassaError("unexpected yookassa response")
        return decoded


def _basic_auth(shop_id: str, secret_key: str) -> str:
    token = base64.b64encode(f"{shop_id}:{secret_key}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _payment_from_payload(payload: dict[str, Any]) -> YooKassaPayment:
    confirmation = payload.get("confirmation")
    confirmation_url = confirmation.get("confirmation_url") if isinstance(confirmation, dict) else None
    return YooKassaPayment(
        id=str(payload.get("id", "")),
        status=str(payload.get("status", "")),
        paid=bool(payload.get("paid", False)),
        confirmation_url=str(confirmation_url) if confirmation_url else None,
    )
