# Runtime Integration Plan

Status: blocked on product/legal decision.

The mobile UI, backend config contract, and native module boundaries are ready for a VPN runtime, but the actual packet proxy engine is intentionally not bundled yet.

## Current Boundary

- Backend emits sing-box-compatible configs.
- Expo UI calls `VpnRouterNative.prepare()`, `start(configJson)`, `stop()`, and `status()`.
- Android native module starts `VpnRouterService`, creates a TUN interface, and passes config JSON plus TUN fd to `SingBoxRunner`.
- iOS native module creates/loads a `NETunnelProviderManager` profile and passes config JSON to the packet tunnel provider through `providerConfiguration`.
- Android and iOS runtime implementations currently fail with explicit missing-runtime errors.

## Decision Required

`sing-box/libbox` is GPL-3.0-or-later. Before bundling it in a distributed mobile app, choose one of these paths:

1. GPL-compatible app distribution.
   - Use sing-box/libbox directly.
   - Publish app source and satisfy GPL obligations.
   - Simplest engineering path, strongest licensing implications.

2. Separate runtime component.
   - Keep closed UI/backend separate from a GPL runtime component.
   - Requires careful legal review and packaging architecture.
   - May be difficult on mobile app stores.

3. Replace primary runtime.
   - Use a permissively licensed engine for the closed app.
   - Likely reduces protocol coverage, especially VLESS/Reality/Hysteria2.
   - Requires backend config format changes or adapters.

4. WireGuard-only first release.
   - Use permissive WireGuard implementations for an initial limited MVP.
   - Does not satisfy the full original sing-box protocol requirement.
   - Easier licensing but weaker anti-blocking behavior.

## Engineering Steps After Decision

Android:

- Replace `MissingSingBoxRunner` in `apps/mobile-expo/modules/vpn-router-native/android`.
- Wire libbox start/stop lifecycle to the existing TUN fd.
- Forward backend config JSON to the runtime.
- Add foreground service notification and lifecycle recovery.
- Add Android device tests for connect, disconnect, reconnect, permission denial, and backend outage fallback.

iOS:

- Add a real Network Extension target to the Expo/EAS native project.
- Replace `MissingSingBoxRunner` in the packet tunnel provider.
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
- No GPL/AGPL source is copied into closed code without an explicit approved decision.
- `docs/oss-decisions.md` records the chosen distribution model before runtime code lands.
