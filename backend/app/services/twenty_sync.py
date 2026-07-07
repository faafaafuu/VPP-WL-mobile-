from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.domain.models import CommercialSubscription
from app.domain.tariffs import Tariff


class TwentySync:
    """Push paid orders into a self-hosted Twenty CRM as opportunities.

    Best-effort: any API failure is logged and swallowed so that payment
    activation never depends on the CRM being up.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        tariffs_by_id: dict[str, Tariff],
        timeout_seconds: int = 15,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.tariffs_by_id = tariffs_by_id
        self.timeout_seconds = timeout_seconds

    def on_activated(self, subscription: CommercialSubscription) -> bool:
        try:
            payload = self._opportunity_payload(subscription)
            self._post("/rest/opportunities", payload)
            return True
        except Exception as exc:
            print(f"twenty-sync error: {exc}")
            return False

    def _opportunity_payload(self, subscription: CommercialSubscription) -> dict[str, object]:
        tariff = self.tariffs_by_id.get(subscription.tariff_id)
        title = tariff.title if tariff else subscription.tariff_id
        name = f"VPN {subscription.token[:12].upper()} · {title}"
        if subscription.pay_coin_id:
            name += f" · {subscription.pay_coin_id}"
        payload: dict[str, object] = {
            "name": name,
            "stage": "CUSTOMER",
            "closeDate": datetime.now(timezone.utc).isoformat(),
        }
        if tariff:
            try:
                amount_micros = int(Decimal(tariff.price_rub) * 1_000_000)
                payload["amount"] = {"amountMicros": amount_micros, "currencyCode": "RUB"}
            except InvalidOperation:
                pass
        return payload

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
