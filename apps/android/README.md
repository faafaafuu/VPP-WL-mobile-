# Android Foundation

## Approach

- Language: Kotlin.
- VPN API: Android `VpnService`.
- Runtime target: sing-box/libbox config execution.
- UI target: one primary connect/disconnect control, small status panel, subscription screen.

## OSS Reviewed

- sing-box / libbox: primary config/runtime target, GPL licensing requires explicit distribution decision before bundling in a closed app.
- v2rayNG: Android VPN/core integration reference only; GPL code is not copied.
- ClashMetaForAndroid: Android rule/tunnel reference only; GPL code is not copied.
- WireGuard Android: permissive Apache-2.0 option for WireGuard-specific mode, not the MVP runtime.

See `docs/oss-decisions.md` for licensing notes.

## Planned Modules

```text
apps/android/
  app/
    src/main/java/.../MainActivity.kt
    src/main/java/.../VpnRouterService.kt
    src/main/java/.../config/ConfigRepository.kt
    src/main/java/.../auth/TokenStore.kt
    src/main/java/.../vpn/SingBoxRunner.kt
```

## VPN Flow

1. User taps connect.
2. App ensures VPN permission through `VpnService.prepare`.
3. App obtains or refreshes API token.
4. App calls backend `GET /api/config`.
5. App stores last known good config securely.
6. `VpnRouterService` starts sing-box/libbox with the config.
7. Client health checks trigger config refresh or reconnect when repeated failures happen.

## Not Implemented Yet

- Gradle scaffold.
- sing-box AAR/libbox dependency.
- Actual `VpnService` implementation.
- Secure token storage.
- UI.

Create the Gradle/Kotlin scaffold after the backend contract stabilizes and the sing-box distribution/license decision is explicit.

