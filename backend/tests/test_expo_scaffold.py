from __future__ import annotations

import json
import unittest
from pathlib import Path


EXPO_ROOT = Path("../apps/mobile-expo")


class ExpoScaffoldTest(unittest.TestCase):
    def test_expo_scaffold_declares_development_build_boundary(self) -> None:
        readme = (EXPO_ROOT / "README.md").read_text(encoding="utf-8")
        package_json = json.loads((EXPO_ROOT / "package.json").read_text(encoding="utf-8"))
        tsconfig = json.loads((EXPO_ROOT / "tsconfig.json").read_text(encoding="utf-8"))
        app_config = (EXPO_ROOT / "app.config.ts").read_text(encoding="utf-8")
        eas = json.loads((EXPO_ROOT / "eas.json").read_text(encoding="utf-8"))
        env_example = (EXPO_ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("Expo Development Builds", readme)
        self.assertIn("Expo Go is not enough", readme)
        self.assertIn("react-native", package_json["dependencies"])
        self.assertIn("expo-secure-store", package_json["dependencies"])
        self.assertIn("expo-modules-core", package_json["dependencies"])
        self.assertEqual("tsc --noEmit", package_json["scripts"]["typecheck"])
        self.assertEqual("expo/tsconfig.base", tsconfig["extends"])
        self.assertTrue(tsconfig["compilerOptions"]["strict"])
        self.assertIn("src/**/*.tsx", tsconfig["include"])
        self.assertEqual("file:./modules/vpn-router-native", package_json["dependencies"]["vpn-router-native"])
        self.assertIn("./plugins/withVpnRouterNative", app_config)
        self.assertTrue(eas["build"]["development"]["developmentClient"])
        self.assertEqual("internal", eas["build"]["development"]["distribution"])
        self.assertIn("EXPO_PUBLIC_API_BASE_URL", env_example)
        self.assertIn("EXPO_PUBLIC_PRIVACY_URL", env_example)
        self.assertIn("EXPO_PUBLIC_TERMS_URL", env_example)
        self.assertIn("privacyUrl", app_config)
        self.assertIn("termsUrl", app_config)

    def test_expo_backend_client_uses_mobile_api_contract(self) -> None:
        client = (EXPO_ROOT / "src/api/backendClient.ts").read_text(encoding="utf-8")

        self.assertIn("/api/config", client)
        self.assertIn("/api/auth/init", client)
        self.assertIn("/api/me", client)
        self.assertIn("/api/me/export", client)
        self.assertIn("/api/nodes", client)
        self.assertIn("/api/version", client)
        self.assertIn("/api/auth/receipt", client)
        self.assertIn("/api/payments/yookassa", client)
        self.assertIn("createYooKassaPayment", client)
        self.assertIn("method: \"DELETE\"", client)
        self.assertIn("exportMe(accessToken", client)
        self.assertIn("deleteMe(accessToken", client)
        self.assertIn("Authorization", client)
        self.assertIn("Bearer ${accessToken}", client)

    def test_expo_auth_repository_activates_subscription_without_storing_receipt(self) -> None:
        auth_repository = (EXPO_ROOT / "src/auth/AuthRepository.ts").read_text(encoding="utf-8")
        app = (EXPO_ROOT / "src/App.tsx").read_text(encoding="utf-8")

        self.assertIn("activateSandboxReceipt", auth_repository)
        self.assertIn("createYooKassaPayment", auth_repository)
        self.assertIn("activateYooKassaPayment", auth_repository)
        self.assertIn("platform: \"yookassa\"", auth_repository)
        self.assertIn("initDevice", auth_repository)
        self.assertIn("loadCurrentSubscription", auth_repository)
        self.assertIn("exportAccountData", auth_repository)
        self.assertIn("deleteAccount", auth_repository)
        self.assertIn("platform: \"sandbox\"", auth_repository)
        self.assertIn("product_id: \"vpn.monthly\"", auth_repository)
        self.assertIn("fetchMe(token)", auth_repository)
        self.assertIn("exportMe(token)", auth_repository)
        self.assertIn("deleteMe(token)", auth_repository)
        self.assertIn("initAuth(normalizedDeviceId)", auth_repository)
        self.assertIn("subscription-required", auth_repository)
        self.assertIn("saveAccessToken(response.access_token)", auth_repository)
        self.assertIn("clearLastKnownGoodConfig", auth_repository)
        self.assertNotIn("saveReceipt", auth_repository)
        self.assertIn("Sandbox", app)
        self.assertIn("Pay with YooKassa", app)
        self.assertIn("Confirm pay", app)
        self.assertIn("Linking.openURL(result.confirmationUrl)", app)
        self.assertIn("Create user", app)
        self.assertIn("Check plan", app)
        self.assertIn("Export data", app)
        self.assertIn("Delete", app)
        self.assertIn("Alert.alert", app)
        self.assertIn("Linking.openURL(privacyUrl)", app)
        self.assertIn("Linking.openURL(termsUrl)", app)
        self.assertIn("Subscription", app)
        self.assertIn("secureTextEntry", app)
        self.assertIn("Connect", app)
        self.assertIn("Smart routing", app)

    def test_expo_node_repository_loads_public_node_diagnostics(self) -> None:
        node_repository = (EXPO_ROOT / "src/nodes/NodeRepository.ts").read_text(encoding="utf-8")
        app = (EXPO_ROOT / "src/App.tsx").read_text(encoding="utf-8")

        self.assertIn("fetchNodes(token)", node_repository)
        self.assertIn("auth-required", node_repository)
        self.assertIn("clearAccessToken", node_repository)
        self.assertIn("Refresh nodes", app)
        self.assertIn("renderNodes", app)
        self.assertIn("node.score", app)

    def test_expo_version_repository_loads_backend_compatibility(self) -> None:
        version_repository = (EXPO_ROOT / "src/version/VersionRepository.ts").read_text(encoding="utf-8")
        app = (EXPO_ROOT / "src/App.tsx").read_text(encoding="utf-8")

        self.assertIn("fetchVersion()", version_repository)
        self.assertIn("VersionResponse", version_repository)
        self.assertIn("Check API version", app)
        self.assertIn("renderVersion", app)
        self.assertIn("config_format", app)

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
        self.assertIn("clearLastKnownGoodConfig", secure_store)
        self.assertIn("AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY", secure_store)

    def test_expo_native_vpn_module_is_boundary_only(self) -> None:
        native_module = (EXPO_ROOT / "src/vpn/VpnRouterNative.ts").read_text(encoding="utf-8")
        module_readme = (EXPO_ROOT / "modules/vpn-router-native/README.md").read_text(encoding="utf-8")
        controller = (EXPO_ROOT / "src/vpn/VpnController.ts").read_text(encoding="utf-8")
        app = (EXPO_ROOT / "src/App.tsx").read_text(encoding="utf-8")

        self.assertIn("requireNativeModule", native_module)
        self.assertIn("VpnRouterNative", native_module)
        self.assertIn("prepare(): Promise<VpnPrepareStatus>", native_module)
        self.assertIn("not bundled yet", native_module)
        self.assertIn("Do not copy GPL/AGPL client code", module_readme)
        self.assertLess(controller.index("loadConfig()"), controller.index("VpnRouterNative.prepare()"))
        self.assertIn("try {", controller)
        self.assertIn("Unable to start VPN", controller)
        self.assertIn("Unable to stop VPN", app)
        self.assertFalse(any(path.name.lower().startswith("sing-box") for path in EXPO_ROOT.rglob("*")))

    def test_expo_config_plugin_declares_platform_vpn_hooks(self) -> None:
        plugin = (EXPO_ROOT / "plugins/withVpnRouterNative.ts").read_text(encoding="utf-8")

        self.assertIn("withAndroidManifest", plugin)
        self.assertIn("withEntitlementsPlist", plugin)
        self.assertIn("withXcodeProject", plugin)
        self.assertIn("copyTunnelTemplate", plugin)
        self.assertIn("ensurePacketTunnelTarget", plugin)
        self.assertIn("project.addTarget(TUNNEL_TARGET_NAME, \"app_extension\"", plugin)
        self.assertIn("VPNRouterTunnel", plugin)
        self.assertIn("VPNRouterTunnel-Info.plist", plugin)
        self.assertIn("VPNRouterTunnel.entitlements", plugin)
        self.assertIn("NetworkExtension.framework", plugin)
        self.assertIn("CODE_SIGN_ENTITLEMENTS", plugin)
        self.assertIn("APPLICATION_EXTENSION_API_ONLY", plugin)
        self.assertIn("packet-tunnel-provider", plugin)
        self.assertIn("android.permission.FOREGROUND_SERVICE", plugin)
        self.assertIn("android.permission.BIND_VPN_SERVICE", plugin)
        self.assertIn("com.vpnrouter.nativevpn.VpnRouterService", plugin)
        self.assertIn("VpnRouterTunnelProviderBundleIdentifier", plugin)

    def test_expo_ios_packet_tunnel_target_templates_are_present(self) -> None:
        packet_tunnel_root = EXPO_ROOT / "modules/vpn-router-native/ios/PacketTunnel"
        info_plist = (packet_tunnel_root / "VPNRouterTunnel-Info.plist").read_text(encoding="utf-8")
        entitlements = (packet_tunnel_root / "VPNRouterTunnel.entitlements").read_text(encoding="utf-8")

        self.assertIn("com.apple.networkextension.packet-tunnel", info_plist)
        self.assertIn("VpnRouterPacketTunnelProvider", info_plist)
        self.assertIn("packet-tunnel-provider", entitlements)
        self.assertIn("com.apple.developer.networking.networkextension", entitlements)

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
        self.assertIn("AsyncFunction(\"prepare\")", native_module)
        self.assertIn("activity.startActivity(prepareIntent)", native_module)
        self.assertIn("AsyncFunction(\"start\")", native_module)
        self.assertIn("VpnService.prepare", native_module)
        self.assertIn("class VpnRouterService : VpnService()", service)
        self.assertIn("EXTRA_CONFIG_JSON", service)
        self.assertIn("runner.start(configJson, fd)", service)

    def test_expo_ios_native_module_declares_network_extension_controller(self) -> None:
        module_config = json.loads(
            (EXPO_ROOT / "modules/vpn-router-native/expo-module.config.json").read_text(encoding="utf-8")
        )
        podspec = (EXPO_ROOT / "modules/vpn-router-native/ios/VpnRouterNative.podspec").read_text(
            encoding="utf-8"
        )
        native_module = (
            EXPO_ROOT / "modules/vpn-router-native/ios/Sources/VpnRouterNativeModule.swift"
        ).read_text(encoding="utf-8")
        controller = (
            EXPO_ROOT / "modules/vpn-router-native/ios/Sources/VpnRouterTunnelController.swift"
        ).read_text(encoding="utf-8")

        self.assertEqual(["android", "apple"], module_config["platforms"])
        self.assertEqual(["VpnRouterNativeModule"], module_config["apple"]["modules"])
        self.assertIn("NetworkExtension", podspec)
        self.assertIn("Name(\"VpnRouterNative\")", native_module)
        self.assertIn("AsyncFunction(\"prepare\")", native_module)
        self.assertIn("AsyncFunction(\"start\")", native_module)
        self.assertIn("NETunnelProviderManager", controller)
        self.assertIn("NETunnelProviderProtocol", controller)
        self.assertIn("providerConfiguration", controller)
        self.assertIn("VpnRouterTunnelProviderBundleIdentifier", controller)

    def test_expo_ios_packet_tunnel_template_reads_config_and_keeps_runtime_boundary(self) -> None:
        packet_tunnel_root = EXPO_ROOT / "modules/vpn-router-native/ios/PacketTunnel"
        provider = (packet_tunnel_root / "VpnRouterPacketTunnelProvider.swift").read_text(encoding="utf-8")
        runner = (packet_tunnel_root / "SingBoxTunnelRunner.swift").read_text(encoding="utf-8")
        missing_runner = (packet_tunnel_root / "MissingSingBoxTunnelRunner.swift").read_text(encoding="utf-8")
        errors = (packet_tunnel_root / "VpnRouterPacketTunnelError.swift").read_text(encoding="utf-8")
        readme = (EXPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("NEPacketTunnelProvider", provider)
        self.assertIn("providerConfiguration", provider)
        self.assertIn("\"configJson\"", provider)
        self.assertIn("packetFlow", provider)
        self.assertIn("startTunnel", provider)
        self.assertIn("stopTunnel", provider)
        self.assertIn("protocol SingBoxTunnelRunner", runner)
        self.assertIn("MissingSingBoxTunnelRunner", missing_runner)
        self.assertIn("runtimeMissing", errors)
        self.assertIn("Packet Tunnel Swift sources", readme)


if __name__ == "__main__":
    unittest.main()
