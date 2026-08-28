from __future__ import annotations

import unittest
from decimal import Decimal
from typing import Any

from app.services.chain_providers import (
    COIN_SYMBOLS,
    BitcoinProvider,
    ChainProviderError,
    EtherscanProvider,
    SolanaProvider,
    TonProvider,
    TronProvider,
    build_providers,
)

_TRON_PAYLOAD = {
    "data": [
        {
            "transaction_id": "tron-tx-1",
            "from": "TSenderAddr",
            "to": "TWalletAddr",
            "value": "2030000",
            "token_info": {"symbol": "USDT", "decimals": 6},
        },
        {
            # malformed entry must be skipped
            "transaction_id": "",
            "value": "oops",
            "token_info": {},
        },
    ]
}

_TOKENTX_PAYLOAD = {
    "status": "1",
    "result": [
        {
            "hash": "0xToken1",
            "from": "0xSender",
            "to": "0xWallet",
            "value": "2030000000000000000",
            "tokenSymbol": "BSC-USD",
            "tokenDecimal": "18",
            "confirmations": "35",
        }
    ],
}

_TXLIST_PAYLOAD = {
    "status": "1",
    "result": [
        {
            "hash": "0xNative1",
            "from": "0xSender",
            "to": "0xWallet",
            "value": "1250000000000000",
            "confirmations": "20",
            "isError": "0",
        },
        {
            "hash": "0xFailed",
            "from": "0xSender",
            "to": "0xWallet",
            "value": "1250000000000000",
            "confirmations": "20",
            "isError": "1",
        },
    ],
}


def _http(payload: Any, seen: list[str] | None = None):
    def http_get(url: str, headers: dict[str, str]) -> Any:
        if seen is not None:
            seen.append(url)
        return payload

    return http_get


class BitcoinProviderTest(unittest.TestCase):
    _TXS = [
        {
            "txid": "btc-tx-1",
            "vin": [{"prevout": {"scriptpubkey_address": "bc1sender"}}],
            "vout": [
                {"scriptpubkey_address": "bc1wallet", "value": 250000},
                {"scriptpubkey_address": "bc1change", "value": 900000},
            ],
            "status": {"confirmed": True, "block_height": 800000},
        },
        {
            "txid": "btc-tx-outgoing",
            "vin": [{"prevout": {"scriptpubkey_address": "bc1wallet"}}],
            "vout": [{"scriptpubkey_address": "bc1someoneelse", "value": 100000}],
            "status": {"confirmed": True, "block_height": 800001},
        },
    ]

    def _provider(self) -> BitcoinProvider:
        def http_get(url: str, headers: dict[str, Any]) -> Any:
            return 800010 if url.endswith("/blocks/tip/height") else self._TXS

        return BitcoinProvider(http_get=http_get)

    def test_counts_only_outputs_paying_our_address(self) -> None:
        transfers = self._provider().incoming_transfers("bc1wallet")

        self.assertEqual(len(transfers), 1)
        transfer = transfers[0]
        self.assertEqual(transfer.tx_id, "btc-tx-1")
        self.assertEqual(transfer.amount, Decimal("0.0025"))  # change output excluded
        self.assertEqual(transfer.symbol, "BTC")
        self.assertEqual(transfer.from_address, "bc1sender")

    def test_confirmations_counted_from_chain_tip(self) -> None:
        transfers = self._provider().incoming_transfers("bc1wallet")

        self.assertEqual(transfers[0].confirmations, 11)  # 800010 - 800000 + 1

    def test_unconfirmed_transaction_has_zero_confirmations(self) -> None:
        def http_get(url: str, headers: dict[str, Any]) -> Any:
            if url.endswith("/blocks/tip/height"):
                return 800010
            return [
                {
                    "txid": "btc-mempool",
                    "vin": [],
                    "vout": [{"scriptpubkey_address": "bc1wallet", "value": 250000}],
                    "status": {"confirmed": False},
                }
            ]

        transfers = BitcoinProvider(http_get=http_get).incoming_transfers("bc1wallet")

        self.assertEqual(transfers[0].confirmations, 0)


