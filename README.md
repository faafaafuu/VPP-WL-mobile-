# VPN Router MVP

Mobile VPN/router service with "install and forget" UX. The first backend slice focuses on subscription-aware config delivery for sing-box clients.

## MVP Scope

- Issue an API token after a store receipt handoff.
- Expose API/config compatibility metadata through `GET /api/version`.
- Keep users, subscriptions, and VPN nodes behind repository interfaces.
- Return a sing-box client config from `GET /api/config`.
- Return current user/subscription state from `GET /api/me`.
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
  backend-readiness.md  checklist before mobile development
  privacy-policy-draft.md  privacy policy draft for legal review
  terms-draft.md  terms draft for legal review
  store-readiness.md  app store submission checklist
  runtime-integration-plan.md  VPN runtime licensing and integration plan
deploy/
  monitoring/        Prometheus alerts and Grafana dashboard templates
  nginx/             HTTPS reverse proxy template for production
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
Set `VPN_ROUTER_CORS_ORIGINS` only for browser-based dev tooling such as Expo Web; native mobile clients do not require CORS.
Set `VPN_ROUTER_RATE_LIMIT_PER_MINUTE=0` only for isolated local debugging; production should keep rate limiting enabled.
Set `VPN_ROUTER_HSTS_ENABLED=true` only when the API is served over HTTPS.

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

Monitoring templates are in `deploy/monitoring/`. Replace placeholder API/node targets before deploying Prometheus or Grafana.

## Test

```bash
make test
```

Run the local CI-equivalent checks:

```bash
make ci
```

Optional sing-box binary validation:

```bash
make sing-box-check
python3 tools/check_sing_box_config.py --require-binary
```

The default target validates config shape and skips the binary step when `sing-box` is not installed. Use `--require-binary` in staging/release jobs with a pinned binary.

Validate a deployment env file before starting staging/prod:

```bash
VPN_ROUTER_ENV_FILE=.env make env-check
python3 tools/check_env_ready.py --env-file .env --require-hsts
```

## Graphify

```bash
make graphify
```

The current graph artifacts are in `graphify-out/graph.json` and `graphify-out/manifest.json`.
