import { ConfigRepository, ConfigState } from "../config/configRepository";

import { VpnRouterNative, VpnStatus } from "./VpnRouterNative";

export type StartResult = {
  status: VpnStatus;
  configState: ConfigState;
};

export class VpnController {
  constructor(private readonly configRepository: ConfigRepository) {}

  async start(): Promise<StartResult> {
    const configState = await this.configRepository.loadConfig();

    if (configState.kind !== "fresh" && configState.kind !== "last-known-good") {
      return { status: "error", configState };
    }

    const prepareStatus = await VpnRouterNative.prepare();
    if (prepareStatus === "requested") {
      return {
        status: "disconnected",
        configState: { kind: "error", message: "VPN permission requested. Press connect again after approving it." }
      };
    }

    try {
      await VpnRouterNative.start(configState.configJson);
      return { status: "connected", configState };
    } catch (error) {
      return {
        status: "error",
        configState: {
          kind: "error",
          message: error instanceof Error ? error.message : "Unable to start VPN"
        }
      };
    }
  }

  async stop(): Promise<void> {
    await VpnRouterNative.stop();
  }

  async status(): Promise<VpnStatus> {
    return VpnRouterNative.status();
  }
}
