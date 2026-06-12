from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.domain.models import (
    NodeHealth,
    NodeHealthEvent,
    NodeStatus,
    Platform,
    Protocol,
    ReceiptClaim,
    ShadowsocksOptions,
    Subscription,
    User,
    VlessOptions,
    VpnNode,
    new_id,
)


class InMemoryRepository:
    def __init__(self) -> None:
        self.users_by_id: dict[str, User] = {}
        self.users_by_device_id: dict[str, str] = {}
        self.subscriptions_by_user_id: dict[str, Subscription] = {}
        self.nodes_by_id: dict[str, VpnNode] = {}
        self.health_events_by_node_id: dict[str, list[NodeHealthEvent]] = {}
        self._seed_nodes()

    def get_or_create_user(self, device_id: str) -> User:
        existing_user_id = self.users_by_device_id.get(device_id)
        if existing_user_id:
            return self.users_by_id[existing_user_id]

        user = User(id=new_id("usr"), device_id=device_id)
        self.users_by_id[user.id] = user
        self.users_by_device_id[device_id] = user.id
        return user

    def get_user(self, user_id: str) -> User | None:
        return self.users_by_id.get(user_id)

    def export_user_data(self, user_id: str) -> dict[str, object] | None:
        user = self.get_user(user_id)
        if user is None:
            return None
        subscription = self.subscriptions_by_user_id.get(user_id)
        return {
            "user": {
                "id": user.id,
                "device_id": user.device_id,
                "created_at": user.created_at.isoformat(),
            },
            "subscription": _subscription_export(subscription) if subscription else None,
        }

    def delete_user(self, user_id: str) -> bool:
        user = self.users_by_id.pop(user_id, None)
        if user is None:
            return False
        self.users_by_device_id.pop(user.device_id, None)
        self.subscriptions_by_user_id.pop(user_id, None)
        return True

    def activate_subscription(self, claim: ReceiptClaim) -> Subscription:
        user = self.get_or_create_user(claim.device_id)
        if claim.platform != Platform.SANDBOX and len(claim.receipt.strip()) < 24:
            raise ValueError("receipt is too short for non-sandbox validation")

        subscription = Subscription(
            user_id=user.id,
            platform=claim.platform,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            product_id=claim.product_id,
            original_transaction_id=f"{claim.platform.value}:{hash(claim.receipt)}",
        )
        self.subscriptions_by_user_id[user.id] = subscription
        return subscription

    def get_active_subscription(self, user_id: str) -> Subscription | None:
        subscription = self.subscriptions_by_user_id.get(user_id)
        if subscription and subscription.is_active():
            return subscription
        return None

    def list_nodes(self) -> list[VpnNode]:
        return list(self.nodes_by_id.values())

    def get_node(self, node_id: str) -> VpnNode | None:
        return self.nodes_by_id.get(node_id)

    def upsert_node(self, node: VpnNode) -> None:
        self.nodes_by_id[node.id] = node

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
        node = self.nodes_by_id.get(node_id)
        if node is None:
            return None
        updated = replace(
            node,
            health_score=health_score,
            status=status or node.status,
            latency_ms=latency_ms if latency_ms is not None else node.latency_ms,
            success_rate=success_rate if success_rate is not None else node.success_rate,
            health=health or node.health,
            last_check_at=last_check_at or node.last_check_at,
        )
        self.nodes_by_id[node_id] = updated
        return updated

    def add_node_health_event(self, event: NodeHealthEvent) -> None:
        self.health_events_by_node_id.setdefault(event.node_id, []).insert(0, event)

    def list_node_health_events(self, node_id: str, limit: int = 50) -> list[NodeHealthEvent]:
        return self.health_events_by_node_id.get(node_id, [])[:limit]

    def prune_node_health_events(self, cutoff: datetime) -> int:
        deleted = 0
        for node_id, events in list(self.health_events_by_node_id.items()):
            kept = [event for event in events if event.checked_at >= cutoff]
            deleted += len(events) - len(kept)
            if kept:
                self.health_events_by_node_id[node_id] = kept
            else:
                self.health_events_by_node_id.pop(node_id, None)
        return deleted

    def _seed_nodes(self) -> None:
        nodes = [
            VpnNode(
                id="node_eu_1",
                tag="vless-eu-1",
                region="eu-central",
                provider="hetzner",
                country_code="DE",
                host="eu1.vpn.example.com",
                port=443,
                protocol=Protocol.VLESS,
                status=NodeStatus.ACTIVE,
                priority=10,
                health_score=98,
                latency_ms=55,
                success_rate=0.99,
                options=VlessOptions(
                    uuid="00000000-0000-4000-8000-000000000001",
                    server_name="cdn.example.com",
                    transport={"type": "ws", "path": "/api/cdn"},
                ),
            ),
            VpnNode(
                id="node_eu_2",
                tag="ss-eu-2",
                region="eu-west",
                provider="digitalocean",
                country_code="NL",
                host="eu2.vpn.example.com",
                port=8443,
                protocol=Protocol.SHADOWSOCKS,
                status=NodeStatus.ACTIVE,
                priority=20,
                health_score=92,
                latency_ms=70,
                success_rate=0.97,
                options=ShadowsocksOptions(
                    method="2022-blake3-aes-128-gcm",
                    password="replace-with-user-or-node-secret",
                ),
            ),
            VpnNode(
                id="node_us_1",
                tag="vless-us-1",
                region="us-east",
                provider="aws",
                country_code="US",
                host="us1.vpn.example.com",
                port=443,
                protocol=Protocol.VLESS,
                status=NodeStatus.DRAINING,
                priority=30,
                health_score=70,
                latency_ms=140,
                success_rate=0.92,
                options=VlessOptions(
                    uuid="00000000-0000-4000-8000-000000000003",
                    server_name="assets.example.com",
                ),
            ),
            VpnNode(
                id="node_bad_1",
                tag="vless-disabled",
                region="asia",
                provider="scaleway",
                country_code="SG",
                host="sg1.vpn.example.com",
                port=443,
                protocol=Protocol.VLESS,
                status=NodeStatus.DISABLED,
                priority=40,
                health_score=10,
                latency_ms=350,
                success_rate=0.10,
                health=NodeHealth.DISABLED,
                options=VlessOptions(
                    uuid="00000000-0000-4000-8000-000000000004",
                    server_name="assets.example.com",
                ),
            ),
        ]
        self.nodes_by_id = {node.id: node for node in nodes}


def _subscription_export(subscription: Subscription) -> dict[str, object]:
    return {
        "platform": subscription.platform.value,
        "expires_at": subscription.expires_at.isoformat(),
        "product_id": subscription.product_id,
        "original_transaction_id": subscription.original_transaction_id,
        "active": subscription.is_active(),
    }
