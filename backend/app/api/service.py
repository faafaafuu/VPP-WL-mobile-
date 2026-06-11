from __future__ import annotations

import hmac
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from app.domain.config_builder import ConfigBuilder
from app.domain.config_validation import ConfigValidationError, validate_config_shape
from app.domain.models import NodeStatus, Platform, ReceiptClaim
from app.domain.node_selection import choose_preferred_nodes
from app.repositories.factory import Repository
from app.security.tokens import TokenError, TokenService


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
        admin_token: str = "dev-admin-token",
    ) -> None:
        self.repository = repository
        self.token_service = token_service
        self.config_builder = config_builder
        self.admin_token = admin_token

    def auth_init(self, payload: dict[str, Any]) -> dict[str, Any]:
        device_id = str(payload.get("device_id", "")).strip()
        if not device_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, {"error": "device_id is required"})
        user = self.repository.get_or_create_user(device_id)
        return {"user_id": user.id}

    def auth_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        claim = self._receipt_claim_from_payload(payload)
        try:
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

    def admin_nodes(self, admin_token: str) -> dict[str, Any]:
        self._require_admin(admin_token)
        return {"nodes": [_admin_node(node) for node in self.repository.list_nodes()]}

    def admin_update_node_health(self, admin_token: str, node_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_admin(admin_token)
        health_score = self._health_score_from_payload(payload)
        status = self._node_status_from_payload(payload)
        node = self.repository.update_node_health(node_id, health_score=health_score, status=status)
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
        "country_code": node.country_code,
        "protocol": node.protocol.value,
        "status": node.status.value,
        "health_score": node.health_score,
        "priority": node.priority,
    }


def _admin_node(node: Any) -> dict[str, Any]:
    return {
        **_public_node(node),
        "tag": node.tag,
        "host": node.host,
        "port": node.port,
        "weight": node.weight,
        "usable": node.is_usable(),
    }
