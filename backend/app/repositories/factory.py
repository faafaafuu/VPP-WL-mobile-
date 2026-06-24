from __future__ import annotations

import os
from typing import Protocol as TypingProtocol

from datetime import datetime

from app.domain.models import (
    AdminAuditEvent,
    CommercialSubscription,
    NodeHealth,
    NodeHealthEvent,
    NodeStatus,
    ReceiptClaim,
    Subscription,
    User,
    VpnNode,
)
from app.repositories.memory import InMemoryRepository
from app.repositories.sqlite import SqliteRepository


class Repository(TypingProtocol):
    def get_or_create_user(self, device_id: str) -> User:
        ...

    def get_user(self, user_id: str) -> User | None:
        ...

    def export_user_data(self, user_id: str) -> dict[str, object] | None:
        ...

    def delete_user(self, user_id: str) -> bool:
        ...

    def activate_subscription(self, claim: ReceiptClaim) -> Subscription:
        ...

    def get_active_subscription(self, user_id: str) -> Subscription | None:
        ...

    def create_commercial_subscription(
        self,
        token: str,
        tariff_id: str,
        payment_id: str | None = None,
    ) -> CommercialSubscription:
        ...

    def get_commercial_subscription(self, token: str) -> CommercialSubscription | None:
        ...

    def activate_commercial_subscription(
        self,
        token: str,
        duration_days: int,
        payment_id: str | None = None,
    ) -> CommercialSubscription | None:
        ...

    def list_nodes(self) -> list[VpnNode]:
        ...

    def get_node(self, node_id: str) -> VpnNode | None:
        ...

    def upsert_node(self, node: VpnNode) -> None:
        ...

    def update_node_health(
        self,
        node_id: str,
        health_score: int,
        status: NodeStatus | None = None,
        latency_ms: int | None = None,
        success_rate: float | None = None,
        health: NodeHealth | None = None,
        last_check_at: datetime | None = None,
    ) -> VpnNode | None:
        ...

    def add_node_health_event(self, event: NodeHealthEvent) -> None:
        ...

    def list_node_health_events(self, node_id: str, limit: int = 50) -> list[NodeHealthEvent]:
        ...

    def prune_node_health_events(self, cutoff: datetime) -> int:
        ...

    def count_node_health_events_by_result(self) -> dict[str, int]:
        ...

    def add_admin_audit_event(self, event: AdminAuditEvent) -> None:
        ...

    def list_admin_audit_events(self, limit: int = 50) -> list[AdminAuditEvent]:
        ...

    def prune_admin_audit_events(self, cutoff: datetime) -> int:
        ...

    def count_admin_audit_events(self) -> int:
        ...


def create_repository() -> Repository:
    backend = os.getenv("VPN_ROUTER_REPOSITORY", "sqlite").lower()
    if backend == "memory":
        return InMemoryRepository()
    if backend == "sqlite":
        database_path = os.getenv("VPN_ROUTER_SQLITE_PATH", "data/vpn-router.db")
        return SqliteRepository(database_path)
    raise ValueError(f"unsupported repository backend: {backend}")
