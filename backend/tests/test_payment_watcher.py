from __future__ import annotations

import unittest
from decimal import Decimal

from app.domain.coins import COINS_BY_ID
from app.domain.tariffs import DEFAULT_TARIFFS, tariffs_by_id
from app.domain.unique_amount import AmountCollisionError, unique_coin_amount
from app.repositories.memory import InMemoryRepository
from app.services.chain_providers import IncomingTransfer
from app.services.payment_watcher import PaymentWatcher

_WALLET = "TTestWalletAddress1234567890ABCDE"
_USDT = COINS_BY_ID["usdt_trc20"]


class FakeProvider:
    def __init__(self, transfers: list[IncomingTransfer] | None = None) -> None:
        self.transfers = transfers or []
        self.calls = 0

    def incoming_transfers(self, address: str) -> list[IncomingTransfer]:
        self.calls += 1
        return self.transfers


def _transfer(
    amount: str,
    to_address: str = _WALLET,
    symbol: str = "USDT",
    confirmations: int = 100,
    tx_id: str = "tx-1",
) -> IncomingTransfer:
    return IncomingTransfer(
        tx_id=tx_id,
        from_address="TPayerAddress999",
        to_address=to_address,
        amount=Decimal(amount),
        symbol=symbol,
        confirmations=confirmations,
    )


def _pending_subscription(repository: InMemoryRepository, amount: str = "2.03") -> str:
    token = "tok-" + amount
    repository.create_commercial_subscription(token, "vpn.1m")
    repository.set_payment_intent(token, "usdt_trc20", amount, _WALLET)
    return token


def _watcher(repository: InMemoryRepository, provider: FakeProvider, min_confirmations: int = 1) -> PaymentWatcher:
    return PaymentWatcher(
        repository,
        {"usdt_trc20": provider},
        tariffs_by_id(DEFAULT_TARIFFS),
        min_confirmations=min_confirmations,
    )


