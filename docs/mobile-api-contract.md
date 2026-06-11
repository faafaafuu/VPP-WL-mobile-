# Mobile API Contract

This contract is for Android/iOS clients that embed a VPN runtime and request sing-box configs from the backend.

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
- Only usable backend nodes sorted by score.

## Nodes Flow

`GET /api/nodes`

Use this for diagnostics/status UI only. The VPN runtime should use `/api/config`.

## Error Handling

| Status | Meaning | Mobile Client Reaction |
| --- | --- | --- |
| 400 | Bad request | Show generic setup error; client bug or invalid receipt payload. |
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

