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
    src/main/java/.../config/EncryptedConfigStore.kt
    src/main/java/.../auth/TokenStore.kt
    src/main/java/.../auth/EncryptedTokenStore.kt
    src/main/java/.../vpn/SingBoxRunner.kt
```

The initial scaffold now contains these files, but `SingBoxRunner` is intentionally an interface with a missing-runtime implementation. No sing-box/libbox source or binary is vendored into this repository.

## VPN Flow

1. User taps connect.
2. App ensures VPN permission through `VpnService.prepare`.
3. App obtains or refreshes API token.
4. `ConfigRepository` calls backend `GET /api/config`.
5. Fresh configs are stored through `EncryptedConfigStore`.
6. On network/5xx/503 errors, `ConfigRepository` can return the encrypted last-known-good config.
7. `MainActivity` starts `VpnRouterService.connectIntent(context, configJson)` with fresh or cached config.
8. `VpnRouterService` starts sing-box/libbox with the config after runtime integration is approved.
9. Client health checks trigger config refresh or reconnect when repeated failures happen.

## Not Implemented Yet

- sing-box AAR/libbox dependency.
- Production `VpnService` runtime wiring.
- Subscription UI.

## Local Secure Storage

- `EncryptedTokenStore` stores access tokens using AndroidX Security `EncryptedSharedPreferences`.
- `EncryptedConfigStore` stores the last-known-good sing-box config and save timestamp using the same encrypted preferences factory.
- The implementation still needs instrumentation tests on a device/emulator once Android SDK is available in CI.

## Build Requirements

On a development machine, install:

- JDK 17 or newer.
- Android SDK command line tools.
- Android SDK Platform 35.
- Android SDK Build Tools 34.0.0 or newer.

Then run:

```bash
python3 tools/check_mobile_build_ready.py --android
make android-debug
```

The project uses the checked-in Gradle Wrapper, not the system Gradle package. If `ANDROID_HOME` is not set, `make android-debug` defaults to `/usr/lib/android-sdk`.

Before wiring the actual VPN runtime, decide whether the app is GPL-compatible or whether sing-box/libbox is distributed as a separate component.
