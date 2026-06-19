from __future__ import annotations

import subprocess
import sys


FORBIDDEN_PARTS = (
    "__pycache__/",
    ".pyc",
    "backend/data/",
    "apps/android/app/libs/libbox.aar",
    "apps/android/app/libs/libbox-legacy.aar",
)
FORBIDDEN_EXACT = {
    ".env",
    "apps/mobile-expo/.env",
    "apps/mobile-expo/.env.local",
}


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    forbidden = [
        path
        for path in tracked
        if path in FORBIDDEN_EXACT or any(part in path for part in FORBIDDEN_PARTS)
    ]
    if forbidden:
        print("Forbidden generated or secret-like files are tracked:", file=sys.stderr)
        for path in forbidden:
            print(f"- {path}", file=sys.stderr)
        return 1
    print("tracked artifact check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
