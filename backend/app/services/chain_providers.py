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
HttpPost = Callable[[str, dict[str, Any]], Any]

# TON and Solana only return committed transactions, so like Tron they report
# an effectively unlimited confirmation count.
_COMMITTED = 10**9


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


def _default_http_post(url: str, payload: dict[str, Any]) -> Any:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
            return json.load(response)
    except (URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise ChainProviderError(f"chain RPC request failed: {exc}") from exc


class BitcoinProvider:
    """Incoming BTC transfers via the mempool.space REST API (no key needed).

    Only outputs paying our address count, and each transaction is collapsed
    into one transfer carrying the total it paid us — a wallet that splits a
    payment across several outputs still has to match the invoiced amount.
    """

    def __init__(
        self,
        base_url: str = "https://mempool.space/api",
        http_get: HttpGet | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.http_get = http_get or _default_http_get

    def incoming_transfers(self, address: str) -> list[IncomingTransfer]:
        payload = self.http_get(f"{self.base_url}/address/{address}/txs", {})
        if not isinstance(payload, list):
            return []
        tip = self._tip_height()
        transfers: list[IncomingTransfer] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            tx_id = str(item.get("txid", "")).strip()
            if not tx_id:
                continue
            sats = 0
            for vout in item.get("vout", []) or []:
                if isinstance(vout, dict) and str(vout.get("scriptpubkey_address", "")) == address:
                    sats += _int(vout.get("value"))
            if sats <= 0:
                continue
            status = item.get("status") if isinstance(item.get("status"), dict) else {}
            confirmations = 0
            if status.get("confirmed"):
                height = _int(status.get("block_height"))
                confirmations = max(tip - height + 1, 1) if tip and height else 1
            vin = item.get("vin", []) or []
            sender = ""
            if vin and isinstance(vin[0], dict):
                prevout = vin[0].get("prevout")
                if isinstance(prevout, dict):
                    sender = str(prevout.get("scriptpubkey_address", ""))
            transfers.append(
                IncomingTransfer(
                    tx_id=tx_id,
                    from_address=sender,
                    to_address=address,
                    amount=Decimal(sats).scaleb(-8),
                    symbol="BTC",
                    confirmations=confirmations,
                )
            )
        return transfers

    def _tip_height(self) -> int:
        try:
            return _int(self.http_get(f"{self.base_url}/blocks/tip/height", {}))
        except ChainProviderError:
            return 0


class TonProvider:
    """Incoming native TON transfers via the toncenter API (no key needed)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://toncenter.com/api/v2",
        http_get: HttpGet | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_get = http_get or _default_http_get

    def incoming_transfers(self, address: str) -> list[IncomingTransfer]:
        params = {"address": address, "limit": "100"}
        if self.api_key:
            params["api_key"] = self.api_key
        payload = self.http_get(f"{self.base_url}/getTransactions?{urlencode(params)}", {})
        if not isinstance(payload, dict):
            return []
        if not payload.get("ok", False):
            raise ChainProviderError(f"toncenter rejected the request: {payload.get('error')}")
        items = payload.get("result")
        if not isinstance(items, list):
            return []
        transfers: list[IncomingTransfer] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            in_msg = item.get("in_msg")
            if not isinstance(in_msg, dict):
                continue
            # An in_msg with no source is the account's own outgoing message.
            source = str(in_msg.get("source", "")).strip()
            if not source:
                continue
            amount = _token_amount(in_msg.get("value"), 9)
            tx_id = str((item.get("transaction_id") or {}).get("hash", "")).strip()
            if amount is None or amount == 0 or not tx_id:
                continue
            transfers.append(
                IncomingTransfer(
                    tx_id=tx_id,
                    from_address=source,
                    to_address=str(in_msg.get("destination", "")),
                    amount=amount,
                    symbol="TON",
                    confirmations=_COMMITTED,
                )
            )
        return transfers


class SolanaProvider:
    """Incoming native SOL transfers via the public Solana JSON-RPC.

    Solana has no "list incoming transfers" call, so this walks the recent
    signatures for the address and reads each transaction's balance delta
    for that account — a positive delta is money arriving.
    """

    def __init__(
        self,
        base_url: str = "https://api.mainnet-beta.solana.com",
        http_post: HttpPost | None = None,
        signature_limit: int = 25,
    ) -> None:
        self.base_url = base_url
        self.http_post = http_post or _default_http_post
        self.signature_limit = signature_limit

    def _rpc(self, method: str, params: list[Any]) -> Any:
        payload = self.http_post(
            self.base_url,
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        if not isinstance(payload, dict):
            return None
        if "error" in payload:
            raise ChainProviderError(f"solana RPC error: {payload['error']}")
        return payload.get("result")

    def latest_blockhash(self) -> str:
        """A blockhash recent enough for a wallet to sign against — a
        transaction built on a stale one is rejected outright."""
        result = self._rpc("getLatestBlockhash", [{"commitment": "finalized"}])
        blockhash = ((result or {}).get("value") or {}).get("blockhash")
        if not blockhash:
            raise ChainProviderError("solana RPC returned no blockhash")
        return str(blockhash)

    def incoming_transfers(self, address: str) -> list[IncomingTransfer]:
        signatures = self._rpc(
            "getSignaturesForAddress", [address, {"limit": self.signature_limit}]
        )
        if not isinstance(signatures, list):
            return []
        transfers: list[IncomingTransfer] = []
        for entry in signatures:
            if not isinstance(entry, dict) or entry.get("err") is not None:
                continue
            signature = str(entry.get("signature", "")).strip()
            if not signature:
                continue
            transfer = self._transfer_for(signature, address, entry.get("confirmationStatus"))
            if transfer is not None:
                transfers.append(transfer)
        return transfers

    def _transfer_for(self, signature: str, address: str, status: Any) -> IncomingTransfer | None:
        tx = self._rpc(
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
        )
        if not isinstance(tx, dict):
            return None
        meta = tx.get("meta") if isinstance(tx.get("meta"), dict) else {}
        if meta.get("err") is not None:
            return None
        keys = (((tx.get("transaction") or {}).get("message") or {}).get("accountKeys")) or []
        index = None
        for i, key in enumerate(keys):
            pubkey = key.get("pubkey") if isinstance(key, dict) else key
            if str(pubkey) == address:
                index = i
                break
        if index is None:
            return None
        pre = meta.get("preBalances") or []
        post = meta.get("postBalances") or []
        if index >= len(pre) or index >= len(post):
            return None
        delta = _int(post[index]) - _int(pre[index])
        if delta <= 0:
            return None
        sender = ""
        if keys:
            first = keys[0]
            sender = str(first.get("pubkey") if isinstance(first, dict) else first)
        return IncomingTransfer(
            tx_id=signature,
            from_address=sender,
            to_address=address,
            amount=Decimal(delta).scaleb(-9),
            symbol="SOL",
            confirmations=_COMMITTED if status == "finalized" else 1,
        )


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
        if isinstance(items, str):
            # Etherscan reports refusals ("Free API access is not supported for
            # this chain", rate limits, bad key) as status "0" with the reason
            # in `result` as a string. Treating that as "no transfers" silently
            # stops confirming real payments — the watcher must see an error.
            raise ChainProviderError(f"chain API rejected the request: {items}")
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


# Accepted token symbols per coin id. Explorers name the same asset
# differently per chain: BscScan reports Binance-Peg USDT as BSC-USD, and
# Polygon carries both native USDC and the bridged USDC.e.
COIN_SYMBOLS: dict[str, frozenset[str]] = {
    "usdt_trc20": frozenset({"USDT"}),
    "usdc_trc20": frozenset({"USDC"}),
    "usdt_bep20": frozenset({"USDT", "BSC-USD"}),
    "usdt_erc20": frozenset({"USDT"}),
    "usdc_erc20": frozenset({"USDC"}),
    "usdt_polygon": frozenset({"USDT", "USDT.e"}),
    "usdc_polygon": frozenset({"USDC", "USDC.e"}),
    "eth": frozenset({"ETH"}),
    "btc": frozenset({"BTC"}),
    "ton": frozenset({"TON"}),
    "sol": frozenset({"SOL"}),
}


def build_providers(
    trongrid_api_key: str | None,
    etherscan_api_key: str | None,
    http_get: HttpGet | None = None,
    bep20_enabled: bool = False,
    http_post: HttpPost | None = None,
    ton_api_key: str | None = None,
) -> dict[str, ChainProvider]:
    """Map coin_id -> provider for coins whose incoming payments we can
    actually confirm on-chain.

    Only coins listed here get offered on the invoice page — anything else
    would take the customer's money with no way to notice it arrived.

    Tron, Bitcoin, TON and Solana need no API key at all; Ethereum and
    Polygon reuse the Etherscan v2 key. BSC (chain 56) is the one exception
    and stays opt-in: Etherscan's free tier refuses that chain outright
    ("Free API access is not supported for this chain"), so it needs a paid
    key plus CRYPTO_BEP20_ENABLED=1.
    """
    providers: dict[str, ChainProvider] = {}
    tron = TronProvider(api_key=trongrid_api_key, http_get=http_get)
    providers["usdt_trc20"] = tron
    providers["usdc_trc20"] = tron
    providers["btc"] = BitcoinProvider(http_get=http_get)
    providers["ton"] = TonProvider(api_key=ton_api_key, http_get=http_get)
    providers["sol"] = SolanaProvider(http_post=http_post)
    if etherscan_api_key:
        providers["eth"] = EtherscanProvider(chain_id=1, api_key=etherscan_api_key, native=True, http_get=http_get)
        providers["usdt_erc20"] = EtherscanProvider(chain_id=1, api_key=etherscan_api_key, http_get=http_get)
        providers["usdc_erc20"] = providers["usdt_erc20"]
        providers["usdt_polygon"] = EtherscanProvider(chain_id=137, api_key=etherscan_api_key, http_get=http_get)
        providers["usdc_polygon"] = providers["usdt_polygon"]
        if bep20_enabled:
            providers["usdt_bep20"] = EtherscanProvider(chain_id=56, api_key=etherscan_api_key, http_get=http_get)
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
