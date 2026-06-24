from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from decimal import ROUND_UP, Decimal
from urllib.error import URLError
from urllib.request import urlopen

from app.domain.coins import COINGECKO_IDS, Coin


_COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    f"?ids={','.join(COINGECKO_IDS)}&vs_currencies=rub"
)
_CACHE_TTL = timedelta(minutes=15)
_REQUEST_TIMEOUT = 8


class ExchangeRateService:
    def __init__(self, provider: str = "coingecko") -> None:
        self._provider = provider
        self._rates: dict[str, Decimal] = {}
        self._last_updated: datetime | None = None
        self._lock = threading.Lock()

    def coin_amount(self, price_rub: str, coin: Coin) -> str | None:
        """Return the amount of coin needed for price_rub. None if rate unavailable."""
        rate = self._get_rate(coin.coingecko_id)
        if rate is None:
            return None
        rub = Decimal(price_rub)
        quantize = Decimal("0." + "0" * coin.decimals)
        amount = (rub / rate).quantize(quantize, rounding=ROUND_UP)
        return str(amount)

    def refresh(self) -> None:
        """Force refresh rates (thread-safe)."""
        with self._lock:
            self._refresh_locked()

    def last_updated(self) -> datetime | None:
        return self._last_updated

    def _get_rate(self, coingecko_id: str) -> Decimal | None:
        with self._lock:
            if self._is_stale():
                self._refresh_locked()
            return self._rates.get(coingecko_id)

    def _is_stale(self) -> bool:
        if self._last_updated is None:
            return True
        return datetime.now(timezone.utc) - self._last_updated > _CACHE_TTL

    def _refresh_locked(self) -> None:
        if self._provider == "fixed":
            return
        try:
            with urlopen(_COINGECKO_URL, timeout=_REQUEST_TIMEOUT) as resp:
                data: dict[str, dict[str, float]] = json.load(resp)
            new_rates: dict[str, Decimal] = {}
            for coin_id, prices in data.items():
                rub_price = prices.get("rub")
                if rub_price and rub_price > 0:
                    new_rates[coin_id] = Decimal(str(rub_price))
            if new_rates:
                self._rates = new_rates
                self._last_updated = datetime.now(timezone.utc)
        except (URLError, json.JSONDecodeError, Exception):
            pass


_singleton: ExchangeRateService | None = None
_singleton_lock = threading.Lock()


def get_exchange_rate_service(provider: str = "coingecko") -> ExchangeRateService:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = ExchangeRateService(provider)
    return _singleton


def make_fixed_rate_service(rates_rub: dict[str, Decimal]) -> ExchangeRateService:
    """Create an ExchangeRateService with pre-seeded rates (for testing)."""
    svc = ExchangeRateService("fixed")
    svc._rates = dict(rates_rub)
    svc._last_updated = datetime.now(timezone.utc)
    return svc
