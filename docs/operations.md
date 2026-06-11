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
- does not log user identifiers, generated configs, access tokens, admin tokens, or VPN credentials.

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

