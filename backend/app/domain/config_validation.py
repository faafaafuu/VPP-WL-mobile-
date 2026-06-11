from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class ConfigValidationError(ValueError):
    pass


def validate_config_shape(config: dict[str, Any]) -> None:
    _require_dict(config, "config")
    inbounds = _require_list(config, "inbounds")
    outbounds = _require_list(config, "outbounds")
    route = _require_dict(config.get("route"), "route")

    if not inbounds:
        raise ConfigValidationError("inbounds must not be empty")
    if not outbounds:
        raise ConfigValidationError("outbounds must not be empty")

    outbound_tags = set()
    for index, outbound in enumerate(outbounds):
        _require_dict(outbound, f"outbounds[{index}]")
        outbound_type = _require_str(outbound, "type", f"outbounds[{index}]")
        tag = _require_str(outbound, "tag", f"outbounds[{index}]")
        if outbound_type not in {"urltest", "vless", "shadowsocks", "wireguard", "hysteria2", "direct", "block"}:
            raise ConfigValidationError(f"outbounds[{index}].type is unsupported: {outbound_type}")
        if tag in outbound_tags:
            raise ConfigValidationError(f"duplicate outbound tag: {tag}")
        outbound_tags.add(tag)

    if "direct" not in outbound_tags:
        raise ConfigValidationError("direct outbound is required")
    if "auto" not in outbound_tags:
        raise ConfigValidationError("auto outbound is required")

    rules = _require_list(route, "rules", container_name="route")
    final = _require_str(route, "final", "route")
    if final not in outbound_tags:
        raise ConfigValidationError("route.final must reference an outbound tag")

    for index, rule in enumerate(rules):
        _require_dict(rule, f"route.rules[{index}]")
        outbound = rule.get("outbound")
        if outbound is not None and outbound not in outbound_tags:
            raise ConfigValidationError(f"route.rules[{index}].outbound must reference an outbound tag")

    if not any(rule.get("outbound") == "direct" for rule in rules):
        raise ConfigValidationError("at least one direct route rule is required")


def optional_sing_box_check(config: dict[str, Any], binary: str = "sing-box") -> tuple[bool, str]:
    executable = shutil.which(binary)
    if executable is None:
        return False, f"{binary} binary not found"

    with tempfile.TemporaryDirectory() as tempdir:
        config_path = Path(tempdir) / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        result = subprocess.run(
            [executable, "check", "-c", str(config_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    if result.returncode != 0:
        raise ConfigValidationError(output or "sing-box check failed")
    return True, output


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f"{name} must be an object")
    return value


def _require_list(container: dict[str, Any], key: str, container_name: str = "config") -> list[Any]:
    value = container.get(key)
    if not isinstance(value, list):
        raise ConfigValidationError(f"{container_name}.{key} must be a list")
    return value


def _require_str(container: dict[str, Any], key: str, container_name: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigValidationError(f"{container_name}.{key} must be a non-empty string")
    return value
