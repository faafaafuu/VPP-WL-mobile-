from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.domain.models import (
    AdminAuditEvent,
    CommercialSubscription,
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
from app.domain.receipt_fingerprint import receipt_transaction_id


class InMemoryRepository:
    def __init__(self, nodes: list[VpnNode] | None = None) -> None:
        self.users_by_id: dict[str, User] = {}
        self.users_by_device_id: dict[str, str] = {}
        self.subscriptions_by_user_id: dict[str, Subscription] = {}
        self.commercial_subscriptions_by_token: dict[str, CommercialSubscription] = {}
        self.nodes_by_id: dict[str, VpnNode] = {}
        self.health_events_by_node_id: dict[str, list[NodeHealthEvent]] = {}
        self.admin_audit_events: list[AdminAuditEvent] = []
        self._seed_nodes(nodes)

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
        if claim.platform in {Platform.APPLE, Platform.GOOGLE} and len(claim.receipt.strip()) < 24:
            raise ValueError("receipt is too short for non-sandbox validation")

        subscription = Subscription(
            user_id=user.id,
            platform=claim.platform,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            product_id=claim.product_id,
            original_transaction_id=receipt_transaction_id(claim.platform, claim.receipt),
        )
        self.subscriptions_by_user_id[user.id] = subscription
        return subscription

    def get_active_subscription(self, user_id: str) -> Subscription | None:
        subscription = self.subscriptions_by_user_id.get(user_id)
        if subscription and subscription.is_active():
            return subscription
        return None

    def create_commercial_subscription(
        self,
        token: str,
        tariff_id: str,
        payment_id: str | None = None,
    ) -> CommercialSubscription:
        now = datetime.now(timezone.utc)
        subscription = CommercialSubscription(
            token=token,
            tariff_id=tariff_id,
            payment_id=payment_id,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self.commercial_subscriptions_by_token[token] = subscription
        return subscription

    def get_commercial_subscription(self, token: str) -> CommercialSubscription | None:
        return self.commercial_subscriptions_by_token.get(token)

    def activate_commercial_subscription(
        self,
        token: str,
        duration_days: int,
        payment_id: str | None = None,
        paid_tx: str | None = None,
        payer: str | None = None,
    ) -> CommercialSubscription | None:
        subscription = self.commercial_subscriptions_by_token.get(token)
        if subscription is None:
            return None
        now = datetime.now(timezone.utc)
        base = subscription.expires_at if subscription.expires_at and subscription.expires_at > now else now
        updated = replace(
            subscription,
            status="active",
            expires_at=base + timedelta(days=duration_days),
            payment_id=payment_id or subscription.payment_id,
            paid_tx=paid_tx or subscription.paid_tx,
            payer=payer or subscription.payer,
            updated_at=now,
        )
        self.commercial_subscriptions_by_token[token] = updated
        return updated

    def set_payment_intent(
        self,
        token: str,
        coin_id: str,
        amount: str,
        address: str,
    ) -> CommercialSubscription | None:
        subscription = self.commercial_subscriptions_by_token.get(token)
        if subscription is None:
            return None
        updated = replace(
            subscription,
            pay_coin_id=coin_id,
            pay_amount=amount,
            pay_address=address,
            updated_at=datetime.now(timezone.utc),
        )
        self.commercial_subscriptions_by_token[token] = updated
        return updated

    def list_commercial_subscriptions(self, status: str | None = None) -> list[CommercialSubscription]:
        subscriptions = list(self.commercial_subscriptions_by_token.values())
        if status is None:
            return subscriptions
        return [subscription for subscription in subscriptions if subscription.status == status]

    def bind_telegram(self, token: str, tg_chat_id: str) -> CommercialSubscription | None:
        subscription = self.commercial_subscriptions_by_token.get(token)
        if subscription is None:
            return None
        updated = replace(subscription, tg_chat_id=tg_chat_id, updated_at=datetime.now(timezone.utc))
        self.commercial_subscriptions_by_token[token] = updated
        return updated

    def set_customer_email(self, token: str, email: str) -> CommercialSubscription | None:
        subscription = self.commercial_subscriptions_by_token.get(token)
        if subscription is None:
            return None
        updated = replace(subscription, customer_email=email, updated_at=datetime.now(timezone.utc))
        self.commercial_subscriptions_by_token[token] = updated
        return updated

    def list_commercial_subscriptions_by_telegram(self, tg_chat_id: str) -> list[CommercialSubscription]:
        return [
            subscription
            for subscription in self.commercial_subscriptions_by_token.values()
            if subscription.tg_chat_id == tg_chat_id
        ]

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

    def count_node_health_events_by_result(self) -> dict[str, int]:
        counts = {"success": 0, "failure": 0}
        for events in self.health_events_by_node_id.values():
            for event in events:
                result = "failure" if event.error else "success"
                counts[result] += 1
        return counts

    def add_admin_audit_event(self, event: AdminAuditEvent) -> None:
        self.admin_audit_events.insert(0, event)

    def list_admin_audit_events(self, limit: int = 50) -> list[AdminAuditEvent]:
        return self.admin_audit_events[:limit]

    def prune_admin_audit_events(self, cutoff: datetime) -> int:
        kept = [event for event in self.admin_audit_events if event.occurred_at >= cutoff]
        deleted = len(self.admin_audit_events) - len(kept)
        self.admin_audit_events = kept
        return deleted

    def count_admin_audit_events(self) -> int:
        return len(self.admin_audit_events)

    def _seed_nodes(self, nodes: list[VpnNode] | None = None) -> None:
        if nodes:
            self.nodes_by_id = {node.id: node for node in nodes}
            return
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
                    public_key="mvpRealityPublicKey111111111111111111111111111",
                    short_id="a1b2c3d4",
                    label="VPN Router 1",
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
                    public_key="mvpRealityPublicKey222222222222222222222222222",
                    short_id="b2c3d4e5",
                    label="VPN Router 2",
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
                    public_key="mvpRealityPublicKey333333333333333333333333333",
                    short_id="c3d4e5f6",
                    label="VPN Router disabled",
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