class PaymentIntentRepositoryTest(unittest.TestCase):
    def test_memory_set_payment_intent_roundtrip(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok", "vpn.1m")

        updated = repository.set_payment_intent("tok", "usdt_trc20", "2.07", _WALLET)

        assert updated is not None
        self.assertEqual(updated.pay_coin_id, "usdt_trc20")
        self.assertEqual(updated.pay_amount, "2.07")
        self.assertEqual(updated.pay_address, _WALLET)
        self.assertTrue(updated.has_payment_intent())

    def test_memory_set_payment_intent_unknown_token(self) -> None:
        repository = InMemoryRepository()

        self.assertIsNone(repository.set_payment_intent("missing", "usdt_trc20", "2.07", _WALLET))

    def test_memory_list_by_status(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-a", "vpn.1m")
        repository.create_commercial_subscription("tok-b", "vpn.1m")
        repository.activate_commercial_subscription("tok-b", 30)

        pending = repository.list_commercial_subscriptions(status="pending")
        active = repository.list_commercial_subscriptions(status="active")

        self.assertEqual([s.token for s in pending], ["tok-a"])
        self.assertEqual([s.token for s in active], ["tok-b"])
        self.assertEqual(len(repository.list_commercial_subscriptions()), 2)

    def test_memory_activate_records_paid_tx_and_payer(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok", "vpn.1m")

        activated = repository.activate_commercial_subscription(
            "tok", 30, paid_tx="tx-abc", payer="TPayer"
        )

        assert activated is not None
        self.assertEqual(activated.paid_tx, "tx-abc")
        self.assertEqual(activated.payer, "TPayer")

    def test_sqlite_payment_intent_and_activation(self) -> None:
        import tempfile
        from pathlib import Path

        from app.repositories.sqlite import SqliteRepository

        with tempfile.TemporaryDirectory() as tmp:
            repository = SqliteRepository(Path(tmp) / "test.db")
            repository.create_commercial_subscription("tok", "vpn.1m")

            updated = repository.set_payment_intent("tok", "usdt_trc20", "2.07", _WALLET)
            assert updated is not None
            self.assertEqual(updated.pay_amount, "2.07")

            pending = repository.list_commercial_subscriptions(status="pending")
            self.assertEqual([s.token for s in pending], ["tok"])

            activated = repository.activate_commercial_subscription(
                "tok", 30, paid_tx="tx-abc", payer="TPayer"
            )
            assert activated is not None
            self.assertEqual(activated.paid_tx, "tx-abc")
            self.assertEqual(activated.payer, "TPayer")
            self.assertTrue(activated.is_active())
            repository.close()

    def test_sqlite_migrates_existing_table_without_intent_columns(self) -> None:
        import sqlite3
        import tempfile
        from pathlib import Path

        from app.repositories.sqlite import SqliteRepository

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.db"
            connection = sqlite3.connect(path)
            connection.execute(
                """
                CREATE TABLE commercial_subscriptions (
                    token TEXT PRIMARY KEY,
                    tariff_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    payment_id TEXT
                )
                """
            )
            connection.commit()
            connection.close()

            repository = SqliteRepository(path)
            repository.create_commercial_subscription("tok", "vpn.1m")
            updated = repository.set_payment_intent("tok", "usdt_trc20", "2.07", _WALLET)
            assert updated is not None
            self.assertEqual(updated.pay_coin_id, "usdt_trc20")
            repository.close()


class UniqueAmountTest(unittest.TestCase):
    def test_amount_is_above_base(self) -> None:
        amount = unique_coin_amount("2.00", _USDT, set())

        self.assertGreater(Decimal(amount), Decimal("2.00"))
        self.assertLessEqual(Decimal(amount), Decimal("2.99"))

    def test_amount_avoids_taken_values(self) -> None:
        taken = {f"2.{tail:02d}" for tail in range(1, 99)}

        amount = unique_coin_amount("2.00", _USDT, taken)

        self.assertNotIn(amount, taken)

    def test_exhausted_space_raises(self) -> None:
        taken = {f"2.{tail:02d}" for tail in range(1, 100)}

        with self.assertRaises(AmountCollisionError):
            unique_coin_amount("2.00", _USDT, taken)

    def test_high_decimal_coin_keeps_precision(self) -> None:
        eth = COINS_BY_ID["eth"]

        amount = unique_coin_amount("0.001250", eth, set())

        self.assertGreater(Decimal(amount), Decimal("0.001250"))
        self.assertLess(Decimal(amount), Decimal("0.001350"))


class PaymentWatcherTest(unittest.TestCase):
    def test_exact_amount_activates_subscription(self) -> None:
        repository = InMemoryRepository()
        token = _pending_subscription(repository, amount="2.03")
        watcher = _watcher(repository, FakeProvider([_transfer("2.03")]))

        summary = watcher.run_once()

        self.assertEqual(summary.activated, 1)
        subscription = repository.get_commercial_subscription(token)
        assert subscription is not None
        self.assertTrue(subscription.is_active())
        self.assertEqual(subscription.paid_tx, "tx-1")
        self.assertEqual(subscription.payer, "TPayerAddress999")

    def test_wrong_amount_does_not_activate(self) -> None:
        repository = InMemoryRepository()
        token = _pending_subscription(repository, amount="2.03")
        watcher = _watcher(repository, FakeProvider([_transfer("2.04")]))

        summary = watcher.run_once()

        self.assertEqual(summary.activated, 0)
        subscription = repository.get_commercial_subscription(token)
        assert subscription is not None
        self.assertEqual(subscription.status, "pending")

    def test_wrong_symbol_does_not_activate(self) -> None:
        repository = InMemoryRepository()
        _pending_subscription(repository, amount="2.03")
        watcher = _watcher(repository, FakeProvider([_transfer("2.03", symbol="USDC")]))

        self.assertEqual(watcher.run_once().activated, 0)

    def test_wrong_address_does_not_activate(self) -> None:
        repository = InMemoryRepository()
        _pending_subscription(repository, amount="2.03")
        watcher = _watcher(repository, FakeProvider([_transfer("2.03", to_address="TSomeoneElse")]))

        self.assertEqual(watcher.run_once().activated, 0)

    def test_insufficient_confirmations_does_not_activate(self) -> None:
        repository = InMemoryRepository()
        _pending_subscription(repository, amount="2.03")
        watcher = _watcher(repository, FakeProvider([_transfer("2.03", confirmations=2)]), min_confirmations=12)

        self.assertEqual(watcher.run_once().activated, 0)

    def test_same_tx_never_credits_two_orders(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-a", "vpn.1m")
        repository.set_payment_intent("tok-a", "usdt_trc20", "2.03", _WALLET)
        repository.create_commercial_subscription("tok-b", "vpn.1m")
        repository.set_payment_intent("tok-b", "usdt_trc20", "2.03", _WALLET)
        watcher = _watcher(repository, FakeProvider([_transfer("2.03")]))

        summary = watcher.run_once()

        self.assertEqual(summary.activated, 1)

    def test_provider_fetch_is_cached_per_address(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok-a", "vpn.1m")
        repository.set_payment_intent("tok-a", "usdt_trc20", "2.03", _WALLET)
        repository.create_commercial_subscription("tok-b", "vpn.1m")
        repository.set_payment_intent("tok-b", "usdt_trc20", "2.05", _WALLET)
        provider = FakeProvider([])
        watcher = _watcher(repository, provider)

        watcher.run_once()

        self.assertEqual(provider.calls, 1)

    def test_activation_writes_audit_event(self) -> None:
        repository = InMemoryRepository()
        _pending_subscription(repository, amount="2.03")
        watcher = _watcher(repository, FakeProvider([_transfer("2.03")]))

        watcher.run_once()

        actions = [event.action for event in repository.list_admin_audit_events()]
        self.assertIn("commercial_subscription.crypto_paid", actions)

    def test_pending_without_intent_is_skipped(self) -> None:
        repository = InMemoryRepository()
        repository.create_commercial_subscription("tok", "vpn.1m")
        provider = FakeProvider([_transfer("2.03")])
        watcher = _watcher(repository, provider)

        summary = watcher.run_once()

        self.assertEqual(summary.checked, 0)
        self.assertEqual(provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
