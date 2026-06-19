from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ANDROID_LIBBOX_AAR = REPO_ROOT / "apps" / "android" / "app" / "libs" / "libbox.aar"
ANDROID_REQUIRED_AAR_ENTRIES = {
    "classes.jar",
    "jni/armeabi-v7a/libbox.so",
    "jni/arm64-v8a/libbox.so",
    "jni/x86/libbox.so",
    "jni/x86_64/libbox.so",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_android_artifact(path: Path, require: bool) -> int:
    if not path.exists():
        print(f"missing: Android libbox AAR -> {path}")
        if require:
            return 1
        print("libbox artifact check skipped: add libbox.aar to enable real Android VPN runtime")
        return 0

    if not zipfile.is_zipfile(path):
        print(f"invalid: Android libbox AAR is not a zip/AAR file -> {path}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    missing = sorted(ANDROID_REQUIRED_AAR_ENTRIES - names)
    if missing:
        print(f"invalid: Android libbox AAR is missing {', '.join(missing)}", file=sys.stderr)
        return 1

    print(f"ok: Android libbox AAR -> {path}")
    print(f"sha256: {sha256(path)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local sing-box/libbox mobile artifacts.")
    parser.add_argument("--android", action="store_true", help="Check Android libbox.aar.")
    parser.add_argument(
        "--android-path",
        type=Path,
        default=ANDROID_LIBBOX_AAR,
        help="Override Android libbox.aar path for tests or custom builds.",
    )
    parser.add_argument("--require", action="store_true", help="Fail if an artifact is missing.")
    args = parser.parse_args()

    if not args.android:
        parser.error("select at least one platform, e.g. --android")

    status = 0
    if args.android:
        status = max(status, check_android_artifact(args.android_path, args.require))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
