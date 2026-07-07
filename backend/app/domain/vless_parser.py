"""Parse a ``vless://`` URL into a :class:`VpnNode`.

The raw URL is stored verbatim on the node options so the subscription can serve
it unchanged (only the ``#label`` fragment is replaced). This keeps every
transport — Reality, xhttp, gRPC, plain TLS — working without re-deriving keys.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

from app.domain.models import NodeHealth, NodeStatus, Protocol, VlessOptions, VpnNode


class VlessParseError(ValueError):
    """Raised when a vless:// URL cannot be parsed."""


def parse_vless_url(
    vless_url: str,
    *,
    node_id: str | None = None,
    label: str | None = None,
    priority: int = 100,
    enabled: bool = True,
    country_code: str = "XX",
    region: str = "unknown",
    provider: str = "3x-ui",
    source: str = "3x-ui",
    source_panel: str = "local-3x-ui",
) -> VpnNode:
    """Parse a vless:// URL and return a VpnNode that serves it verbatim."""
    raw = (vless_url or "").strip()
    if not raw.lower().startswith("vless://"):
        raise VlessParseError("URL must start with vless://")

    parsed = urlparse(raw)
    uuid = unquote(parsed.username or "").strip()
    host = (parsed.hostname or "").strip()
    port = parsed.port
    if not uuid:
        raise VlessParseError("vless URL is missing UUID")
    if not host:
        raise VlessParseError("vless URL is missing host")
    if not port:
        raise VlessParseError("vless URL is missing port")

    query = {k: (v[0] if v else "") for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    fragment_label = unquote(parsed.fragment).strip()
    display_label = (label or fragment_label or host).strip()

    security = query.get("security", "reality").strip() or "reality"
    transport_type = query.get("type", "tcp").strip() or "tcp"

    options = VlessOptions(
        uuid=uuid,
        server_name=query.get("sni", "").strip() or host,
        flow=query.get("flow", "").strip() or None,
        transport={"type": transport_type},
        security=security,
        public_key=query.get("pbk", "").strip() or None,
        short_id=query.get("sid", "").strip() or None,
        fingerprint=query.get("fp", "").strip() or "chrome",
        label=display_label,
        raw_url=raw,
        source=source,
        source_panel=source_panel,
    )

    now = datetime.now(timezone.utc)
    status = NodeStatus.ACTIVE if enabled else NodeStatus.DISABLED
    health = NodeHealth.HEALTHY if enabled else NodeHealth.DISABLED
    generated_id = node_id or _slugify(display_label) or f"{host}-{port}"

    return VpnNode(
        id=generated_id,
        tag=display_label,
        region=region,
        provider=provider,
        country_code=country_code.upper()[:2] if country_code else "XX",
        host=host,
        port=int(port),
        protocol=Protocol.VLESS,
        status=status,
        priority=int(priority),
        health=health,
        last_check_at=now,
        options=options,
    )


def _slugify(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {" ", "-", "_", ".", "·"}:
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug
