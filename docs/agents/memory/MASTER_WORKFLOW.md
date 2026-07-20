---
name: master-workflow
description: "Complete workflow: who we are, what we build, how we work, exact commands"
metadata: 
  node_type: memory
  type: project
  verified: 2026-07-10
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

# MASTER WORKFLOW — CulinEire Development

## WHO WE ARE

**Owner:** GreenBear (Dmitry Golovin, dmitry.golovin.irl@gmail.com)
- Creator of CulinEire
- Special privileges: can access all systems, code intentionally supports him
- Direct communication in Russian language only
- Final decision-maker on all features

**I am:** Bolt — lead developer. GreenBear (the agent) is my subordinate,
Junior Front End Developer, MANUAL mode: he works only on my explicit order.
READ GOLDEN_RULES.md BEFORE ANY WORK — after every limit and every compact.
- Full access to codebase, server, deployment
- Work in English (code, commits, comments)
- Autonomous deployment (no permission required)

---

## WHAT WE BUILD

**CulinEire** - Irish culinary heritage platform
- Recipes database with moderation
- Articles about Irish food
- Pinch: social network for sharing notes
- Chef Battles: gamification layer (competitive cooking)
- Custom Django CMS (no external admin)

**Current Major Project:** Arena Master Console (AMC)
- 10-phase system for managing Chef Battles
- Owner-only console at `/chef-battle/master/`
- Phase 1-9 complete, Phase 10 compliance audit in progress
- Latest: v2.5.171 — audit trail, idempotency keys, CSRF tests deployed

---

## TECH STACK

- **Django 5.2** (Python framework)
- **Database:** PostgreSQL 16 (production AND local). SQLite is gone;
  older notes saying otherwise are stale and have burned us before.
- **Frontend:** HTML/CSS/JavaScript (no React, no build step)
- **Server:** Linode (80.85.84.156)
- **Deployment:** SSH + bash script (no CI/CD)

---

## SERVER STRUCTURE

```
/srv/culineire/
├── current/          → git checkout (where we work)
├── venv/             → Python virtualenv
├── shared/
│   ├── .env          → production secrets (DJANGO_SECRET_KEY, etc.)
│   ├── staticfiles/  → collected static files (CSS/JS after collectstatic)
│   ├── cache/        → runtime cache & maintenance flag
│   └── logs/         → application logs
└── scripts/
    └── deploy.sh     → complete deployment script
```

**Important:** Do NOT commit `.env` — it lives only on server.

---

## EXACT COMMANDS (VERIFIED 2026-07-10)

### 1. CONNECT TO SERVER

```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode deploy@80.85.84.156 'command'"
```

**Details:**
- SSH key: `~/.ssh/culineire_linode` (in WSL, user golovin)
- User: **deploy** — NEVER root. Files created by root cannot be read by the
  web worker: that took the site down on 2026-07-14 and again on 2026-07-20,
  and burned a paid API call whose output could not be written.
- Host: 80.85.84.156 (Linode)
- **Verified:** Works ✓

### 2. DEPLOY TO PRODUCTION

```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode deploy@80.85.84.156 'bash /srv/culineire/scripts/deploy.sh 2>&1'"
```

**What deploy.sh does:**
1. `git pull origin main` (with rebase if needed)
2. Clean untracked/modified files if in git already
3. `python manage.py migrate --no-input`
4. `python manage.py collectstatic --no-input`
5. `sudo systemctl restart unit` (NGINX Unit server)
6. Health check on https://www.culineire.ie/

**Rules:**
- ✓ Runs **automatically** after every `git push`
- ✓ No permission request needed
- ✓ Repeatable (idempotent) — safe to run multiple times
- ✓ Script is verified to exist at `/srv/culineire/scripts/deploy.sh`

### 3. GIT COMMIT (with multi-line message)

