# Operations

## Health-Check Worker

Run one pass locally:

```bash
cd backend
VPN_ROUTER_REPOSITORY=sqlite VPN_ROUTER_SQLITE_PATH=data/vpn-router.db \
  python3 -m app.cli.health_check
```

The worker:

- probes enabled VPN nodes;
- updates latency, success rate, health score, health state, and last check timestamp;
- writes a node health audit event;
- prunes old node health audit events using `VPN_ROUTER_AUDIT_RETENTION_DAYS` (default 30, `0` disables cleanup);
- does not log user identifiers, generated configs, access tokens, admin tokens, or VPN credentials.

## Admin Audit

`PATCH /api/admin/nodes/{node_id}/health` writes an admin audit event without storing the admin token. Recent events are available through `GET /api/admin/audit` with `X-Admin-Token`.

## Backend Release Gate

Before handing the backend to mobile development, verify:

```bash
make ci
```

Then deploy the API and run one health-check pass in the target environment.

## systemd Timer

Example units are in `deploy/systemd/`.

Install outline:

```bash
sudo install -o root -g root -m 0644 deploy/systemd/vpn-router-health-check.service /etc/systemd/system/
sudo install -o root -g root -m 0644 deploy/systemd/vpn-router-health-check.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vpn-router-health-check.timer
```

Expected env file: `/etc/vpn-router/backend.env`.

## Docker Compose

Example override is in `deploy/docker/docker-compose.healthcheck.yml`.

For production, prefer a scheduler such as systemd timer, Kubernetes CronJob, Nomad periodic job, or cloud scheduler rather than a long-running loop inside the application container.
