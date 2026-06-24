from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Mapping

from app.domain.node_config import NodeConfigError, parse_nodes_from_env
from app.domain.models import VpnNode
from app.domain.tariffs import Tariff, parse_tariffs


PLACEHOLDER_VALUES = {
    "replace-with-random-32-byte-secret",
    "replace-with-random-admin-token",
    "replace-with-yookassa-shop-id",
    "replace-with-yookassa-secret-key",
}


class SettingsError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    token_secret: str
    admin_token: str
    host: str = "127.0.0.1"
    port: int = 8080
    cors_origins: tuple[str, ...] = ()
    allowed_product_ids: tuple[str, ...] = ("vpn.monthly",)
    rate_limit_per_minute: int = 120
    audit_retention_days: int = 30
    hsts_enabled: bool = False
    yookassa_shop_id: str | None = None
    yookassa_secret_key: str | None = None
    yookassa_return_url: str | None = None
    product_prices_rub: dict[str, str] = field(default_factory=lambda: {"vpn.monthly": "399.00"})
    public_base_url: str = "http://127.0.0.1:8080"
    checkout_mode: str = "mock"
    tariffs: tuple[Tariff, ...] = field(default_factory=parse_tariffs)
    nodes: tuple[VpnNode, ...] = field(default_factory=tuple)
    crypto_usdt_trc20_address: str | None = None
    crypto_usdt_rate_rub: str = "90.00"
    crypto_wallets: dict[str, str] = field(default_factory=dict)
    crypto_rate_provider: str = "coingecko"
    crypto_enable_testnet: bool = False


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    source = env or os.environ
    token_secret = _required_secret(source, "VPN_ROUTER_TOKEN_SECRET", min_length=16)
    admin_token = _required_secret(source, "VPN_ROUTER_ADMIN_TOKEN", min_length=16)
    host = source.get("VPN_ROUTER_HOST", "127.0.0.1")
    port = _port(source.get("VPN_ROUTER_PORT", "8080"))
    cors_origins = _csv(source.get("VPN_ROUTER_CORS_ORIGINS", ""))
    allowed_product_ids = _csv(source.get("VPN_ROUTER_ALLOWED_PRODUCT_IDS", "vpn.monthly"))
    if not allowed_product_ids:
        raise SettingsError("VPN_ROUTER_ALLOWED_PRODUCT_IDS must not be empty")
    rate_limit_per_minute = _non_negative_int(
        source.get("VPN_ROUTER_RATE_LIMIT_PER_MINUTE", "120"),
        "VPN_ROUTER_RATE_LIMIT_PER_MINUTE",
    )
    audit_retention_days = _non_negative_int(
        source.get("VPN_ROUTER_AUDIT_RETENTION_DAYS", "30"),
        "VPN_ROUTER_AUDIT_RETENTION_DAYS",
    )
    hsts_enabled = _bool(source.get("VPN_ROUTER_HSTS_ENABLED", "false"), "VPN_ROUTER_HSTS_ENABLED")
    yookassa_shop_id = _optional_secret(source, "VPN_ROUTER_YOOKASSA_SHOP_ID", min_length=3)
    yookassa_secret_key = _optional_secret(source, "VPN_ROUTER_YOOKASSA_SECRET_KEY", min_length=16)
    yookassa_return_url = _optional_url(source.get("VPN_ROUTER_YOOKASSA_RETURN_URL", ""))
    if bool(yookassa_shop_id) != bool(yookassa_secret_key):
        raise SettingsError("VPN_ROUTER_YOOKASSA_SHOP_ID and VPN_ROUTER_YOOKASSA_SECRET_KEY must be set together")
    if yookassa_shop_id and not yookassa_return_url:
        raise SettingsError("VPN_ROUTER_YOOKASSA_RETURN_URL is required when YooKassa credentials are set")
    product_prices_rub = _product_prices(
        source.get("VPN_ROUTER_PRODUCT_PRICES_RUB", "vpn.monthly:200.00,vpn.1m:200.00,vpn.3m:500.00,vpn.6m:900.00")
    )
    public_base_url = _required_url(source.get("PUBLIC_BASE_URL", f"http://127.0.0.1:{port}"), "PUBLIC_BASE_URL")
    checkout_mode = source.get("CHECKOUT_MODE", "mock").strip().lower()
    if checkout_mode not in {"mock", "yookassa", "crypto_manual"}:
        raise SettingsError("CHECKOUT_MODE must be mock, yookassa, or crypto_manual")
    try:
        tariffs = parse_tariffs(source.get("VPN_ROUTER_TARIFFS", ""), product_prices_rub)
    except ValueError as exc:
        raise SettingsError(f"VPN_ROUTER_TARIFFS invalid: {exc}") from exc
    try:
        nodes = tuple(parse_nodes_from_env(source))
    except NodeConfigError as exc:
        raise SettingsError(str(exc)) from exc
    # crypto wallets: CRYPTO_WALLET_TRC20, _TON, _ETH, _BTC
    # CRYPTO_USDT_TRC20_ADDRESS is a legacy alias for CRYPTO_WALLET_TRC20
    crypto_wallets = _parse_crypto_wallets(source)
    crypto_usdt_trc20_address = crypto_wallets.get("trc20") or source.get("CRYPTO_USDT_TRC20_ADDRESS", "").strip() or None
    if checkout_mode == "crypto_manual" and not crypto_wallets and not crypto_usdt_trc20_address:
        raise SettingsError(
            "At least one crypto wallet required for CHECKOUT_MODE=crypto_manual "
            "(set CRYPTO_WALLET_TRC20, CRYPTO_WALLET_TON, CRYPTO_WALLET_ETH or CRYPTO_WALLET_BTC)"
        )
    # backfill legacy address into wallets dict if only legacy env is set
    if crypto_usdt_trc20_address and "trc20" not in crypto_wallets:
        crypto_wallets = {**crypto_wallets, "trc20": crypto_usdt_trc20_address}
    crypto_usdt_rate_rub = _decimal_str(
        source.get("CRYPTO_USDT_RATE_RUB", "90.00"), "CRYPTO_USDT_RATE_RUB"
    )
    crypto_rate_provider_raw = source.get("CRYPTO_RATE_PROVIDER", "coingecko").strip().lower()
    if crypto_rate_provider_raw not in {"coingecko", "fixed"}:
        raise SettingsError("CRYPTO_RATE_PROVIDER must be coingecko or fixed")
    crypto_enable_testnet = _bool(source.get("CRYPTO_ENABLE_TESTNET", "false"), "CRYPTO_ENABLE_TESTNET")
    return Settings(
        token_secret=token_secret,
        admin_token=admin_token,
        host=host,
        port=port,
        cors_origins=cors_origins,
        allowed_product_ids=allowed_product_ids,
        rate_limit_per_minute=rate_limit_per_minute,
        audit_retention_days=audit_retention_days,
        hsts_enabled=hsts_enabled,
        yookassa_shop_id=yookassa_shop_id,
        yookassa_secret_key=yookassa_secret_key,
        yookassa_return_url=yookassa_return_url,
        product_prices_rub=product_prices_rub,
        public_base_url=public_base_url,
        checkout_mode=checkout_mode,
        tariffs=tariffs,
        nodes=nodes,
        crypto_usdt_trc20_address=crypto_usdt_trc20_address,
        crypto_usdt_rate_rub=crypto_usdt_rate_rub,
        crypto_wallets=crypto_wallets,
        crypto_rate_provider=crypto_rate_provider_raw,
        crypto_enable_testnet=crypto_enable_testnet,
    )


