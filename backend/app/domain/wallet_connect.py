"""What the invoice page needs to hand a ready-made transfer to a wallet.

Copying an address and typing an amount by hand is where crypto payments go
wrong: a truncated address, a rounded amount, the wrong network. Every entry
here lets the browser build the transfer itself, so the buyer only confirms.

Three mechanisms, picked per chain by what actually exists:

* ``evm``  — EIP-1193 injected provider (MetaMask, Trust, OKX, Rabby …).
  Native coins go out as a plain value transfer; tokens as an ERC-20
  ``transfer(address,uint256)`` call built in the page.
* ``tron`` — TronLink's injected ``tronWeb``, same idea via a TRC-20 call.
* ``uri``  — BTC/TON/SOL have no injected-provider standard, but they do have
  a universal payment-URI scheme every wallet app registers. Opening one
  prefills recipient and amount in the wallet the buyer already uses.

``token_decimals`` is the on-chain unit scale, deliberately unrelated to
``Coin.decimals``, which only controls how many digits we *display*.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

# Read by wallet_addEthereumChain when the buyer's wallet doesn't know the
# chain yet. Public RPCs, keyless — used only by the wallet, never by us.
_EVM_CHAINS: dict[int, dict[str, Any]] = {
    1: {
        "chainId": "0x1",
        "chainName": "Ethereum Mainnet",
        "nativeCurrency": {"name": "Ether", "symbol": "ETH", "decimals": 18},
        "rpcUrls": ["https://ethereum-rpc.publicnode.com"],
        "blockExplorerUrls": ["https://etherscan.io"],
    },
    56: {
        "chainId": "0x38",
        "chainName": "BNB Smart Chain",
        "nativeCurrency": {"name": "BNB", "symbol": "BNB", "decimals": 18},
        "rpcUrls": ["https://bsc-rpc.publicnode.com"],
        "blockExplorerUrls": ["https://bscscan.com"],
    },
    137: {
        "chainId": "0x89",
        "chainName": "Polygon Mainnet",
        "nativeCurrency": {"name": "POL", "symbol": "POL", "decimals": 18},
        "rpcUrls": ["https://polygon-rpc.com"],
        "blockExplorerUrls": ["https://polygonscan.com"],
    },
}


@dataclass(frozen=True)
class TransferSpec:
    kind: str  # "evm" | "tron" | "uri"
    token_decimals: int
    chain_id: int | None = None
    contract: str | None = None  # None = the chain's native coin
    uri_template: str | None = None  # {address} and {amount} placeholders
    uri_decimals: int = 0  # amount scaled by 10**this in the URI (0 = as-is)
    explorer_tx: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"kind": self.kind, "token_decimals": self.token_decimals}
        if self.chain_id is not None:
            data["chain_id"] = self.chain_id
            data["chain_hex"] = hex(self.chain_id)
            data["add_chain"] = _EVM_CHAINS[self.chain_id]
        if self.contract:
            data["contract"] = self.contract
        if self.uri_template:
            data["uri_template"] = self.uri_template
            data["uri_decimals"] = self.uri_decimals
        if self.explorer_tx:
            data["explorer_tx"] = self.explorer_tx
        return data


TRANSFER_SPECS: dict[str, TransferSpec] = {
    "eth": TransferSpec("evm", 18, chain_id=1, explorer_tx="https://etherscan.io/tx/"),
    "usdt_erc20": TransferSpec(
        "evm", 6, chain_id=1,
        contract="0xdAC17F958D2ee523a2206206994597C13D831ec7",
        explorer_tx="https://etherscan.io/tx/",
    ),
    "usdc_erc20": TransferSpec(
        "evm", 6, chain_id=1,
        contract="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        explorer_tx="https://etherscan.io/tx/",
    ),
    "usdt_polygon": TransferSpec(
        "evm", 6, chain_id=137,
        contract="0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        explorer_tx="https://polygonscan.com/tx/",
    ),
    # Native (Circle-issued) USDC on Polygon, not the bridged USDC.e — both
    # settle to the same address and the watcher accepts either symbol.
    "usdc_polygon": TransferSpec(
        "evm", 6, chain_id=137,
        contract="0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        explorer_tx="https://polygonscan.com/tx/",
    ),
    "usdt_bep20": TransferSpec(
        "evm", 18, chain_id=56,
        contract="0x55d398326f99059fF775485246999027B3197955",
        explorer_tx="https://bscscan.com/tx/",
    ),
    "usdt_trc20": TransferSpec(
        "tron", 6,
        contract="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        explorer_tx="https://tronscan.org/#/transaction/",
    ),
    "usdc_trc20": TransferSpec(
        "tron", 6,
        contract="TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8",
        explorer_tx="https://tronscan.org/#/transaction/",
    ),
    "btc": TransferSpec(
        "uri", 8,
        uri_template="bitcoin:{address}?amount={amount}",
        explorer_tx="https://mempool.space/tx/",
    ),
    # Tonkeeper and friends take the amount in nanotons, hence uri_decimals=9.
    "ton": TransferSpec(
        "uri", 9,
        uri_template="ton://transfer/{address}?amount={amount}",
        uri_decimals=9,
        explorer_tx="https://tonviewer.com/transaction/",
    ),
    # Solana Pay — Phantom, Solflare and Backpack all register this scheme.
    "sol": TransferSpec(
        "uri", 9,
        uri_template="solana:{address}?amount={amount}",
        explorer_tx="https://solscan.io/tx/",
    ),
}


def transfer_spec(coin_id: str) -> dict[str, Any] | None:
    spec = TRANSFER_SPECS.get(coin_id)
    return spec.as_dict() if spec else None


def payment_uri(coin_id: str, address: str, amount: str) -> str | None:
    """A one-tap payment link for this exact transfer, or None if the chain
    has no such scheme.

    Built here rather than in the page so the QR code and the button always
    encode the same request, and so the amount is scaled by exact decimal
    arithmetic — a float round-trip of, say, 0.00095238 ETH sends a number
    the payment watcher will not recognise.

    EVM chains use EIP-681, which every major mobile wallet opens straight
    on its send screen with recipient, network and amount filled in.
    """
    spec = TRANSFER_SPECS.get(coin_id)
    if spec is None or not address:
        return None
    try:
        value = Decimal(str(amount).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if value <= 0:
        return None

    if spec.kind == "uri" and spec.uri_template:
        scaled = _scale(value, spec.uri_decimals) if spec.uri_decimals else _plain(value)
        return spec.uri_template.replace("{address}", quote(address, safe="")).replace("{amount}", scaled)

    if spec.kind == "evm":
        units = _scale(value, spec.token_decimals)
        if spec.contract:
            return (
                f"ethereum:{spec.contract}@{spec.chain_id}/transfer"
                f"?address={quote(address, safe='')}&uint256={units}"
            )
        return f"ethereum:{quote(address, safe='')}@{spec.chain_id}?value={units}"

    if spec.kind == "tron":
        # Tron has no equivalent scheme; TronLink is driven by the page itself.
        return None
    return None


def _scale(value: Decimal, decimals: int) -> str:
    return str(int(value.scaleb(decimals).to_integral_value()))


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


def payment_units(coin_id: str, amount: str) -> str | None:
    """The transfer amount in the chain's smallest unit, as an exact integer
    string — what a wallet link or an ERC-20 call has to carry."""
    spec = TRANSFER_SPECS.get(coin_id)
    if spec is None:
        return None
    try:
        value = Decimal(str(amount).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if value <= 0:
        return None
    decimals = spec.uri_decimals if (spec.kind == "uri" and spec.uri_decimals) else spec.token_decimals
    return _scale(value, decimals)


# --- wallet catalogue -------------------------------------------------------
#
# On desktop, EIP-6963 lets installed wallets announce themselves with their
# own name and icon, so that list is always the accurate one. Mobile browsers
# inject nothing, and the page previously fell back to exactly two hardcoded
# names with no icons. This catalogue is that fallback: the wallets whose
# deep links are documented and stable, drawn as small inline marks so the
# sheet needs no external requests (an image the network blocks is worse than
# none). Where a logo is not simple geometry we use a lettered badge in the
# brand colour rather than a bad imitation of it.

def _svg(body: str, bg: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        f'<rect width="32" height="32" rx="8" fill="{bg}"/>{body}</svg>'
    )
    return "data:image/svg+xml," + quote(svg, safe="")


def _mono_icon(letter: str, bg: str, fg: str = "#fff") -> str:
    body = (
        f'<text x="16" y="22" text-anchor="middle" fill="{fg}" '
        f'font-family="monospace" font-size="17" font-weight="700">{letter}</text>'
    )
    return _svg(body, bg)


_ICON_COINBASE = _svg('<circle cx="16" cy="16" r="9" fill="#fff"/><rect x="12.5" y="12.5" width="7" height="7" rx="1.6" fill="#0052ff"/>', "#0052ff")
_ICON_OKX = _svg(
    '<g fill="#fff">'
    '<rect x="6" y="6" width="6" height="6"/><rect x="20" y="6" width="6" height="6"/>'
    '<rect x="13" y="13" width="6" height="6"/>'
    '<rect x="6" y="20" width="6" height="6"/><rect x="20" y="20" width="6" height="6"/>'
    '</g>', "#111")
_ICON_TRUST = _svg('<path d="M16 6l8 3v7c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V9z" fill="#fff"/>', "#3375bb")
_ICON_TONKEEPER = _svg('<circle cx="16" cy="16" r="10" fill="#fff"/><path d="M11 12h10l-5 12z" fill="#0098ea"/>', "#0098ea")

@dataclass(frozen=True)
class Wallet:
    id: str
    name: str
    icon: str
    # "dapp" opens our page inside the wallet's own browser; "uri" hands the
    # wallet the payment request directly, landing on its send screen.
    link_kind: str
    template: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name, "icon": self.icon,
                "link_kind": self.link_kind, "template": self.template}


# {url} = this page, url-encoded. {host_path} = host + path, unencoded.
_EVM_WALLETS = (
    Wallet("metamask", "MetaMask", _mono_icon("M", "#f6851b"), "dapp", "https://metamask.app.link/dapp/{host_path}"),
    Wallet("trust", "Trust Wallet", _ICON_TRUST, "dapp", "https://link.trustwallet.com/open_url?coin_id=60&url={url}"),
    Wallet("coinbase", "Coinbase Wallet", _ICON_COINBASE, "dapp", "https://go.cb-w.com/dapp?cb_url={url}"),
    Wallet("okx", "OKX Wallet", _ICON_OKX, "dapp", "okx://wallet/dapp/url?dappUrl={url}"),
    Wallet("bitget", "Bitget Wallet", _mono_icon("B", "#00d0d8"), "dapp", "https://bkcode.vip?action=dapp&url={url}"),
    Wallet("safepal", "SafePal", _mono_icon("S", "#4a21ef"), "dapp", "https://link.safepal.io/dapp?url={url}"),
    Wallet("imtoken", "imToken", _mono_icon("i", "#11c4d1"), "dapp", "imtokenv2://navigate/DappView?url={url}"),
)

_TON_WALLETS = (
    Wallet("tonkeeper", "Tonkeeper", _ICON_TONKEEPER, "uri", "https://app.tonkeeper.com/transfer/{address}?amount={units}"),
)

# TronLink is driven through its injected tronWeb, and its mobile deep-link
# format is undocumented enough that a button built on it would misfire more
# often than it worked — so Tron gets the extension path and a QR, not a
# button that pretends.
_TRON_WALLETS: tuple[Wallet, ...] = ()

# Phantom, Solflare and Backpack all consume the same solana: request, so a
# button per wallet would be theatre: the OS picks whichever is installed.
# They are named in URI_WALLET_HINTS instead.
_SOL_WALLETS: tuple[Wallet, ...] = ()


def wallet_catalogue() -> dict[str, list[dict[str, str]]]:
    """Per-chain fallback wallets, keyed by TransferSpec.kind plus the
    coin-specific groups the page looks up by coin id."""
    return {
        "evm": [w.as_dict() for w in _EVM_WALLETS],
        "tron": [w.as_dict() for w in _TRON_WALLETS],
        "ton": [w.as_dict() for w in _TON_WALLETS],
        "sol": [w.as_dict() for w in _SOL_WALLETS],
        "btc": [],
    }


# Wallets known to open a bitcoin:/solana: request, listed as plain text
# because they all consume the very same URI — separate buttons would only
# pretend the choice mattered.
URI_WALLET_HINTS: dict[str, str] = {
    "btc": "Trust Wallet, Exodus, BlueWallet, Muun, Electrum, Cake Wallet",
    "sol": "Phantom, Solflare, Backpack",
    "ton": "Tonkeeper, MyTonWallet, Tonhub",
}
