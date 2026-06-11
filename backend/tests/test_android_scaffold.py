from __future__ import annotations

import unittest
from pathlib import Path


ANDROID_ROOT = Path("../apps/android")


class AndroidScaffoldTest(unittest.TestCase):
    def test_manifest_declares_vpn_service_permission(self) -> None:
        manifest = (ANDROID_ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")

        self.assertIn("android.permission.BIND_VPN_SERVICE", manifest)
        self.assertIn("android.net.VpnService", manifest)

    def test_vpn_service_extends_android_vpn_service(self) -> None:
        service = (
            ANDROID_ROOT / "app/src/main/java/com/vpnrouter/app/vpn/VpnRouterService.kt"
        ).read_text(encoding="utf-8")

        self.assertIn("class VpnRouterService : VpnService()", service)
        self.assertIn("Builder()", service)
        self.assertIn("addRoute(\"0.0.0.0\", 0)", service)

    def test_sing_box_runtime_is_not_vendored(self) -> None:
        runner = (ANDROID_ROOT / "app/src/main/java/com/vpnrouter/app/vpn/SingBoxRunner.kt").read_text(
            encoding="utf-8"
        )

        self.assertIn("interface SingBoxRunner", runner)
        self.assertIn("not bundled yet", runner)
        self.assertFalse(any(path.name.lower().startswith("sing-box") for path in ANDROID_ROOT.rglob("*")))

    def test_backend_client_uses_bearer_config_contract(self) -> None:
        client = (
            ANDROID_ROOT / "app/src/main/java/com/vpnrouter/app/api/BackendApiClient.kt"
        ).read_text(encoding="utf-8")

        self.assertIn("/api/config", client)
        self.assertIn("Authorization", client)
        self.assertIn("Bearer $accessToken", client)


if __name__ == "__main__":
    unittest.main()

