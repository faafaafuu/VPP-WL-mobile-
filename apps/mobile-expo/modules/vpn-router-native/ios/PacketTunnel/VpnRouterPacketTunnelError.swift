import Foundation

enum VpnRouterPacketTunnelError: LocalizedError {
    case configMissing
    case runtimeMissing

    var errorDescription: String? {
        switch self {
        case .configMissing:
            return "VPN config JSON is missing from providerConfiguration"
        case .runtimeMissing:
            return "sing-box/libbox packet tunnel runtime is not bundled yet"
        }
    }
}
