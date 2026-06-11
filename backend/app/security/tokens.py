from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    expires_at: datetime


class TokenService:
    def __init__(self, secret: str, issuer: str = "vpn-router") -> None:
        if len(secret) < 16:
            raise ValueError("token secret must be at least 16 characters")
        self.secret = secret.encode("utf-8")
        self.issuer = issuer

    def issue(self, subject: str, ttl: timedelta = timedelta(hours=12)) -> str:
        expires_at = datetime.now(timezone.utc) + ttl
        payload = {
            "iss": self.issuer,
            "sub": subject,
            "exp": int(expires_at.timestamp()),
        }
        payload_segment = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = self._sign(payload_segment)
        return f"{payload_segment}.{signature}"

    def verify(self, token: str) -> TokenClaims:
        try:
            payload_segment, signature = token.split(".", 1)
        except ValueError as exc:
            raise TokenError("malformed token") from exc

        expected = self._sign(payload_segment)
        if not hmac.compare_digest(signature, expected):
            raise TokenError("invalid token signature")

        try:
            payload: dict[str, Any] = json.loads(_b64decode(payload_segment))
            subject = str(payload["sub"])
            issuer = str(payload["iss"])
            expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TokenError("invalid token payload") from exc

        if issuer != self.issuer:
            raise TokenError("invalid token issuer")
        if expires_at <= datetime.now(timezone.utc):
            raise TokenError("expired token")
        return TokenClaims(subject=subject, expires_at=expires_at)

    def _sign(self, payload_segment: str) -> str:
        digest = hmac.new(self.secret, payload_segment.encode("ascii"), hashlib.sha256).digest()
        return _b64encode(digest)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(segment: str) -> str:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode((segment + padding).encode("ascii")).decode("utf-8")

