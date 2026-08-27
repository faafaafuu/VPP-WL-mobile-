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


# Grouped by asset (all networks for one asset are contiguous) so the invoice
# page can render one asset header with its network chips underneath, instead
# of a flat mixed row. Color is per-asset, not per-network, so the same coin
# reads as the same color everywhere regardless of which chain it's on.
_USDT = "#26a17b"
_USDC = "#2775ca"

ALL_COINS: tuple[Coin, ...] = (
    # Networks within each asset are ordered by how the row should read left
    # to right, ending on TRC20 (Tron) — cheap and familiar, but listed last
    # by request rather than first.
    Coin("usdt_bep20",   "USDT", "BEP20 (BSC)",       "tether",   "eth",     2, _USDT, 1),
    Coin("usdt_erc20",   "USDT", "ERC20 (Ethereum)",  "tether",   "eth",     2, _USDT, 2),
    Coin("usdt_polygon", "USDT", "Polygon",           "tether",   "polygon", 2, _USDT, 3),
    Coin("usdt_solana",  "USDT", "Solana",            "tether",   "solana",  2, _USDT, 4),
    Coin("usdt_ton",     "USDT", "TON",               "tether",   "ton",     2, _USDT, 5),
    Coin("usdt_trc20",   "USDT", "TRC20 (Tron)",      "tether",   "trc20",   2, _USDT, 6),
    Coin("usdc_bep20",   "USDC", "BEP20 (BSC)",       "usd-coin", "eth",     2, _USDC, 7),
    Coin("usdc_erc20",   "USDC", "ERC20 (Ethereum)",  "usd-coin", "eth",     2, _USDC, 8),
    Coin("usdc_polygon", "USDC", "Polygon",           "usd-coin", "polygon", 2, _USDC, 9),
    Coin("usdc_solana",  "USDC", "Solana",            "usd-coin", "solana",  2, _USDC, 10),
    Coin("usdc_ton",     "USDC", "TON",               "usd-coin", "ton",     2, _USDC, 11),
    Coin("usdc_trc20",   "USDC", "TRC20 (Tron)",      "usd-coin", "trc20",   2, _USDC, 12),
    Coin("ton",          "TON",  "TON Blockchain",    "the-open-network", "ton", 4, "#0098ea", 13),
    Coin("eth",          "ETH",  "Ethereum",          "ethereum", "eth",     6, "#627eea", 14),
    Coin("btc",          "BTC",  "Bitcoin",           "bitcoin",  "btc",     8, "#f7931a", 15),
)

COINS_BY_ID: dict[str, Coin] = {c.id: c for c in ALL_COINS}

COINGECKO_IDS: tuple[str, ...] = tuple(
    dict.fromkeys(c.coingecko_id for c in ALL_COINS)
)
