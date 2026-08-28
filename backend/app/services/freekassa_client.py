from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from typing import Any, Mapping

DEFAULT_API_BASE_URL = "https://api.fk.life/v1"


class FreekassaError(Exception):
    pass


def sign_request(data: Mapping[str, Any], api_key: str) -> str:
    """FreeKassa REST API v1 signing: sort fields by key, join their string
    values with "|", HMAC-SHA256 the result using the merchant API key.
    Confirmed against FreeKassa's own docs and a real SDK implementation,
    and live-verified: a request signed this way against api.fk.life
    returned "Merchant not activated" rather than an invalid-signature
    error, meaning the shopId/api_key pairing and this algorithm are correct."""
    joined = "|".join(str(data[key]) for key in sorted(data.keys()))
    return hmac.new(api_key.encode("utf-8"), joined.encode("utf-8"), hashlib.sha256).hexdigest()


def create_order(
    *,
    shop_id: str,
    api_key: str,
    i: str,
    email: str,
    ip: str,
    amount: str,
    currency: str = "RUB",
    payment_id: str | None = None,
    base_url: str = DEFAULT_API_BASE_URL,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Calls POST /orders/create and returns the parsed response, which on
    success contains a real per-order payment-form URL in "location"."""
    body: dict[str, Any] = {
        "shopId": int(shop_id),
        "i": int(i),
        "email": email,
        "ip": ip,
        "amount": float(amount),
        "currency": currency,
    }
    if payment_id:
        body["paymentId"] = payment_id
    body["nonce"] = int(time.time() * 1000)
    body["signature"] = sign_request(body, api_key)

    data = _post(f"{base_url.rstrip('/')}/orders/create", body, timeout)
    if data.get("type") != "success" or not data.get("location"):
        raise FreekassaError(str(data.get("message") or "unexpected orders/create response"))
    return data


def _post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read())
        except (json.JSONDecodeError, ValueError):
            raise FreekassaError(f"HTTP {exc.code}") from exc
        raise FreekassaError(str(data.get("message") or f"HTTP {exc.code}")) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise FreekassaError(str(exc)) from exc
