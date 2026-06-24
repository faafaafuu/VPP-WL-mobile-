from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Coin:
    id: str
    label: str
    network_label: str
    coingecko_id: str
    wallet_key: str
    decimals: int
    color: str
    order: int


ALL_COINS: tuple[Coin, ...] = (
    Coin("usdt_trc20", "USDT", "TRC20 (Tron)",    "tether",   "trc20", 2, "#26a17b", 1),
    Coin("usdc_trc20", "USDC", "TRC20 (Tron)",    "usd-coin", "trc20", 2, "#2775ca", 2),
    Coin("ton",        "TON",  "TON Blockchain",   "toncoin",  "ton",   4, "#0098ea", 3),
    Coin("usdt_bep20", "USDT", "BEP20 (BSC)",      "tether",   "eth",   2, "#f0b90b", 4),
    Coin("eth",        "ETH",  "Ethereum",          "ethereum", "eth",   6, "#627eea", 5),
    Coin("btc",        "BTC",  "Bitcoin",           "bitcoin",  "btc",   8, "#f7931a", 6),
)

COINS_BY_ID: dict[str, Coin] = {c.id: c for c in ALL_COINS}

COINGECKO_IDS: tuple[str, ...] = tuple(
    dict.fromkeys(c.coingecko_id for c in ALL_COINS)
)
