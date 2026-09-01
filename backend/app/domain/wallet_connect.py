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
    """The amount exactly as the invoice states it, in positional notation.

    No normalize(): it strips trailing zeros, so an invoice for 0.00002260
    produced a link carrying 0.0000226. The two are the same number, but the
    buyer comparing the wallet sheet against the invoice sees two amounts,
    and the watcher waits on the string it was given.
    """
    return format(value, "f")


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




# --- wallet buttons ---------------------------------------------------------
#
# One button per popular wallet: tapping it opens that wallet with the amount,
# recipient and network already filled in, so the buyer only confirms.
#
# Where a wallet publishes its own payment deep link (MetaMask, Trust,
# Tonkeeper, Tonhub) the button uses it and lands in that exact wallet. The
# rest register their chain's standard payment scheme instead, so the button
# carries the same request and the phone opens whichever of them is installed
# — which is what "if you have it, it opens" means in practice. Nothing here
# is invented: a wallet with no documented link and no scheme (TronLink) gets
# no button at all, because one that misfires is worse than none.
#
# Icons are inline SVG marks: an icon fetched over the network is exactly what
# a filtering mobile connection drops, leaving a sheet of blank squares. Where
# a logo is plain geometry it is drawn; otherwise it is a lettered badge in the
# brand colour rather than a bad imitation.


def _svg(body: str, bg: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        f'<rect width="32" height="32" rx="8" fill="{bg}"/>{body}</svg>'
    )
    return "data:image/svg+xml," + quote(svg, safe="")


def _mono(letter: str, bg: str, fg: str = "#fff") -> str:
    return _svg(
        f'<text x="16" y="22" text-anchor="middle" fill="{fg}" font-family="monospace" '
        f'font-size="17" font-weight="700">{letter}</text>',
        bg,
    )


WALLET_ICONS: dict[str, str] = {
    "metamask": _mono("M", "#f6851b"),
    "trust": _svg('<path d="M16 6l8 3v7c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V9z" fill="#fff"/>', "#3375bb"),
    "coinbase": _svg(
        '<circle cx="16" cy="16" r="9" fill="#fff"/>'
        '<rect x="12.5" y="12.5" width="7" height="7" rx="1.6" fill="#0052ff"/>', "#0052ff"),
    "okx": _svg(
        '<g fill="#fff"><rect x="6" y="6" width="6" height="6"/><rect x="20" y="6" width="6" height="6"/>'
        '<rect x="13" y="13" width="6" height="6"/><rect x="6" y="20" width="6" height="6"/>'
        '<rect x="20" y="20" width="6" height="6"/></g>', "#111"),
    "bitget": _mono("B", "#00d0d8"),
    "safepal": _mono("S", "#4a21ef"),
    "tonkeeper": _svg('<circle cx="16" cy="16" r="10" fill="#fff"/><path d="M11 12h10l-5 12z" fill="#0098ea"/>', "#0098ea"),
    "tonhub": _mono("T", "#1c8fe3"),
    "mytonwallet": _mono("MT", "#2a6df4"),
    "phantom": _svg(
        '<path d="M8 19a8 8 0 0116 0v6l-2.7-2-2.6 2-2.7-2-2.7 2-2.6-2L8 25z" fill="#fff"/>'
        '<circle cx="13.5" cy="17" r="1.7" fill="#ab9ff2"/><circle cx="19" cy="17" r="1.7" fill="#ab9ff2"/>',
        "#ab9ff2"),
    "solflare": _mono("S", "#fc7227"),
    "backpack": _mono("B", "#e33e3f"),
    "exodus": _mono("E", "#1f2033"),
    "bluewallet": _mono("BW", "#1c6bd6"),
    "muun": _mono("M", "#2474cd"),
}

# Trust Wallet addresses an asset by SLIP-44 coin id, with "_t<contract>" for
# a token on that chain.
_TRUST_ASSET = {1: "c60", 137: "c966", 56: "c20000714"}


def wallet_links(coin_id: str, address: str, amount: str) -> list[dict[str, str]]:
    """Popular wallets for this coin, each as a ready link that opens the
    wallet on its send screen with this exact transfer filled in."""
    spec = TRANSFER_SPECS.get(coin_id)
    if spec is None or not address:
        return []
    uri = payment_uri(coin_id, address, amount)
    units = payment_units(coin_id, amount)
    if not uri or not units:
        return []
    plain = _plain(Decimal(str(amount).replace(",", ".")))
    addr = quote(address, safe="")

    if spec.kind == "evm":
        # MetaMask takes the EIP-681 request itself, minus the scheme.
        deep = uri.split(":", 1)[1]
        asset = _TRUST_ASSET.get(spec.chain_id or 0)
        if asset and spec.contract:
            asset = f"{asset}_t{spec.contract}"
        links = [_w("metamask", "MetaMask", f"https://metamask.app.link/send/{deep}")]
        if asset:
            links.append(_w("trust", "Trust Wallet",
                            f"https://link.trustwallet.com/send?asset={asset}&address={addr}&amount={plain}"))
        links += [_w(i, n, uri) for i, n in (
            ("coinbase", "Coinbase Wallet"), ("okx", "OKX Wallet"),
            ("bitget", "Bitget Wallet"), ("safepal", "SafePal"))]
        return links

    if coin_id == "ton":
        return [
            _w("tonkeeper", "Tonkeeper", f"https://app.tonkeeper.com/transfer/{addr}?amount={units}"),
            _w("tonhub", "Tonhub", f"https://tonhub.com/transfer/{addr}?amount={units}"),
            _w("mytonwallet", "MyTonWallet", uri),
        ]

    if coin_id == "sol":
        return [_w(i, n, uri) for i, n in (
            ("phantom", "Phantom"), ("solflare", "Solflare"), ("backpack", "Backpack"))]

    if coin_id == "btc":
        return [
            _w("trust", "Trust Wallet",
               f"https://link.trustwallet.com/send?asset=c0&address={addr}&amount={plain}"),
            _w("exodus", "Exodus", uri),
            _w("bluewallet", "BlueWallet", uri),
            _w("muun", "Muun", uri),
        ]

    # Tron: no payment scheme exists and TronLink's mobile link format is
    # undocumented, so the panel keeps it to the extension plus manual copy.
    return []


def _w(wallet_id: str, name: str, url: str) -> dict[str, str]:
    return {"id": wallet_id, "name": name, "url": url}
