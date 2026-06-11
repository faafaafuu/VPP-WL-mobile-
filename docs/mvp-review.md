# MVP Review

## Product Slice

The first releasable technical slice should be small:

- User installs the app and starts VPN with one primary action.
- Client sends a store receipt or sandbox receipt to the backend.
- Backend validates entitlement state and returns an access token.
- Client fetches `GET /api/config`.
- The config contains several nodes, RU direct routing, and an automatic outbound group.
- Backend can remove unhealthy nodes from future configs without a mobile release through admin health updates.

## Decisions For This Code Slice

- Backend language: Python for fast iteration.
- Storage in this scaffold: SQLite by default, with an in-memory repository available for tests and demos. The repository interface is intentionally narrow so PostgreSQL can replace it without touching API handlers.
- Auth in this scaffold: signed opaque HMAC token, not a full JWT dependency.
- sing-box config generation is isolated in `ConfigBuilder`.
- Store receipt validation is represented as an interface boundary. Real Google Play/App Store calls are not faked as production code.
- SQL schema lives in `backend/migrations/001_initial.sql`; it is SQLite-compatible for local MVP and should become Alembic/PostgreSQL migrations before production.
- Admin node health endpoints use `X-Admin-Token`; production should replace this with operator auth, audit logs, and least-privilege service tokens.

## Technical Risks

- The exact sing-box JSON schema must be pinned to a specific sing-box release before mobile integration.
- iOS Network Extension entitlements can block release if the developer account and VPN capability are not approved early.
- Domain-based split tunneling depends on DNS handling. Leaks and incorrect direct/proxy decisions need device-level tests.
- "Protocol fallback" is not just a config problem. It needs client-side health checks, protocol-specific errors, and controlled rollout.
- RU direct lists require an update channel, versioning, and rollback because banking/government domains change.

## Compliance Risks

- App Store and Google Play VPN policies must be checked against current official rules before submission.
- Privacy policy, terms, and data retention must be reviewed by counsel for target jurisdictions.
- Avoid claiming exact DPI detection percentages unless backed by current measurements and documented methodology.

## Deferred From MVP

- Full IAP verification against Apple/Google production APIs.
- Production PostgreSQL deployment and migration tooling.
- Admin panel.
- Prometheus/Grafana deployment.
- Mobile sing-box integration.
- Protocol auto-switch telemetry.

## Acceptance Criteria For Backend MVP

- `POST /api/auth/receipt` returns a token for a valid sandbox payload.
- `GET /api/config` rejects missing, invalid, and expired tokens.
- `GET /api/config` rejects users without active subscription.
- Generated config includes `direct`, an automatic proxy outbound, route rules for `.ru`, and rule sets for RU geo data.
- Disabled nodes are not emitted into config.
- `PATCH /api/admin/nodes/{node_id}/health` can mark a node disabled and remove it from future configs.
