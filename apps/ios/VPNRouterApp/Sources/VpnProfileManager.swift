import Foundation
import NetworkExtension

final class VpnProfileManager {
    func saveProfile(serverAddress: String, providerBundleIdentifier: String) async throws {
        let manager = NETunnelProviderManager()
        let tunnelProtocol = NETunnelProviderProtocol()
        tunnelProtocol.serverAddress = serverAddress
        tunnelProtocol.providerBundleIdentifier = providerBundleIdentifier
        manager.protocolConfiguration = tunnelProtocol
        manager.localizedDescription = "VPN Router"
        manager.isEnabled = true
        try await manager.saveToPreferences()
    }
}

