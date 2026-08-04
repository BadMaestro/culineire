# GreenBear handoff — 2026-08-04 (end of day)

Production **v2.5.808**. Constitution **AGENTS.md v2.6.0**. Onboarding package
**1.5d**. Read everything from `origin/main`, never from a working tree.

## Do these two before anything else

```bash
git config core.hooksPath .githooks
git config user.name "GreenBear"       # commits went out as "YourName" all day
```

`.githooks/pre-commit` refuses a commit that is not signed by a roster name, and
it is OFF in a fresh clone because `core.hooksPath` is local config.

## The law that outranks everything

**`greenbear` is the Owner's own account** — superuser id 1, slug `greenbear`,
holder of the Arena crown. AGENTS.md **§18**: his account, presence, page,
`is_god_author` and `god_mode.css` are untouchable, indirect changes included.
Do not refactor `"greenbear"` into `settings.OWNER_SLUG`. When a slug, path or
asset says `greenbear`, it means THE OWNER, not the agent that shares the name.

## What changed today

- **AGENTS.md 2.1.0 → 2.6.0.** **§19**: a reply ends the work run — no
  acknowledgements, no interim status; work continuously and answer once.
  **§20**: privileges are the Owner's alone — no agent writes `is_staff`,
  `is_superuser`, `has_bearseeker_privileges` or `has_arena_console_access` by
  any means, and building a tool that makes it easier is itself the violation.
  §5 gained English + JSON-object bodies between agents, and commit signing.
- **Access gate rewritten twice, final: `is_staff or is_superuser`.** Tiers are
  AUTHOR (`is_staff` False) / (Bear)seeker Admin / (Bear)seeker Super User,
  separated by the staff bit. Master Console stays owner-only via `OWNER_SLUG`.
  Root cause of the confusion: the panel's "Grant (Bear)seeker Privileges" set
  the moderator flag *without* the staff bit — fixed in `accounts/views.py`.
- **A07 shipped and was reverted within the hour** (v2.5.792 → v2.5.793).
- **Ember retired.** Roster is GreenBear + Bolt. Eight open cards it suggested
  are now unassigned, **A09 among them**.
- Mail 43 → 10. `requirements-lock.txt` deleted. `tblib` pinned.

## The one thing that matters for A07

The Design Template's floor is a **1120 × 1120 square** — the same as this SVG's
viewBox. Its 2.375 aspect comes from its camera (57deg, perspective 1600px,
centred origins), **not** from a wider octagon. At 42deg the 2.375 target is
unreachable by any multiplier. Do not re-propose 57deg as a discovery: he saw it
and reverted it.

## Landmines, measured, still live

1. **The Arena camera is declared in `arena_deck_polish.css` seven times, one
   with `!important`.** That file wins, not `arena_render.css`. An inline
   override of `arena_render.css` reads back unchanged and produces silent
   "no effect" measurements.
2. `filter: none !important` on every arena cell (`arena_atmosphere.css`) kills
   any filter on the floor.
3. A CSS declaration beats an SVG presentation attribute.
4. **Version collisions twice today.** `git fetch` and read `origin/main`'s
   footer immediately before the bump — sixteen minutes of tests is long enough
   for another agent to take your number.
5. PowerShell `Get-Content | Set-Content` double-encodes UTF-8. Never round-trip
   a file through it; verify encoding by reading bytes, not by reading the diff.

## Open — the Owner's call

- Eight untracked files under `docs/ai/audits/`; he has not ruled.
- Journal backlog: 116 shipped 2.5 releases with no row, the whole 600–699 band
  empty. **Assigned to Bolt** (Carpet #3480). Measure with
  `python ops/audits/journal_integrity.py`.
- **A07 is NEXT, A09 unassigned.** Nothing starts without his word.

## How he wants the work done (his words, 2026-08-04)

Orphaned file → bin it, roll back if it breaks. Batch small fixes into **one**
deploy, not one each. Short journal rows. Ceremony costs the weekly limit, and
the limit is the real constraint on how much product moves.

Still not simplified, because the failures behind them are real: the §8 gate
before every deploy, never two deploys under one version, and never touching
privileges or the access gate without his word.

## Rollback

`rollback/2026-07-28-stable-v2.5.675` — annotated tag, commit `3b4f88ad`.
Today's releases revert individually; see journal rows v2.5.791–808.
