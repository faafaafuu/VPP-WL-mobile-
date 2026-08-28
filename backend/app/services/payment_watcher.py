from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable

from app.domain.models import AdminAuditEvent, CommercialSubscription, new_id
from app.domain.tariffs import Tariff
from app.repositories.factory import Repository
from app.services.chain_providers import (
    COIN_SYMBOLS,
    ChainProvider,
    ChainProviderError,
    IncomingTransfer,
)


# Relative tolerance applied when matching an incoming transfer's amount
# against a pending order's quoted amount. The quote is generated from our
# own exchange-rate snapshot; the buyer's wallet converts at its own
# real-time rate a little later, so a small drift between the two is normal
# and not a sign of the wrong order. Observed in production: a real payment
# landed 1.05% above its quote and sat unmatched — and therefore never
# activated — for over an hour before this was added.
#
# 2% is comfortably above ordinary rate drift while staying far below the
# per-coin unique-amount tail spacing (domain/unique_amount.py caps the tail
# at 20-99 minor units), so it practically never lets a transfer match a
# *different* pending order's amount by coincidence.
_AMOUNT_TOLERANCE = Decimal("0.02")


@dataclass(frozen=True)
class WatchSummary:
    checked: int = 0
    activated: int = 0
    errors: int = 0
    activated_tokens: list[str] = field(default_factory=list)


class PaymentWatcher:
    """Match pending crypto invoices against on-chain incoming transfers.

    A pending subscription with a payment intent is activated when a transfer
    to its address carries the exact unique amount, an accepted token symbol,
    and enough confirmations.
    """

    def __init__(
        self,
        repository: Repository,
        providers: dict[str, ChainProvider],
        tariffs_by_id: dict[str, Tariff],
        min_confirmations: int = 1,
        on_activated: Callable[[CommercialSubscription], None] | None = None,
    ) -> None:
        self.repository = repository
        self.providers = providers
        self.tariffs_by_id = tariffs_by_id
        self.min_confirmations = min_confirmations
        self.on_activated = on_activated

    def run_once(self) -> WatchSummary:
        pending = [
            subscription
            for subscription in self.repository.list_commercial_subscriptions(status="pending")
            if subscription.has_payment_intent() and subscription.pay_coin_id in self.providers
        ]
        if not pending:
            return WatchSummary()

        used_txs = {
            subscription.paid_tx
            for subscription in self.repository.list_commercial_subscriptions(status="active")
            if subscription.paid_tx
        }
        transfers_cache: dict[tuple[int, str], list[IncomingTransfer] | None] = {}
        checked = 0
        errors = 0
        activated_tokens: list[str] = []
        for subscription in pending:
            checked += 1
            transfers = self._transfers_for(subscription, transfers_cache)
            if transfers is None:
                errors += 1
                continue
            match = self._match(subscription, transfers, used_txs)
            if match is None:
                continue
            if self._activate(subscription, match):
                used_txs.add(match.tx_id)
                activated_tokens.append(subscription.token)
        return WatchSummary(
            checked=checked,
            activated=len(activated_tokens),
            errors=errors,
            activated_tokens=activated_tokens,
        )

    def _transfers_for(
        self,
        subscription: CommercialSubscription,
        cache: dict[tuple[int, str], list[IncomingTransfer] | None],
    ) -> list[IncomingTransfer] | None:
        provider = self.providers[subscription.pay_coin_id or ""]
        address = subscription.pay_address or ""
        key = (id(provider), address)
        if key not in cache:
            try:
                cache[key] = provider.incoming_transfers(address)
            except ChainProviderError:
                cache[key] = None
        return cache[key]

    def _match(
        self,
        subscription: CommercialSubscription,
        transfers: list[IncomingTransfer],
        used_txs: set[str | None],
    ) -> IncomingTransfer | None:
        coin_id = subscription.pay_coin_id or ""
        accepted_symbols = COIN_SYMBOLS.get(coin_id)
        if accepted_symbols is None:
            return None
        try:
            expected_amount = Decimal(subscription.pay_amount or "")
        except InvalidOperation:
            return None
        if expected_amount <= 0:
            return None
        tolerance = expected_amount * _AMOUNT_TOLERANCE
        address = (subscription.pay_address or "").lower()
        for transfer in transfers:
            if transfer.tx_id in used_txs:
                continue
            if transfer.to_address.lower() != address:
                continue
            if transfer.symbol not in accepted_symbols:
                continue
            if abs(transfer.amount - expected_amount) > tolerance:
                continue
            if transfer.confirmations < self.min_confirmations:
                continue
            return transfer
        return None

    def _activate(self, subscription: CommercialSubscription, transfer: IncomingTransfer) -> bool:
        tariff = self.tariffs_by_id.get(subscription.tariff_id)
        if tariff is None:
            return False
        activated = self.repository.activate_commercial_subscription(
            subscription.token,
            tariff.duration_days,
            payment_id=f"crypto:{subscription.pay_coin_id}",
            paid_tx=transfer.tx_id,
            payer=transfer.from_address,
        )
        if activated is None:
            return False
        self.repository.add_admin_audit_event(
            AdminAuditEvent(
                id=new_id("aae"),
                occurred_at=datetime.now(timezone.utc),
                action="commercial_subscription.crypto_paid",
                target_type="commercial_subscription",
                target_id=_mask_token(subscription.token),
                result="success",
                details={
                    "coin_id": subscription.pay_coin_id,
                    "amount": subscription.pay_amount,
                    "tx": transfer.tx_id,
                    "duration_days": tariff.duration_days,
                },
            )
        )
        if self.on_activated is not None:
            try:
                self.on_activated(activated)
            except Exception:  # notification failures must not block activation
                pass
        return True


def _mask_token(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"
