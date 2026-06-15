# Runtime Integration Plan

Status: GPL-compatible sing-box/libbox integration approved on 2026-06-15; Android runtime adapter is present behind reflection and activates when libbox is on the APK classpath. Remaining blockers are pinned runtime artifacts, device QA, staging credentials, and iOS EAS/Apple credentials.

The mobile UI, backend config contract, and native module boundaries are ready for a VPN runtime, but the actual packet proxy engine is intentionally not bundled yet.

## Current Boundary

- Backend emits sing-box-compatible configs.
- Expo UI calls `VpnRouterNative.prepare()`, `start(configJson)`, `stop()`, and `status()`.
- Android native module starts `VpnRouterService` and passes config JSON to `SingBoxRunner`.
- `ReflectionLibboxRunner` detects `io.nekohasekai.libbox` at runtime, creates a libbox `CommandServer`, and provides `PlatformInterface.OpenTun` via Android `VpnService.Builder`.
- iOS native module creates/loads a `NETunnelProviderManager` profile and passes config JSON to the packet tunnel provider through `providerConfiguration`.
- `apps/mobile-expo/modules/vpn-router-native/ios/PacketTunnel` contains a minimal `NEPacketTunnelProvider` source template that reads `configJson` and delegates packet handling to a `SingBoxTunnelRunner` boundary. It intentionally keeps `MissingSingBoxTunnelRunner` until libbox artifacts are added.
- Android still falls back to `MissingSingBoxRunner` when libbox is not bundled.
- iOS runtime implementation still fails with an explicit missing-runtime error until the real framework and Network Extension target are built through EAS/Xcode.

## Approved Runtime Decision

`sing-box/libbox` is GPL-3.0-or-later. Product decision on 2026-06-15 selected the GPL-compatible app distribution path:

- Use sing-box/libbox directly in mobile runtime modules.
- Publish app source and satisfy GPL obligations for distributed mobile builds.
- Keep backend proprietary/GPL boundary under legal review if distribution model changes later.
- Do not copy unrelated GPL/AGPL client source from v2rayNG, ClashMetaForAndroid, Marzban, or 3X-UI.

## Engineering Steps

Android:

- Add the pinned GPL libbox AAR/framework artifact to the Android build.
- Device-test `ReflectionLibboxRunner` against the exact generated gomobile Java API.
- Forward backend config JSON to the runtime. (Implemented in standalone Android scaffold.)
- Keep foreground service notification and lifecycle recovery. (Implemented in standalone Android scaffold.)
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
