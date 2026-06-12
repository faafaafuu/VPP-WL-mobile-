from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from app.domain.config_builder import ConfigBuilder
from app.domain.config_validation import ConfigValidationError, validate_config_shape
from app.domain.models import NodeHealth, NodeStatus, Platform, ReceiptClaim
from app.domain.node_scoring import node_score
from app.domain.node_selection import choose_preferred_nodes
from app.repositories.factory import Repository
from app.security.tokens import TokenError, TokenService
from app.services.receipt_verifier import MvpReceiptVerifier, ReceiptVerifier


@dataclass(frozen=True)
class ApiError(Exception):
    status: HTTPStatus
    payload: dict[str, Any]


class ApiService:
    def __init__(
        self,
        repository: Repository,
        token_service: TokenService,
        config_builder: ConfigBuilder,
        admin_token: str,
        receipt_verifier: ReceiptVerifier | None = None,
    ) -> None:
        if not admin_token:
            raise ValueError("admin token is required")
        self.repository = repository
        self.token_service = token_service
        self.config_builder = config_builder
        self.admin_token = admin_token
        self.receipt_verifier = receipt_verifier or MvpReceiptVerifier()

    def auth_init(self, payload: dict[str, Any]) -> dict[str, Any]:
        device_id = str(payload.get("device_id", "")).strip()
        if not device_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "device_id is required"})
        user = self.repository.get_or_create_user(device_id)
        return {"user_id": user.id}

    def auth_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        claim = self._receipt_claim_from_payload(payload)
        try:
            self.receipt_verifier.verify(claim)
            subscription = self.repository.activate_subscription(claim)
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": str(exc)}) from exc
        token = self.token_service.issue(subscription.user_id)
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_at": subscription.expires_at.isoformat(),
        }

    def nodes(self, user_id: str) -> dict[str, Any]:
        self._require_known_user(user_id)
        return {"nodes": [_public_node(node) for node in choose_preferred_nodes(self.repository.list_nodes())]}

    def me(self, user_id: str) -> dict[str, Any]:
        self._require_known_user(user_id)
        subscription = self.repository.get_active_subscription(user_id)
        return {
            "user_id": user_id,
            "subscription": _public_subscription(subscription) if subscription else None,
        }

    def admin_nodes(self, admin_token: str) -> dict[str, Any]:
        self._require_admin(admin_token)
        return {"nodes": [_admin_node(node) for node in self.repository.list_nodes()]}

    def admin_update_node_health(self, admin_token: str, node_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_admin(admin_token)
        health_score = self._health_score_from_payload(payload)
        status = self._node_status_from_payload(payload)
        latency_ms = self._latency_from_payload(payload)
        success_rate = self._success_rate_from_payload(payload)
        health = self._health_from_payload(payload)
        node = self.repository.update_node_health(
            node_id,
            health_score=health_score,
            status=status,
            latency_ms=latency_ms,
            success_rate=success_rate,
            health=health,
            last_check_at=datetime.now(timezone.utc),
        )
        if node is None:
            raise ApiError(HTTPStatus.NOT_FOUND, {"error": "node not found"})
        return {"node": _admin_node(node)}

    def config(self, user_id: str) -> dict[str, Any]:
        self._require_known_user(user_id)
        if self.repository.get_active_subscription(user_id) is None:
            raise ApiError(HTTPStatus.FORBIDDEN, {"error": "active subscription required"})
        try:
            config = self.config_builder.build_client_config(choose_preferred_nodes(self.repository.list_nodes()))
            validate_config_shape(config)
            return config
        except (ValueError, ConfigValidationError) as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}) from exc

    def user_id_from_authorization(self, authorization: str) -> str:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": "bearer token required"})
        try:
            claims = self.token_service.verify(token)
        except TokenError as exc:
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": str(exc)}) from exc
        self._require_known_user(claims.subject)
        return claims.subject

    def _require_admin(self, admin_token: str) -> None:
        if not self.admin_token or not hmac.compare_digest(admin_token, self.admin_token):
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": "admin token required"})

    def _health_score_from_payload(self, payload: dict[str, Any]) -> int:
        try:
            health_score = int(payload.get("health_score"))
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "health_score must be an integer"}) from exc
        if not 0 <= health_score <= 100:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "health_score must be between 0 and 100"})
        return health_score

    def _node_status_from_payload(self, payload: dict[str, Any]) -> NodeStatus | None:
        raw_status = payload.get("status")
        if raw_status is None:
            return None
        try:
            return NodeStatus(str(raw_status))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "status must be active, draining, or disabled"}) from exc

    def _latency_from_payload(self, payload: dict[str, Any]) -> int | None:
        raw_latency = payload.get("latency_ms")
        if raw_latency is None:
            return None
        try:
            latency_ms = int(raw_latency)
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "latency_ms must be an integer"}) from exc
        if latency_ms < 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "latency_ms must be positive"})
        return latency_ms

    def _success_rate_from_payload(self, payload: dict[str, Any]) -> float | None:
        raw_success_rate = payload.get("success_rate")
        if raw_success_rate is None:
            return None
        try:
            success_rate = float(raw_success_rate)
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "success_rate must be a number"}) from exc
        if not 0 <= success_rate <= 1:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "success_rate must be between 0 and 1"})
        return success_rate

    def _health_from_payload(self, payload: dict[str, Any]) -> NodeHealth | None:
        raw_health = payload.get("health")
        if raw_health is None:
            return None
        try:
            return NodeHealth(str(raw_health))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "health must be healthy, degraded, or disabled"}) from exc

    def _receipt_claim_from_payload(self, payload: dict[str, Any]) -> ReceiptClaim:
        try:
            platform = Platform(str(payload.get("platform", "")).lower())
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "platform must be apple, google, or sandbox"}) from exc

        receipt = str(payload.get("receipt", "")).strip()
        device_id = str(payload.get("device_id", "")).strip()
        product_id = str(payload.get("product_id", "vpn.monthly")).strip() or "vpn.monthly"
        if not receipt:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "receipt is required"})
        if not device_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "device_id is required"})
        return ReceiptClaim(platform=platform, receipt=receipt, device_id=device_id, product_id=product_id)

    def _require_known_user(self, user_id: str) -> None:
        if self.repository.get_user(user_id) is None:
            raise ApiError(HTTPStatus.UNAUTHORIZED, {"error": "unknown user"})


def _public_node(node: Any) -> dict[str, Any]:
    return {
        "id": node.id,
        "region": node.region,
        "provider": node.provider,
        "country_code": node.country_code,
        "protocol": node.protocol.value,
        "status": node.status.value,
        "health": node.health.value,
        "health_score": node.health_score,
        "latency_ms": node.latency_ms,
        "success_rate": node.success_rate,
        "priority": node.priority,
        "score": round(node_score(node), 2),
    }


def _public_subscription(subscription: Any) -> dict[str, Any]:
    return {
        "active": subscription.is_active(),
        "platform": subscription.platform.value,
        "product_id": subscription.product_id,
        "expires_at": subscription.expires_at.isoformat(),
    }


def _admin_node(node: Any) -> dict[str, Any]:
    return {
        **_public_node(node),
        "tag": node.tag,
        "host": node.host,
        "port": node.port,
        "weight": node.weight,
        "last_check_at": node.last_check_at.isoformat() if node.last_check_at else None,
        "usable": node.is_usable(),
    }
