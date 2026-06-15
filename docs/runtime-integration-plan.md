# Runtime Integration Plan

Status: GPL-compatible sing-box/libbox integration approved on 2026-06-15; implementation blocked on runtime artifacts, Android SDK/device testing, and iOS EAS/Xcode build environment.

The mobile UI, backend config contract, and native module boundaries are ready for a VPN runtime, but the actual packet proxy engine is intentionally not bundled yet.

## Current Boundary

- Backend emits sing-box-compatible configs.
- Expo UI calls `VpnRouterNative.prepare()`, `start(configJson)`, `stop()`, and `status()`.
- Android native module starts `VpnRouterService`, creates a TUN interface, and passes config JSON plus TUN fd to `SingBoxRunner`.
- iOS native module creates/loads a `NETunnelProviderManager` profile and passes config JSON to the packet tunnel provider through `providerConfiguration`.
- `apps/mobile-expo/modules/vpn-router-native/ios/PacketTunnel` contains a minimal `NEPacketTunnelProvider` source template that reads `configJson` and delegates packet handling to a `SingBoxTunnelRunner` boundary. It intentionally keeps `MissingSingBoxTunnelRunner` until libbox artifacts are added.
- Android and iOS runtime implementations currently fail with explicit missing-runtime errors.

## Approved Runtime Decision

`sing-box/libbox` is GPL-3.0-or-later. Product decision on 2026-06-15 selected the GPL-compatible app distribution path:

- Use sing-box/libbox directly in mobile runtime modules.
- Publish app source and satisfy GPL obligations for distributed mobile builds.
- Keep backend proprietary/GPL boundary under legal review if distribution model changes later.
- Do not copy unrelated GPL/AGPL client source from v2rayNG, ClashMetaForAndroid, Marzban, or 3X-UI.

## Engineering Steps

Android:

- Replace `MissingSingBoxRunner` in `apps/mobile-expo/modules/vpn-router-native/android`.
- Wire libbox start/stop lifecycle to the existing TUN fd.
- Forward backend config JSON to the runtime.
- Add foreground service notification and lifecycle recovery.
- Add Android device tests for connect, disconnect, reconnect, permission denial, and backend outage fallback.

iOS:

- Add a real Network Extension target to the Expo/EAS native project and include the `ios/PacketTunnel` source template in that target.
- Replace `MissingSingBoxTunnelRunner` in the packet tunnel provider.
- Load config JSON from `providerConfiguration` or shared app group storage.
- Wire packet flow and stop tunnel error handling.
- Add device tests for profile install, connect, disconnect, and config refresh.

Backend:

- Pin the exact sing-box config schema/version in `GET /api/version`.
- Add optional `sing-box check` smoke validation in CI when the binary is present.
- Keep generated config backward compatible across mobile releases.

## Acceptance Criteria

- Android development build starts a real tunnel with backend config.
- iOS development build starts a real Packet Tunnel with backend config.
- `GET /api/config` output passes pinned sing-box validation.
- No unrelated GPL/AGPL source is copied into the app/backend.
- `docs/oss-decisions.md` records GPL-compatible sing-box/libbox distribution.
