import NetworkExtension

final class VpnRouterPacketTunnelProvider: NEPacketTunnelProvider {
    private let runner: SingBoxTunnelRunner = MissingSingBoxTunnelRunner()

    override func startTunnel(
        options: [String: NSObject]?,
        completionHandler: @escaping (Error?) -> Void
    ) {
        guard
            let providerConfiguration = protocolConfiguration.providerConfiguration,
            let configJson = providerConfiguration["configJson"] as? String,
            !configJson.isEmpty
        else {
            completionHandler(VpnRouterPacketTunnelError.configMissing)
            return
        }

        Task {
            do {
                try await runner.start(configJson: configJson, packetFlow: packetFlow)
                completionHandler(nil)
            } catch {
                completionHandler(error)
            }
        }
    }

    override func stopTunnel(
        with reason: NEProviderStopReason,
        completionHandler: @escaping () -> Void
    ) {
        Task {
            await runner.stop()
            completionHandler()
        }
    }
}
