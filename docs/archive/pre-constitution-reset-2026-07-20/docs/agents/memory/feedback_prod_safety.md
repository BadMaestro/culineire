---
name: Never break production
description: Prod safety is absolute — no deploy without full local verification
type: feedback
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
Never push code that could break the production server. Production downtime damages reputation and costs money.

**Why:** We already broke prod once during a permissions change session. Every deploy must be safe.

**How to apply — mandatory checklist before every push:**

1. `manage.py check` passes with no errors
2. `manage.py migrate --run-syncdb` dry-run or check passes locally
3. If models.py changed — ALWAYS create and commit the migration in the same commit, never push without it
4. If there is a new migration — run it locally first and verify it applies cleanly
5. If middleware or signals are changed — manually trace the request path for errors
6. If static files changed — verify CSS version is bumped
7. If settings or permissions logic changed — think through what the running Unit process needs
8. Bump the release version in base.html footer before the final push

**Never assume collectstatic or restart is safe without verifying Django starts cleanly first.**

If in doubt — do NOT push. Fix the doubt first.

**CSS/layout changes — mandatory local preview before deploy:**
Always verify visual changes in the local preview server before committing and deploying. Never iterate CSS on production. If the preview server times out on screenshots, use `preview_eval` to inspect DOM/styles, or ask the user to check locally. Do not push CSS experiments to prod — test first, deploy once.

