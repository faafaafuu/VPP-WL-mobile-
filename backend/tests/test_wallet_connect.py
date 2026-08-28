from __future__ import annotations

import json
import re
import unittest
from decimal import Decimal
from http import HTTPStatus

from app.api.service import ApiError, ApiService
from app.domain.coins import COINS_BY_ID
from app.domain.config_builder import ConfigBuilder
from app.domain.wallet_connect import TRANSFER_SPECS, transfer_spec
from app.repositories.memory import InMemoryRepository
from app.security.tokens import TokenService
from app.services.chain_providers import build_providers
from app.services.exchange_rates import make_fixed_rate_service

_WALLETS = {
    "trc20": "TTestWalletAddress1234567890ABCDE",
    "eth": "0x75B5000000000000000000000000000000000001",
    "polygon": "0xBD13000000000000000000000000000000000002",
    "btc": "bc1qtestaddress000000000000000000000000000",
    "ton": "UQAldTestAddress0000000000000000000000000000",
    "solana": "5tCQWWTestAddress000000000000000000000000000",
}


def _service() -> ApiService:
    rate_svc = make_fixed_rate_service({
        "tether": Decimal("100.00"),
        "usd-coin": Decimal("100.00"),
        "the-open-network": Decimal("650.00"),
        "bitcoin": Decimal("9000000.00"),
        "ethereum": Decimal("320000.00"),
        "solana": Decimal("20000.00"),
    })
    return ApiService(
        InMemoryRepository(),
        TokenService("test-secret-with-length"),
        ConfigBuilder(),
        admin_token="test-admin-token-xx",
        public_base_url="http://127.0.0.1:8080",
        checkout_mode="crypto_manual",
        crypto_wallets=dict(_WALLETS),
        exchange_rate_service=rate_svc,
        # Same filter production runs: only coins whose payments we can confirm.
        watchable_coin_ids=frozenset(build_providers(None, "etherscan-key")),
    )


def _coins_from(html: str) -> list[dict]:
    match = re.search(r"const COINS = (\[.*?\]);\n", html, re.S)
    assert match, "invoice page must embed its coin list"
    return json.loads(match.group(1))


class TransferSpecTest(unittest.TestCase):
    def test_every_spec_names_a_real_coin(self) -> None:
        self.assertEqual(set(TRANSFER_SPECS) - set(COINS_BY_ID), set())

    def test_evm_specs_carry_a_chain_the_wallet_can_be_asked_to_add(self) -> None:
        for coin_id, spec in TRANSFER_SPECS.items():
            if spec.kind != "evm":
                continue
            with self.subTest(coin_id=coin_id):
                data = spec.as_dict()
                self.assertEqual(data["chain_hex"], hex(data["chain_id"]))
                self.assertEqual(data["add_chain"]["chainId"], data["chain_hex"])
                self.assertTrue(data["add_chain"]["rpcUrls"])

    def test_token_decimals_are_chain_units_not_display_digits(self) -> None:
        """Coin.decimals only controls how many digits we print; sending
        6-decimal USDT as if it had 2 would transfer 1/10000th of the price."""
        self.assertEqual(TRANSFER_SPECS["usdt_erc20"].token_decimals, 6)
        self.assertEqual(COINS_BY_ID["usdt_erc20"].decimals, 2)
        self.assertEqual(TRANSFER_SPECS["eth"].token_decimals, 18)

    def test_uri_specs_have_both_placeholders(self) -> None:
        for coin_id, spec in TRANSFER_SPECS.items():
            if spec.kind != "uri":
                continue
            with self.subTest(coin_id=coin_id):
                self.assertIn("{address}", spec.uri_template)
                self.assertIn("{amount}", spec.uri_template)

    def test_unknown_coin_has_no_spec(self) -> None:
        self.assertIsNone(transfer_spec("doge"))


class InvoiceWalletConnectTest(unittest.TestCase):
    def test_every_offered_coin_ships_a_transfer_spec(self) -> None:
        """A coin the page can't hand to a wallet falls back to copy-paste,
        which is exactly where wrong-network and rounded-amount errors come
        from — so every coin we actually offer must carry one."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        for coin in _coins_from(svc.invoice_html(token)):
            with self.subTest(coin_id=coin["id"]):
                self.assertIsNotNone(coin["pay"])

    def test_connect_button_rendered_for_each_coin_panel(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)
        coins = _coins_from(html)

        self.assertEqual(html.count('onclick="payWithWallet('), len(coins))

    def test_token_transfers_are_sent_as_erc20_transfer_calls(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        # transfer(address,uint256) selector
        self.assertIn("0xa9059cbb", html)
        self.assertIn("eth_sendTransaction", html)
        self.assertIn("wallet_switchEthereumChain", html)
        # EIP-6963 discovery rather than guessing at window.ethereum
        self.assertIn("eip6963:requestProvider", html)

    def test_amounts_are_converted_with_bigint_not_floats(self) -> None:
        """0.00095238 ETH through a double loses digits, and the watcher
        matches on the amount — the page must scale the decimal string."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn("function toUnits(", html)
        self.assertIn("BigInt(", html)
        self.assertNotIn("parseFloat(coin.amount", html)


class InvoiceContactGateTest(unittest.TestCase):
    def test_payment_steps_are_hidden_until_a_contact_is_known(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertIn('<div id="paySteps" hidden>', html)
        self.assertIn("let hasContact = false;", html)

    def test_payment_steps_open_once_an_email_is_saved(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})

        html = svc.invoice_html(token)

        self.assertIn('<div id="paySteps">', html)
        self.assertIn("let hasContact = true;", html)

    def test_telegram_binding_alone_counts_as_a_contact(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.repository.bind_telegram(token, "4242")

        self.assertTrue(svc.invoice_status(token)["contact"])
        self.assertTrue(svc.invoice_status(token)["contact_telegram"])
        svc.select_invoice_coin(token, {"coin_id": "usdt_trc20"})

    def test_selecting_a_coin_without_a_contact_is_refused(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        with self.assertRaises(ApiError) as ctx:
            svc.select_invoice_coin(token, {"coin_id": "usdt_trc20"})
        self.assertEqual(ctx.exception.status, HTTPStatus.CONFLICT)

    def test_status_reports_contact_so_the_page_can_unlock_itself(self) -> None:
        """Telegram gets bound in the bot, in another app entirely — the
        open invoice tab learns about it only by polling for it."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        self.assertFalse(svc.invoice_status(token)["contact"])
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})
        status = svc.invoice_status(token)
        self.assertTrue(status["contact"])
        self.assertEqual(status["contact_email"], "buyer@example.com")


class InvoiceCardErrorTest(unittest.TestCase):
    def test_card_error_is_rendered_when_passed(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token, card_error="Оплата картой временно недоступна")

        self.assertIn('id="cardError"', html)
        self.assertIn("Оплата картой временно недоступна", html)

    def test_no_card_error_block_by_default(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        self.assertNotIn('id="cardError"', svc.invoice_html(token))


if __name__ == "__main__":
    unittest.main()
