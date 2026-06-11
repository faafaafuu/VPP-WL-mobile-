from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from app.api.service import ApiError, ApiService
from app.core.settings import load_settings
from app.domain.config_builder import ConfigBuilder
from app.repositories.factory import create_repository
from app.security.tokens import TokenService


SETTINGS = load_settings()
REPOSITORY = create_repository()
TOKEN_SERVICE = TokenService(SETTINGS.token_secret)
CONFIG_BUILDER = ConfigBuilder()
API_SERVICE = ApiService(
    REPOSITORY,
    TOKEN_SERVICE,
    CONFIG_BUILDER,
    admin_token=SETTINGS.admin_token,
)


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "VpnRouterMVP/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
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
        if path == "/api/admin/nodes":
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(lambda: API_SERVICE.admin_nodes(admin_token))
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
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

    def do_PATCH(self) -> None:
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
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    httpd = ThreadingHTTPServer((host, port), ApiHandler)
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"vpn-router backend listening on http://{host}:{port} started_at={started_at}")
    httpd.serve_forever()


if __name__ == "__main__":
    run(host=SETTINGS.host, port=SETTINGS.port)
