#!/usr/bin/env bash
# setup.sh — first-time setup and optional SSL configuration.
#
# Usage:
#   ./setup.sh                              # HTTP mode (IP:80), generates .env with random secrets
#   ./setup.sh --ssl vpn.example.com admin@example.com  # HTTPS with Let's Encrypt
#   ./setup.sh --force                      # overwrite existing .env
#
# Requires: docker, docker compose v2
set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[setup]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
die()   { echo -e "${RED}[err]${NC}  $*" >&2; exit 1; }

# ── parse args ───────────────────────────────────────────────────────────────
SSL_DOMAIN=""
SSL_EMAIL=""
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssl)
            [[ $# -ge 3 ]] || die "Usage: --ssl DOMAIN EMAIL"
            SSL_DOMAIN="$2"; SSL_EMAIL="$3"; shift 3 ;;
        --force) FORCE=true; shift ;;
        -h|--help)
            echo "Usage: $0 [--ssl DOMAIN EMAIL] [--force]"
            exit 0 ;;
        *) die "Unknown argument: $1" ;;
    esac
done

# ── checks ───────────────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || die "docker not found. Install Docker: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "docker compose v2 not found. Update Docker Desktop or install the plugin."

cd "$(dirname "$(realpath "$0")")"

# ── generate .env ─────────────────────────────────────────────────────────────
if [[ -f .env && "$FORCE" == false ]]; then
    warn ".env already exists — skipping secret generation (use --force to overwrite)"
else
    info "Creating .env from .env.example with random secrets..."
    cp .env.example .env

    # Generate cryptographically random secrets
    if command -v openssl >/dev/null 2>&1; then
        TOKEN_SECRET=$(openssl rand -hex 32)
        ADMIN_TOKEN=$(openssl rand -hex 24)
    else
        TOKEN_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        ADMIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(24))")
    fi

    # Replace placeholder values in .env
    sed -i "s|replace-with-random-32-byte-secret|${TOKEN_SECRET}|g" .env
    sed -i "s|replace-with-random-admin-token|${ADMIN_TOKEN}|g"     .env

    ok "Generated VPN_ROUTER_TOKEN_SECRET and VPN_ROUTER_ADMIN_TOKEN"
fi

# ── sanitize .env: comment out any remaining placeholder values ───────────────
# Settings validation rejects "replace-with-*" values; comment them out so the
# API treats optional services (YooKassa, etc.) as unconfigured rather than crashing.
if grep -qE '^[^#].*=replace-with-' .env 2>/dev/null; then
    warn "Found placeholder values in .env — commenting them out (configure manually when needed)"
    sed -i 's|^\([^#][^=]*=replace-with-[^[:space:]]*\)|# \1|g' .env
fi

# ── set PUBLIC_BASE_URL ──────────────────────────────────────────────────────
if [[ -n "$SSL_DOMAIN" ]]; then
    BASE_URL="https://${SSL_DOMAIN}"
else
    # Try to detect the server's public IP for the URL hint
    SERVER_IP=$(curl -s --max-time 3 https://api.ipify.org 2>/dev/null || echo "YOUR_SERVER_IP")
    BASE_URL="http://${SERVER_IP}"
fi

# Only update if it still has the placeholder
if grep -q "SERVER_IP\|example\.com" .env 2>/dev/null; then
    sed -i "s|PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=${BASE_URL}|g" .env
    ok "Set PUBLIC_BASE_URL=${BASE_URL}"
fi

# ── stop and remove all existing project containers ───────────────────────────
info "Stopping existing containers..."
docker compose down --remove-orphans 2>/dev/null || true
# Also clean up containers from old project name (directory rename, etc.)
old_containers=$(docker ps -a --format "{{.Names}}" 2>/dev/null \
    | grep -E "^(vpp-wl-mobile--|vpn-router-)" || true)
if [[ -n "$old_containers" ]]; then
    warn "Removing stale containers: $(echo "$old_containers" | tr '\n' ' ')"
    echo "$old_containers" | xargs docker rm -f 2>/dev/null || true
fi
ok "Cleaned up old containers"

# ── check for processes holding ports 80/443 ──────────────────────────────────
_listeners_on_port() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -tlnp 2>/dev/null | awk 'NR>1 && /LISTEN/' | grep -E ":${port}([^0-9]|$)" || true
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tlnp 2>/dev/null | grep "LISTEN" | grep -E ":${port}([^0-9]|$)" || true
    else
        lsof -iTCP:"${port}" -sTCP:LISTEN -n -P 2>/dev/null || true
    fi
}

