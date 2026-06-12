# Mobile Expo UI

This is the React Native + Expo UI shell for the VPN client.

It is intentionally separate from `apps/android` and `apps/ios` because the VPN runtime still needs native platform code:

- Android: `VpnService` plus sing-box/libbox integration.
- iOS: `NEPacketTunnelProvider` plus sing-box/libbox integration.
- Expo Go is not enough because it cannot include custom native VPN services, app entitlements, or Network Extension targets.
- Use Expo Development Builds / EAS builds for devices that need the VPN module.

## Why Expo Here

The UI can be developed on Windows with Metro and Android tooling while iOS native project work is handled later by EAS or a macOS CI runner. This keeps the user-facing application in TypeScript/React Native and leaves the privileged VPN lifecycle in native modules.

Official docs checked:

- Expo development builds: https://docs.expo.dev/develop/development-builds/introduction/
- Expo Modules API: https://docs.expo.dev/modules/overview/
- Expo config plugins: https://docs.expo.dev/config-plugins/introduction/

## Runtime Boundary

The UI calls a native module contract:

```ts
VpnRouterNative.prepare()
VpnRouterNative.start(configJson)
VpnRouterNative.stop()
VpnRouterNative.status()
```

The module must be implemented per platform. This scaffold only defines the TypeScript boundary and a clear missing-runtime error. It does not vendor sing-box, Xray, v2rayNG, ClashMetaForAndroid, Marzban, or 3X-UI code.

## Android Native Module

`modules/vpn-router-native` declares an Expo local module named `VpnRouterNative`.

Current Android skeleton:

- exposes `start(configJson)`, `stop()`, and `status()` to JavaScript;
- checks Android VPN permission with `VpnService.prepare`;
- opens the Android system VPN permission screen through `prepare()`;
- starts `VpnRouterService` with the backend-provided sing-box config JSON;
- creates a TUN interface and passes its file descriptor to `SingBoxRunner`;
- keeps `MissingSingBoxRunner` until the sing-box/libbox distribution and license decision is explicit.

This gives the UI a stable native boundary without bundling the proxy runtime yet.

## iOS Native Module

The same local module also declares an Apple Expo module.

Current iOS skeleton:

- exposes `start(configJson)`, `stop()`, and `status()` to JavaScript;
- exposes `prepare()` as a no-op because iOS permission is handled by the saved VPN profile flow;
- uses `NETunnelProviderManager` to create or load the VPN profile;
- stores the backend-provided sing-box config JSON in `providerConfiguration`;
- reads `VpnRouterTunnelProviderBundleIdentifier` from Info.plist;
- requires a real Network Extension target and entitlements before device testing.

iOS still needs EAS or a macOS/Xcode runner for actual builds.

## Backend Flow

1. Store an access token in secure storage.
2. Fetch `GET /api/config` with `Authorization: Bearer <token>`.
3. Save the returned sing-box JSON as last-known-good config.
4. Start the native VPN module with that config.
5. On `503` or `5xx`, fall back to the encrypted last-known-good config if present.
6. On `401`, clear auth and show the subscription/auth state.
7. On `403`, stop VPN and show subscription required.

The current UI includes a sandbox auth panel for MVP testing. It can call `/api/auth/init` to create/resume a user by device id, then sends the receipt to `/api/auth/receipt`, stores only the returned access token, and does not persist the receipt.
Privacy and terms links are shown before activation/purchase and are configured through `EXPO_PUBLIC_PRIVACY_URL` and `EXPO_PUBLIC_TERMS_URL`.

The UI also includes a diagnostics-only node panel backed by `GET /api/nodes`. The VPN runtime should still use `/api/config` for actual routing and failover.

## Local Development

Install dependencies only when Node tooling is available:

```bash
npm install
npm run start
```

Copy `.env.example` to `.env.local` and set the backend URL:

```bash
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8080
EXPO_PUBLIC_PRIVACY_URL=https://example.com/privacy
EXPO_PUBLIC_TERMS_URL=https://example.com/terms
```

For native VPN testing, create a development build:

```bash
npx expo prebuild
npx eas build --profile development --platform android
npx eas build --profile development --platform ios
```

Windows developers can run Metro and Android builds locally. iOS builds require EAS or macOS/Xcode.

`eas.json` contains three profiles:

- `development`: internal development client with native VPN module included.
- `preview`: internal APK/TestFlight-style validation.
- `production`: store-oriented build with local app versioning.

## Files To Add Later

- Native Android implementation of `VpnRouterNative`.
- Native iOS Expo module that controls the app-side `NETunnelProviderManager`.
- iOS Network Extension target generated/maintained through config plugin or dedicated native project.
- Store purchase UI and receipt flow.
