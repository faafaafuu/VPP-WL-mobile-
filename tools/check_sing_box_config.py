from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.domain.config_builder import ConfigBuilder  # noqa: E402
from app.domain.config_validation import ConfigValidationError, optional_sing_box_check, validate_config_shape  # noqa: E402
from app.domain.node_selection import choose_preferred_nodes  # noqa: E402
from app.repositories.memory import InMemoryRepository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated sing-box config shape and optional binary check.")
    parser.add_argument("--binary", default="sing-box", help="sing-box binary name or path.")
    parser.add_argument("--require-binary", action="store_true", help="Fail if the sing-box binary is unavailable.")
    args = parser.parse_args()

    try:
        config = ConfigBuilder().build_client_config(choose_preferred_nodes(InMemoryRepository().list_nodes()))
        validate_config_shape(config)
        checked, message = optional_sing_box_check(config, binary=args.binary)
    except (ConfigValidationError, ValueError) as exc:
        print(f"sing-box config validation failed: {exc}", file=sys.stderr)
        return 1

    if checked:
        print(message or "sing-box check passed")
        return 0

    print(f"sing-box binary check skipped: {message}")
    return 1 if args.require_binary else 0


if __name__ == "__main__":
    raise SystemExit(main())
