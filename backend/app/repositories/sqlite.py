from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.domain.models import (
    AdminAuditEvent,
    Hysteria2Options,
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
    WireGuardOptions,
    new_id,
)
from app.domain.receipt_fingerprint import receipt_transaction_id
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
        self._ensure_node_columns()
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

    def export_user_data(self, user_id: str) -> dict[str, object] | None:
        user = self.get_user(user_id)
        if user is None:
            return None
        row = self.connection.execute(
            """
            SELECT user_id, platform, expires_at, product_id, original_transaction_id
            FROM subscriptions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        subscription = _subscription_from_row(row) if row else None
        return {
            "user": {
                "id": user.id,
                "device_id": user.device_id,
                "created_at": _dt_to_text(user.created_at),
            },
            "subscription": _subscription_export(subscription) if subscription else None,
        }

    def delete_user(self, user_id: str) -> bool:
        cursor = self.connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def activate_subscription(self, claim: ReceiptClaim) -> Subscription:
        user = self.get_or_create_user(claim.device_id)
        if claim.platform != Platform.SANDBOX and len(claim.receipt.strip()) < 24:
            raise ValueError("receipt is too short for non-sandbox validation")

        subscription = Subscription(
            user_id=user.id,
            platform=claim.platform,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            product_id=claim.product_id,
            original_transaction_id=receipt_transaction_id(claim.platform, claim.receipt),
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
            SELECT id, tag, region, provider, country_code, host, port, protocol, status,
                   priority, weight, health_score, latency_ms, success_rate, last_check_at,
                   health, options_json
            FROM nodes
            ORDER BY priority ASC, health_score DESC, tag ASC
            """
        ).fetchall()
        return [_node_from_row(row) for row in rows]

    def get_node(self, node_id: str) -> VpnNode | None:
        row = self.connection.execute(
            """
            SELECT id, tag, region, provider, country_code, host, port, protocol, status,
                   priority, weight, health_score, latency_ms, success_rate, last_check_at,
                   health, options_json
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
                (id, tag, region, provider, country_code, host, port, protocol, status,
                 priority, weight, health_score, latency_ms, success_rate, last_check_at,
                 health, options_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                tag = excluded.tag,
                region = excluded.region,
                provider = excluded.provider,
                country_code = excluded.country_code,
                host = excluded.host,
                port = excluded.port,
                protocol = excluded.protocol,
                status = excluded.status,
                priority = excluded.priority,
                weight = excluded.weight,
                health_score = excluded.health_score,
                latency_ms = excluded.latency_ms,
                success_rate = excluded.success_rate,
                last_check_at = excluded.last_check_at,
                health = excluded.health,
                options_json = excluded.options_json
            """,
            (
                node.id,
                node.tag,
                node.region,
                node.provider,
                node.country_code,
                node.host,
                node.port,
                node.protocol.value,
                node.status.value,
                node.priority,
                node.weight,
                node.health_score,
                node.latency_ms,
                node.success_rate,
                _dt_to_text(node.last_check_at) if node.last_check_at else None,
                node.health.value,
                _options_to_json(node),
            ),
        )
        self.connection.commit()

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
        existing = self.get_node(node_id)
        if existing is None:
            return None
        next_status = status or existing.status
        next_health = health or existing.health
        next_latency = latency_ms if latency_ms is not None else existing.latency_ms
        next_success_rate = success_rate if success_rate is not None else existing.success_rate
        next_last_check_at = last_check_at or existing.last_check_at
        self.connection.execute(
            """
            UPDATE nodes
            SET health_score = ?, status = ?, latency_ms = ?, success_rate = ?,
                last_check_at = ?, health = ?
            WHERE id = ?
            """,
            (
                health_score,
                next_status.value,
                next_latency,
                next_success_rate,
                _dt_to_text(next_last_check_at) if next_last_check_at else None,
                next_health.value,
                node_id,
            ),
        )
        self.connection.commit()
        return self.get_node(node_id)

    def add_node_health_event(self, event: NodeHealthEvent) -> None:
        self.connection.execute(
            """
            INSERT INTO node_health_events
                (id, node_id, checked_at, old_health, new_health, old_status, new_status,
                 old_success_rate, new_success_rate, old_latency_ms, new_latency_ms,
                 health_score, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.node_id,
                _dt_to_text(event.checked_at),
                event.old_health.value if event.old_health else None,
                event.new_health.value,
                event.old_status.value if event.old_status else None,
                event.new_status.value,
                event.old_success_rate,
                event.new_success_rate,
                event.old_latency_ms,
                event.new_latency_ms,
                event.health_score,
                event.error,
            ),
        )
        self.connection.commit()

    def add_admin_audit_event(self, event: AdminAuditEvent) -> None:
        self.connection.execute(
            """
            INSERT INTO admin_audit_events
                (id, occurred_at, action, target_type, target_id, result, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                _dt_to_text(event.occurred_at),
                event.action,
                event.target_type,
                event.target_id,
                event.result,
                json.dumps(event.details, separators=(",", ":"), sort_keys=True),
            ),
        )
        self.connection.commit()

    def list_admin_audit_events(self, limit: int = 50) -> list[AdminAuditEvent]:
        rows = self.connection.execute(
            """
            SELECT id, occurred_at, action, target_type, target_id, result, details_json
            FROM admin_audit_events
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_admin_audit_event_from_row(row) for row in rows]

    def prune_admin_audit_events(self, cutoff: datetime) -> int:
        cursor = self.connection.execute(
            "DELETE FROM admin_audit_events WHERE occurred_at < ?",
            (_dt_to_text(cutoff),),
        )
        self.connection.commit()
        return cursor.rowcount

    def list_node_health_events(self, node_id: str, limit: int = 50) -> list[NodeHealthEvent]:
        rows = self.connection.execute(
            """
            SELECT id, node_id, checked_at, old_health, new_health, old_status, new_status,
                   old_success_rate, new_success_rate, old_latency_ms, new_latency_ms,
                   health_score, error
            FROM node_health_events
            WHERE node_id = ?
            ORDER BY checked_at DESC
            LIMIT ?
            """,
            (node_id, limit),
        ).fetchall()
        return [_health_event_from_row(row) for row in rows]

    def prune_node_health_events(self, cutoff: datetime) -> int:
        cursor = self.connection.execute(
            "DELETE FROM node_health_events WHERE checked_at < ?",
            (_dt_to_text(cutoff),),
        )
        self.connection.commit()
        return cursor.rowcount

    def seed_nodes_if_empty(self) -> None:
        count = self.connection.execute("SELECT COUNT(*) AS count FROM nodes").fetchone()["count"]
        if count:
            return
        for node in InMemoryRepository().list_nodes():
            self.upsert_node(node)

    def _ensure_node_columns(self) -> None:
        existing = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(nodes)").fetchall()
        }
        columns = {
            "provider": "TEXT NOT NULL DEFAULT 'unknown'",
            "latency_ms": "INTEGER",
            "success_rate": "REAL NOT NULL DEFAULT 1.0",
            "last_check_at": "TEXT",
            "health": "TEXT NOT NULL DEFAULT 'healthy'",
        }
        for name, definition in columns.items():
            if name not in existing:
                self.connection.execute(f"ALTER TABLE nodes ADD COLUMN {name} {definition}")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_events (
                id TEXT PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                result TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_admin_audit_events_occurred
            ON admin_audit_events(occurred_at DESC)
            """
        )


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


