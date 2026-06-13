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
        self.assertIn("EXTRA_CONFIG_JSON", service)
        self.assertIn("getStringExtra(EXTRA_CONFIG_JSON)", service)
        self.assertIn("runner.start(configJson, fd)", service)
        self.assertIn("connectIntent(context", service)
        self.assertNotIn("runner.start(\"{}\"", service)
        self.assertIn("startForeground(NOTIFICATION_ID, notification())", service)
        self.assertIn("NotificationChannel", service)
        self.assertIn("createNotificationChannel", service)
        self.assertIn("ic_dialog_info", service)

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

    def test_android_uses_encrypted_preferences_for_tokens_and_config(self) -> None:
        gradle = (ANDROID_ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        factory = (
            ANDROID_ROOT / "app/src/main/java/com/vpnrouter/app/storage/EncryptedPreferencesFactory.kt"
        ).read_text(encoding="utf-8")
        token_store = (
            ANDROID_ROOT / "app/src/main/java/com/vpnrouter/app/auth/EncryptedTokenStore.kt"
        ).read_text(encoding="utf-8")
        config_store = (
            ANDROID_ROOT / "app/src/main/java/com/vpnrouter/app/config/EncryptedConfigStore.kt"
        ).read_text(encoding="utf-8")

        self.assertIn("androidx.security:security-crypto", gradle)
        self.assertIn("EncryptedSharedPreferences.create", factory)
        self.assertIn("MasterKey.KeyScheme.AES256_GCM", factory)
        self.assertIn("PrefValueEncryptionScheme.AES256_GCM", factory)
        self.assertIn("EncryptedPreferencesFactory.create", token_store)
        self.assertIn("EncryptedPreferencesFactory.create", config_store)
        self.assertIn("last_known_good_config_json", config_store)

    def test_config_repository_fetches_config_and_uses_lkg_fallback(self) -> None:
        repository = (
            ANDROID_ROOT / "app/src/main/java/com/vpnrouter/app/config/ConfigRepository.kt"
        ).read_text(encoding="utf-8")
        api_client = (
            ANDROID_ROOT / "app/src/main/java/com/vpnrouter/app/api/BackendApiClient.kt"
        ).read_text(encoding="utf-8")

        self.assertIn("apiClient.fetchConfig(token)", repository)
        self.assertIn("configStore.saveLastKnownGoodConfig", repository)
        self.assertIn("fallbackConfig()", repository)
        self.assertIn("AuthRequired", repository)
        self.assertIn("statusCode == 503 || statusCode >= 500", api_client)


if __name__ == "__main__":
    unittest.main()
