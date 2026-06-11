import Foundation
import NetworkExtension

final class VpnRouterTunnelController {
    static let shared = VpnRouterTunnelController()

    private(set) var status: String = "disconnected"

    private init() {}

    func start(configJson: String) async throws {
        status = "connecting"

        let manager = try await loadOrCreateManager()
        let tunnelProtocol = NETunnelProviderProtocol()
        tunnelProtocol.providerBundleIdentifier = try tunnelBundleIdentifier()
        tunnelProtocol.serverAddress = "VPN Router"
        tunnelProtocol.providerConfiguration = [
            "configJson": configJson
        ]

        manager.protocolConfiguration = tunnelProtocol
        manager.localizedDescription = "VPN Router"
        manager.isEnabled = true

        try await save(manager)
        try manager.connection.startVPNTunnel()
        status = "connected"
    }

    func stop() async throws {
        let manager = try await loadOrCreateManager()
        manager.connection.stopVPNTunnel()
        status = "disconnected"
    }

    private func tunnelBundleIdentifier() throws -> String {
        guard
            let value = Bundle.main.object(forInfoDictionaryKey: "VpnRouterTunnelProviderBundleIdentifier") as? String,
            !value.isEmpty
        else {
            throw VpnRouterNativeError.tunnelBundleIdentifierMissing
        }
        return value
    }

    private func loadOrCreateManager() async throws -> NETunnelProviderManager {
        let managers = try await loadManagers()
        if let existing = managers.first(where: { $0.localizedDescription == "VPN Router" }) {
            return existing
        }
        return NETunnelProviderManager()
    }

    private func loadManagers() async throws -> [NETunnelProviderManager] {
        try await withCheckedThrowingContinuation { continuation in
            NETunnelProviderManager.loadAllFromPreferences { managers, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                continuation.resume(returning: managers ?? [])
            }
        }
    }

    private func save(_ manager: NETunnelProviderManager) async throws {
        try await withCheckedThrowingContinuation { continuation in
            manager.saveToPreferences { error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                continuation.resume(returning: ())
            }
        }
    }
}
