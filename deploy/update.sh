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
SHARED_DIR=/srv/culineire/shared
APP_USER=deploy
APP_GROUP=deploy
NGINX_MODSEC_DIR=/etc/nginx/modsec
MODSEC_ENGINE_CONF=/etc/modsecurity/modsecurity.conf

DEPLOY_BRANCH=main

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
info "Deploying branch: $DEPLOY_BRANCH"
echo ""

# --- 1. Pull latest code -----------------------------------------------------
info "Pulling latest code from GitHub..."
cd "$APP"

if [ ! -w "$APP/.git" ] || [ ! -w "$APP/.git/objects" ]; then
    fail "Git checkout is not writable by $(whoami). Fix ownership first: sudo chown -R $APP_USER:$APP_GROUP $APP"
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    fail "Working tree has uncommitted changes — aborting deploy. Run 'git status' to inspect."
fi

git fetch origin
BEFORE=$(git rev-parse HEAD)
git checkout "$DEPLOY_BRANCH"
git reset --hard "origin/$DEPLOY_BRANCH"
AFTER=$(git rev-parse HEAD)
if [ "$BEFORE" = "$AFTER" ]; then
    ok "Already up to date on $DEPLOY_BRANCH ($AFTER)"
else
    ok "Updated $BEFORE → $AFTER on $DEPLOY_BRANCH"
    git log --oneline "$BEFORE".."$AFTER"
fi

# --- 2. Classify the diff: restart Unit only when the app process must reload --
# CSS/JS/images are served from disk by nginx after collectstatic — no Unit restart.
# Django templates use APP_DIRS filesystem loaders (not cached.Loader) — disk read.
# Python modules and Unit config stay in memory until the workers are restarted.
NEED_UNIT_RESTART=0
NEED_COLLECTSTATIC=0
NEED_PIP=0
NEED_UNIT_RECONFIGURE=0

if [ "$BEFORE" = "$AFTER" ]; then
    info "No new commits — skipping Unit restart (override with FORCE_UNIT_RESTART=1)"
