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

export DJANGO_ENV_FILE="$ENV_FILE"

if [ ! -f "$ENV_FILE" ]; then
    fail "Production .env not found at $ENV_FILE"
fi

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
info() { echo -e "${CYAN}[--]${NC}  $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

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

# --- 4. Django safety checks -------------------------------------------------
info "Running Django checks..."
$PY manage.py check --deploy 2>&1 | grep -v "^System check" || true

info "Checking for unapplied migrations..."
$PY manage.py makemigrations --check --dry-run \
    && ok "No new migrations needed" \
    || fail "Unapplied migrations detected — run manually: $PY manage.py makemigrations"

# --- 5. Apply migrations ------------------------------------------------------
info "Applying migrations..."
$PY manage.py migrate --noinput
ok "Migrations applied"

# --- 6. Collect static files --------------------------------------------------
info "Collecting static files..."
$PY manage.py collectstatic --noinput --clear -v 0
ok "Static files collected"

# --- 7. Run tests -------------------------------------------------------------
info "Running test suite..."
$PY manage.py test --verbosity=0 2>&1 | tail -5
ok "Tests passed"

# --- 8. Restart NGINX Unit ----------------------------------------------------
info "Restarting NGINX Unit..."
sudo systemctl restart unit
sleep 2
if sudo systemctl is-active --quiet unit; then
    ok "NGINX Unit is running"
else
    fail "NGINX Unit failed to start — check: sudo journalctl -u unit -n 50"
fi

# --- 9. Smoke test ------------------------------------------------------------
info "Smoke test: https://culineire.ie/ ..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://culineire.ie/)
if [ "$HTTP_CODE" = "200" ]; then
    ok "Site responded with HTTP $HTTP_CODE"
else
    fail "Unexpected HTTP response: $HTTP_CODE"
fi

echo ""
ok "=== Deploy complete ==="
echo ""
