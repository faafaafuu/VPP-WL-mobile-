from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.domain.models import (
    Hysteria2Options,
    NodeStatus,
    Platform,
    Protocol,
    ReceiptClaim,
    ShadowsocksOptions,
    Subscription,
    User,
    VlessOptions,
    VpnNode,
    WireGuardOptions,
    new_id,
)
from app.repositories.memory import InMemoryRepository


class SqliteRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.migrate()
        self.seed_nodes_if_empty()

    def migrate(self) -> None:
        schema_path = Path(__file__).resolve().parents[2] / "migrations" / "001_initial.sql"
        self.connection.executescript(schema_path.read_text(encoding="utf-8"))
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def get_or_create_user(self, device_id: str) -> User:
        existing = self.connection.execute(
            "SELECT id, device_id, created_at FROM users WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        if existing:
            return _user_from_row(existing)

        user = User(id=new_id("usr"), device_id=device_id)
        self.connection.execute(
            "INSERT INTO users (id, device_id, created_at) VALUES (?, ?, ?)",
            (user.id, user.device_id, _dt_to_text(user.created_at)),
        )
        self.connection.commit()
        return user

    def get_user(self, user_id: str) -> User | None:
        row = self.connection.execute(
            "SELECT id, device_id, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return _user_from_row(row) if row else None

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
        self.connection.execute(
            """
            INSERT INTO subscriptions
                (user_id, platform, expires_at, product_id, original_transaction_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                platform = excluded.platform,
                expires_at = excluded.expires_at,
                product_id = excluded.product_id,
                original_transaction_id = excluded.original_transaction_id
            """,
            (
                subscription.user_id,
                subscription.platform.value,
                _dt_to_text(subscription.expires_at),
                subscription.product_id,
                subscription.original_transaction_id,
            ),
        )
        self.connection.commit()
        return subscription

    def get_active_subscription(self, user_id: str) -> Subscription | None:
        row = self.connection.execute(
            """
            SELECT user_id, platform, expires_at, product_id, original_transaction_id
            FROM subscriptions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return None
        subscription = _subscription_from_row(row)
        return subscription if subscription.is_active() else None

    def list_nodes(self) -> list[VpnNode]:
        rows = self.connection.execute(
            """
            SELECT id, tag, region, country_code, host, port, protocol, status,
                   priority, weight, health_score, options_json
            FROM nodes
            ORDER BY priority ASC, health_score DESC, tag ASC
            """
        ).fetchall()
        return [_node_from_row(row) for row in rows]

    def get_node(self, node_id: str) -> VpnNode | None:
        row = self.connection.execute(
            """
            SELECT id, tag, region, country_code, host, port, protocol, status,
                   priority, weight, health_score, options_json
            FROM nodes
            WHERE id = ?
            """,
            (node_id,),
        ).fetchone()
        return _node_from_row(row) if row else None

    def upsert_node(self, node: VpnNode) -> None:
        self.connection.execute(
            """
            INSERT INTO nodes
                (id, tag, region, country_code, host, port, protocol, status,
                 priority, weight, health_score, options_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                tag = excluded.tag,
                region = excluded.region,
                country_code = excluded.country_code,
                host = excluded.host,
                port = excluded.port,
                protocol = excluded.protocol,
                status = excluded.status,
                priority = excluded.priority,
                weight = excluded.weight,
                health_score = excluded.health_score,
                options_json = excluded.options_json
            """,
            (
                node.id,
                node.tag,
                node.region,
                node.country_code,
                node.host,
                node.port,
                node.protocol.value,
                node.status.value,
                node.priority,
                node.weight,
                node.health_score,
                _options_to_json(node),
            ),
        )
        self.connection.commit()

    def update_node_health(self, node_id: str, health_score: int, status: NodeStatus | None = None) -> VpnNode | None:
        existing = self.get_node(node_id)
        if existing is None:
            return None
        next_status = status or existing.status
        self.connection.execute(
            "UPDATE nodes SET health_score = ?, status = ? WHERE id = ?",
            (health_score, next_status.value, node_id),
        )
        self.connection.commit()
        return self.get_node(node_id)

    def seed_nodes_if_empty(self) -> None:
        count = self.connection.execute("SELECT COUNT(*) AS count FROM nodes").fetchone()["count"]
        if count:
            return
        for node in InMemoryRepository().list_nodes():
            self.upsert_node(node)


def _user_from_row(row: sqlite3.Row) -> User:
    return User(id=row["id"], device_id=row["device_id"], created_at=_dt_from_text(row["created_at"]))


def _subscription_from_row(row: sqlite3.Row) -> Subscription:
    return Subscription(
        user_id=row["user_id"],
        platform=Platform(row["platform"]),
        expires_at=_dt_from_text(row["expires_at"]),
        product_id=row["product_id"],
        original_transaction_id=row["original_transaction_id"],
    )


def _node_from_row(row: sqlite3.Row) -> VpnNode:
    protocol = Protocol(row["protocol"])
    return VpnNode(
        id=row["id"],
        tag=row["tag"],
        region=row["region"],
        country_code=row["country_code"],
        host=row["host"],
        port=int(row["port"]),
        protocol=protocol,
        status=NodeStatus(row["status"]),
        priority=int(row["priority"]),
        weight=int(row["weight"]),
        health_score=int(row["health_score"]),
        options=_options_from_json(protocol, row["options_json"]),
    )


def _options_to_json(node: VpnNode) -> str | None:
    if node.options is None:
        return None
    payload: dict[str, Any]
    if isinstance(node.options, VlessOptions):
        payload = {
            "uuid": node.options.uuid,
            "server_name": node.options.server_name,
            "flow": node.options.flow,
            "transport": node.options.transport,
            "reality": node.options.reality,
        }
    elif isinstance(node.options, ShadowsocksOptions):
        payload = {
            "method": node.options.method,
            "password": node.options.password,
        }
    elif isinstance(node.options, WireGuardOptions):
        payload = {
            "private_key": node.options.private_key,
            "peer_public_key": node.options.peer_public_key,
            "local_address": node.options.local_address,
            "mtu": node.options.mtu,
            "reserved": node.options.reserved,
        }
    elif isinstance(node.options, Hysteria2Options):
        payload = {
            "password": node.options.password,
            "server_name": node.options.server_name,
        }
    else:
        raise ValueError(f"unsupported options type: {type(node.options)!r}")
    return json.dumps(payload, separators=(",", ":"))


def _options_from_json(protocol: Protocol, raw: str | None) -> Any:
    if not raw:
        return None
    payload = json.loads(raw)
    if protocol == Protocol.VLESS:
        return VlessOptions(
            uuid=payload["uuid"],
            server_name=payload["server_name"],
            flow=payload.get("flow"),
            transport=payload.get("transport"),
            reality=payload.get("reality"),
        )
    if protocol == Protocol.SHADOWSOCKS:
        return ShadowsocksOptions(method=payload["method"], password=payload["password"])
    if protocol == Protocol.WIREGUARD:
        return WireGuardOptions(
            private_key=payload["private_key"],
            peer_public_key=payload["peer_public_key"],
            local_address=list(payload["local_address"]),
            mtu=int(payload.get("mtu", 1420)),
            reserved=payload.get("reserved"),
        )
    if protocol == Protocol.HYSTERIA2:
        return Hysteria2Options(password=payload["password"], server_name=payload["server_name"])
    raise ValueError(f"unsupported protocol: {protocol}")


def _dt_to_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _dt_from_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
