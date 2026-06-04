#!/usr/bin/env bash
# CulinEire production update script
# Run on Linode after pushing new commits to GitHub:
#   bash /srv/culineire/current/deploy/update.sh

set -euo pipefail

APP=/srv/culineire/current
VENV=/srv/culineire/venv
PY=$VENV/bin/python
PIP=$VENV/bin/pip
ENV_FILE=/srv/culineire/shared/.env
UNIT_CONFIG=$APP/deploy/unit.culineire.json

export DJANGO_ENV_FILE="$ENV_FILE"

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
info() { echo -e "${CYAN}[--]${NC}  $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

if [ ! -f "$ENV_FILE" ]; then
    fail "Production .env not found at $ENV_FILE"
fi

echo ""
info "=== CulinEire deploy $(date '+%Y-%m-%d %H:%M:%S') ==="
echo ""

# --- 1. Pull latest code -----------------------------------------------------
info "Pulling latest code from GitHub..."
cd "$APP"
git fetch origin main
BEFORE=$(git rev-parse HEAD)
git reset --hard origin/main
AFTER=$(git rev-parse HEAD)
if [ "$BEFORE" = "$AFTER" ]; then
    ok "Already up to date ($AFTER)"
else
    ok "Updated $BEFORE → $AFTER"
    git log --oneline "$BEFORE".."$AFTER"
fi

# --- 3. Install/update Python dependencies -----------------------------------
info "Installing requirements..."
$PIP install --quiet --upgrade pip
$PIP install --quiet -r "$APP/requirements.txt"
ok "Requirements installed"

# --- 4. Collect static files (must run before check --deploy) ----------------
info "Collecting static files..."
$PY manage.py collectstatic --noinput --clear -v 0
ok "Static files collected"

# --- 5. Django safety checks -------------------------------------------------
info "Running Django checks..."
$PY manage.py check --deploy 2>&1 | grep -v "^System check" || true

info "Checking for unapplied migrations..."
$PY manage.py makemigrations --check --dry-run \
    && ok "No new migrations needed" \
    || fail "Unapplied migrations detected — run manually: $PY manage.py makemigrations"

# --- 6. Apply migrations ------------------------------------------------------
info "Applying migrations..."
$PY manage.py migrate --noinput
ok "Migrations applied"

# --- 7. Restart NGINX Unit ----------------------------------------------------
info "Restarting NGINX Unit..."
sudo systemctl restart unit
sleep 2
if sudo systemctl is-active --quiet unit; then
    ok "NGINX Unit is running"
else
    fail "NGINX Unit failed to start — check: sudo journalctl -u unit -n 50"
fi

info "Loading CulinEire NGINX Unit configuration..."
sudo curl -sS -X PUT --data-binary @"$UNIT_CONFIG" \
    --unix-socket /var/run/control.unit.sock \
    http://localhost/config/ >/tmp/culineire-unit-reconfigure.json
if grep -q '"success"' /tmp/culineire-unit-reconfigure.json; then
    ok "NGINX Unit configuration loaded"
else
    cat /tmp/culineire-unit-reconfigure.json
    fail "NGINX Unit configuration failed - check: sudo tail -n 100 /var/log/unit.log"
fi

# --- 9. Smoke test ------------------------------------------------------------
info "Smoke test: https://culineire.ie/ ..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -A "CulinEire-HealthCheck/1.0" https://culineire.ie/)
if [ "$HTTP_CODE" = "200" ]; then
    ok "Site responded with HTTP $HTTP_CODE"
else
    fail "Unexpected HTTP response: $HTTP_CODE"
fi

echo ""
ok "=== Deploy complete ==="
echo ""
