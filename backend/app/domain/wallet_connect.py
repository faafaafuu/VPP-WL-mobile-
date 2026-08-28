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
from typing import Any

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
