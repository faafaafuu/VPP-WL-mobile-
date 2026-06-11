# iOS Foundation

## Approach

- UI app: SwiftUI.
- VPN API: NetworkExtension `NETunnelProviderManager`.
- Tunnel extension: `NEPacketTunnelProvider`.
- Runtime target: sing-box/libbox after explicit GPL distribution decision.

No sing-box/libbox source or binary is vendored into this repository.

## Planned Targets

```text
VPNRouterApp
  App entrypoint
  ApiClient
  KeychainTokenStore
  SecureConfigStore
  VpnProfileManager

VPNRouterTunnel
  PacketTunnelProvider
  SingBoxRunner protocol
```

## Flow

1. App obtains or refreshes access token.
2. App requests `/api/config`.
3. App stores last-known-good config in Keychain-backed storage.
4. App creates/saves a `NETunnelProviderManager` profile.
5. Packet tunnel receives config path/provider configuration.
6. Packet tunnel starts sing-box/libbox after runtime integration is approved.

## Build Requirements

This environment is Linux and has no Xcode or Swift toolchain. On a macOS development machine:

- Create an Xcode workspace/project using these source files.
- Add an iOS app target and a Network Extension Packet Tunnel target.
- Apply `apps/ios/Config/*.entitlements` templates with the correct Team ID/App Group.
- Enable Network Extensions capability for the Apple developer account.

