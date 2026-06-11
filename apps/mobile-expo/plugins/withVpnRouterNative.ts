import { AndroidConfig, ConfigPlugin, withAndroidManifest, withEntitlementsPlist, withInfoPlist } from "expo/config-plugins";

const VPN_SERVICE_CLASS = "com.vpnrouter.nativevpn.VpnRouterService";

const withVpnRouterNative: ConfigPlugin = (config) => {
  config = withAndroidManifest(config, (mod) => {
    const manifest = mod.modResults.manifest;
    AndroidConfig.Permissions.addPermission(manifest, "android.permission.INTERNET");
    AndroidConfig.Permissions.addPermission(manifest, "android.permission.FOREGROUND_SERVICE");

    const application = AndroidConfig.Manifest.getMainApplicationOrThrow(manifest);
    application.service = application.service ?? [];

    const hasVpnService = application.service.some((service) => service.$["android:name"] === VPN_SERVICE_CLASS);
    if (!hasVpnService) {
      application.service.push({
        $: {
          "android:name": VPN_SERVICE_CLASS,
          "android:exported": "false",
          "android:permission": "android.permission.BIND_VPN_SERVICE"
        },
        "intent-filter": [
          {
            action: [{ $: { "android:name": "android.net.VpnService" } }]
          }
        ]
      });
    }

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
