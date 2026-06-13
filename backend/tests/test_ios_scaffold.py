from __future__ import annotations

import unittest
from pathlib import Path


IOS_ROOT = Path("../apps/ios")


class IosScaffoldTest(unittest.TestCase):
    def test_packet_tunnel_provider_uses_network_extension(self) -> None:
        provider = (IOS_ROOT / "VPNRouterTunnel/Sources/PacketTunnelProvider.swift").read_text(encoding="utf-8")
        info = (IOS_ROOT / "VPNRouterTunnel/Resources/Info.plist").read_text(encoding="utf-8")
        entitlements = (IOS_ROOT / "Config/Tunnel.entitlements.template").read_text(encoding="utf-8")

        self.assertIn("import NetworkExtension", provider)
        self.assertIn("NEPacketTunnelProvider", provider)
        self.assertIn("NEPacketTunnelNetworkSettings", provider)
        self.assertIn("providerConfiguration", provider)
        self.assertIn("\"configJson\"", provider)
        self.assertIn("PacketTunnelError.configMissing", provider)
        self.assertNotIn("Data()", provider)
        self.assertIn("com.apple.networkextension.packet-tunnel", info)
        self.assertIn("packet-tunnel-provider", entitlements)

    def test_ios_uses_keychain_for_token_and_config_storage(self) -> None:
        token_store = (IOS_ROOT / "VPNRouterApp/Sources/TokenStore.swift").read_text(encoding="utf-8")
        config_store = (IOS_ROOT / "VPNRouterApp/Sources/ConfigStore.swift").read_text(encoding="utf-8")

        self.assertIn("import Security", token_store)
        self.assertIn("SecItemAdd", token_store)
        self.assertIn("kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly", token_store)
        self.assertIn("import Security", config_store)
        self.assertIn("SecItemAdd", config_store)
        self.assertIn("last_known_good_config", config_store)

    def test_ios_config_repository_uses_backend_contract_and_fallback(self) -> None:
        api_client = (IOS_ROOT / "VPNRouterApp/Sources/ApiClient.swift").read_text(encoding="utf-8")
        repository = (IOS_ROOT / "VPNRouterApp/Sources/ConfigRepository.swift").read_text(encoding="utf-8")

        self.assertIn("/api/config", api_client)
        self.assertIn("Authorization", api_client)
        self.assertIn("Bearer", api_client)
        self.assertIn("allowsConfigFallback", api_client)
        self.assertIn("configStore.saveLastKnownGoodConfig", repository)
        self.assertIn("readLastKnownGoodConfig", repository)
        self.assertIn("authRequired", repository)

    def test_ios_profile_manager_passes_config_json_to_packet_tunnel(self) -> None:
        manager = (IOS_ROOT / "VPNRouterApp/Sources/VpnProfileManager.swift").read_text(encoding="utf-8")

        self.assertIn("configData: Data", manager)
        self.assertIn("String(data: configData, encoding: .utf8)", manager)
        self.assertIn("providerConfiguration", manager)
        self.assertIn("\"configJson\"", manager)
        self.assertIn("VpnProfileError.configEncodingFailed", manager)

    def test_ios_sing_box_runtime_is_not_vendored(self) -> None:
        runner = (IOS_ROOT / "VPNRouterTunnel/Sources/SingBoxRunner.swift").read_text(encoding="utf-8")

        self.assertIn("protocol SingBoxRunner", runner)
        self.assertIn("start(configJson: String)", runner)
        self.assertIn("MissingSingBoxRuntimeError", runner)
        self.assertFalse(any(path.name.lower().startswith("sing-box") for path in IOS_ROOT.rglob("*")))


if __name__ == "__main__":
    unittest.main()
