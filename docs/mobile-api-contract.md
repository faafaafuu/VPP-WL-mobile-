# Mobile API Contract

This contract is for Android/iOS clients that embed a VPN runtime and request sing-box configs from the backend. The current UI direction may use React Native + Expo, but the VPN lifecycle remains a native module on both platforms.

The machine-readable API sketch is tracked in `docs/openapi.yaml`.

## Version Flow

`GET /api/version`

Use this endpoint before rollout testing and after app updates to check API/config compatibility. It returns API version, sing-box config version, minimum supported client version, and feature flags.

Current feature flags:

- `smart-routing`
- `node-scoring`
- `last-known-good-config`
- `expo-native-vpn-boundary`
- `account-data-export`
- `account-deletion`
- `admin-audit`

## Base Requirements

- All production calls must use HTTPS.
- Mobile clients store access tokens in Android Keystore / iOS Keychain.
- Clients must not log access tokens, receipts, or full generated configs.
- Clients should send `Authorization: Bearer <access_token>` for protected endpoints.

## Auth Flow

### Create Or Resume User

`POST /api/auth/init`

Request:

```json
{"device_id":"stable-installation-id"}
```

Response:

```json
{"user_id":"usr_..."}
```

### Activate Subscription

`POST /api/auth/receipt`

Request:

```json
{
  "platform": "sandbox",
  "receipt": "store-receipt-or-sandbox-token",
  "device_id": "stable-installation-id",
  "product_id": "vpn.monthly"
}
```

Response:

```json
{
  "access_token": "opaque-hmac-token",
  "token_type": "Bearer",
  "expires_at": "2026-07-11T00:00:00+00:00"
}
```

Production platforms will be `apple` and `google` after store validation is implemented.
`product_id` must be one of the backend allowlisted products, configured through `VPN_ROUTER_ALLOWED_PRODUCT_IDS`.

## Config Flow

`GET /api/config`

Headers:

```text
Authorization: Bearer <access_token>
```

Response:

```json
{
  "inbounds": [{"type":"tun","tag":"tun-in"}],
  "outbounds": [{"type":"urltest","tag":"auto"}],
  "route": {"rules": [], "final": "auto"}
}
```

The response is a sing-box client config. It includes:

- `direct` outbound for RU domains/rule sets.
- `auto` outbound group for proxy nodes.
- Explicit proxy rules for Telegram, Instagram, YouTube, OpenAI, X, Discord, and GitHub.
- Remote RU rule sets use versioned URLs with checksum query parameters and a 24h update interval.
- Only usable backend nodes sorted by score.

## Nodes Flow

`GET /api/nodes`

Use this for diagnostics/status UI only. The VPN runtime should use `/api/config`.

## Account Flow

`GET /api/me`

Returns the current user id and active subscription summary. Mobile clients should use this after app start or foreground resume to refresh subscription UI without requesting a VPN config.

`GET /api/me/export`

Returns account and subscription data for privacy export flows. This is not used by the VPN runtime; it is only for account/privacy screens.

`DELETE /api/me`

Deletes the current user account and subscription data. The mobile client must clear the stored access token and last-known-good config after a successful response.

## Error Handling

| Status | Meaning | Mobile Client Reaction |
| --- | --- | --- |
| 400 | Bad request | Show generic setup error; client bug, invalid receipt payload, or production store validation not configured. |
| 401 | Missing/invalid/expired token | Stop VPN if already running, clear token, re-run receipt/auth flow. |
| 403 | No active subscription | Stop VPN, show subscription screen. |
| 404 | Missing resource | Treat as non-retryable client/backend version mismatch. |
| 503 | No usable nodes or invalid generated config | Keep last known good config if available, retry with backoff. |
| 5xx | Backend failure | Keep last known good config if available, retry with exponential backoff. |

## Config Refresh

- Fetch config on first connect.
- Refresh config at app foreground if older than 6 hours.
- Refresh config after VPN failure or node failover exhaustion.
- Use exponential backoff for backend failures: 15s, 30s, 60s, 5m, max 15m.
- Keep the last known good config encrypted at rest so a short backend outage does not break existing users.

## Fallback Behavior

1. sing-box `urltest` chooses the best available outbound from the config.
2. Backend excludes disabled/degraded/flaky nodes from future configs.
3. Client should request a fresh config when connection checks fail repeatedly.
4. If all nodes fail, client shows a simple service-unavailable state and keeps retrying in the background.

## Expo UI Boundary

Expo is allowed for the shared UI shell and backend contract handling.

- Expo Go is not a target runtime for VPN features.
- Development builds/EAS builds are required once `VpnRouterNative` is implemented.
- The JavaScript UI calls `VpnRouterNative.prepare()`, `start(configJson)`, `stop()`, and `status()`.
- Android implementation wraps `VpnService`.
- iOS implementation controls `NETunnelProviderManager`; packet traffic stays inside `NEPacketTunnelProvider`.
- The UI must not log access tokens, store receipts, or full configs.
