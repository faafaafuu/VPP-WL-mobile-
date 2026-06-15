from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCheck:
    name: str
    command: str
    required_for: str


ANDROID_TOOLS = (
    ToolCheck("Java JDK", "java", "Android Gradle builds"),
    ToolCheck("Android Debug Bridge", "adb", "Android device QA"),
)

ANDROID_COMPILE_SDK = "35"
REPO_ROOT = Path(__file__).resolve().parents[1]
ANDROID_PROJECT_ROOT = REPO_ROOT / "apps" / "android"


def find_tool(command: str) -> str | None:
    path = shutil.which(command)
    if path:
        return path
    if command == "eas":
        npm_global_eas = Path.home() / ".npm-global" / "bin" / "eas"
        if npm_global_eas.exists():
            return str(npm_global_eas)
    return None


EXPO_TOOLS = (
    ToolCheck("Node.js", "node", "Expo UI development"),
    ToolCheck("npm", "npm", "Expo dependency install and scripts"),
    ToolCheck("EAS CLI", "eas", "Expo development and iOS cloud builds"),
)

IOS_TOOLS = (
    ToolCheck("Xcode build tools", "xcodebuild", "local iOS builds on macOS"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check mobile build toolchain readiness.")
    parser.add_argument("--android", action="store_true", help="Require Android build tools.")
    parser.add_argument("--expo", action="store_true", help="Require Expo/Node tools.")
    parser.add_argument("--ios", action="store_true", help="Require local iOS build tools on macOS.")
    parser.add_argument("--eas-ios", action="store_true", help="Require Expo/EAS tools for cloud iOS builds.")
    args = parser.parse_args()

    selected = []
    if args.android:
        selected.extend(ANDROID_TOOLS)
    if args.expo or args.eas_ios:
        selected.extend(EXPO_TOOLS)
    if args.ios:
        selected.extend(IOS_TOOLS)
    if not selected:
        selected.extend((*ANDROID_TOOLS, *EXPO_TOOLS, *IOS_TOOLS))

    missing: list[ToolCheck] = []
    for check in selected:
        path = find_tool(check.command)
        if path:
            print(f"ok: {check.name} ({check.command}) -> {path}")
        else:
            print(f"missing: {check.name} ({check.command}) required for {check.required_for}")
            missing.append(check)

    if args.android or not any((args.android, args.expo, args.ios, args.eas_ios)):
        gradlew = ANDROID_PROJECT_ROOT / "gradlew"
        if gradlew.exists():
            print(f"ok: Gradle Wrapper -> {gradlew}")
        else:
            print(f"missing: Gradle Wrapper ({gradlew}) required for reproducible Android builds")
            missing.append(ToolCheck("Gradle Wrapper", str(gradlew), "Android debug/release builds"))

        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if android_home:
            sdk_root = Path(android_home)
            if sdk_root.exists():
                print(f"ok: Android SDK root -> {sdk_root}")
            else:
                print(f"missing: Android SDK root path does not exist: {sdk_root}")
                missing.append(ToolCheck("Android SDK root", "ANDROID_HOME", "Android Gradle builds"))
        else:
            default_sdk_root = Path("/usr/lib/android-sdk")
            if default_sdk_root.exists():
                print(f"warning: ANDROID_HOME is not set; detected {default_sdk_root}")
                sdk_root = default_sdk_root
            else:
                print("missing: ANDROID_HOME or ANDROID_SDK_ROOT required for Android Gradle builds")
                missing.append(ToolCheck("Android SDK root", "ANDROID_HOME", "Android Gradle builds"))
                sdk_root = None

        if sdk_root:
            platform_dir = sdk_root / "platforms" / f"android-{ANDROID_COMPILE_SDK}"
            if platform_dir.exists():
                print(f"ok: Android SDK Platform {ANDROID_COMPILE_SDK} -> {platform_dir}")
            else:
                print(
                    "missing: Android SDK Platform "
                    f"{ANDROID_COMPILE_SDK} ({platform_dir}) required for compileSdk={ANDROID_COMPILE_SDK}"
                )
                missing.append(
                    ToolCheck(
                        f"Android SDK Platform {ANDROID_COMPILE_SDK}",
                        f"platforms;android-{ANDROID_COMPILE_SDK}",
                        "Android Gradle builds",
                    )
                )

    if missing:
        print(f"mobile build readiness failed: {len(missing)} missing tool(s)")
        return 1

    print("mobile build readiness ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
