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


class PaymentUriTest(unittest.TestCase):
    def test_evm_native_uses_eip681_value(self) -> None:
        from app.domain.wallet_connect import payment_uri

        uri = payment_uri("eth", "0xAbC0000000000000000000000000000000000001", "0.00095238")

        self.assertEqual(uri, "ethereum:0xAbC0000000000000000000000000000000000001@1?value=952380000000000")

    def test_evm_token_uses_eip681_transfer(self) -> None:
        from app.domain.wallet_connect import payment_uri

        uri = payment_uri("usdt_polygon", "0xBD13000000000000000000000000000000000002", "10.61")

        self.assertIn("ethereum:0xc2132D05D31c914a87C6611C10748AEb04B58e8F@137/transfer", uri)
        self.assertIn("uint256=10610000", uri)

    def test_ton_amount_is_scaled_to_nanotons(self) -> None:
        from app.domain.wallet_connect import payment_uri

        self.assertEqual(payment_uri("ton", "UQAld", "0.0104"), "ton://transfer/UQAld?amount=10400000")

    def test_btc_and_sol_keep_the_decimal_amount(self) -> None:
        from app.domain.wallet_connect import payment_uri

        self.assertEqual(payment_uri("btc", "bc1qx", "0.00003016"), "bitcoin:bc1qx?amount=0.00003016")
        self.assertEqual(payment_uri("sol", "5tCQ", "0.0226"), "solana:5tCQ?amount=0.0226")

    def test_tron_has_no_uri_scheme(self) -> None:
        from app.domain.wallet_connect import payment_uri

        self.assertIsNone(payment_uri("usdt_trc20", "TTest", "2.00"))

    def test_garbage_amounts_produce_no_link(self) -> None:
        from app.domain.wallet_connect import payment_uri

        for amount in ("—", "", "0", "-1", "abc"):
            with self.subTest(amount=amount):
                self.assertIsNone(payment_uri("btc", "bc1qx", amount))

    def test_units_are_exact_integers(self) -> None:
        from app.domain.wallet_connect import payment_units

        self.assertEqual(payment_units("eth", "0.00095238"), "952380000000000")
        self.assertEqual(payment_units("ton", "1.6650"), "1665000000")
        self.assertEqual(payment_units("usdt_trc20", "2.50"), "2500000")