class TonProviderTest(unittest.TestCase):
    def test_parses_incoming_transfers(self) -> None:
        payload = {
            "ok": True,
            "result": [
                {
                    "transaction_id": {"hash": "ton-tx-1"},
                    "in_msg": {"source": "UQsender", "destination": "UQwallet", "value": "1500000000"},
                },
                {
                    # own outgoing message: no source
                    "transaction_id": {"hash": "ton-tx-out"},
                    "in_msg": {"source": "", "destination": "UQwallet", "value": "500000000"},
                },
            ],
        }
        transfers = TonProvider(http_get=_http(payload)).incoming_transfers("UQwallet")

        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0].tx_id, "ton-tx-1")
        self.assertEqual(transfers[0].amount, Decimal("1.5"))
        self.assertEqual(transfers[0].symbol, "TON")

    def test_api_error_raises(self) -> None:
        provider = TonProvider(http_get=_http({"ok": False, "error": "rate limited"}))

        with self.assertRaises(ChainProviderError):
            provider.incoming_transfers("UQwallet")


class SolanaProviderTest(unittest.TestCase):
    def _provider(self, signatures: Any, tx: Any) -> SolanaProvider:
        def http_post(url: str, payload: dict[str, Any]) -> Any:
            if payload["method"] == "getSignaturesForAddress":
                return {"result": signatures}
            return {"result": tx}

        return SolanaProvider(http_post=http_post)

    def test_positive_balance_delta_is_an_incoming_transfer(self) -> None:
        signatures = [{"signature": "sol-sig-1", "err": None, "confirmationStatus": "finalized"}]
        tx = {
            "meta": {"err": None, "preBalances": [1000, 5_000_000_000], "postBalances": [1000, 5_020_000_000]},
            "transaction": {"message": {"accountKeys": [{"pubkey": "SolSender"}, {"pubkey": "SolWallet"}]}},
        }

        transfers = self._provider(signatures, tx).incoming_transfers("SolWallet")

        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0].amount, Decimal("0.02"))
        self.assertEqual(transfers[0].symbol, "SOL")
        self.assertEqual(transfers[0].from_address, "SolSender")

    def test_outgoing_transfer_is_ignored(self) -> None:
        signatures = [{"signature": "sol-sig-2", "err": None, "confirmationStatus": "finalized"}]
        tx = {
            "meta": {"err": None, "preBalances": [5_000_000_000, 1000], "postBalances": [4_900_000_000, 1000]},
            "transaction": {"message": {"accountKeys": [{"pubkey": "SolWallet"}, {"pubkey": "SolOther"}]}},
        }

        self.assertEqual(self._provider(signatures, tx).incoming_transfers("SolWallet"), [])

    def test_failed_transactions_are_skipped(self) -> None:
        signatures = [{"signature": "sol-sig-3", "err": {"InstructionError": []}}]

        self.assertEqual(self._provider(signatures, {}).incoming_transfers("SolWallet"), [])


class TronProviderTest(unittest.TestCase):
    def test_parses_trc20_transfers(self) -> None:
        urls: list[str] = []
        provider = TronProvider(api_key="key", http_get=_http(_TRON_PAYLOAD, urls))

        transfers = provider.incoming_transfers("TWalletAddr")

        self.assertEqual(len(transfers), 1)
        transfer = transfers[0]
        self.assertEqual(transfer.tx_id, "tron-tx-1")
        self.assertEqual(transfer.amount, Decimal("2.03"))
        self.assertEqual(transfer.symbol, "USDT")
        self.assertEqual(transfer.to_address, "TWalletAddr")
        self.assertIn("only_confirmed=true", urls[0])
        self.assertIn("TWalletAddr", urls[0])

    def test_empty_payload_returns_no_transfers(self) -> None:
        provider = TronProvider(http_get=_http({}))

        self.assertEqual(provider.incoming_transfers("TWalletAddr"), [])