```bash
cd "E:\CulinEire Project\CulinEire\CulinEire" && git commit -m "$(cat <<'EOF'
v2.5.X — feature description

- Bullet point 1
- Bullet point 2

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

**Rules:**
- Message in **ENGLISH only**
- Always end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Use heredoc for multi-line messages (verified format above)

### 4. GIT PUSH

```bash
git push origin main
```

**Rule:** After push, deployment runs automatically (see #2).

### 5. BUMP VERSION BEFORE DEPLOY

Edit `templates/base.html`:
```html
<span class="footer-version">v2.5.171</span>  <!-- increment patch: 170→171 -->
```

Then commit and push as normal. Deploy follows automatically.

---

## CURRENT WORK STATE (2026-07-10, 09:14:23 UTC)

**Last Deploy:** v2.5.171
- Commit: 19ea48b (Claude: AMC compliance audit)
- Status: ✓ Deployed successfully
- Tests: 35/35 passing (ArenaMasterActionSecurityTests)

**What was added in v2.5.171:**
1. `OperatorActionIdempotencyKey` model + migration 0060
2. `record_rejected_operator_action()` function — audit every rejection
3. `operator_broadcast()` with idempotency guard (correlation_id dedup)
4. `master_action` view refactored with `_reject()` closure
5. 11 new security tests (TransactionTestCase)

**Remaining compliance audit items (3 of 4):**
1. ✓ Audit rejected actions + idempotency key (DONE in v2.5.171)
2. Granular security checklist (instead of single boolean)
3. Bulk-load instead of N+1 queries (P02–P05)
4. Missing combat metrics (P04: misses/defended/surviving)
5. Update stale documentation (P01/P02 reports, public roadmap)

---

## MISTAKES THAT KEEP COSTING US (read before touching production)

1. **Never render pages through Django shell or the test client on production.**
   It writes cache files under the wrong owner and returns the whole site 500.
   Happened 2026-07-14 and again 2026-07-20. Check visuals over real HTTP only.
2. **Never work on the server as root.** Deploy user is `deploy`. After any
   deploy: `find /srv/culineire/shared/{cache,media,staticfiles,logs} ! -user deploy`.
3. **Never copy throwaway scripts to the server.** Make it a management command
   and ship it through git — reviewable, repeatable, and it survives a reboot.
4. **Two agents must never edit the same layout.** One file, one owner. Beating
   the cascade from a neighbouring file is how the arena was wrecked on 2026-07-20.
5. **Never change the acceptance measurement mid-way.** What accepted it at the
   start accepts it at the end.
6. **Fetch before push, always.** 39 version numbers collided in three weeks
   because two agents numbered releases independently.

## CRITICAL RULES

**Communication:**
- User speaks Russian, I respond in Russian
- All code/commits/comments/work in English

**Development:**
- Work in `main` branch only (no worktree branches for features)
- Commit + Push + Deploy as atomic workflow
- No manual testing on production (server runs as owner sees it)

**Code Quality:**
- No hacks or workarounds (only proper fixes)
- Test before commit (`python manage.py test`)
- Read CLAUDE.md for locked hero layout, locked god_mode.css, etc.

**Deployment:**
- Always bump version in `templates/base.html` before deploy
- Deploy happens automatically after push
- Never `git reset --hard` on server without owner approval (chews other agents' work)

---

## FILES TO PROTECT

**NEVER TOUCH without explicit permission:**
- `/recipes/author/greenbear/` page (is_god_author=True, god_mode.css applied)
- `static/css/god_mode.css` (intentional code for owner)
- Hero layout specs (object-position: center 60%, min-height: clamp(...), etc.)

**DO NOT COMMIT:**
- `.env` file (lives only on server)
- Secrets, API keys
- Debug output

---

## IF SOMETHING FAILS

1. Check server health: `https://www.culineire.ie/` loads?
2. Check logs: `ssh ... 'tail -f /srv/culineire/shared/logs/...'`
3. Check git state on server: `ssh ... 'cd /srv/culineire/current && git status'`
4. If worktree dirty: deploy.sh fails — clean it via SSH or git checkout
5. If migration fails: check `manage.py showmigrations`

---

## HANDOFF FOR NEXT AGENT

If I go offline and GreenBear needs another developer:
1. Read this file first
2. Copy it to your own memory
3. Check current version at bottom of `/templates/base.html`
4. Check `/srv/culineire/current` git status on server
5. Follow exact commands above (they are verified)
