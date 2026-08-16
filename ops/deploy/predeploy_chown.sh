#!/usr/bin/env bash
# Preflight for scripts/deploy.sh - fixes the root-owned-files trap before it
# can fail a pull.
#
# WHY THIS EXISTS, AND WHY IT IS NOT A CHANGE TO deploy.sh ITSELF (GreenBear,
# Carpet #3524; Bolt, Carpet #3525): the culineire-deploy SSH key is installed
# in BOTH deploy's and root's authorized_keys, so one wrong `root@` in an ssh
# command silently writes files as root:root under /srv/culineire/current.
# The next `git pull --rebase` then fails with "insufficient permission for
# adding an object to repository database .git/objects" - it has hit both of
# us, independently, on different days. Removing the shared key is the real
# fix and is the Owner's call (AGENTS.md section 20), not ours.
#
# /srv/culineire/scripts/deploy.sh is root:deploy, mode 750, OUTSIDE this
# repository - deploy can execute it but cannot write to it, and it is not
# git-pulled. Editing it means a root session, which is the exact trap this
# script exists to stop needing. This file lives INSIDE the repo instead, so
# every `git pull` makes it deploy-owned automatically, and it only ever
# calls chown on ITS OWN checkout, never on deploy.sh or anything outside it.
set -euo pipefail

APP_ROOT="/srv/culineire"
CURRENT="${APP_ROOT}/current"

foreign_count="$(find "$CURRENT" -not -user deploy 2>/dev/null | wc -l)"

if [ "$foreign_count" -gt 0 ]; then
  echo "predeploy_chown: ${foreign_count} non-deploy-owned file(s) under ${CURRENT} - fixing"
  find "$CURRENT" -not -user deploy -print
  sudo chown -R deploy:deploy "$CURRENT"
  echo "predeploy_chown: done"
else
  echo "predeploy_chown: clean, nothing to do"
fi

exec "${APP_ROOT}/scripts/deploy.sh"
