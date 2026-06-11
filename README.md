# VPN Router MVP

Mobile VPN/router service with "install and forget" UX. The first backend slice focuses on subscription-aware config delivery for sing-box clients.

## MVP Scope

- Issue an API token after a store receipt handoff.
- Keep users, subscriptions, and VPN nodes behind repository interfaces.
- Return a sing-box client config from `GET /api/config`.
- Route Russian domains and rule sets directly, route the rest through an automatic proxy group.
- Expose active nodes through `GET /api/nodes`.
- Keep implementation dependency-light so the domain layer is testable without network installs.

## Repository Layout

```text
backend/
  app/
    api/             HTTP API entrypoint
    domain/          dataclasses, config generation, node selection
    repositories/    SQLite and in-memory repositories
    security/        HMAC token service
  migrations/        SQL schema
  tests/             unittest test suite
docs/
  mvp-review.md      narrowed MVP, risks, and next decisions
```

## Run Locally

```bash
make run
```

The server listens on `127.0.0.1:8080` by default.
By default it uses SQLite at `backend/data/vpn-router.db` and creates the schema automatically.
Set required secrets before running:

```bash
export VPN_ROUTER_TOKEN_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export VPN_ROUTER_ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Do not run the backend with the placeholder values from `.env.example`; they are rejected by runtime settings validation.

Repository modes:

```bash
VPN_ROUTER_REPOSITORY=sqlite VPN_ROUTER_SQLITE_PATH=data/vpn-router.db make run
VPN_ROUTER_REPOSITORY=memory make run
```

Use `.env.example` as a checklist; do not commit real `.env` files.

Example flow:

```bash
curl -s -X POST http://127.0.0.1:8080/api/auth/receipt \
  -H 'Content-Type: application/json' \
  -d '{"platform":"sandbox","receipt":"demo","device_id":"device-1"}'
```

Use the returned `access_token`:

```bash
curl -s http://127.0.0.1:8080/api/config \
  -H "Authorization: Bearer $TOKEN"
```

Admin node health flow:

```bash
curl -s http://127.0.0.1:8080/api/admin/nodes \
  -H "X-Admin-Token: $VPN_ROUTER_ADMIN_TOKEN"

curl -s -X PATCH http://127.0.0.1:8080/api/admin/nodes/node_eu_1/health \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $VPN_ROUTER_ADMIN_TOKEN" \
  -d '{"health_score":0,"status":"disabled"}'
```

Disabled nodes are excluded from subsequent user configs.

Run one automated node health-check pass:

```bash
cd backend
VPN_ROUTER_REPOSITORY=sqlite VPN_ROUTER_SQLITE_PATH=data/vpn-router.db \
  python3 -m app.cli.health_check
```

The worker probes enabled nodes, updates latency/success-rate/health, and future `/api/config` responses use the updated scores.

## Docker

```bash
cp .env.example .env
# edit .env and replace placeholder secrets before starting the API
docker compose build
docker compose up api
```

For syntax checks without a real `.env`:

```bash
VPN_ROUTER_ENV_FILE=.env.example docker compose config
```

Run a one-shot health-check job against the same SQLite volume:

```bash
docker compose --profile jobs run --rm health-check
```

## Test

```bash
make test
```

Run the local CI-equivalent checks:

```bash
make ci
```

## Graphify

```bash
make graphify
```

The current graph artifacts are in `graphify-out/graph.json` and `graphify-out/manifest.json`.