else
    CHANGED_FILES=$(git diff --name-only "$BEFORE" "$AFTER" || true)
    while IFS= read -r path; do
        [ -z "$path" ] && continue
        case "$path" in
            requirements.txt|requirements*.txt)
                NEED_PIP=1
                NEED_UNIT_RESTART=1
                ;;
            deploy/unit*.json)
                NEED_UNIT_RESTART=1
                NEED_UNIT_RECONFIGURE=1
                ;;
            deploy/modsecurity/*|deploy/nginx*.conf)
                # nginx/WAF only — handled in section 8; no Unit restart
                ;;
            static/*|*/static/*)
                NEED_COLLECTSTATIC=1
                ;;
            templates/*|*.html)
                # Templates are read from disk each request (APP_DIRS, no cached loader).
                NEED_COLLECTSTATIC=1
                ;;
            *.py|manage.py)
                NEED_UNIT_RESTART=1
                ;;
            *.md|*.txt|*.yml|*.yaml|*.json|docs/*|ops/*|.cursor/*|AGENTS.md)
                # Docs / ops noise — no process reload
                ;;
            *)
                # Unknown path: fail-safe restart so we never silently miss a runtime change
                NEED_UNIT_RESTART=1
                ;;
        esac
    done <<< "$CHANGED_FILES"

    info "Change class: Unit restart=$NEED_UNIT_RESTART  collectstatic=$NEED_COLLECTSTATIC  pip=$NEED_PIP  unit reconfigure=$NEED_UNIT_RECONFIGURE"
fi

if [ "${FORCE_UNIT_RESTART:-0}" = "1" ]; then
    NEED_UNIT_RESTART=1
    NEED_UNIT_RECONFIGURE=1
    info "FORCE_UNIT_RESTART=1 — Unit restart forced"
fi

# --- 3. Install/update Python dependencies -----------------------------------
if [ "$NEED_PIP" = "1" ] || [ "${FORCE_PIP:-0}" = "1" ]; then
    info "Installing requirements..."
    $PIP install --quiet --upgrade pip
    $PIP install --quiet -r "$APP/requirements.txt"
    ok "Requirements installed"
else
    info "requirements.txt unchanged — skipping pip install"
fi

# --- 3b. Ensure writable shared directories ----------------------------------
info "Ensuring shared directory permissions..."
sudo mkdir -p "$SHARED_DIR"/{staticfiles,media,logs,cache}
sudo chown -R "$APP_USER:$APP_GROUP" \
    "$SHARED_DIR/staticfiles" \
    "$SHARED_DIR/media" \
    "$SHARED_DIR/logs" \
    "$SHARED_DIR/cache"
sudo chmod -R u+rwX,g+rwX \
    "$SHARED_DIR/staticfiles" \
    "$SHARED_DIR/media" \
    "$SHARED_DIR/logs" \
    "$SHARED_DIR/cache"
ok "Shared directories are writable by $APP_USER"

# --- 4. Collect static files -------------------------------------------------
if [ "$NEED_COLLECTSTATIC" = "1" ] || [ "$NEED_UNIT_RESTART" = "1" ] || [ "${FORCE_COLLECTSTATIC:-0}" = "1" ]; then
    # Also collect on Unit restarts: py changes sometimes ship with companion static.
    info "Collecting static files..."
    $PY manage.py collectstatic --noinput --clear -v 0
    ok "Static files collected"
else
    info "No static/template changes — skipping collectstatic"
fi

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

# --- 7. Restart NGINX Unit (only when the in-memory app must reload) ----------
if [ "$NEED_UNIT_RESTART" = "1" ]; then
    info "Restarting NGINX Unit (Python / Unit config / fail-safe change)..."
    sudo systemctl restart unit
    sleep 2
    if sudo systemctl is-active --quiet unit; then
        ok "NGINX Unit is running"
    else
        fail "NGINX Unit failed to start — check: sudo journalctl -u unit -n 50"
    fi
else
    info "Skipping Unit restart — static/template-only (or no) diff; no 502 window"
    if sudo systemctl is-active --quiet unit; then
        ok "NGINX Unit still running"
    else
        fail "NGINX Unit is not active — forcing recovery restart"
    fi
fi

if [ "$NEED_UNIT_RESTART" = "1" ] || [ "$NEED_UNIT_RECONFIGURE" = "1" ]; then
    info "Loading CulinEire NGINX Unit configuration..."
    UNIT_RECONFIGURE_RESPONSE=$(mktemp)
    trap 'rm -f "$UNIT_RECONFIGURE_RESPONSE"' EXIT
    sudo curl -sS -X PUT --data-binary @"$UNIT_CONFIG" \
        --unix-socket /var/run/control.unit.sock \
        http://localhost/config/ >"$UNIT_RECONFIGURE_RESPONSE"
    if grep -q '"success"' "$UNIT_RECONFIGURE_RESPONSE"; then
        ok "NGINX Unit configuration loaded"
    else
        cat "$UNIT_RECONFIGURE_RESPONSE"
        fail "NGINX Unit configuration failed - check: sudo tail -n 100 /var/log/unit.log"
    fi
else
    info "Skipping Unit reconfigure — config unchanged"
fi

# --- 8. Sync ModSecurity rules when WAF is installed -------------------------
if [ -d "$NGINX_MODSEC_DIR" ]; then
    info "Updating ModSecurity rules..."
    if [ ! -f "$MODSEC_ENGINE_CONF" ]; then
        sudo mkdir -p "$(dirname "$MODSEC_ENGINE_CONF")"
        if [ -f /etc/modsecurity/modsecurity.conf-recommended ]; then
            sudo cp /etc/modsecurity/modsecurity.conf-recommended "$MODSEC_ENGINE_CONF"
        elif [ -f /etc/modsecurity.d/modsecurity.conf-recommended ]; then
            sudo cp /etc/modsecurity.d/modsecurity.conf-recommended "$MODSEC_ENGINE_CONF"
        elif [ -f /usr/share/doc/libmodsecurity3/examples/modsecurity.conf-recommended ]; then
            sudo cp /usr/share/doc/libmodsecurity3/examples/modsecurity.conf-recommended "$MODSEC_ENGINE_CONF"
        else
            printf '%s\n' \
                'SecRuleEngine On' \
                'SecRequestBodyAccess On' \
                'SecResponseBodyAccess Off' \
                'SecAuditEngine RelevantOnly' \
                'SecAuditLog /var/log/modsec_audit.log' \
                'SecAuditLogParts ABIJDEFHZ' \
                | sudo tee "$MODSEC_ENGINE_CONF" >/dev/null
        fi
    fi
    sudo sed -i -E 's/^[[:space:]]*SecRuleEngine[[:space:]]+.*/SecRuleEngine On/' "$MODSEC_ENGINE_CONF"
    if ! sudo grep -qE '^[[:space:]]*SecRuleEngine[[:space:]]+' "$MODSEC_ENGINE_CONF"; then
        printf '%s\n' 'SecRuleEngine On' | sudo tee -a "$MODSEC_ENGINE_CONF" >/dev/null
    fi
    sudo cp "$APP/deploy/modsecurity/culineire-main.conf" "$NGINX_MODSEC_DIR/culineire-main.conf"
    sudo cp "$APP/deploy/modsecurity/culineire-probes.conf" "$NGINX_MODSEC_DIR/culineire-probes.conf"
    sudo nginx -t
    sudo systemctl reload nginx
    ok "ModSecurity rules synced and NGINX reloaded"
else
    info "ModSecurity directory not present; skipping WAF rule sync"
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
