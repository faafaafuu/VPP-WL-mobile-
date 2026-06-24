from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.api.pages import not_found_page
from app.api.rate_limit import RateLimiter
from app.api.service import ApiError, ApiService
from app.core.settings import load_settings
from app.domain.config_builder import ConfigBuilder
from app.repositories.factory import create_repository
from app.security.tokens import TokenService
from app.services.exchange_rates import get_exchange_rate_service
from app.services.receipt_verifier import MvpReceiptVerifier
from app.services.yookassa import DisabledYooKassaProvider, HttpYooKassaProvider, YooKassaConfig


SETTINGS = load_settings()
RATE_LIMITER = RateLimiter(SETTINGS.rate_limit_per_minute)
REPOSITORY = create_repository(nodes=list(SETTINGS.nodes) if SETTINGS.nodes else None)
TOKEN_SERVICE = TokenService(SETTINGS.token_secret)
CONFIG_BUILDER = ConfigBuilder()
YOOKASSA_PROVIDER = (
    HttpYooKassaProvider(
        YooKassaConfig(
            shop_id=SETTINGS.yookassa_shop_id or "",
            secret_key=SETTINGS.yookassa_secret_key or "",
            return_url=SETTINGS.yookassa_return_url or "",
            product_prices_rub=SETTINGS.product_prices_rub,
        )
    )
    if SETTINGS.yookassa_shop_id and SETTINGS.yookassa_secret_key and SETTINGS.yookassa_return_url
    else DisabledYooKassaProvider()
)
EXCHANGE_RATE_SERVICE = get_exchange_rate_service(SETTINGS.crypto_rate_provider)
API_SERVICE = ApiService(
    REPOSITORY,
    TOKEN_SERVICE,
    CONFIG_BUILDER,
    admin_token=SETTINGS.admin_token,
    receipt_verifier=MvpReceiptVerifier(SETTINGS.allowed_product_ids),
    yookassa_provider=YOOKASSA_PROVIDER,
    public_base_url=SETTINGS.public_base_url,
    checkout_mode=SETTINGS.checkout_mode,
    tariffs=SETTINGS.tariffs,
    crypto_usdt_trc20_address=SETTINGS.crypto_usdt_trc20_address,
    crypto_usdt_rate_rub=SETTINGS.crypto_usdt_rate_rub,
    crypto_wallets=SETTINGS.crypto_wallets,
    exchange_rate_service=EXCHANGE_RATE_SERVICE,
    crypto_enable_testnet=SETTINGS.crypto_enable_testnet,
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
        if path == "/":
            self._send_html(HTTPStatus.OK, API_SERVICE.landing_html())
            return
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path.startswith("/connect/"):
            token = path.removeprefix("/connect/").strip("/")
            try:
                self._send_html(HTTPStatus.OK, API_SERVICE.connect_html(token))
            except ApiError as exc:
                if exc.status == HTTPStatus.NOT_FOUND:
                    self._send_html(HTTPStatus.NOT_FOUND, not_found_page())
                else:
                    self._send_json(exc.status, exc.payload)
            return
        if path.startswith("/sub/") and path.endswith("/raw"):
            token = path.removeprefix("/sub/")[: -len("/raw")].strip("/")
            self._send_text_response(lambda: API_SERVICE.raw_v2ray_subscription(token), "text/plain")
            return
        if path.startswith("/sub/") and path.endswith("/qr"):
            token = path.removeprefix("/sub/")[: -len("/qr")].strip("/")
            self._send_text_response(lambda: API_SERVICE.subscription_qr_svg(token), "image/svg+xml")
            return
        if path.startswith("/sub/"):
            token = path.removeprefix("/sub/").strip("/")
            self._send_text_response(lambda: API_SERVICE.v2ray_subscription(token), "text/plain")
            return
        if path.startswith("/invoice/") and "/qr/" in path:
            # /invoice/{token}/qr/{coin_id}
            rest = path.removeprefix("/invoice/")
            parts = rest.split("/qr/", 1)
            token = parts[0].strip("/")
            coin_id = parts[1].strip("/") if len(parts) > 1 else None
            try:
                self._send_text(HTTPStatus.OK, API_SERVICE.invoice_wallet_qr_svg(token, coin_id), "image/svg+xml")
            except ApiError as exc:
                self._send_json(exc.status, exc.payload)
            return
        if path.startswith("/invoice/") and path.endswith("/qr"):
            token = path.removeprefix("/invoice/")[: -len("/qr")].strip("/")
            try:
                self._send_text(HTTPStatus.OK, API_SERVICE.invoice_wallet_qr_svg(token, None), "image/svg+xml")
            except ApiError as exc:
                self._send_json(exc.status, exc.payload)
            return
        if path.startswith("/invoice/"):
            token = path.removeprefix("/invoice/").strip("/")
            try:
                self._send_html(HTTPStatus.OK, API_SERVICE.invoice_html(token))
            except ApiError as exc:
                if exc.status == HTTPStatus.NOT_FOUND:
                    self._send_html(HTTPStatus.NOT_FOUND, not_found_page())
                else:
                    self._send_json(exc.status, exc.payload)
            return
        if path == "/api/version":
            self._send_service_response(lambda: API_SERVICE.version())
            return
        if path == "/metrics":
            self._send_text(HTTPStatus.OK, API_SERVICE.prometheus_metrics(), "text/plain; version=0.0.4")
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
        if path in {"/api/admin/nodes", "/admin/nodes"}:
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(lambda: API_SERVICE.admin_nodes(admin_token))
            return
        if path == "/api/admin/audit":
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(lambda: API_SERVICE.admin_audit_events(admin_token))
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
        admin_node_prefix = "/api/admin/nodes/"
        if path.startswith(admin_node_prefix):
            node_id = path[len(admin_node_prefix):].strip("/")
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(lambda: API_SERVICE.admin_disable_node(admin_token, node_id))
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if self._is_rate_limited():
            return
        path = urlparse(self.path).path
        if path == "/checkout":
            payload = self._read_form_or_json()
            if payload is None:
                return
            try:
                response = API_SERVICE.checkout(payload)
                self._send_redirect(str(response["redirect_url"]))
            except ApiError as exc:
                self._send_json(exc.status, exc.payload)
            return

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

        if path == "/api/payments/yookassa":
            payload = self._read_json()
            if payload is None:
                return
            self._send_service_response(lambda: API_SERVICE.create_yookassa_payment(payload))
            return

        if path == "/api/webhook/yookassa":
            payload = self._read_json()
            if payload is None:
                return
            self._send_service_response(lambda: API_SERVICE.yookassa_webhook(payload))
            return

        if path in {"/api/admin/nodes/import-vless", "/admin/nodes/import-vless"}:
            payload = self._read_json()
            if payload is None:
                return
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(lambda: API_SERVICE.admin_import_vless(admin_token, payload))
            return

        if path in {"/api/admin/nodes", "/admin/nodes"}:
            payload = self._read_json()
            if payload is None:
                return
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(lambda: API_SERVICE.admin_upsert_node(admin_token, payload))
            return

        admin_prefix = "/admin/subscriptions/"
        admin_suffix = "/activate"
        if path.startswith(admin_prefix) and path.endswith(admin_suffix):
            payload = self._read_json()
            if payload is None:
                return
            token = path[len(admin_prefix) : -len(admin_suffix)]
            admin_token = self.headers.get("X-Admin-Token", "")
            self._send_service_response(
                lambda: API_SERVICE.admin_activate_commercial_subscription(admin_token, token, payload)
            )
            return

        if path in {"/api/webhook/apple", "/api/webhook/google"}:
            self._send_json(HTTPStatus.ACCEPTED, {"status": "accepted"})
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

        # PATCH /admin/nodes/{id} or /api/admin/nodes/{id} — toggle enabled / label / priority
        for node_prefix in ("/api/admin/nodes/", "/admin/nodes/"):
            if path.startswith(node_prefix) and not path.endswith("/health"):
                node_id = path[len(node_prefix):].strip("/")
                if node_id:
                    payload = self._read_json()
                    if payload is None:
                        return
                    admin_token = self.headers.get("X-Admin-Token", "")
                    self._send_service_response(lambda: API_SERVICE.admin_patch_node(admin_token, node_id, payload))
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

    def _read_form_or_json(self) -> dict[str, Any] | None:
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return self._read_json()
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_length).decode("utf-8")
        parsed = parse_qs(raw_body, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in parsed.items()}

    def _send_service_response(self, action: Any) -> None:
        try:
            self._send_json(HTTPStatus.OK, action())
        except ApiError as exc:
            self._send_json(exc.status, exc.payload)

    def _send_text_response(self, action: Any, content_type: str) -> None:
        try:
            self._send_text(HTTPStatus.OK, action(), content_type)
        except ApiError as exc:
            self._send_text(exc.status, str(exc.payload.get("error", "error")), "text/plain")

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

    def _send_text(self, status: HTTPStatus, payload: str, content_type: str) -> None:
        body = payload.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._send_cors_headers()
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: HTTPStatus, payload: str) -> None:
        body = payload.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._send_cors_headers()
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER.value)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self._send_cors_headers()
        self._send_security_headers()
        self.end_headers()

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
