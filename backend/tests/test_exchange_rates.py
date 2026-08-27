from __future__ import annotations

import unittest
from decimal import Decimal

from app.domain.coins import ALL_COINS, COINS_BY_ID, Coin
from app.services.exchange_rates import ExchangeRateService, make_fixed_rate_service


class ExchangeRateServiceTest(unittest.TestCase):
    def _svc(self) -> ExchangeRateService:
        return make_fixed_rate_service({
            "tether":   Decimal("90.00"),
            "usd-coin": Decimal("90.00"),
            "toncoin":  Decimal("600.00"),
            "bitcoin":  Decimal("9000000.00"),
            "ethereum": Decimal("310000.00"),
        })

    def test_usdt_amount_rounds_up(self) -> None:
        svc = self._svc()
        coin = COINS_BY_ID["usdt_trc20"]

        result = svc.coin_amount("200.00", coin)

        # 200 / 90 = 2.2222... → rounds up to 2.23
        self.assertEqual(result, "2.23")

    def test_exact_division_no_rounding(self) -> None:
        svc = self._svc()
        coin = COINS_BY_ID["usdt_trc20"]

        result = svc.coin_amount("180.00", coin)

        self.assertEqual(result, "2.00")

    def test_ton_amount_uses_4_decimals(self) -> None:
        svc = self._svc()
        coin = COINS_BY_ID["ton"]

        result = svc.coin_amount("200.00", coin)

        # 200 / 600 = 0.3333... → rounds up to 0.3334
        self.assertEqual(result, "0.3334")

    def test_btc_amount_uses_8_decimals(self) -> None:
        svc = self._svc()
        coin = COINS_BY_ID["btc"]

        result = svc.coin_amount("200.00", coin)

        # 200 / 9000000 = 0.0000222... → rounds up to 0.00002223
        self.assertEqual(result, "0.00002223")
        assert result is not None
        self.assertEqual(len(result.split(".")[1]), 8)

    def test_unknown_rate_returns_none(self) -> None:
        svc = ExchangeRateService("fixed")

        coin = COINS_BY_ID["usdt_trc20"]
        result = svc.coin_amount("200.00", coin)

        self.assertIsNone(result)

    def test_fixed_provider_does_not_refresh(self) -> None:
        svc = ExchangeRateService("fixed")
        svc.refresh()

        self.assertIsNone(svc.last_updated())

    def test_stale_check_preserves_rates_in_fixed_mode(self) -> None:
        svc = make_fixed_rate_service({"tether": Decimal("100.00")})
        from datetime import datetime, timedelta, timezone
        svc._last_updated = datetime.now(timezone.utc) - timedelta(minutes=20)

        coin = COINS_BY_ID["usdt_trc20"]
        result = svc.coin_amount("200.00", coin)

        # Fixed mode refresh is a no-op: existing rates survive a stale check
        self.assertEqual(result, "2.00")


