from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


PLACEHOLDER_VALUES = {
    "replace-with-random-32-byte-secret",
    "replace-with-random-admin-token",
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


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    source = env or os.environ
    token_secret = _required_secret(source, "VPN_ROUTER_TOKEN_SECRET", min_length=16)
    admin_token = _required_secret(source, "VPN_ROUTER_ADMIN_TOKEN", min_length=16)
    host = source.get("VPN_ROUTER_HOST", "127.0.0.1")
    port = _port(source.get("VPN_ROUTER_PORT", "8080"))
    cors_origins = _csv(source.get("VPN_ROUTER_CORS_ORIGINS", ""))
    return Settings(
        token_secret=token_secret,
        admin_token=admin_token,
        host=host,
        port=port,
        cors_origins=cors_origins,
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