class EtherscanProviderTest(unittest.TestCase):
    def test_parses_token_transfers(self) -> None:
        urls: list[str] = []
        provider = EtherscanProvider(chain_id=56, api_key="key", http_get=_http(_TOKENTX_PAYLOAD, urls))

        transfers = provider.incoming_transfers("0xWallet")

        self.assertEqual(len(transfers), 1)
        transfer = transfers[0]
        self.assertEqual(transfer.amount, Decimal("2.03"))
        self.assertEqual(transfer.symbol, "BSC-USD")
        self.assertEqual(transfer.confirmations, 35)
        self.assertIn("chainid=56", urls[0])
        self.assertIn("action=tokentx", urls[0])

    def test_parses_native_transfers_and_skips_failed(self) -> None:
        urls: list[str] = []
        provider = EtherscanProvider(chain_id=1, api_key="key", native=True, http_get=_http(_TXLIST_PAYLOAD, urls))

        transfers = provider.incoming_transfers("0xWallet")

        self.assertEqual(len(transfers), 1)
        transfer = transfers[0]
        self.assertEqual(transfer.tx_id, "0xNative1")
        self.assertEqual(transfer.amount, Decimal("0.00125"))
        self.assertEqual(transfer.symbol, "ETH")
        self.assertIn("action=txlist", urls[0])


    def test_api_refusal_raises_instead_of_reporting_no_transfers(self) -> None:
        """Etherscan reports refusals as status "0" with the reason in
        `result` as a plain string. Reading that as an empty transfer list
        made a dead watcher look like a quiet one — real BEP20 payments went
        unconfirmed with nothing in the logs."""
        refusal = {
            "status": "0",
            "message": "NOTOK",
            "result": "Free API access is not supported for this chain",
        }
        provider = EtherscanProvider(chain_id=56, api_key="key", http_get=_http(refusal))

        with self.assertRaises(ChainProviderError):
            provider.incoming_transfers("0xWallet")

    def test_genuinely_empty_result_is_not_an_error(self) -> None:
        empty = {"status": "0", "message": "No transactions found", "result": []}
        provider = EtherscanProvider(chain_id=1, api_key="key", native=True, http_get=_http(empty))

        self.assertEqual(provider.incoming_transfers("0xWallet"), [])


class BuildProvidersTest(unittest.TestCase):
    def test_keyless_chains_are_always_available(self) -> None:
        """Tron, Bitcoin, TON and Solana all have free public APIs, so these
        coins can be offered even with no API keys configured at all."""
        providers = build_providers(None, None)

        for coin_id in ("usdt_trc20", "usdc_trc20", "btc", "ton", "sol"):
            self.assertIn(coin_id, providers)
        self.assertNotIn("eth", providers)
        self.assertNotIn("usdt_bep20", providers)

    def test_etherscan_coins_require_api_key(self) -> None:
        providers = build_providers(None, "etherscan-key")

        for coin_id in ("eth", "usdt_erc20", "usdc_erc20", "usdt_polygon", "usdc_polygon"):
            self.assertIn(coin_id, providers)

    def test_every_watched_coin_has_accepted_symbols(self) -> None:
        """A coin with a provider but no COIN_SYMBOLS entry can never match a
        transfer — the watcher bails out before comparing amounts, so the
        payment would silently never confirm."""
        providers = build_providers("tron-key", "etherscan-key", bep20_enabled=True)

        for coin_id in providers:
            self.assertIn(coin_id, COIN_SYMBOLS, f"{coin_id} has a provider but no accepted symbols")

    def test_bep20_is_off_unless_explicitly_enabled(self) -> None:
        """Etherscan's v2 free tier refuses chain 56 outright, so BEP20 must
        not be watched — and therefore not offered — by default. Offering it
        meant customers paid to an address nothing was checking."""
        self.assertNotIn("usdt_bep20", build_providers(None, "etherscan-key"))
        self.assertIn("usdt_bep20", build_providers(None, "etherscan-key", bep20_enabled=True))


if __name__ == "__main__":
    unittest.main()