def _subscription_export(subscription: Subscription) -> dict[str, object]:
    return {
        "platform": subscription.platform.value,
        "expires_at": _dt_to_text(subscription.expires_at),
        "product_id": subscription.product_id,
        "original_transaction_id": subscription.original_transaction_id,
        "active": subscription.is_active(),
    }


def _node_from_row(row: sqlite3.Row) -> VpnNode:
    protocol = Protocol(row["protocol"])
    return VpnNode(
        id=row["id"],
        tag=row["tag"],
        region=row["region"],
        provider=row["provider"],
        country_code=row["country_code"],
        host=row["host"],
        port=int(row["port"]),
        protocol=protocol,
        status=NodeStatus(row["status"]),
        priority=int(row["priority"]),
        weight=int(row["weight"]),
        health_score=int(row["health_score"]),
        latency_ms=int(row["latency_ms"]) if row["latency_ms"] is not None else None,
        success_rate=float(row["success_rate"]),
        last_check_at=_dt_from_text(row["last_check_at"]) if row["last_check_at"] else None,
        health=NodeHealth(row["health"]),
        options=_options_from_json(protocol, row["options_json"]),
    )


def _health_event_from_row(row: sqlite3.Row) -> NodeHealthEvent:
    return NodeHealthEvent(
        id=row["id"],
        node_id=row["node_id"],
        checked_at=_dt_from_text(row["checked_at"]),
        old_health=NodeHealth(row["old_health"]) if row["old_health"] else None,
        new_health=NodeHealth(row["new_health"]),
        old_status=NodeStatus(row["old_status"]) if row["old_status"] else None,
        new_status=NodeStatus(row["new_status"]),
        old_success_rate=float(row["old_success_rate"]) if row["old_success_rate"] is not None else None,
        new_success_rate=float(row["new_success_rate"]),
        old_latency_ms=int(row["old_latency_ms"]) if row["old_latency_ms"] is not None else None,
        new_latency_ms=int(row["new_latency_ms"]) if row["new_latency_ms"] is not None else None,
        health_score=int(row["health_score"]),
        error=row["error"],
    )


def _admin_audit_event_from_row(row: sqlite3.Row) -> AdminAuditEvent:
    details = json.loads(row["details_json"] or "{}")
    if not isinstance(details, dict):
        details = {}
    return AdminAuditEvent(
        id=row["id"],
        occurred_at=_dt_from_text(row["occurred_at"]),
        action=row["action"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        result=row["result"],
        details=details,
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
