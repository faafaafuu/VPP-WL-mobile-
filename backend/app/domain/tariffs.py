from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True)
class Tariff:
    id: str
    title: str
    duration_days: int
    price_rub: str
    badge: str | None = None


DEFAULT_TARIFFS: tuple[Tariff, ...] = (
    Tariff(id="vpn.1m", title="1 месяц", duration_days=30, price_rub="399.00"),
    Tariff(id="vpn.3m", title="3 месяца", duration_days=90, price_rub="999.00", badge="выгоднее"),
    Tariff(id="vpn.6m", title="6 месяцев", duration_days=180, price_rub="1799.00", badge="лучший выбор"),
)


def tariffs_by_id(tariffs: tuple[Tariff, ...]) -> dict[str, Tariff]:
    return {tariff.id: tariff for tariff in tariffs}


def parse_tariffs(raw_value: str | None = None, product_prices: Mapping[str, str] | None = None) -> tuple[Tariff, ...]:
    prices = dict(product_prices or {})
    if not raw_value:
        return tuple(_with_configured_price(tariff, prices) for tariff in DEFAULT_TARIFFS)

    parsed: list[Tariff] = []
    for item in _csv(raw_value):
        parts = [part.strip() for part in item.split(":")]
        if len(parts) not in {4, 5}:
            raise ValueError("tariff items must use id:title:duration_days:price_rub[:badge]")
        tariff_id, title, raw_duration, raw_price = parts[:4]
        badge = parts[4] if len(parts) == 5 and parts[4] else None
        if not tariff_id or not title:
            raise ValueError("tariff id and title must not be empty")
        try:
            duration_days = int(raw_duration)
        except ValueError as exc:
            raise ValueError("tariff duration_days must be an integer") from exc
        if duration_days <= 0:
            raise ValueError("tariff duration_days must be positive")
        parsed.append(Tariff(tariff_id, title, duration_days, _decimal_price(raw_price), badge))
    if not parsed:
        raise ValueError("at least one tariff is required")
    return tuple(parsed)


def _with_configured_price(tariff: Tariff, prices: Mapping[str, str]) -> Tariff:
    if tariff.id not in prices:
        return tariff
    return Tariff(
        id=tariff.id,
        title=tariff.title,
        duration_days=tariff.duration_days,
        price_rub=_decimal_price(prices[tariff.id]),
        badge=tariff.badge,
    )


def _decimal_price(raw_value: str) -> str:
    try:
        amount = Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError("tariff price must be a decimal RUB value") from exc
    if amount <= 0:
        raise ValueError("tariff price must be positive")
    return f"{amount:.2f}"


def _csv(raw_value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())
