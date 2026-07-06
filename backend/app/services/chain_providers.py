from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Protocol as TypingProtocol
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_REQUEST_TIMEOUT = 15

# TronGrid only_confirmed returns solidified transactions (19+ blocks), so we
# report an effectively unlimited confirmation count for them.
_TRON_CONFIRMED = 10**9

HttpGet = Callable[[str, dict[str, str]], Any]


@dataclass(frozen=True)
class IncomingTransfer:
    tx_id: str
    from_address: str
    to_address: str
    amount: Decimal
    symbol: str
    confirmations: int


class ChainProvider(TypingProtocol):
    def incoming_transfers(self, address: str) -> list[IncomingTransfer]:
        ...


class ChainProviderError(RuntimeError):
    pass


def _default_http_get(url: str, headers: dict[str, str]) -> Any:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
            return json.load(response)
    except (URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise ChainProviderError(f"chain API request failed: {exc}") from exc


class TronProvider:
    """Incoming TRC20 token transfers to an address via TronGrid."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.trongrid.io",
        http_get: HttpGet | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_get = http_get or _default_http_get

    def incoming_transfers(self, address: str) -> list[IncomingTransfer]:
        url = (
            f"{self.base_url}/v1/accounts/{address}/transactions/trc20"
            "?only_confirmed=true&only_to=true&limit=100"
        )
        headers = {"TRON-PRO-API-KEY": self.api_key} if self.api_key else {}
        payload = self.http_get(url, headers)
        items = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []
        transfers: list[IncomingTransfer] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            token_info = item.get("token_info")
            token_info = token_info if isinstance(token_info, dict) else {}
            amount = _token_amount(item.get("value"), token_info.get("decimals"))
            tx_id = str(item.get("transaction_id", "")).strip()
            if amount is None or not tx_id:
                continue
            transfers.append(
                IncomingTransfer(
                    tx_id=tx_id,
                    from_address=str(item.get("from", "")),
                    to_address=str(item.get("to", "")),
                    amount=amount,
                    symbol=str(token_info.get("symbol", "")).upper(),
                    confirmations=_TRON_CONFIRMED,
                )
            )
        return transfers


class EtherscanProvider:
    """Incoming ERC20/BEP20 token or native transfers via Etherscan v2 API."""

    def __init__(
        self,
        chain_id: int,
        api_key: str | None = None,
        native: bool = False,
        native_symbol: str = "ETH",
        base_url: str = "https://api.etherscan.io/v2/api",
        http_get: HttpGet | None = None,
    ) -> None:
        self.chain_id = chain_id
        self.api_key = api_key
        self.native = native
        self.native_symbol = native_symbol.upper()
        self.base_url = base_url
        self.http_get = http_get or _default_http_get

    def incoming_transfers(self, address: str) -> list[IncomingTransfer]:
        params = {
            "chainid": str(self.chain_id),
            "module": "account",
            "action": "txlist" if self.native else "tokentx",
            "address": address,
            "page": "1",
            "offset": "100",
            "sort": "desc",
        }
        if self.api_key:
            params["apikey"] = self.api_key
        payload = self.http_get(f"{self.base_url}?{urlencode(params)}", {})
        items = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []
        transfers: list[IncomingTransfer] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            transfer = self._native_transfer(item) if self.native else self._token_transfer(item)
            if transfer is not None:
                transfers.append(transfer)
        return transfers

    def _token_transfer(self, item: dict[str, Any]) -> IncomingTransfer | None:
        amount = _token_amount(item.get("value"), item.get("tokenDecimal"))
        tx_id = str(item.get("hash", "")).strip()
        if amount is None or not tx_id:
            return None
        return IncomingTransfer(
            tx_id=tx_id,
            from_address=str(item.get("from", "")).lower(),
            to_address=str(item.get("to", "")).lower(),
            amount=amount,
            symbol=str(item.get("tokenSymbol", "")).upper(),
            confirmations=_int(item.get("confirmations")),
        )

    def _native_transfer(self, item: dict[str, Any]) -> IncomingTransfer | None:
        if str(item.get("isError", "0")) != "0":
            return None
        amount = _token_amount(item.get("value"), 18)
        tx_id = str(item.get("hash", "")).strip()
        if amount is None or not tx_id or amount == 0:
            return None
        return IncomingTransfer(
            tx_id=tx_id,
            from_address=str(item.get("from", "")).lower(),
            to_address=str(item.get("to", "")).lower(),
            amount=amount,
            symbol=self.native_symbol,
            confirmations=_int(item.get("confirmations")),
        )


# Accepted token symbols per coin id (BscScan reports Binance-Peg USDT as BSC-USD).
COIN_SYMBOLS: dict[str, frozenset[str]] = {
    "usdt_trc20": frozenset({"USDT"}),
    "usdc_trc20": frozenset({"USDC"}),
    "usdt_bep20": frozenset({"USDT", "BSC-USD"}),
    "eth": frozenset({"ETH"}),
}


def build_providers(
    trongrid_api_key: str | None,
    etherscan_api_key: str | None,
    http_get: HttpGet | None = None,
) -> dict[str, ChainProvider]:
    """Map coin_id -> provider for coins with live chain watching (TRON + Ethereum/BSC)."""
    providers: dict[str, ChainProvider] = {}
    tron = TronProvider(api_key=trongrid_api_key, http_get=http_get)
    providers["usdt_trc20"] = tron
    providers["usdc_trc20"] = tron
    if etherscan_api_key:
        providers["usdt_bep20"] = EtherscanProvider(chain_id=56, api_key=etherscan_api_key, http_get=http_get)
        providers["eth"] = EtherscanProvider(chain_id=1, api_key=etherscan_api_key, native=True, http_get=http_get)
    return providers


def _token_amount(raw_value: Any, raw_decimals: Any) -> Decimal | None:
    try:
        value = int(str(raw_value))
        decimals = int(str(raw_decimals))
    except (TypeError, ValueError):
        return None
    if value < 0 or decimals < 0:
        return None
    try:
        return Decimal(value).scaleb(-decimals)
    except InvalidOperation:
        return None


def _int(raw_value: Any) -> int:
    try:
        return int(str(raw_value))
    except (TypeError, ValueError):
        return 0
