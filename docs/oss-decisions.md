# OSS Decisions

This file records upstream projects checked before larger implementation work. Do not copy GPL/AGPL code into proprietary parts without an explicit product/license decision.

## Decisions

| Project | Upstream | License Observed | Use Decision | Reason |
| --- | --- | --- | --- | --- |
| sing-box / libbox | https://github.com/SagerNet/sing-box | GPL-3.0-or-later text in README/LICENSE | Use directly in the mobile app under a GPL-compatible distribution model. | Best protocol coverage for VLESS, Shadowsocks, WireGuard, Hysteria2 and sing-box config format. Product decision on 2026-06-15 accepted GPL runtime integration. |
| sing-box for Android | https://github.com/SagerNet/sing-box-for-android | GPL-3.0-or-later text in README/LICENSE | Reference only; do not copy client code. | Upstream confirms Android libbox integration uses `CommandServer` and `PlatformInterface`. Our adapter uses independently written reflection/proxy code. |
| sing-box for Apple | https://github.com/SagerNet/sing-box-for-apple | GPL-3.0-or-later text in README/LICENSE | Reference only; do not copy client code. | Upstream confirms Apple app wraps packet tunnel implementation through app/library targets. Our iOS template remains independently written until framework artifacts are added. |
| Xray-core | https://github.com/XTLS/Xray-core | MPL-2.0 | Reference or separate component fallback; no current integration. | Useful protocol reference, but MVP config target remains sing-box. MPL is file-level copyleft; still avoid copying source. |
| v2rayNG | https://github.com/2dust/v2rayNG | GPL-3.0 | Reference only. | Android VPN and core integration patterns are useful, but GPL code must not be copied into closed app. |
| ClashMetaForAndroid | https://github.com/MetaCubeX/ClashMetaForAndroid | GPL-3.0 | Reference only. | Useful Android rule-based tunnel reference; GPL code must not be copied. |
| WireGuard Android | https://github.com/WireGuard/wireguard-android | Apache-2.0 | Allowed as dependency/reference if WireGuard-specific mode is needed. | Official Android tunnel library is permissively licensed and published as a library. Not the primary MVP protocol. |
| WireGuard Apple | https://github.com/WireGuard/wireguard-apple | MIT | Allowed as reference for iOS/macOS tunnel structure if WireGuard mode is needed. | Permissive license; still not the primary MVP protocol. |
| Apple NEPacketTunnelProvider docs | https://developer.apple.com/documentation/networkextension/nepackettunnelprovider | Apple documentation | Reference only. | Required iOS API surface for packet tunnel extensions. |
| React Native | https://github.com/facebook/react-native | MIT | Use for shared mobile UI layer. | Permissive license and practical Windows-friendly UI development path. Native VPN services still require platform modules. |
| Expo | https://github.com/expo/expo | MIT | Use for UI shell, config plugin, secure storage, and development-build workflow. | Expo Go cannot host the VPN native runtime, but Expo Development Builds/EAS can include custom native modules. |
| Marzban | https://github.com/Gozargah/Marzban | AGPL-3.0 | Reference or separate deployed component only. | Useful panel/backend reference, but AGPL is not acceptable for copying into closed backend. |
| 3X-UI | https://github.com/MHSanaei/3x-ui | GPL-3.0 | Reference or separate deployed component only. | Useful Xray node/panel reference; do not copy GPL code. |
| v2rayN / Hiddify / Streisand / Shadowrocket | External user-installed clients | Mixed external licenses / proprietary distribution | Do not embed; support through subscription URL, QR, and short instructions only. | The subscription-link MVP avoids shipping our own app in this branch. No external client source code is copied into the backend. |

## Current Choice

- Backend emits sing-box-compatible JSON configs.
- Mobile plan targets a React Native + Expo UI shell with native Android/iOS VPN modules underneath.
- Android native module targets `VpnService` plus sing-box/libbox runtime.
- iOS native module targets `NETunnelProviderManager` plus `NEPacketTunnelProvider`.
- Product decision on 2026-06-15: mobile app distribution must be GPL-compatible if sing-box/libbox is linked or bundled.
- GPL/AGPL projects other than the approved sing-box/libbox runtime remain documentation/reference sources only in this repository.
- Runtime integration decision details are tracked in `docs/runtime-integration-plan.md`.
- Android runtime adapter is independently implemented in `apps/android/app/src/main/java/com/vpnrouter/app/vpn/ReflectionLibboxRunner.kt` and does not vendor upstream GPL source.
- `subscription-link-mvp` does not embed native VPN runtimes or third-party client code. It sells V2Ray/VLESS subscription links for user-installed clients.
- Xray-core (MPL-2.0) is used as a **deployed server-side component** (separate process, not linked). No Xray source is copied into this repository. See `docs/server-setup-vless-reality.md` for setup instructions.
