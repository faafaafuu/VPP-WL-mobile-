# Backend Readiness Before Mobile Development

This checklist defines the backend state needed before starting Android/iOS implementation.

## Ready

- Subscription-aware auth stub exists.
- Production Apple/Google receipts fail closed until real store validation is configured.
- Protected `/api/config` returns validated sing-box JSON.
- Routing rules engine emits direct/proxy categories.
- RU direct placeholders and common proxy fallback domains are present.
- Node model supports provider, protocol, latency, success rate, last check time, health state, and score.
- Config includes only usable nodes sorted by score.
- Admin health update endpoint is protected by env-provided admin token.
- Automated health-check worker updates node metrics.
- Health-check events are audited without user traffic logs.
- Self-service account export/delete endpoints exist for privacy flows.
- SQLite persistence works for MVP/local/staging.
- Docker image and Docker Compose config exist.
- systemd timer/service snippets exist for health checks.
- OpenAPI sketch exists in `docs/openapi.yaml`.
- Mobile API contract exists in `docs/mobile-api-contract.md`.
- CI runs unit tests, compileall, compose config validation, and graphify JSON sanity.
- OSS licensing decisions are documented.
- Graphify graph is tracked at `graphify-out/graph.json`.

## Required Before Public Production

- Replace sandbox receipt validation with real Apple/Google validation.
- Move from SQLite to PostgreSQL with managed backups and migration tooling.
- Replace shared admin token with operator auth and scoped service tokens.
- Add audit retention policy for backend health/admin events.
- Replace rule-set placeholder URLs with signed/versioned real artifacts.
- Run sing-box binary validation against the pinned sing-box version.
- Add TLS/HTTPS deployment in front of API.
- Add monitoring dashboards and alerts for API, DB, and health-check job failures.
- Complete privacy policy, terms, and store compliance review.

## Mobile Can Start When

- Mobile team accepts `docs/mobile-api-contract.md`.
- Android team accepts `apps/android/README.md` architecture.
- iOS team accepts `apps/ios/README.md` architecture and Network Extension scaffold.
- Product/legal explicitly decides how sing-box/libbox GPL distribution will be handled.
- A staging API URL is deployed from this backend image.
- A non-placeholder `.env` exists in staging secret storage.
