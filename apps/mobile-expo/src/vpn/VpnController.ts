import { ConfigRepository, ConfigState } from "../config/configRepository";

import { VpnRouterNative, VpnStatus } from "./VpnRouterNative";

export type StartResult = {
  status: VpnStatus;
  configState: ConfigState;
};

export class VpnController {
  constructor(private readonly configRepository: ConfigRepository) {}

  async start(): Promise<StartResult> {
    const prepareStatus = await VpnRouterNative.prepare();
    if (prepareStatus === "requested") {
      return {
        status: "disconnected",
        configState: { kind: "error", message: "VPN permission requested. Press connect again after approving it." }
      };
    }

    const configState = await this.configRepository.loadConfig();

    if (configState.kind !== "fresh" && configState.kind !== "last-known-good") {
      return { status: "error", configState };
    }

    await VpnRouterNative.start(configState.configJson);
    return { status: "connected", configState };
  }

  async stop(): Promise<void> {
    await VpnRouterNative.stop();
  }

  async status(): Promise<VpnStatus> {
    return VpnRouterNative.status();
  }
}