def _required_secret(source: Mapping[str, str], key: str, min_length: int) -> str:
    value = source.get(key, "").strip()
    if not value:
        raise SettingsError(f"{key} is required")
    if value in PLACEHOLDER_VALUES:
        raise SettingsError(f"{key} must not use placeholder value")
    if len(value) < min_length:
        raise SettingsError(f"{key} must be at least {min_length} characters")
    return value


def _optional_secret(source: Mapping[str, str], key: str, min_length: int) -> str | None:
    value = source.get(key, "").strip()
    if not value:
        return None
    if value in PLACEHOLDER_VALUES:
        raise SettingsError(f"{key} must not use placeholder value")
    if len(value) < min_length:
        raise SettingsError(f"{key} must be at least {min_length} characters")
    return value


def _port(raw_value: str) -> int:
    try:
        port = int(raw_value)
    except ValueError as exc:
        raise SettingsError("VPN_ROUTER_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise SettingsError("VPN_ROUTER_PORT must be between 1 and 65535")
    return port


def _csv(raw_value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())


def _optional_url(raw_value: str) -> str | None:
    value = raw_value.strip()
    if not value:
        return None
    if value in PLACEHOLDER_VALUES:
        raise SettingsError("VPN_ROUTER_YOOKASSA_RETURN_URL must not use placeholder value")
    if not value.startswith(("https://", "http://")):
        raise SettingsError("VPN_ROUTER_YOOKASSA_RETURN_URL must be an absolute URL")
    return value


def _required_url(raw_value: str, key: str) -> str:
    value = raw_value.strip().rstrip("/")
    if not value:
        raise SettingsError(f"{key} is required")
    if not value.startswith(("https://", "http://")):
        raise SettingsError(f"{key} must be an absolute URL")
    return value


def _product_prices(raw_value: str) -> dict[str, str]:
    prices: dict[str, str] = {}
    for item in _csv(raw_value):
        if ":" not in item:
            raise SettingsError("VPN_ROUTER_PRODUCT_PRICES_RUB items must use product_id:amount")
        product_id, raw_amount = (part.strip() for part in item.split(":", 1))
        if not product_id:
            raise SettingsError("VPN_ROUTER_PRODUCT_PRICES_RUB product_id must not be empty")
        try:
            amount = Decimal(raw_amount)
        except InvalidOperation as exc:
            raise SettingsError("VPN_ROUTER_PRODUCT_PRICES_RUB amount must be decimal RUB value") from exc
        if amount <= 0:
            raise SettingsError("VPN_ROUTER_PRODUCT_PRICES_RUB amount must be positive")
        prices[product_id] = f"{amount:.2f}"
    if not prices:
        raise SettingsError("VPN_ROUTER_PRODUCT_PRICES_RUB must not be empty")
    return prices


def _non_negative_int(raw_value: str, key: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise SettingsError(f"{key} must be an integer") from exc
    if value < 0:
        raise SettingsError(f"{key} must be non-negative")
    return value


def _bool(raw_value: str, key: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise SettingsError(f"{key} must be true or false")


def _decimal_str(raw_value: str, key: str) -> str:
    try:
        amount = Decimal(raw_value.strip())
    except InvalidOperation as exc:
        raise SettingsError(f"{key} must be a decimal number") from exc
    if amount <= 0:
        raise SettingsError(f"{key} must be positive")
    return f"{amount:.2f}"


def _parse_crypto_wallets(source: Mapping[str, str]) -> dict[str, str]:
    wallets: dict[str, str] = {}
    for key in ("trc20", "ton", "eth", "btc"):
        addr = source.get(f"CRYPTO_WALLET_{key.upper()}", "").strip()
        if addr:
            wallets[key] = addr
    return wallets
