# Security Policy

## Backend MVP Rules

- Do not log traffic contents.
- Do not store traffic contents.
- Do not log access tokens, admin tokens, store receipts, VPN keys, or generated client secrets.
- Runtime secrets must come from environment variables or a secret manager.
- `VPN_ROUTER_TOKEN_SECRET` is required for HMAC access tokens.
- `VPN_ROUTER_ADMIN_TOKEN` is required for admin endpoints.
- `.env` files are ignored and must not be committed.
- SQLite is for MVP/local operation only. Production should move to PostgreSQL with managed backups and migration tooling.
- Admin endpoints currently use a shared token; production needs operator auth, scoped service tokens, and audit logs.
- Config delivery must stay over HTTPS in production.
- Health-check workers must not log VPN credentials, generated configs, or user identifiers.

## Privacy By Design

- Collect the minimum data needed for subscription state, support, and abuse prevention.
- Keep traffic logs out of the product by default.
- Keep user deletion/export requirements in the mobile API and backend roadmap.
- Crash/error reporting must redact tokens, receipts, endpoint secrets, and user traffic metadata.
