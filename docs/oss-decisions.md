# OSS Decisions

This file records upstream projects checked before larger implementation work. Do not copy GPL/AGPL code into proprietary parts without an explicit product/license decision.

## Decisions

| Project | Upstream | License Observed | Use Decision | Reason |
| --- | --- | --- | --- | --- |
| sing-box / libbox | https://github.com/SagerNet/sing-box | GPL-3.0-or-later text in README/LICENSE | Use directly in the mobile app under a GPL-compatible distribution model. | Best protocol coverage for VLESS, Shadowsocks, WireGuard, Hysteria2 and sing-box config format. Product decision on 2026-06-15 accepted GPL runtime integration. |
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

## Current Choice

- Backend emits sing-box-compatible JSON configs.
- Mobile plan targets a React Native + Expo UI shell with native Android/iOS VPN modules underneath.
- Android native module targets `VpnService` plus sing-box/libbox runtime.
- iOS native module targets `NETunnelProviderManager` plus `NEPacketTunnelProvider`.
- Product decision on 2026-06-15: mobile app distribution must be GPL-compatible if sing-box/libbox is linked or bundled.
- GPL/AGPL projects other than the approved sing-box/libbox runtime remain documentation/reference sources only in this repository.
- Runtime integration decision details are tracked in `docs/runtime-integration-plan.md`.
