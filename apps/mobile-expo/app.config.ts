import type { ExpoConfig } from "expo/config";

const config: ExpoConfig = {
  name: "VPN Router",
  slug: "vpn-router",
  scheme: "vpnrouter",
  version: "0.1.0",
  orientation: "portrait",
  userInterfaceStyle: "automatic",
  ios: {
    bundleIdentifier: "com.vpnrouter.app",
    supportsTablet: false,
    infoPlist: {
      NSVpnUsageDescription: "VPN Router uses a packet tunnel to route traffic according to the selected subscription config."
    }
  },
  android: {
    package: "com.vpnrouter.app",
    permissions: ["INTERNET", "FOREGROUND_SERVICE"]
  },
  plugins: ["./plugins/withVpnRouterNative"],
  extra: {
    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8080",
    privacyUrl: process.env.EXPO_PUBLIC_PRIVACY_URL ?? "https://example.com/privacy",
    termsUrl: process.env.EXPO_PUBLIC_TERMS_URL ?? "https://example.com/terms"
  }
};

export default config;
