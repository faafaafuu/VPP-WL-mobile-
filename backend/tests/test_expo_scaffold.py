from __future__ import annotations

import json
import unittest
from pathlib import Path


EXPO_ROOT = Path("../apps/mobile-expo")


class ExpoScaffoldTest(unittest.TestCase):
    def test_expo_scaffold_declares_development_build_boundary(self) -> None:
        readme = (EXPO_ROOT / "README.md").read_text(encoding="utf-8")
        package_json = json.loads((EXPO_ROOT / "package.json").read_text(encoding="utf-8"))
        app_config = (EXPO_ROOT / "app.config.ts").read_text(encoding="utf-8")

        self.assertIn("Expo Development Builds", readme)
        self.assertIn("Expo Go is not enough", readme)
        self.assertIn("react-native", package_json["dependencies"])
        self.assertIn("expo-secure-store", package_json["dependencies"])
        self.assertIn("expo-modules-core", package_json["dependencies"])
        self.assertIn("./plugins/withVpnRouterNative", app_config)

    def test_expo_backend_client_uses_mobile_api_contract(self) -> None:
        client = (EXPO_ROOT / "src/api/backendClient.ts").read_text(encoding="utf-8")

        self.assertIn("/api/config", client)
        self.assertIn("/api/auth/receipt", client)
        self.assertIn("Authorization", client)
        self.assertIn("Bearer ${accessToken}", client)

    def test_expo_config_repository_uses_lkg_fallback(self) -> None:
        repository = (EXPO_ROOT / "src/config/configRepository.ts").read_text(encoding="utf-8")
        client = (EXPO_ROOT / "src/api/backendClient.ts").read_text(encoding="utf-8")

        self.assertIn("saveLastKnownGoodConfig", repository)
        self.assertIn("readLastKnownGoodConfig", repository)
        self.assertIn("auth-required", repository)
        self.assertIn("subscription-required", repository)
        self.assertIn("statusCode === 503 || this.statusCode >= 500", client)

    def test_expo_uses_secure_store_for_tokens_and_configs(self) -> None:
        secure_store = (EXPO_ROOT / "src/storage/secureStore.ts").read_text(encoding="utf-8")

        self.assertIn("expo-secure-store", secure_store)
        self.assertIn("vpn_router_access_token", secure_store)
        self.assertIn("vpn_router_last_known_good_config", secure_store)
        self.assertIn("AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY", secure_store)

    def test_expo_native_vpn_module_is_boundary_only(self) -> None:
        native_module = (EXPO_ROOT / "src/vpn/VpnRouterNative.ts").read_text(encoding="utf-8")
        module_readme = (EXPO_ROOT / "modules/vpn-router-native/README.md").read_text(encoding="utf-8")

        self.assertIn("requireNativeModule", native_module)
        self.assertIn("VpnRouterNative", native_module)
        self.assertIn("not bundled yet", native_module)
        self.assertIn("Do not copy GPL/AGPL client code", module_readme)
        self.assertFalse(any(path.name.lower().startswith("sing-box") for path in EXPO_ROOT.rglob("*")))

    def test_expo_config_plugin_declares_platform_vpn_hooks(self) -> None:
        plugin = (EXPO_ROOT / "plugins/withVpnRouterNative.ts").read_text(encoding="utf-8")

        self.assertIn("withAndroidManifest", plugin)
        self.assertIn("withEntitlementsPlist", plugin)
        self.assertIn("packet-tunnel-provider", plugin)
        self.assertIn("android.permission.FOREGROUND_SERVICE", plugin)
        self.assertIn("android.permission.BIND_VPN_SERVICE", plugin)
        self.assertIn("com.vpnrouter.nativevpn.VpnRouterService", plugin)

    def test_expo_android_native_module_declares_vpn_service(self) -> None:
        module_config = json.loads(
            (EXPO_ROOT / "modules/vpn-router-native/expo-module.config.json").read_text(encoding="utf-8")
        )
        manifest = (
            EXPO_ROOT / "modules/vpn-router-native/android/src/main/AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        native_module = (
            EXPO_ROOT
            / "modules/vpn-router-native/android/src/main/java/com/vpnrouter/nativevpn/VpnRouterNativeModule.kt"
        ).read_text(encoding="utf-8")
        service = (
            EXPO_ROOT / "modules/vpn-router-native/android/src/main/java/com/vpnrouter/nativevpn/VpnRouterService.kt"
        ).read_text(encoding="utf-8")

        self.assertEqual(["com.vpnrouter.nativevpn.VpnRouterNativeModule"], module_config["android"]["modules"])
        self.assertIn("android.permission.BIND_VPN_SERVICE", manifest)
        self.assertIn("android.net.VpnService", manifest)
        self.assertIn("Name(\"VpnRouterNative\")", native_module)
        self.assertIn("AsyncFunction(\"start\")", native_module)
        self.assertIn("VpnService.prepare", native_module)
        self.assertIn("class VpnRouterService : VpnService()", service)
        self.assertIn("EXTRA_CONFIG_JSON", service)
        self.assertIn("runner.start(configJson, fd)", service)


if __name__ == "__main__":
    unittest.main()
