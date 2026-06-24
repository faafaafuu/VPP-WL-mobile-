import {
  AndroidConfig,
  ConfigPlugin,
  withAndroidManifest,
  withEntitlementsPlist,
  withInfoPlist,
  withXcodeProject
} from "expo/config-plugins";

declare const __dirname: string;
declare function require(moduleName: string): any;

const fs = require("fs");
const path = require("path");

const VPN_SERVICE_CLASS = "com.vpnrouter.nativevpn.VpnRouterService";
const TUNNEL_TARGET_NAME = "VPNRouterTunnel";
const TUNNEL_BUNDLE_SUFFIX = ".Tunnel";
const TUNNEL_TEMPLATE_ROOT = path.join(
  __dirname,
  "..",
  "modules",
  "vpn-router-native",
  "ios",
  "PacketTunnel"
);
const TUNNEL_SOURCE_FILES = [
  "VpnRouterPacketTunnelProvider.swift",
  "SingBoxTunnelRunner.swift",
  "MissingSingBoxTunnelRunner.swift",
  "VpnRouterPacketTunnelError.swift"
];
const TUNNEL_SUPPORT_FILES = ["VPNRouterTunnel-Info.plist", "VPNRouterTunnel.entitlements"];

const withVpnRouterNative: ConfigPlugin = (config) => {
  config = withAndroidManifest(config, (mod) => {
    AndroidConfig.Permissions.addPermission(mod.modResults, "android.permission.INTERNET");
    AndroidConfig.Permissions.addPermission(mod.modResults, "android.permission.FOREGROUND_SERVICE");

    const application = AndroidConfig.Manifest.getMainApplicationOrThrow(mod.modResults);
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
    mod.modResults.VpnRouterTunnelProviderBundleIdentifier =
      mod.modResults.VpnRouterTunnelProviderBundleIdentifier ?? "$(PRODUCT_BUNDLE_IDENTIFIER).Tunnel";
    return mod;
  });

  config = withEntitlementsPlist(config, (mod) => {
    mod.modResults["com.apple.developer.networking.networkextension"] =
      mod.modResults["com.apple.developer.networking.networkextension"] ?? ["packet-tunnel-provider"];
    return mod;
  });

  config = withXcodeProject(config, (mod) => {
    copyTunnelTemplate(mod.modRequest.platformProjectRoot);
    ensurePacketTunnelTarget(mod.modResults, config.ios?.bundleIdentifier ?? "com.vpnrouter.app");
    return mod;
  });

  return config;
};

function copyTunnelTemplate(platformProjectRoot: string) {
  const destinationRoot = path.join(platformProjectRoot, TUNNEL_TARGET_NAME);
  fs.mkdirSync(destinationRoot, { recursive: true });

  for (const fileName of [...TUNNEL_SOURCE_FILES, ...TUNNEL_SUPPORT_FILES]) {
    fs.copyFileSync(path.join(TUNNEL_TEMPLATE_ROOT, fileName), path.join(destinationRoot, fileName));
  }
}

function ensurePacketTunnelTarget(project: any, appBundleIdentifier: string) {
  if (findNativeTarget(project, TUNNEL_TARGET_NAME)) {
    return;
  }

  const tunnelBundleIdentifier = `${appBundleIdentifier}${TUNNEL_BUNDLE_SUFFIX}`;
  const target = project.addTarget(TUNNEL_TARGET_NAME, "app_extension", TUNNEL_TARGET_NAME, tunnelBundleIdentifier);
  const targetUuid = target.uuid;

  project.addBuildPhase([], "PBXSourcesBuildPhase", "Sources", targetUuid);
  project.addBuildPhase([], "PBXFrameworksBuildPhase", "Frameworks", targetUuid);

  const mainGroupUuid = project.getFirstProject().firstProject.mainGroup;
  const tunnelGroup = project.addPbxGroup([], TUNNEL_TARGET_NAME, TUNNEL_TARGET_NAME, '"<group>"');
  project.addToPbxGroup(tunnelGroup.uuid, mainGroupUuid);

  for (const sourceFile of TUNNEL_SOURCE_FILES) {
    project.addSourceFile(`${TUNNEL_TARGET_NAME}/${sourceFile}`, { target: targetUuid }, tunnelGroup.uuid);
  }

  for (const supportFile of TUNNEL_SUPPORT_FILES) {
    project.addFile(`${TUNNEL_TARGET_NAME}/${supportFile}`, tunnelGroup.uuid);
  }

  project.addFramework("NetworkExtension.framework", { target: targetUuid });
  setTunnelBuildSettings(project, target.pbxNativeTarget.buildConfigurationList, tunnelBundleIdentifier);
}

function findNativeTarget(project: any, targetName: string) {
  const nativeTargets = project.pbxNativeTargetSection();
  return Object.values(nativeTargets).find((target: any) => target?.name === `"${targetName}"` || target?.name === targetName);
}

function setTunnelBuildSettings(project: any, buildConfigurationListId: string, bundleIdentifier: string) {
  const configurationList = project.pbxXCConfigurationList()[buildConfigurationListId];
  const buildConfigurations = project.pbxXCBuildConfigurationSection();

  for (const item of configurationList.buildConfigurations ?? []) {
    const configuration = buildConfigurations[item.value];
    if (!configuration?.buildSettings) {
      continue;
    }
    configuration.buildSettings.APPLICATION_EXTENSION_API_ONLY = "YES";
    configuration.buildSettings.CODE_SIGN_ENTITLEMENTS = `${TUNNEL_TARGET_NAME}/VPNRouterTunnel.entitlements`;
    configuration.buildSettings.DEFINES_MODULE = "YES";
    configuration.buildSettings.INFOPLIST_FILE = `${TUNNEL_TARGET_NAME}/VPNRouterTunnel-Info.plist`;
    configuration.buildSettings.IPHONEOS_DEPLOYMENT_TARGET = "15.1";
    configuration.buildSettings.PRODUCT_BUNDLE_IDENTIFIER = bundleIdentifier;
    configuration.buildSettings.PRODUCT_NAME = `"${TUNNEL_TARGET_NAME}"`;
    configuration.buildSettings.SWIFT_VERSION = "5.0";
  }
}

export default withVpnRouterNative;