class CoinDefinitionsTest(unittest.TestCase):
    def test_all_coins_have_unique_ids(self) -> None:
        ids = [c.id for c in ALL_COINS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_coins_by_id_covers_all(self) -> None:
        self.assertEqual(set(COINS_BY_ID.keys()), {c.id for c in ALL_COINS})

    def test_usdt_trc20_is_first(self) -> None:
        self.assertEqual(ALL_COINS[0].id, "usdt_trc20")

    def test_all_coins_have_valid_wallet_keys(self) -> None:
        valid_keys = {"trc20", "ton", "eth", "btc", "polygon", "solana"}
        for coin in ALL_COINS:
            self.assertIn(coin.wallet_key, valid_keys, f"{coin.id} has invalid wallet_key")

    def test_stablecoins_have_2_decimals(self) -> None:
        for coin in ALL_COINS:
            if coin.label in {"USDT", "USDC"}:
                self.assertEqual(coin.decimals, 2, f"{coin.id} should have 2 decimals")

    def test_btc_has_8_decimals(self) -> None:
        self.assertEqual(COINS_BY_ID["btc"].decimals, 8)

    def test_ton_has_4_decimals(self) -> None:
        self.assertEqual(COINS_BY_ID["ton"].decimals, 4)


class BuildCoinOptionsTest(unittest.TestCase):
    def test_single_trc20_wallet_shows_usdt_and_usdc(self) -> None:
        from app.api.service import _build_coin_options

        wallets = {"trc20": "TAddr123"}
        svc = make_fixed_rate_service({"tether": Decimal("90.00"), "usd-coin": Decimal("90.00")})

        opts = _build_coin_options("200.00", wallets, svc)

        ids = [o["id"] for o in opts]
        self.assertIn("usdt_trc20", ids)
        self.assertIn("usdc_trc20", ids)

    def test_all_wallets_configured_shows_all_coins(self) -> None:
        from app.api.service import _build_coin_options

        wallets = {"trc20": "T1", "ton": "UQ1", "eth": "0x1", "btc": "bc1"}
        svc = make_fixed_rate_service({
            "tether": Decimal("90.00"), "usd-coin": Decimal("90.00"),
            "toncoin": Decimal("600.00"), "ethereum": Decimal("310000.00"),
            "bitcoin": Decimal("9000000.00"),
        })

        opts = _build_coin_options("200.00", wallets, svc)

        self.assertGreaterEqual(len(opts), 5)

    def test_no_wallets_returns_empty(self) -> None:
        from app.api.service import _build_coin_options
        from app.services.exchange_rates import ExchangeRateService

        opts = _build_coin_options("200.00", {}, ExchangeRateService("fixed"))

        self.assertEqual(opts, [])

    def test_missing_rate_shows_dash(self) -> None:
        from app.api.service import _build_coin_options

        wallets = {"trc20": "TAddr"}
        svc = ExchangeRateService("fixed")

        opts = _build_coin_options("200.00", wallets, svc)

        for opt in opts:
            self.assertEqual(opt["amount"], "—")

    def test_amount_is_correct(self) -> None:
        from app.api.service import _build_coin_options

        wallets = {"trc20": "TAddr"}
        svc = make_fixed_rate_service({"tether": Decimal("100.00"), "usd-coin": Decimal("100.00")})

        opts = _build_coin_options("200.00", wallets, svc)

        usdt_opt = next(o for o in opts if o["id"] == "usdt_trc20")
        self.assertEqual(usdt_opt["amount"], "2.00")

    def test_one_evm_address_shows_every_network_that_shares_it(self) -> None:
        """usdt_bep20, usdt_erc20 and eth all declare wallet_key="eth" — one
        configured address must surface all three, not just the first match."""
        from app.api.service import _build_coin_options

        wallets = {"eth": "0xShared"}
        svc = make_fixed_rate_service({"tether": Decimal("90.00"), "usd-coin": Decimal("90.00"), "ethereum": Decimal("300000.00")})

        opts = _build_coin_options("200.00", wallets, svc)

        ids = [o["id"] for o in opts]
        for expected in ("usdt_bep20", "usdt_erc20", "usdc_bep20", "usdc_erc20", "eth"):
            self.assertIn(expected, ids)
            addr = next(o["address"] for o in opts if o["id"] == expected)
            self.assertEqual(addr, "0xShared")


class CoinTabButtonsTest(unittest.TestCase):
    def test_multi_network_asset_gets_one_header_and_a_chip_per_network(self) -> None:
        from app.api.pages import _coin_tab_buttons

        wallets = {"trc20": "T1", "eth": "0x1"}
        svc = make_fixed_rate_service({"tether": Decimal("90.00")})
        from app.api.service import _build_coin_options
        opts = [o for o in _build_coin_options("200.00", wallets, svc) if o["label"] == "USDT"]

        html = _coin_tab_buttons(opts)

        self.assertEqual(html.count(">USDT<"), 1)  # one group header, not one per network
        self.assertIn("TRC20 (Tron)", html)
        self.assertIn("BEP20 (BSC)", html)
        self.assertIn("ERC20 (Ethereum)", html)

    def test_single_network_assets_share_one_row(self) -> None:
        from app.api.pages import _coin_tab_buttons

        wallets = {"ton": "UQ1", "eth": "0x1", "btc": "bc1"}
        svc = make_fixed_rate_service({"toncoin": Decimal("600.00"), "ethereum": Decimal("310000.00"), "bitcoin": Decimal("9000000.00")})
        from app.api.service import _build_coin_options
        opts = [o for o in _build_coin_options("200.00", wallets, svc) if o["label"] in {"TON", "ETH", "BTC"}]

        html = _coin_tab_buttons(opts)

        self.assertEqual(html.count('class="coin-group-chips"'), 1)
        self.assertEqual(html.count('class="coin-group"'), 0)  # no asset header for singles


class SettingsCryptoWalletsTest(unittest.TestCase):
    def _base(self) -> dict[str, str]:
        return {
            "VPN_ROUTER_TOKEN_SECRET": "test-secret-with-enough-len",
            "VPN_ROUTER_ADMIN_TOKEN": "test-admin-with-enough-len",
            "PUBLIC_BASE_URL": "http://127.0.0.1:8080",
        }

    def test_wallets_parsed_from_env(self) -> None:
        from app.core.settings import load_settings

        env = {
            **self._base(),
            "CRYPTO_WALLET_TRC20": "TXxx",
            "CRYPTO_WALLET_TON": "UQxx",
            "CRYPTO_WALLET_ETH": "0xAB",
            "CRYPTO_WALLET_BTC": "bc1xx",
        }

        s = load_settings(env)

        self.assertEqual(s.crypto_wallets["trc20"], "TXxx")
        self.assertEqual(s.crypto_wallets["ton"], "UQxx")
        self.assertEqual(s.crypto_wallets["eth"], "0xAB")
        self.assertEqual(s.crypto_wallets["btc"], "bc1xx")

    def test_legacy_usdt_address_backfilled_into_wallets(self) -> None:
        from app.core.settings import load_settings

        env = {**self._base(), "CRYPTO_USDT_TRC20_ADDRESS": "TLegacy"}

        s = load_settings(env)

        self.assertEqual(s.crypto_wallets.get("trc20"), "TLegacy")

    def test_rate_provider_default_is_coingecko(self) -> None:
        from app.core.settings import load_settings

        s = load_settings(self._base())

        self.assertEqual(s.crypto_rate_provider, "coingecko")

    def test_rate_provider_fixed(self) -> None:
        from app.core.settings import load_settings

        env = {**self._base(), "CRYPTO_RATE_PROVIDER": "fixed"}

        s = load_settings(env)

        self.assertEqual(s.crypto_rate_provider, "fixed")

    def test_invalid_rate_provider_raises(self) -> None:
        from app.core.settings import SettingsError, load_settings

        env = {**self._base(), "CRYPTO_RATE_PROVIDER": "binance"}

        with self.assertRaises(SettingsError):
            load_settings(env)


if __name__ == "__main__":
    unittest.main()
