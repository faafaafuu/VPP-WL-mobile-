import NetworkExtension

final class PacketTunnelProvider: NEPacketTunnelProvider {
    private let runner: SingBoxRunner = MissingSingBoxRunner()

    override func startTunnel(options: [String: NSObject]?) async throws {
        guard
            let providerConfiguration = protocolConfiguration.providerConfiguration,
            let configJson = providerConfiguration["configJson"] as? String,
            !configJson.isEmpty
        else {
            throw PacketTunnelError.configMissing
        }

        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: "127.0.0.1")
        settings.ipv4Settings = NEIPv4Settings(addresses: ["172.19.0.2"], subnetMasks: ["255.255.255.252"])
        settings.ipv4Settings?.includedRoutes = [NEIPv4Route.default()]
        try await setTunnelNetworkSettings(settings)

        try runner.start(configJson: configJson)
    }

    override func stopTunnel(with reason: NEProviderStopReason) async {
        runner.stop()
    }
}

enum PacketTunnelError: Error {
    case configMissing
}
