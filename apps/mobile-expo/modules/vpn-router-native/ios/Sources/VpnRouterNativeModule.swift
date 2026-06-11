import ExpoModulesCore

public class VpnRouterNativeModule: Module {
    public func definition() -> ModuleDefinition {
        Name("VpnRouterNative")

        AsyncFunction("start") { (configJson: String) async throws in
            try await VpnRouterTunnelController.shared.start(configJson: configJson)
        }

        AsyncFunction("stop") { async throws in
            try await VpnRouterTunnelController.shared.stop()
        }

        AsyncFunction("status") {
            VpnRouterTunnelController.shared.status
        }
    }
}
