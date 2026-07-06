from __future__ import annotations

import unittest
from decimal import Decimal
from typing import Any

from app.services.chain_providers import (
    EtherscanProvider,
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


class BuildProvidersTest(unittest.TestCase):
    def test_tron_always_available(self) -> None:
        providers = build_providers(None, None)

        self.assertIn("usdt_trc20", providers)
        self.assertIn("usdc_trc20", providers)
        self.assertNotIn("eth", providers)
        self.assertNotIn("usdt_bep20", providers)

    def test_etherscan_coins_require_api_key(self) -> None:
        providers = build_providers(None, "etherscan-key")

        self.assertIn("eth", providers)
        self.assertIn("usdt_bep20", providers)


if __name__ == "__main__":
    unittest.main()
