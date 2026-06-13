import Foundation
import NetworkExtension

final class MissingSingBoxTunnelRunner: SingBoxTunnelRunner {
    func start(configJson: String, packetFlow: NEPacketTunnelFlow) async throws {
        throw VpnRouterPacketTunnelError.runtimeMissing
    }

    func stop() async {}
}
