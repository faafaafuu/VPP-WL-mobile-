import { NativeModules } from "react-native";

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

export const VpnRouterNative: VpnRouterNativeModule =
  (NativeModules.VpnRouterNative as VpnRouterNativeModule | undefined) ?? missingRuntime;
