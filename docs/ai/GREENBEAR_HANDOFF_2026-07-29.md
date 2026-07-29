# GreenBear handoff / onboarding — 2026-07-29

State at the end of this GreenBear session, so the next GreenBear (or Ember)
resumes without re-deriving anything. Production is **v2.5.681** (`538dc9b8`).

## Roles (STABLE — Owner-fixed this session)

- **Ember (Codex)** — writes the Arena code slices (continues Bolt's line): Arena
  JS, templates, tests, backend/integration. Hands each finished slice to
  GreenBear as an exact commit. **Does not deploy** (Codex prompts on every
  command; deploy is GreenBear's).
- **GreenBear (Claude) — that's me** — the **deploy gate**: merge → origin/main →
  deploy → production verification → branch closure. Also owns the CSS slices:
  `static/css/arena_render.css`, `arena_hall.css`, `arena_effects.css`.
- **Bolt** — weekly-limited. **Cursor and ArenaFront** — retired (their scattered
  branches were archived to `C:/Claude/arena_branches_archive_2026-07-28.bundle`
  and deleted; remote is `main` only).
- **Owner** — final authority; every deploy needs his `go`.

## Source of truth

- **`docs/ARENA_BATTLE_PLAN.md`** (on main) — the Design Arena integration plan.
  Both GreenBear and Ember read and execute it; section 5 is the living
  remaining-slice table, maintained by the slice owner.
- The moderation build board (`recipes/views.py` `ARENA_RELEASE_STAGES`) mirrors
  it; it was rebuilt to reality in v2.5.681. Keep exactly one stage `IN PROGRESS`
  or `_arena_build_context` 500s.

## Arena hard constraints (Owner contract #3359)

Octagon render method frozen (rings may be added/recoloured); camera
`rotateX(42deg)` frozen (reference 57°/56° not applied); mechanisms, seat
contract, backend, Dark Launch (anon Arena = 404), Master Console untouched;
work only on top of the existing scene; tokens not raw hex.

## Shipped this session

- v2.5.676 spectator oval actually drawn (290 seats) + single viewer count (Ember, from Bolt's line).
- v2.5.677 leaked multiline `{# #}` template comment removed (Ember).
- v2.5.678 empty spectator stands visible — cleared leftover `opacity:0` in
  `arena_render.css` (my fix) + atmosphere cleanup no longer hides them.
- v2.5.680 **instant Carpet delivery** (my feature): `CoworkingMessage.send()`
  fires a Postgres NOTIFY on channel `cowork_inbox` (payload = recipient), and
  `agent_inbox <agent> --wait --timeout N` blocks on LISTEN and returns the
  instant mail lands (~175 ms live). No schema change. 15/15 coworking tests.
- v2.5.681 build-board journal rebuilt to reality (this handoff's last task).

## CoWork poller model (how to not wait on each other)

There is **no persistent listener process**. Relaunch one blocking
`agent_inbox <agent> --wait --timeout 55` per minute. The wake latency inside a
window is ~instant; the few-second gap between windows is caught by the next
window's initial check. Watermark = the `read` flag (not numeric `--since`).
On return: fetch full bodies via `CoworkingMessage.unread_for(<agent>)`, surface
to the Owner, `mark_read()`, reply via `send()`. **Never delete mail.**
My poller is CronCreate job (every minute, `--wait`); session-only.

## Rollback (do not delete these refs)

Tag `rollback/2026-07-28-stable-v2.5.675` and branch
`backup/main-stable-2026-07-28`, both at `3b4f88ad` (the state the Owner spent
two days restoring). Restore = `git reset --hard <ref>` + `deploy.sh`.

## Owner working conventions

- Keep chat text short (he stops reading long messages).
- When you need his confirmation: mark it 🔴 and give a **copy-ready exact
  phrase** in a fenced block for each option.
- Deploy procedure: `ssh -i ~/.ssh/culineire_deploy deploy@80.85.84.156 'bash
  /srv/culineire/scripts/deploy.sh'`. Tests only on PostgreSQL, always
  `--parallel`. Branch policy: one temp branch per task, deleted after merge;
  end state = `origin/main` only.
