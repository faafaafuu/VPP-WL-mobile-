import { requireNativeModule } from "expo-modules-core";

export type VpnStatus = "disconnected" | "connecting" | "connected" | "error";

export type VpnRouterNativeModule = {
  start(configJson: string): Promise<void>;
  stop(): Promise<void>;
  status(): Promise<VpnStatus>;
};

const missingRuntime: VpnRouterNativeModule = {
  async start(): Promise<void> {
    throw new Error("VpnRouterNative runtime is not bundled yet");
  },
  async stop(): Promise<void> {
    return undefined;
  },
  async status(): Promise<VpnStatus> {
    return "disconnected";
  }
};

function loadNativeModule(): VpnRouterNativeModule {
  try {
    return requireNativeModule<VpnRouterNativeModule>("VpnRouterNative");
  } catch {
    return missingRuntime;
  }
}

export const VpnRouterNative: VpnRouterNativeModule = loadNativeModule();