class WalletLinksTest(unittest.TestCase):
    def test_metamask_gets_its_own_deep_link_for_tokens(self) -> None:
        from app.domain.wallet_connect import wallet_links

        links = {w["id"]: w["url"] for w in wallet_links("usdt_polygon", "0xTo", "2.54")}

        self.assertTrue(links["metamask"].startswith("https://metamask.app.link/send/"))
        self.assertIn("@137/transfer", links["metamask"])
        self.assertIn("uint256=2540000", links["metamask"])

    def test_trust_uses_its_own_asset_notation(self) -> None:
        from app.domain.wallet_connect import wallet_links

        links = {w["id"]: w["url"] for w in wallet_links("usdt_polygon", "0xTo", "2.54")}

        self.assertIn("asset=c966_t0xc2132D05D31c914a87C6611C10748AEb04B58e8F", links["trust"])
        self.assertIn("amount=2.54", links["trust"])

    def test_native_eth_carries_the_value_in_wei(self) -> None:
        from app.domain.wallet_connect import wallet_links

        links = {w["id"]: w["url"] for w in wallet_links("eth", "0xTo", "0.001026")}

        self.assertIn("@1?value=1026000000000000", links["metamask"])

    def test_ton_wallets_get_nanoton_amounts(self) -> None:
        from app.domain.wallet_connect import wallet_links

        links = {w["id"]: w["url"] for w in wallet_links("ton", "UQAld", "1.6650")}

        self.assertEqual(links["tonkeeper"], "https://app.tonkeeper.com/transfer/UQAld?amount=1665000000")
        self.assertEqual(links["tonhub"], "https://tonhub.com/transfer/UQAld?amount=1665000000")

    def test_every_button_carries_the_amount_somewhere(self) -> None:
        """A wallet opened on an empty send screen is worse than no button:
        the buyer retypes the amount and the watcher never matches it."""
        from app.domain.wallet_connect import wallet_links

        cases = [("usdt_erc20", "0xTo", "2.54"), ("eth", "0xTo", "0.001026"),
                 ("ton", "UQAld", "1.6650"), ("btc", "bc1qx", "0.00003016"), ("sol", "5tCQ", "0.0226")]
        for coin_id, address, amount in cases:
            for wallet in wallet_links(coin_id, address, amount):
                with self.subTest(coin_id=coin_id, wallet=wallet["id"]):
                    self.assertRegex(wallet["url"], r"(amount|value|uint256)=")

    def test_every_button_has_an_inline_icon(self) -> None:
        """An icon fetched over the network is exactly what a filtering
        mobile connection drops, leaving a sheet of blank squares."""
        from app.domain.wallet_connect import WALLET_ICONS, wallet_links

        for coin_id in ("usdt_erc20", "eth", "ton", "btc", "sol"):
            for wallet in wallet_links(coin_id, "0xTo", "1.5"):
                with self.subTest(coin_id=coin_id, wallet=wallet["id"]):
                    self.assertTrue(WALLET_ICONS[wallet["id"]].startswith("data:image/svg+xml,"))

    def test_tron_offers_no_buttons(self) -> None:
        """TRC20 has no payment scheme and TronLink's mobile link format is
        undocumented — a button there would misfire more often than work."""
        from app.domain.wallet_connect import wallet_links

        self.assertEqual(wallet_links("usdt_trc20", "TTest", "2.50"), [])

    def test_a_trailing_zero_in_the_amount_survives_into_the_link(self) -> None:
        """The anti-collision surcharge lands on a trailing zero roughly one
        invoice in ten. The link has to carry the amount the buyer was quoted,
        digit for digit, or the wallet sheet and the invoice disagree."""
        from app.domain.wallet_connect import wallet_links

        links = {w["id"]: w["url"] for w in wallet_links("btc", "bc1qx", "0.00002260")}

        self.assertIn("amount=0.00002260", links["trust"])

    def test_no_buttons_before_an_amount_is_known(self) -> None:
        from app.domain.wallet_connect import wallet_links

        self.assertEqual(wallet_links("btc", "bc1qx", "—"), [])


