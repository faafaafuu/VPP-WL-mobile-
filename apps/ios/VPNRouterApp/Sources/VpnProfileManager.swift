import Foundation
import NetworkExtension

final class VpnProfileManager {
    func saveProfile(serverAddress: String, providerBundleIdentifier: String, configData: Data) async throws {
        guard let configJson = String(data: configData, encoding: .utf8), !configJson.isEmpty else {
            throw VpnProfileError.configEncodingFailed
        }

        let manager = NETunnelProviderManager()
        let tunnelProtocol = NETunnelProviderProtocol()
        tunnelProtocol.serverAddress = serverAddress
        tunnelProtocol.providerBundleIdentifier = providerBundleIdentifier
        tunnelProtocol.providerConfiguration = ["configJson": configJson]
        manager.protocolConfiguration = tunnelProtocol
        manager.localizedDescription = "VPN Router"
        manager.isEnabled = true
        try await manager.saveToPreferences()
    }
}

enum VpnProfileError: Error {
    case configEncodingFailed
}
