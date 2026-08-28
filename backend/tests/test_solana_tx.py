from __future__ import annotations

import unittest
from decimal import Decimal
from http import HTTPStatus

from app.api.service import ApiError, ApiService
from app.domain.config_builder import ConfigBuilder
from app.domain.solana_tx import (
    SYSTEM_PROGRAM_ID,
    SolanaTxError,
    b58decode,
    b58encode,
    build_transfer_message,
)
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService
from app.services.exchange_rates import make_fixed_rate_service

_FROM = "BQWWFhzBdw2vKKBUX17NHeFbCoFQHfRARpdztPE2tDJ"
_TO = "5tCQWWzufUwDaEgTUpgVNh2HrMuv1Y9mSUzs1gfujffG"
_BLOCKHASH = "EETubP5AKHgjPAhzPAFcb8BAY1hMH639CWCFTqi3hq2V"

# Byte-for-byte what @solana/web3.js compiles for the same transfer —
# checked against the library rather than against my own reading of the spec.
_REFERENCE = (
    "87PYqqfz2XkKBUFu6zuyiY8P73Ff8kigTXjXxoRCSqNQhMSXMCx28mhCpU7TvvCuDGM6XBAbnLF3XnTe2XGPs775"
    "Fqih6mehvLVkotkw7bBqTLcBhgMTS1TJ5wTqC6Qg2jnt1yJUZruRMdFcRY2R4ZyQUFEUxvMxhnTPj5Q9iNGdoirv"
    "tAsQbtWeTJaoKQiCKHnCj6kFTeHV"
)


class Base58Test(unittest.TestCase):
    def test_round_trip(self) -> None:
        for raw in (b"", b"\x00", b"\x00\x00abc", bytes(range(32))):
            with self.subTest(raw=raw):
                self.assertEqual(b58decode(b58encode(raw)), raw)

    def test_leading_zero_bytes_survive(self) -> None:
        """They carry no numeric value, so an integer round trip drops them
        and the address silently becomes a different one."""
        self.assertEqual(b58encode(b"\x00\x00" + b"\x01" * 30)[:2], "11")

    def test_rejects_non_base58(self) -> None:
        with self.assertRaises(SolanaTxError):
            b58decode("0OIl")


class BuildTransferMessageTest(unittest.TestCase):
    def test_matches_the_reference_library_byte_for_byte(self) -> None:
        self.assertEqual(build_transfer_message(_FROM, _TO, 22600000, _BLOCKHASH), _REFERENCE)

    def test_amount_changes_the_message(self) -> None:
        other = build_transfer_message(_FROM, _TO, 22600001, _BLOCKHASH)

        self.assertNotEqual(other, _REFERENCE)

    def test_system_program_is_the_last_account(self) -> None:
        raw = b58decode(build_transfer_message(_FROM, _TO, 1000, _BLOCKHASH))
        keys = [raw[4 + i * 32: 36 + i * 32] for i in range(3)]

        self.assertEqual(b58encode(keys[0]), _FROM)
        self.assertEqual(b58encode(keys[1]), _TO)
        self.assertEqual(b58encode(keys[2]), SYSTEM_PROGRAM_ID)

    def test_rejects_nonsense(self) -> None:
        for args in (
            (_FROM, _TO, 0, _BLOCKHASH),
            (_FROM, _TO, -1, _BLOCKHASH),
            (_FROM, _FROM, 100, _BLOCKHASH),
            (_FROM, "notanaddress", 100, _BLOCKHASH),
            (_FROM, _TO, 100, "short"),
        ):
            with self.subTest(args=args):
                with self.assertRaises(SolanaTxError):
                    build_transfer_message(*args)


class _StubSolanaProvider:
    def __init__(self, blockhash: str = _BLOCKHASH) -> None:
        self.blockhash = blockhash

    def latest_blockhash(self) -> str:
        return self.blockhash


def _service() -> ApiService:
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token="test-admin-token-xx",
        public_base_url="http://127.0.0.1:8080",
        checkout_mode="crypto_manual",
        crypto_wallets={"solana": _TO, "trc20": "TTestWalletAddress1234567890ABCDE"},
        exchange_rate_service=make_fixed_rate_service({
            "solana": Decimal("20000.00"), "tether": Decimal("100.00"),
        }),
        chain_providers={"sol": _StubSolanaProvider()},
    )


class SolanaTransferEndpointTest(unittest.TestCase):
    def _order(self, svc: ApiService) -> str:
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})
        return token

    def test_builds_a_message_for_the_selected_amount(self) -> None:
        svc = _service()
        token = self._order(svc)
        amount = svc.select_invoice_coin(token, {"coin_id": "sol"})["amount"]

        result = svc.solana_transfer_message(token, {"from": _FROM})

        self.assertEqual(result["amount"], amount)
        self.assertEqual(result["address"], _TO)
        self.assertTrue(result["message"])

    def test_refuses_before_a_coin_is_selected(self) -> None:
        """The exact amount is fixed by /select — building a transfer from an
        estimate would send a sum the payment watcher never matches."""
        svc = _service()
        token = self._order(svc)

        with self.assertRaises(ApiError) as ctx:
            svc.solana_transfer_message(token, {"from": _FROM})
        self.assertEqual(ctx.exception.status, HTTPStatus.CONFLICT)

    def test_refuses_without_a_contact(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        with self.assertRaises(ApiError) as ctx:
            svc.solana_transfer_message(token, {"from": _FROM})
        self.assertEqual(ctx.exception.status, HTTPStatus.CONFLICT)

    def test_refuses_without_a_sender(self) -> None:
        svc = _service()
        token = self._order(svc)
        svc.select_invoice_coin(token, {"coin_id": "sol"})

        with self.assertRaises(ApiError) as ctx:
            svc.solana_transfer_message(token, {"from": ""})
        self.assertEqual(ctx.exception.status, HTTPStatus.BAD_REQUEST)

    def test_recipient_is_ours_not_the_callers(self) -> None:
        """The page only relays the message; the payee is decided here."""
        svc = _service()
        token = self._order(svc)
        svc.select_invoice_coin(token, {"coin_id": "sol"})

        raw = b58decode(svc.solana_transfer_message(token, {"from": _FROM, "to": "attacker"})["message"])

        self.assertEqual(b58encode(raw[36:68]), _TO)


class SheetHonestyTest(unittest.TestCase):
    def test_page_never_claims_a_wallet_is_missing(self) -> None:
        """The page cannot see whether an app opened. Saying "you don't have
        it" is a guess, and it was wrong exactly when the wallet was there."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertNotIn("приложения нет на этом устройстве", html)

    def test_solana_extensions_are_used_directly(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn("window.phantom", html)
        self.assertIn("signAndSendTransaction", html)


if __name__ == "__main__":
    unittest.main()
