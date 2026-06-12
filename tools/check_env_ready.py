from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.settings import SettingsError, load_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a deployment env file for backend readiness.")
    parser.add_argument("--env-file", default=".env", help="Path to deployment env file.")
    parser.add_argument("--require-hsts", action="store_true", help="Fail unless VPN_ROUTER_HSTS_ENABLED=true.")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if not env_path.exists():
        print(f"env file not found: {env_path}", file=sys.stderr)
        return 1

    try:
        values = _parse_env_file(env_path)
        settings = load_settings(values)
    except (OSError, SettingsError, ValueError) as exc:
        print(f"env readiness check failed: {exc}", file=sys.stderr)
        return 1

    if args.require_hsts and not settings.hsts_enabled:
        print("env readiness check failed: VPN_ROUTER_HSTS_ENABLED must be true", file=sys.stderr)
        return 1

    print(
        "env readiness ok: "
        f"host={settings.host} port={settings.port} "
        f"products={','.join(settings.allowed_product_ids)} "
        f"cors_origins={len(settings.cors_origins)}"
    )
    return 0


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=value")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


if __name__ == "__main__":
    raise SystemExit(main())
