from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Coin:
    id: str
    label: str            # USDT, USDC, ETH, BTC, TON
    network_label: str    # TRC20 · Tron, ERC20 · Ethereum, ...
    coingecko_id: str
    wallet_key: str       # trc20 | eth | btc | ton
    decimals: int
    order: int
    testnet: bool = False
    fixed_amount: str | None = None  # testnet only: amount ignoring live rate


# Mainnet coins. USDT/USDC are offered on several networks; the user picks the
# one their wallet/exchange supports. ERC20 and BEP20 share the same 0x address.
ALL_COINS: tuple[Coin, ...] = (
    Coin("usdt_trc20", "USDT", "TRC20 · Tron",     "tether",   "trc20", 2, 1),
    Coin("usdt_erc20", "USDT", "ERC20 · Ethereum", "tether",   "eth",   2, 2),
    Coin("usdt_bep20", "USDT", "BEP20 · BNB",      "tether",   "eth",   2, 3),
    Coin("usdc_trc20", "USDC", "TRC20 · Tron",     "usd-coin", "trc20", 2, 4),
    Coin("usdc_erc20", "USDC", "ERC20 · Ethereum", "usd-coin", "eth",   2, 5),
    Coin("ton",        "TON",  "TON",              "toncoin",  "ton",   4, 6),
    Coin("eth",        "ETH",  "Ethereum",         "ethereum", "eth",   6, 7),
    Coin("btc",        "BTC",  "Bitcoin",          "bitcoin",  "btc",   8, 8),
    # Developer testnet — pay with free Sepolia test ETH (same 0x address works).
    Coin("eth_sepolia", "ETH", "Sepolia · testnet", "ethereum", "eth", 6, 99, testnet=True, fixed_amount="0.001"),
)

COINS_BY_ID: dict[str, Coin] = {c.id: c for c in ALL_COINS}

COINGECKO_IDS: tuple[str, ...] = tuple(
    dict.fromkeys(c.coingecko_id for c in ALL_COINS)
)