_free_port() {
    local port="$1"
    local listening
    listening=$(_listeners_on_port "$port")
    [[ -z "$listening" ]] && return 0   # port is free

    # Case 1: held by docker-proxy → a container still publishes this port
    if echo "$listening" | grep -q docker-proxy; then
        local containers
        containers=$(docker ps -a --format '{{.ID}} {{.Ports}}' 2>/dev/null \
            | grep -E ":${port}->" | awk '{print $1}' || true)
        if [[ -n "$containers" ]]; then
            warn "Removing containers publishing port ${port}..."
            echo "$containers" | xargs docker rm -f 2>/dev/null || true
            sleep 1
        fi
        # Re-check: if docker-proxy still lingers, it's orphaned → restart daemon
        listening=$(_listeners_on_port "$port")
        if echo "$listening" | grep -q docker-proxy; then
            warn "Orphaned docker-proxy on port ${port} — restarting Docker daemon..."
            systemctl restart docker 2>/dev/null || service docker restart 2>/dev/null || true
            sleep 3
        fi
        listening=$(_listeners_on_port "$port")
        [[ -z "$listening" ]] && return 0
    fi

    # Case 2: held by a system web server → stop it
    for svc in nginx apache2 apache httpd caddy; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            systemctl stop "$svc" && systemctl disable "$svc" \
                && ok "Stopped system service: ${svc}" \
                || die "Could not stop ${svc}. Run: systemctl stop ${svc}"
            return 0
        fi
    done

    listening=$(_listeners_on_port "$port")
    [[ -z "$listening" ]] && return 0
    die "Port ${port} is held by an unknown process:\n  ${listening}\nFree it and re-run setup.sh."
}

info "Checking ports 80 and 443..."
_free_port 80
_free_port 443
ok "Ports 80 and 443 are free"

# ── nginx: HTTP mode (default) ───────────────────────────────────────────────
if [[ -z "$SSL_DOMAIN" ]]; then
    info "nginx → HTTP mode (port 80)"
    # default.conf is already HTTP mode — no changes needed
    echo ""
    info "Starting services..."
    docker compose up -d --build
    echo ""
    ok "All services started."
    echo ""
    echo -e "  ${CYAN}API${NC}        →  http://${SERVER_IP:-localhost}"
    echo -e "  ${CYAN}Health${NC}     →  http://${SERVER_IP:-localhost}/health"
    echo ""
    echo -e "  Admin token: $(grep VPN_ROUTER_ADMIN_TOKEN .env | cut -d= -f2)"
    echo ""
    warn "Running on HTTP. For HTTPS run: ./setup.sh --ssl your.domain.com admin@email.com"
    exit 0
fi

# ── SSL mode ─────────────────────────────────────────────────────────────────
info "SSL mode: domain=${SSL_DOMAIN}, email=${SSL_EMAIL}"

# Validate domain looks reasonable
[[ "$SSL_DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+$ ]] \
    || die "Invalid domain: ${SSL_DOMAIN}"
[[ "$SSL_EMAIL" == *@* ]] || die "Invalid email: ${SSL_EMAIL}"

# Generate HTTPS nginx config from template (replace DOMAIN_PLACEHOLDER)
info "Generating nginx HTTPS config for ${SSL_DOMAIN}..."
sed "s/DOMAIN_PLACEHOLDER/${SSL_DOMAIN}/g" deploy/nginx/ssl.conf.template > deploy/nginx/default.conf
ok "deploy/nginx/default.conf updated for ${SSL_DOMAIN}"

# Update .env with correct PUBLIC_BASE_URL
sed -i "s|PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://${SSL_DOMAIN}|g" .env
ok "PUBLIC_BASE_URL=https://${SSL_DOMAIN}"

# Build the image
info "Building Docker image..."
docker compose build api

# Start api (needs to be healthy before nginx starts)
info "Starting api service..."
docker compose up -d api

info "Waiting for API to become healthy..."
for i in $(seq 1 30); do
    if docker compose exec -T api python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)" 2>/dev/null; then
        ok "API is healthy"
        break
    fi
    [[ $i -eq 30 ]] && die "API did not become healthy in 60s. Check: docker compose logs api"
    sleep 2
done

# Start nginx in HTTP mode to serve ACME challenge
info "Starting nginx (HTTP mode for ACME challenge)..."
docker compose up -d nginx

# Get initial certificate via webroot challenge
info "Requesting Let's Encrypt certificate for ${SSL_DOMAIN}..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --email "${SSL_EMAIL}" \
    --agree-tos \
    --no-eff-email \
    -d "${SSL_DOMAIN}"

ok "Certificate obtained!"

# Reload nginx with HTTPS config (config already points to SSL certs)
info "Reloading nginx with HTTPS config..."
docker compose exec nginx nginx -s reload

# Start certbot renewal daemon
info "Starting certbot renewal daemon..."
docker compose up -d certbot

echo ""
ok "All services running."
echo ""
echo -e "  ${CYAN}API${NC}    →  https://${SSL_DOMAIN}"
echo -e "  ${CYAN}Health${NC} →  https://${SSL_DOMAIN}/health"
echo ""
echo -e "  Admin token: $(grep VPN_ROUTER_ADMIN_TOKEN .env | cut -d= -f2)"
echo ""
info "Cert auto-renews every 12h via certbot service."
info "Check logs: docker compose logs -f"
