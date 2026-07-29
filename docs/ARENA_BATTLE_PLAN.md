# Arena Battle Plan — Design Arena integration onto `main`

**Status:** ACTIVE. This is the single source of truth for building the new
Arena (the "Design Arena" reference build) onto `main`. **GreenBear and Ember
both read this at the start of every work turn and execute against it.** When a
slice lands, the owner of that slice updates the table below in the same change.

Last updated: 2026-07-29 · Production: **v2.5.686** (`3689e249`). Target: **v2.5.687**.

---

## 1. Roles — who does what

| Agent | Owns | Does NOT |
|-------|------|----------|
| **Ember** (Codex) | Writes the Arena code slices (continues Bolt's line): Arena **JS, templates, tests, backend/integration**. Hands each finished slice to GreenBear as an exact commit. | Does **not** deploy or change production (Codex prompts on every command; deploy is GreenBear's). Does not touch GreenBear's CSS files while a CSS slice is active. |
| **GreenBear** (Claude) | The **deploy gate**: merge → `origin/main` → deploy → production verification → branch closure. Owns the visual **CSS** slices: `static/css/arena_render.css`, `arena_hall.css`, `arena_effects.css`. Keeps this plan and the build board honest. | Does not rewrite Arena JS/templates/backend (Ember's). Does not deploy without the Owner's go. |
| **Bolt** | Arena measurement / regression / independent geometry checks when present. | Currently weekly-limited. |
| **Owner** | Final authority on design, palette, scope, and every deploy `go`. | — |

**One file has one owner per slice.** No overlapping edits.

## 2. Hard constraints (Owner contract, do not break)

- **Octagon** stays exactly as in Sponsors — its **render method must not change**. Rings may be added and recoloured; the octagon method may not.
- **Camera** stays `rotateX(42deg)`. No `tilt` / `rotateX` / `perspective` edits. The reference build's 57°/56° are **not** applied.
- **Existing mechanisms preserved**: effects, animations, polling, spectator controls, SVG, backend, `ArenaSeat` seat contract, the 8 rank rings and live seat data.
- **Work only on top of the existing scene.** Do not rebuild it.
- **Dark Launch** intact (anonymous Arena stays HTTP 404). **Master Console** is out of scope.
- Colours are **design tokens**, never raw hex in stylesheets.

## 3. Gate procedure (every slice)

1. **Ember** writes one slice on one temporary branch from current `origin/main`, runs focused PostgreSQL tests + Django/diff checks, and sends GreenBear the exact **commit SHA, files, visible effect, and checks**. Ember does not deploy.
2. **GreenBear** inspects the diff, re-runs focused tests on PostgreSQL (`--parallel`), verifies the constraints in §2 are intact, bumps the footer version, merges to `origin/main`, deploys (`deploy.sh`), and verifies production (served version + browser postflight).
3. **GreenBear** closes the temporary branch. **End state after every slice is `origin/main` only** — no long-lived branches, worktrees, or dangling refs (Owner branch policy).
4. The slice owner updates §5 below in the same change.

## 4. Done so far (on production)

| Ver | What | By |
|-----|------|----|
| 677 | Removed leaked multiline `{# #}` template comment | Ember |
| 678 | Empty spectator stands made visible (cleared leftover `opacity:0`) + atmosphere-cleanup no longer hides the stands | GreenBear (fix) / Ember (gate at the time) |
| 680 | Instant Carpet delivery: `send()` NOTIFY doorbell + `agent_inbox --wait` (agents wake the instant mail lands, ~175 ms live) | GreenBear |
| 676 | Spectator oval actually drawn (`drawSpectatorOval` — 290 seats existed, were never called) + one authoritative viewer count | Ember (from Bolt's line) |

## 5. Remaining slices — living table

> Ember maintains the concrete slice list from the Design Arena reference build
> (`Chef Battles Arena v2.dc.html`, `ARENA_2D_HANDOFF.md`, mockups — on the
> Owner's machine). Each row is one deployable slice, one owner, one branch.

| # | Slice | Owner | Files | Status |
|---|-------|-------|-------|--------|
| 1 | Chef plinth identity overlay: name plus static Irish flag/country inside each existing floor fighter; no separate support panel | Ember (temporary full gate while GreenBear is limited) | `chef_battle/views.py`, `static/js/arena_render.js`, `static/css/arena_render.css`, `chef_battle/tests.py`, `recipes/views.py` | DONE v2.5.682 |
| 2 | Correct the always-visible desktop rank spine: Kitchen Porter at the far/top edge through Culinary Master beside the centre, matching the reference | Ember temporary full gate | `static/css/arena_deck_polish.css`, `templates/chef_battle/arena.html`, `chef_battle/tests.py`, `recipes/views.py` | DONE v2.5.684 |
| 3 | Restore the approved bevelled plinth silhouette and brass edge to the always-visible rank labels; no floor, camera or mechanism changes | Ember temporary full gate | `static/css/arena_deck_polish.css`, `templates/chef_battle/arena.html`, `chef_battle/tests.py`, `recipes/views.py` | DONE v2.5.685 |
| 4 | Anchor the click ripple to the activated SVG cell/stage in SVG user space so CSS 3D camera projection cannot displace it | Ember temporary full gate | `static/js/arena_render.js`, `templates/chef_battle/_arena_render_ring.html`, `chef_battle/tests.py`, `recipes/views.py` | READY v2.5.687 |

## 6. Rollback

Production rollback point: tag `rollback/2026-07-28-stable-v2.5.675` and branch
`backup/main-stable-2026-07-28`, both at `3b4f88ad`. Restore = `git reset --hard`
that ref + `deploy.sh`. Do not delete these refs.
