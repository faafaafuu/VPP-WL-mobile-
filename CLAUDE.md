# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make test                # backend unittest suite (cd backend && python3 -m unittest discover -s tests)
make ci                  # release gate: test + compileall + compose-config + tracked-artifact + sing-box config checks
make run                 # run API locally on 127.0.0.1:8080 (SQLite repo)
make up                  # one-command docker deployment via setup.sh (make up-ssl DOMAIN=... EMAIL=... for HTTPS)
make payment-watch       # one-shot crypto payment watcher pass
make expo-typecheck      # typecheck apps/mobile-expo
make android-debug       # assemble Android debug APK
```

Run a single test module/case (imports resolve from `backend/`):

```bash
cd backend && python3 -m unittest tests.test_api_server
cd backend && python3 -m unittest tests.test_invoice_flow.SomeCase.test_method
```

Before running the server (not needed for tests), export real secrets — placeholder values from `.env.example` are rejected by settings validation:

```bash
export VPN_ROUTER_TOKEN_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export VPN_ROUTER_ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

## Architecture

**Zero-dependency backend.** `backend/pyproject.toml` declares no dependencies on purpose; the API is built on stdlib `http.server.ThreadingHTTPServer` (no FastAPI/Flask), SQLite via stdlib, HMAC tokens via `hmac`/`hashlib`. Keep new code dependency-light so the domain layer stays testable without network installs.

**Layers** (`backend/app/`):
- `api/` — `server.py` holds HTTP routing plus module-level singletons (settings, repository, services) created at import time; `service.py` is the business logic (`ApiService`, raises `ApiError`); `pages.py` renders the public HTML pages (landing, invoice, connect).
- `core/settings.py` — all configuration comes from env vars (`VPN_ROUTER_*`, `CHECKOUT_MODE`, `CRYPTO_*`, `PUBLIC_BASE_URL`), strictly validated at startup via `SettingsError`.
- `domain/` — pure dataclasses and logic: sing-box config generation (`config_builder.py`), V2Ray/VLESS subscription links (`v2ray_subscription.py`), node selection/scoring, tariff parsing, per-order unique crypto amounts (`unique_amount.py`), QR SVG.
- `repositories/` — `factory.py` defines the `Repository` Protocol; `sqlite.py` and `memory.py` implement it. Selected by `VPN_ROUTER_REPOSITORY=sqlite|memory`. Schema in `backend/migrations/001_initial.sql`, applied automatically.
- `security/tokens.py` — HMAC token service.
- `services/` — external integrations: YooKassa, crypto chain providers (TronGrid, Etherscan v2), exchange rates, payment watcher (background thread in the API server, or standalone via `app.cli.payment_watch`), health worker, Telegram bot, Twenty CRM sync, email.

**Two product flows share this backend:**
1. *Mobile app API* — device gets an HMAC token after a store receipt handoff, then `GET /api/config` returns a sing-box client config; `/api/me`, `/api/nodes`, admin node CRUD, health-check worker.
2. *Subscription-link MVP* (current focus, branch `subscription-link-mvp`) — web flow: landing/pricing → `POST /checkout` → payment → `/connect/{token}` → user imports `/sub/{token}` (base64 V2Ray subscription; `/sub/{token}/raw` for debugging, `/sub/{token}/qr`) into v2rayN/v2rayNG/Hiddify/Streisand/Shadowrocket. `CHECKOUT_MODE` is `mock` (instant activation for dev), `yookassa`, or `crypto_manual` (invoice with unique amount matched by the payment watcher).

**Mobile clients** live in `apps/` (native `android/` Gradle project, native `ios/`, and `mobile-expo/`); they consume the API contract in `docs/openapi.yaml` / `docs/mobile-api-contract.md`.

**Repo checks** in `tools/` (env readiness, sing-box config, tracked artifacts, mobile build readiness, libbox artifacts) are wired into Makefile targets and `make ci`; tests in `backend/tests/` also assert on docs, deploy assets, and mobile scaffolds, so structural changes outside `backend/` can fail the suite.

## Conventions

- Tests use stdlib `unittest`, live in `backend/tests/`, and typically use the in-memory repository plus env injection through `load_settings(source=...)`-style dicts.
- Never log user identifiers, generated configs, access tokens, admin tokens, or VPN credentials.
- Do not commit real `.env` files; `.env.example` is the checklist.

## Commit conventions

Every commit MUST follow [Conventional Commits](https://www.conventionalcommits.org/):

- Format: `<type>(<scope>): <summary>` — summary in the imperative mood, lowercase, no trailing period, ≤72 chars.
- Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`.
- Scope: short area touched, e.g. `hysteria2`, `vpn`, `net`, `crm`, `pages`, `settings`, `docker`.
- Body (optional but preferred for non-trivial changes): explain what and why, wrapped ~72 cols.
- Breaking changes: add `!` after the scope (`feat(api)!: …`) or a `BREAKING CHANGE:` footer.
- End every commit message with the `Co-Authored-By` trailer for the active model.
