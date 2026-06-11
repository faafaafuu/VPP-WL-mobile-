from __future__ import annotations

import os
from typing import Protocol as TypingProtocol

from app.domain.models import NodeStatus, ReceiptClaim, Subscription, User, VpnNode
from app.repositories.memory import InMemoryRepository
from app.repositories.sqlite import SqliteRepository


class Repository(TypingProtocol):
    def get_or_create_user(self, device_id: str) -> User:
        ...

    def get_user(self, user_id: str) -> User | None:
        ...

    def activate_subscription(self, claim: ReceiptClaim) -> Subscription:
        ...

    def get_active_subscription(self, user_id: str) -> Subscription | None:
        ...

    def list_nodes(self) -> list[VpnNode]:
        ...

    def get_node(self, node_id: str) -> VpnNode | None:
        ...

    def upsert_node(self, node: VpnNode) -> None:
        ...

    def update_node_health(self, node_id: str, health_score: int, status: NodeStatus | None = None) -> VpnNode | None:
        ...


def create_repository() -> Repository:
    backend = os.getenv("VPN_ROUTER_REPOSITORY", "sqlite").lower()
    if backend == "memory":
        return InMemoryRepository()
    if backend == "sqlite":
        database_path = os.getenv("VPN_ROUTER_SQLITE_PATH", "data/vpn-router.db")
        return SqliteRepository(database_path)
    raise ValueError(f"unsupported repository backend: {backend}")
