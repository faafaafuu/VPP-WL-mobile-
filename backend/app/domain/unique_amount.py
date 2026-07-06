from __future__ import annotations

import secrets
from decimal import ROUND_UP, Decimal

from app.domain.coins import Coin

# Enot-style matching: every pending order gets a unique amount so an incoming
# transfer maps to exactly one order by (address, amount). The tail is added in
# the coin's least significant digits, bounded so the surcharge stays small.
_MAX_TAIL_UNITS = 99
_MAX_ATTEMPTS = 400


class AmountCollisionError(RuntimeError):
    pass


def unique_coin_amount(base_amount: str, coin: Coin, taken_amounts: set[str]) -> str:
    """Return base_amount plus a random micro-tail not present in taken_amounts."""
    base = Decimal(base_amount)
    unit = Decimal(1).scaleb(-coin.decimals)
    quantum = Decimal("0." + "0" * coin.decimals) if coin.decimals else Decimal("1")
    for _ in range(_MAX_ATTEMPTS):
        tail_units = secrets.randbelow(_MAX_TAIL_UNITS) + 1
        candidate = (base + unit * tail_units).quantize(quantum, rounding=ROUND_UP)
        text = format(candidate, "f")
        if text not in taken_amounts:
            return text
    raise AmountCollisionError(
        f"could not find a unique amount near {base_amount} for {coin.id}: "
        f"{len(taken_amounts)} amounts already pending"
    )
