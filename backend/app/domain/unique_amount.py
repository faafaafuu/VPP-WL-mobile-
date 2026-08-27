from __future__ import annotations

import secrets
from decimal import ROUND_UP, Decimal

from app.domain.coins import Coin

# Enot-style matching: every pending order gets a unique amount so an incoming
# transfer maps to exactly one order by (address, amount). The tail is added in
# the coin's least significant digits, bounded so the surcharge stays small.
#
# The bound has to depend on decimals: 99 units of a 2-decimal coin's minor
# unit is $0.99 — a ~40% swing on a $2 tariff, and it visibly changes every
# time the buyer switches network (each network is its own coin_id, so it
# gets its own fresh tail) — reported as "the price keeps jumping around".
# 99 units of BTC's 8th decimal is meanwhile negligible. Scale the cap down
# for coarse (low-decimal) coins so the surcharge stays small in real terms
# everywhere, not just in raw unit count.
_MAX_ATTEMPTS = 400


class AmountCollisionError(RuntimeError):
    pass


def _max_tail_units(coin: Coin) -> int:
    if coin.decimals <= 2:
        return 20
    if coin.decimals <= 4:
        return 50
    return 99


def unique_coin_amount(base_amount: str, coin: Coin, taken_amounts: set[str]) -> str:
    """Return base_amount plus a random micro-tail not present in taken_amounts."""
    base = Decimal(base_amount)
    unit = Decimal(1).scaleb(-coin.decimals)
    quantum = Decimal("0." + "0" * coin.decimals) if coin.decimals else Decimal("1")
    max_tail_units = _max_tail_units(coin)
    for _ in range(_MAX_ATTEMPTS):
        tail_units = secrets.randbelow(max_tail_units) + 1
        candidate = (base + unit * tail_units).quantize(quantum, rounding=ROUND_UP)
        text = format(candidate, "f")
        if text not in taken_amounts:
            return text
    raise AmountCollisionError(
        f"could not find a unique amount near {base_amount} for {coin.id}: "
        f"{len(taken_amounts)} amounts already pending"
    )
