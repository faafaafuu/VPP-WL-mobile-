from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4


class Platform(str, Enum):
    APPLE = "apple"
    GOOGLE = "google"
    YOOKASSA = "yookassa"
    SANDBOX = "sandbox"


class NodeStatus(str, Enum):
    ACTIVE = "active"
    DRAINING = "draining"
    DISABLED = "disabled"


class NodeHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class Protocol(str, Enum):
    VLESS = "vless"
    SHADOWSOCKS = "shadowsocks"
    WIREGUARD = "wireguard"
    HYSTERIA2 = "hysteria2"


@dataclass(frozen=True)
class User:
    id: str
    device_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Subscription:
    user_id: str
    platform: Platform
    expires_at: datetime
    product_id: str
    original_transaction_id: str

    def is_active(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.expires_at > current


@dataclass(frozen=True)
class CommercialSubscription:
    token: str
    tariff_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    payment_id: str | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.status == "active" and self.expires_at is not None and self.expires_at > current


@dataclass(frozen=True)
class VlessOptions:
    uuid: str
    server_name: str
    flow: str | None = None
    transport: dict[str, Any] | None = None
    reality: dict[str, Any] | None = None
    security: str = "reality"
    public_key: str | None = None
    short_id: str | None = None
    fingerprint: str = "chrome"
    label: str | None = None


@dataclass(frozen=True)
class ShadowsocksOptions:
    method: str
    password: str


@dataclass(frozen=True)
class WireGuardOptions:
    private_key: str
    peer_public_key: str
    local_address: list[str]
    mtu: int = 1420
    reserved: list[int] | None = None


@dataclass(frozen=True)
class Hysteria2Options:
    password: str
    server_name: str


@dataclass(frozen=True)
class VpnNode:
    id: str
    tag: str
    region: str
    provider: str
    country_code: str
    host: str
    port: int
    protocol: Protocol
    status: NodeStatus
    priority: int
    weight: int = 100
    health_score: int = 100
    latency_ms: int | None = None
    success_rate: float = 1.0
    last_check_at: datetime | None = None
    health: NodeHealth = NodeHealth.HEALTHY
    options: VlessOptions | ShadowsocksOptions | WireGuardOptions | Hysteria2Options | None = None

    def is_usable(self) -> bool:
        return (
            self.status in {NodeStatus.ACTIVE, NodeStatus.DRAINING}
            and self.health == NodeHealth.HEALTHY
            and self.health_score >= 40
            and self.success_rate >= 0.75
        )


@dataclass(frozen=True)
class ReceiptClaim:
    platform: Platform
    receipt: str
    device_id: str
    product_id: str = "vpn.monthly"


@dataclass(frozen=True)
class NodeHealthEvent:
    id: str
    node_id: str
    checked_at: datetime
    old_health: NodeHealth | None
    new_health: NodeHealth
    old_status: NodeStatus | None
    new_status: NodeStatus
    old_success_rate: float | None
    new_success_rate: float
    old_latency_ms: int | None
    new_latency_ms: int | None
    health_score: int
    error: str | None = None


@dataclass(frozen=True)
class AdminAuditEvent:
    id: str
    occurred_at: datetime
    action: str
    target_type: str
    target_id: str
    result: str
    details: dict[str, Any] = field(default_factory=dict)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def new_subscription_token() -> str:
    return token_urlsafe(32)
