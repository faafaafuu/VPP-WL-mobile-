import { AndroidConfig, ConfigPlugin, withAndroidManifest, withEntitlementsPlist, withInfoPlist } from "expo/config-plugins";

const withVpnRouterNative: ConfigPlugin = (config) => {
  config = withAndroidManifest(config, (mod) => {
    const manifest = mod.modResults.manifest;
    AndroidConfig.Permissions.addPermission(manifest, "android.permission.INTERNET");
    AndroidConfig.Permissions.addPermission(manifest, "android.permission.FOREGROUND_SERVICE");

    // BIND_VPN_SERVICE is declared on the native service, not as a global uses-permission.
    // The service entry is added by the Android native module when implemented.
    return mod;
  });

  config = withInfoPlist(config, (mod) => {
    mod.modResults.NSVpnUsageDescription =
      mod.modResults.NSVpnUsageDescription ??
      "VPN Router uses a packet tunnel to route traffic according to the selected subscription config.";
    return mod;
  });

  config = withEntitlementsPlist(config, (mod) => {
    mod.modResults["com.apple.developer.networking.networkextension"] =
      mod.modResults["com.apple.developer.networking.networkextension"] ?? ["packet-tunnel-provider"];
    return mod;
  });

  return config;
};

export default withVpnRouterNative;
