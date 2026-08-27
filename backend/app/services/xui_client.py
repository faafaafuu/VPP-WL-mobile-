from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Protocol
from urllib import request


class XuiClientError(ValueError):
    pass


@dataclass(frozen=True)
class XuiPanelConfig:
    base_url: str
    api_token: str
    inbound_id: int
    verify_tls: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_token and self.inbound_id)


class XuiClient(Protocol):
    def add_client(
        self, client_uuid: str, email: str, expiry_time_ms: int = 0, limit_ip: int = 0, total_gb: int = 0
    ) -> None:
        ...

    def update_client(
        self, client_uuid: str, email: str, expiry_time_ms: int = 0, limit_ip: int = 0, total_gb: int = 0
    ) -> None:
        ...

    def delete_client(self, email: str) -> None:
        ...


class DisabledXuiClient:
    def add_client(
        self, client_uuid: str, email: str, expiry_time_ms: int = 0, limit_ip: int = 0, total_gb: int = 0
    ) -> None:
        raise XuiClientError("3x-ui panel is not configured")

    def update_client(
        self, client_uuid: str, email: str, expiry_time_ms: int = 0, limit_ip: int = 0, total_gb: int = 0
    ) -> None:
        raise XuiClientError("3x-ui panel is not configured")

    def delete_client(self, email: str) -> None:
        raise XuiClientError("3x-ui panel is not configured")


class HttpXuiClient:
    """Talks to a 3x-ui panel (v3.7+) via its Bearer-token API — no vendored
    3x-ui code, no session-cookie login (the panel's CSRF middleware rejects
    cookie login from a bare non-browser client; the API token bypasses it).

    Client identity is a UUID (VLESS id) at creation, but 3x-ui's own update/
    delete endpoints are keyed by the client's *email* instead, so callers
    must hang on to the email they passed to add_client.
    """

    def __init__(self, config: XuiPanelConfig) -> None:
        self.config = config
        self._opener = request.build_opener(request.HTTPSHandler(context=self._ssl_context()))

    def add_client(
        self, client_uuid: str, email: str, expiry_time_ms: int = 0, limit_ip: int = 0, total_gb: int = 0
    ) -> None:
        self._request_json(
            "POST",
            "/panel/api/clients/add",
            {
                "client": self._client_fields(client_uuid, email, expiry_time_ms, limit_ip, total_gb),
                "inboundIds": [self.config.inbound_id],
            },
        )

    def update_client(
        self, client_uuid: str, email: str, expiry_time_ms: int = 0, limit_ip: int = 0, total_gb: int = 0
    ) -> None:
        self._request_json(
            "POST",
            f"/panel/api/clients/update/{email}",
            {**self._client_fields(client_uuid, email, expiry_time_ms, limit_ip, total_gb), "limitHwid": 0},
        )

    def delete_client(self, email: str) -> None:
        self._request_json("POST", f"/panel/api/clients/del/{email}", {})

    @staticmethod
    def _client_fields(client_uuid: str, email: str, expiry_time_ms: int, limit_ip: int, total_gb: int) -> dict:
        return {
            "id": client_uuid,
            "email": email,
            "enable": True,
            "expiryTime": expiry_time_ms,
            "flow": "xtls-rprx-vision",
            "limitIp": limit_ip,
            # 3x-ui's "totalGB" field is actually a byte count despite the name
            # (its own admin UI multiplies the GB the operator types by 1024^3
            # before sending) — callers pass GB, we convert here.
            "totalGB": total_gb * 1024 ** 3,
            "security": "",
        }

    def _ssl_context(self) -> ssl.SSLContext:
        if self.config.verify_tls:
            return ssl.create_default_context()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def _request_json(self, method: str, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self.config.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.config.api_token}",
            },
        )
        try:
            with self._opener.open(http_request, timeout=20) as response:
                decoded = json.loads(response.read().decode("utf-8") or "{}")
        except Exception as exc:  # noqa: BLE001 - surface as XuiClientError uniformly
            raise XuiClientError(f"3x-ui request failed: {exc}") from exc
        if not decoded.get("success", False):
            raise XuiClientError(f"3x-ui request failed: {decoded.get('msg', 'unknown error')}")
        return decoded
