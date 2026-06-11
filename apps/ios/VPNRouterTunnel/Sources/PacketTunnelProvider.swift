import NetworkExtension

final class PacketTunnelProvider: NEPacketTunnelProvider {
    private let runner: SingBoxRunner = MissingSingBoxRunner()

    override func startTunnel(options: [String: NSObject]?) async throws {
        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: "127.0.0.1")
        settings.ipv4Settings = NEIPv4Settings(addresses: ["172.19.0.2"], subnetMasks: ["255.255.255.252"])
        settings.ipv4Settings?.includedRoutes = [NEIPv4Route.default()]
        try await setTunnelNetworkSettings(settings)

        // The backend-provided sing-box config will be passed through the app group
        // container after sing-box/libbox runtime integration is approved.
        try runner.start(configData: Data())
    }

    override func stopTunnel(with reason: NEProviderStopReason) async {
        runner.stop()
    }
}

