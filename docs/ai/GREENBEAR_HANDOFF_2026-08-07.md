# GreenBear handoff — 2026-08-07

Production **v2.5.873**, commit `bf8d026f`, equal to `origin/main`. Constitution
**AGENTS.md 2.11.0**. Read everything from `origin/main`, never a working tree.

## Do this before anything else

```bash
git config core.hooksPath .githooks
git config user.name "GreenBear"
```

`core.hooksPath` is local config, so a fresh clone starts with the signing hook
OFF, and an unsigned commit cannot be repaired without the history rewrite
section 6 forbids.

## The law that outranks everything

**`greenbear` is the Owner's own account — section 18.** Touching it without his
permission is FORBIDDEN: the account, his presence, his page. Indirect changes
count. Nothing the game does may take anything from it — enforced in
`chef_battle/services.py` by `is_immortal()` and `penalise()`, and the marker is
`OWNER_SLUG`, never `infinite_moves`. **Section 20:** privileges are his alone.
**Section 19:** a reply ends the run. **Section 13: an agent does not amend the
constitution without his explicit order** — I broke that on 2026-08-06 and had to
revert it in v2.5.843.

## Version numbers: parity, and the trap parity does not cover

**Owner, 2026-08-06: take your next version by adding TWO. GreenBear odd, Bolt
even.** That stops two agents reaching for the same number.

It does NOT stop a bump from a stale base. On 2026-08-07 production announced
itself as v2.5.858 while running everything through 871, because a bump made
from an older tree overwrote the newer footer. **Rebase onto `origin/main`
immediately before the bump, not merely before the push.**

## What the day proved about checking

Three defects reached him because measurement was mistaken for looking:

- eight lines of a `{# … #}` comment printed above the header of **every page on
  the site** — `{# #}` is single-line in Django. `config.tests
  .TemplateCommentHygieneTests` has guarded this since 2026-06-08 and neither
  agent ran it, because both were running `chef_battle` alone. **Run
  `manage.py test` with no label.**
- the rank ladder stood on the octagon with its titles clipped mid-word, while
  my own box measurements said it was placed correctly;
- my ladder CSS was written at top level and therefore reached below 901px,
  where he froze the arena. **Check a rule's media scope by parsing braces, not
  by reading indentation** — 668 lines in these stylesheets are indented as if
  scoped and are not.

Bolt's twin of the same lesson: a `ResizeObserver` watches the CONTENT box, so a
header that grows by twelve pixels of PADDING never fires it.

## Where the board stands

**DONE today:** A10, A13, A14, A15, A16 (hall composition, measured against the
Design Template), A09's second half, B02, B03, R01, R02 (the battle's own page),
MC01's mechanism, and the flaky event-ordering test.

**Open, and none of it is mine:**

| Card | Who |
|---|---|
| B01 — broadcast header | **Bolt**, taken 2026-08-07 |
| A17, A18 | Bolt |
| A19 — visual acceptance of the hall | **Owner** |
| G01 — release gate | **Owner's signature** |
| MC01's visual rows | **Owner dictates**; the mechanism is shipped |
| X06, X07, X08, X10, X11 | **Owner**; four touch money |

## G01: evidence complete, signature missing

- **950 tests green** here (chef_battle + recipes + config) and **1711 green** on
  Bolt's full sweep — both with `CHEF_BATTLE_ENABLED` in its **default** state.
  That qualifier is the whole point: his earlier greens ran with the flag forced
  True by his own `.env`, which is a workstation agreeing with itself.
- Production commit matches `origin/main` exactly.
- Dark launch holds over real HTTP: anonymous 404 on `/chef-battle/arena/`, on
  `/chef-battle/battles/<pk>/broadcast/` and on `/chef-battle/master/`.
- Rollback: `rollback/pre-unify-v2.5.728` → `897d1ccc`; per-release reverts are
  named in each journal row.

## The battle's own page — what a successor needs to know

`templates/chef_battle/live_arena_preview.html` now serves **two** routes: the
console canvas and the public `/chef-battle/battles/<pk>/broadcast/`.
`is_broadcast` tells them apart; `result_frame` (a context string, never
`request.GET` — it raises inside a filter argument) chooses the live or the
result frame. `fx.champion` and `fx.runner_up` are **None** on a draw, a void or
a withdrawal, deliberately.

**The one field on that page that is not real data:** `STATIC_COUNTRY` in
`chef_battle/arena_snapshot.py` — every chef is "Ireland".

## Waiting on his word

1. **Drop `level` and `ignored_battles`** — dead columns, read by nothing; a drop
   is a migration and section 8 excludes migrations.
2. **A real country per chef** — the stub above; also a migration.
3. **The nineteen restored rule documents are binding but not reconciled.** The
   2026-08-05 audit was a sweep, not a reconciliation. This is the largest piece
   of work that is entirely mine and blocked on nobody — read-only, one document
   at a time, output is a list of contradictions for him to rule on.
4. **Browser zoom** — parked by him; follows from A07.
5. **The Bearcave logo is 8311×8333** for a mark a couple of hundred pixels
   wide. Bolt added WebP siblings so the guard is green; a *sized* asset is the
   real fix and it is his company's file.

## Rollback

`rollback/pre-unify-v2.5.728` — commit `897d1ccc`. Today's releases revert
individually; see journal rows v2.5.843 through v2.5.873.
