from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCheck:
    name: str
    command: str
    required_for: str


ANDROID_TOOLS = (
    ToolCheck("Java JDK", "java", "Android Gradle builds"),
    ToolCheck("Gradle", "gradle", "Android debug/release builds"),
    ToolCheck("Android Debug Bridge", "adb", "Android device QA"),
)

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
    parser.add_argument("--ios", action="store_true", help="Require local iOS build tools.")
    args = parser.parse_args()

    selected = []
    if args.android:
        selected.extend(ANDROID_TOOLS)
    if args.expo:
        selected.extend(EXPO_TOOLS)
    if args.ios:
        selected.extend(IOS_TOOLS)
    if not selected:
        selected.extend((*ANDROID_TOOLS, *EXPO_TOOLS, *IOS_TOOLS))

    missing: list[ToolCheck] = []
    for check in selected:
        path = shutil.which(check.command)
        if path:
            print(f"ok: {check.name} ({check.command}) -> {path}")
        else:
            print(f"missing: {check.name} ({check.command}) required for {check.required_for}")
            missing.append(check)

    if missing:
        print(f"mobile build readiness failed: {len(missing)} missing tool(s)")
        return 1

    print("mobile build readiness ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