class InvoicePaymentQrTest(unittest.TestCase):
    def test_payment_qr_encodes_the_request_not_the_bare_address(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})
        svc.select_invoice_coin(token, {"coin_id": "btc"})

        svg = svc.invoice_payment_qr_svg(token, "btc")
        address_only = svc.invoice_wallet_qr_svg(token, "btc")

        self.assertIn("<svg", svg)
        self.assertNotEqual(svg, address_only)

    def test_address_qr_stays_a_bare_address(self) -> None:
        """Exchange withdrawal screens scan for an address and choke on a
        URI, so the panel's own QR must not become a payment request."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        self.assertEqual(
            svc.invoice_wallet_qr_svg(token, "btc"),
            svc.invoice_wallet_qr_svg(token, "btc"),
        )

    def test_chain_without_a_uri_scheme_has_no_payment_qr(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        with self.assertRaises(ApiError) as ctx:
            svc.invoice_payment_qr_svg(token, "usdt_trc20")
        self.assertEqual(ctx.exception.status, HTTPStatus.SERVICE_UNAVAILABLE)

    def test_invoice_page_carries_a_link_and_qr_for_every_uri_chain(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        for coin in _coins_from(svc.invoice_html(token)):
            if coin["pay"]["kind"] != "uri":
                continue
            with self.subTest(coin_id=coin["id"]):
                self.assertTrue(coin["pay_uri"])
                self.assertTrue(coin["pay_qr_url"])


class InvoiceSheetLayoutTest(unittest.TestCase):
    def test_each_coin_ships_its_wallet_buttons(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        for coin in _coins_from(svc.invoice_html(token)):
            if coin["pay"]["kind"] == "tron":
                continue
            with self.subTest(coin_id=coin["id"]):
                self.assertTrue(coin["wallets"])

    def test_wallet_buttons_are_refreshed_with_the_final_amount(self) -> None:
        """The page renders an estimate; the amount the watcher waits for is
        only fixed by /select, so the buttons have to be rebuilt then."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})

        result = svc.select_invoice_coin(token, {"coin_id": "btc"})

        self.assertTrue(result["wallets"])
        for wallet in result["wallets"]:
            with self.subTest(wallet=wallet["id"]):
                self.assertIn(result["amount"], wallet["url"])

    def test_injected_wallet_path_skips_the_button_list(self) -> None:
        """A desktop browser with an extension signs on the page itself and
        has nowhere to send a mobile deep link."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)
        branch = html.split("function buildEvmSheet")[1].split("function buildTronSheet")[0]
        injected_branch = branch.split("if (wallets.length) {")[1].split("return;")[0]

        self.assertNotIn("addWalletButtons", injected_branch)

    def test_wallet_buttons_are_real_links(self) -> None:
        """Navigating to a scheme like solana: from script is blocked by
        browsers as an unknown-protocol navigation, so the tap does nothing.
        A real anchor carrying the user's gesture opens the wallet."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)
        block = html.split("function addWalletButtons")[1].split("function notInstalledLater")[0]

        self.assertIn("walletRow(group, w.name, WALLET_ICONS[w.id] || '', w.url)", block)
        self.assertNotIn("window.location.href = w.url", block)

    def test_balance_is_left_to_the_wallet(self) -> None:
        """We only see the account that happens to be connected; refusing on
        its balance blocks a buyer who meant to pay from another one."""
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        html = svc.invoice_html(token)

        self.assertNotIn("evmShortfall", html)
        self.assertNotIn("0x70a08231", html)


class PaymentQrCapacityTest(unittest.TestCase):
    """The QR encoder is a version-5 symbol: 106 bytes and no more. EIP-681
    token transfers are 133-135 bytes, so asking it to draw one raised inside
    a request handler — the buyer got a 502 on the payment page."""

    def test_long_uris_are_reported_not_raised(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})
        svc.select_invoice_coin(token, {"coin_id": "usdt_polygon"})

        with self.assertRaises(ApiError) as ctx:
            svc.invoice_payment_qr_svg(token, "usdt_polygon")

        self.assertEqual(ctx.exception.status, HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertEqual(ctx.exception.payload["error"], "qr_too_long")

    def test_no_qr_button_is_offered_when_it_cannot_be_drawn(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})

        result = svc.select_invoice_coin(token, {"coin_id": "usdt_polygon"})

        self.assertIsNone(result["pay_qr_url"])

    def test_short_uris_still_get_a_qr(self) -> None:
        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]
        svc.set_invoice_contact(token, {"email": "buyer@example.com"})

        for coin_id in ("btc", "ton", "sol", "eth"):
            with self.subTest(coin_id=coin_id):
                result = svc.select_invoice_coin(token, {"coin_id": coin_id})
                self.assertIsNotNone(result["pay_qr_url"])
                self.assertIn("<svg", svc.invoice_payment_qr_svg(token, coin_id))

    def test_every_offered_uri_either_fits_or_offers_no_button(self) -> None:
        from app.domain.qr_svg import fits

        svc = _service()
        token = svc.checkout({"tariff_id": "vpn.1m"})["token"]

        for coin in _coins_from(svc.invoice_html(token)):
            with self.subTest(coin_id=coin["id"]):
                if coin["pay_qr_url"]:
                    self.assertTrue(fits(coin["pay_uri"]))
