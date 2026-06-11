# VPN Router Native Module

This directory reserves the native module boundary for Expo Development Builds.

Do not copy GPL/AGPL client code here. The implementation should either:

- call the separately approved sing-box/libbox runtime under an explicit product license decision, or
- delegate to platform-native VPN code maintained in this repository.

Expected JavaScript contract:

```ts
start(configJson: string): Promise<void>
stop(): Promise<void>
status(): Promise<"disconnected" | "connecting" | "connected" | "error">
```

Android implementation will wrap `VpnService`. iOS implementation will control `NETunnelProviderManager` and communicate with `NEPacketTunnelProvider`.
