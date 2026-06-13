import Foundation
import NetworkExtension

protocol SingBoxTunnelRunner {
    func start(configJson: String, packetFlow: NEPacketTunnelFlow) async throws
    func stop() async
}
