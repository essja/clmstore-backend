#!/usr/bin/env bash
# ============================================================
# CLMStore — Production Deployment Script
# Run this on your Ubuntu/Debian server as a non-root user
# with sudo access.
# ============================================================
set -euo pipefail

DOMAIN="api.clmstore.sl"
APP_DIR="/opt/clmstore"
COMPOSE_FILE="docker-compose.prod.yml"

# Colours
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. Prerequisites ──────────────────────────────────────────
install_docker() {
    if command -v docker &>/dev/null; then
        info "Docker already installed: $(docker --version)"
        return
    fi
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | bash
    sudo usermod -aG docker "$USER"
    sudo systemctl enable docker
    sudo systemctl start docker
    info "Docker installed. You may need to log out and back in for group changes to take effect."
}

install_docker

# ── 2. Copy code (if running locally, skip; on server pull from git) ──
if [ ! -f "$APP_DIR/$COMPOSE_FILE" ]; then
    info "Creating app directory at $APP_DIR"
    sudo mkdir -p "$APP_DIR"
    sudo chown "$USER:$USER" "$APP_DIR"
    info "Copy your project files to $APP_DIR or run: git clone <your-repo> $APP_DIR"
    error "App directory is empty. Add your code first."
fi

cd "$APP_DIR"

# ── 3. Environment file ───────────────────────────────────────
if [ ! -f ".env.production" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env.production
        # Fix Docker service hostnames (localhost → container names)
        sed -i 's|@localhost:5432|@postgres:5432|g'  .env.production
        sed -i 's|redis://localhost|redis://redis|g'  .env.production
        # Also set DB_USER/DB_NAME/DB_PASSWORD/REDIS_PASSWORD for compose interpolation
        echo "" >> .env.production
        echo "# Docker Compose variables (must match what postgres/redis services use)" >> .env.production
        echo "DB_USER=clmstore" >> .env.production
        echo "DB_NAME=clmstore_db" >> .env.production
        echo "DB_PASSWORD=CHANGE_ME_STRONG_DB_PASSWORD" >> .env.production
        echo "REDIS_PASSWORD=CHANGE_ME_STRONG_REDIS_PASSWORD" >> .env.production
        warn ".env.production created — fill in all CHANGE_ME values and API keys, then re-run."
        error "Edit .env.production and re-run this script."
    else
        error ".env.production not found. Create it from .env.example."
    fi
fi

info "Environment file found."

# ── 4. Initial SSL (HTTP-only bootstrap) ──────────────────────
# First-time only: issue the certificate before starting nginx with SSL
issue_ssl() {
    info "Issuing SSL certificate for $DOMAIN via Let's Encrypt..."

    # Temporarily start nginx in HTTP-only mode for ACME challenge
    # Comment out the HTTPS server block during initial issue
    docker run --rm \
        -v "$APP_DIR/nginx/ssl:/etc/letsencrypt" \
        -v "$APP_DIR/certbot_www:/var/www/certbot" \
        -p 80:80 \
        certbot/certbot certonly \
            --standalone \
            --non-interactive \
            --agree-tos \
            --email "tech@clmstore.sl" \
            -d "$DOMAIN"

    # Copy certs to nginx/ssl where nginx expects them
    sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$APP_DIR/nginx/ssl/fullchain.pem"
    sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem  "$APP_DIR/nginx/ssl/privkey.pem"
    sudo chmod 644 "$APP_DIR/nginx/ssl/fullchain.pem"
    sudo chmod 600 "$APP_DIR/nginx/ssl/privkey.pem"

    info "SSL certificates issued and copied."
}

if [ ! -f "nginx/ssl/fullchain.pem" ]; then
    issue_ssl
else
    info "SSL certificates already present."
fi

# ── 5. Build and start ────────────────────────────────────────
info "Building Docker image..."
docker compose -f "$COMPOSE_FILE" build --no-cache api

info "Running database migrations..."
docker compose -f "$COMPOSE_FILE" run --rm api alembic upgrade head

info "Seeding database (creates SUPER_ADMIN and ADMIN from env vars)..."
docker compose -f "$COMPOSE_FILE" run --rm api python seed.py

info "Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d

# ── 6. Health check ───────────────────────────────────────────
info "Waiting for API to become healthy..."
for i in $(seq 1 15); do
    if curl -sf "http://localhost:8000/api/v1/health" >/dev/null 2>&1; then
        info "API is healthy."
        break
    fi
    if [ "$i" -eq 15 ]; then
        error "API did not become healthy after 30s. Run: docker compose -f $COMPOSE_FILE logs api"
    fi
    sleep 2
done

info "========================================================"
info "CLMStore is live at https://$DOMAIN"
info "API docs: https://$DOMAIN/api/v1/docs"
info "========================================================"
