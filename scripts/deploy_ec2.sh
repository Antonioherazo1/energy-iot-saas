#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
WEB_ROOT="/var/www/thinc"

echo "==> Deploy Energy IoT SaaS"
echo "Root: $ROOT_DIR"

if [ ! -d "$BACKEND_DIR" ]; then
  echo "Backend directory not found: $BACKEND_DIR" >&2
  exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "Frontend directory not found: $FRONTEND_DIR" >&2
  exit 1
fi

echo "==> Rebuilding backend"
cd "$BACKEND_DIR"
docker compose down
docker compose up -d --build
docker compose exec api alembic upgrade head

echo "==> Building frontend"
cd "$FRONTEND_DIR"
npm install
npm run build

echo "==> Publishing frontend to $WEB_ROOT"
sudo mkdir -p "$WEB_ROOT"
sudo cp -r "$FRONTEND_DIR/dist/"* "$WEB_ROOT/"

echo "==> Adding firmware nginx location if missing"
FIRMWARE_CONF="/etc/nginx/snippets/firmware.conf"
if [ ! -f "$FIRMWARE_CONF" ]; then
  echo 'location /firmware/ { proxy_pass http://127.0.0.1:8000/firmware/; proxy_set_header Host $host; }' | sudo tee "$FIRMWARE_CONF" > /dev/null
  echo "Created $FIRMWARE_CONF"
fi
# Check if the include is in the main nginx config
if ! grep -q "firmware.conf" /etc/nginx/conf.d/thinc.conf 2>/dev/null; then
  echo "WARNING: Add 'include /etc/nginx/snippets/firmware.conf;' inside the server block of /etc/nginx/conf.d/thinc.conf, then run sudo nginx -t && sudo systemctl reload nginx"
fi

echo "==> Reloading Nginx"
sudo nginx -t
sudo systemctl reload nginx

echo "==> Health check"
curl -fsS https://thinc.site/api/v1/health
echo
echo "Deploy completed."
