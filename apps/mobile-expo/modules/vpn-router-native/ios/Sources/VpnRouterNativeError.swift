import Foundation

enum VpnRouterNativeError: Error, LocalizedError {
    case tunnelBundleIdentifierMissing
    case managerUnavailable

    var errorDescription: String? {
        switch self {
        case .tunnelBundleIdentifierMissing:
            return "VpnRouterTunnelProviderBundleIdentifier is missing from Info.plist"
        case .managerUnavailable:
            return "Unable to create or load NETunnelProviderManager"
        }
    }
}
