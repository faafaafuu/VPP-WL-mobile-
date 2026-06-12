from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from app.api.rate_limit import RateLimiter
from app.api.service import ApiError, ApiService
from app.core.settings import load_settings
from app.domain.config_builder import ConfigBuilder
from app.repositories.factory import create_repository
from app.security.tokens import TokenService
from app.services.receipt_verifier import MvpReceiptVerifier


SETTINGS = load_settings()
RATE_LIMITER = RateLimiter(SETTINGS.rate_limit_per_minute)
REPOSITORY = create_repository()
TOKEN_SERVICE = TokenService(SETTINGS.token_secret)
CONFIG_BUILDER = ConfigBuilder()
API_SERVICE = ApiService(
    REPOSITORY,
    TOKEN_SERVICE,
    CONFIG_BUILDER,
    admin_token=SETTINGS.admin_token,
    receipt_verifier=MvpReceiptVerifier(SETTINGS.allowed_product_ids),
)


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "VpnRouterMVP/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self._send_cors_headers()
        self._send_security_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if self._is_rate_limited():
            return
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/api/version":
            self._send_service_response(lambda: API_SERVICE.version())
            return
        if path == "/api/nodes":
            user_id = self._require_user_id()
            if user_id is None:
                return
            self._send_service_response(lambda: API_SERVICE.nodes(user_id))
            return
        if path == "/api/config":
            user_id = self._require_user_id()
            if user_id is None:
                return
            self._send_service_response(lambda: API_SERVICE.config(user_id))
            return
        if path == "/api/me":
            user_id = self._require_user_id()
            if user_id is None:
                return
            self._send_service_response(lambda: API_SERVICE.me(user_id))
            return
        if path == "/api/me/export":
            user_id = self._require_user_id()
            if user_id is None:
                return
            self._send_service_response(lambda: API_SERVICE.export_me(user_id))
            return
        if path == "/api/admin/nodes":
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(lambda: API_SERVICE.admin_nodes(admin_token))
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if self._is_rate_limited():
            return
        path = urlparse(self.path).path
        if path == "/api/auth/init":
            payload = self._read_json()
            if payload is None:
                return
            self._send_service_response(lambda: API_SERVICE.auth_init(payload))
            return

        if path == "/api/auth/receipt":
            payload = self._read_json()
            if payload is None:
                return
            self._send_service_response(lambda: API_SERVICE.auth_receipt(payload))
            return

        if path in {"/api/webhook/apple", "/api/webhook/google"}:
            self._send_json(HTTPStatus.ACCEPTED, {"status": "accepted"})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_DELETE(self) -> None:
        if self._is_rate_limited():
            return
        path = urlparse(self.path).path
        if path == "/api/me":
            user_id = self._require_user_id()
            if user_id is None:
                return
            self._send_service_response(lambda: API_SERVICE.delete_me(user_id))
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_PATCH(self) -> None:
        if self._is_rate_limited():
            return
        path = urlparse(self.path).path
        prefix = "/api/admin/nodes/"
        suffix = "/health"
        if path.startswith(prefix) and path.endswith(suffix):
            payload = self._read_json()
            if payload is None:
                return
            node_id = path[len(prefix) : -len(suffix)]
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(lambda: API_SERVICE.admin_update_node_health(admin_token, node_id, payload))
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _require_user_id(self) -> str | None:
        authorization = self.headers.get("Authorization", "")
        try:
            return API_SERVICE.user_id_from_authorization(authorization)
        except ApiError as exc:
            self._send_json(exc.status, exc.payload)
            return None

    def _is_rate_limited(self) -> bool:
        path = urlparse(self.path).path
        if path == "/health":
            return False

        client_ip = self.client_address[0] if self.client_address else "unknown"
        if RATE_LIMITER.allow(client_ip):
            return False

        self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate limit exceeded"})
        return True

    def _read_json(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
            return None
        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON object expected"})
            return None
        return payload

    def _send_service_response(self, action: Any) -> None:
        try:
            self._send_json(HTTPStatus.OK, action())
        except ApiError as exc:
            self._send_json(exc.status, exc.payload)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._send_cors_headers()
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if not origin or not SETTINGS.cors_origins:
            return

        if "*" in SETTINGS.cors_origins:
            allowed_origin = "*"
        elif origin in SETTINGS.cors_origins:
            allowed_origin = origin
        else:
            return

        self.send_header("Access-Control-Allow-Origin", allowed_origin)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type,X-Admin-Token")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if SETTINGS.hsts_enabled:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    httpd = ThreadingHTTPServer((host, port), ApiHandler)
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"vpn-router backend listening on http://{host}:{port} started_at={started_at}")
    httpd.serve_forever()


if __name__ == "__main__":
    run(host=SETTINGS.host, port=SETTINGS.port)
