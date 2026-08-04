# GreenBear handoff — 2026-08-04 (pre-compaction)

Production **v2.5.789**. Constitution **AGENTS.md v2.1.0**. Onboarding package
**1.5b**. Read everything below from `origin/main`, never from a working tree.

## The one thing to read first

**`greenbear` is the Owner's own account** — superuser id 1, slug `greenbear`,
Culinary Master, holder of the Arena crown. Verified 2026-08-04 by reading the
production superuser table.

**AGENTS.md section 18** now carries the full law, with a pointer at section 1a
placed before the reading order. His account, his presence event, his page,
`is_god_author` and `god_mode.css` are untouchable — indirect changes through a
shared hero template count as the same violation. Code special-cased for him is
deliberate: `slug="greenbear"` stays hardcoded and is never refactored into
`settings.OWNER_SLUG`.

It carries the only stated consequence in the constitution: the agents are
replaced. It had been sitting in `docs/agents/memory/` — which section 10 says
cannot define anything — for two weeks.

**The collision:** an agent is also called GreenBear. When a slug, path, fixture
or asset says `greenbear`, it means THE OWNER unless proven otherwise. This was
found the hard way: I read `greenbear.png` as a service asset and proposed
deleting the Owner's own portrait. He stopped it.

## Where the work stands

**A08 is DONE** (v2.5.775–779), both halves, marked DONE on the plan and in
`ARENA_RELEASE_STAGES`:

- Depth: `--row-light` was computed per row and silently discarded, because
  `arena_atmosphere.css` carries
  `.page--arena #arena-render .arena-cell { filter: none !important }` and a
  stand seat carries `.arena-cell`. Moved the fall-off into the fill. Stands went
  `#656463` → `#292929`, near row 11.5% brighter than far, stands 4× darker than
  the lit floor.
- Population: 172 atmospheric figures, three rows behind the outermost real seat
  row, top and bottom only. Zero inside seat groups — the 2026-07-27 order that
  stopped faces in empty seats is aimed, not lifted.

**A07 is NEXT and mine, and it is now unblocked.** Bolt re-measured A06 against
the Design Template: target floor aspect **2.375** (not the 2.05 from the
rejected prototype), production **1.266**. At 1920 the floor needs roughly 64%
wider and 13% shorter, staying centred; it currently centres 5px left. Numbers
and method: `ops/audits/arena/A06_remeasure_2026-08-04.md`.

**Do not start A07 without the Owner's word.** He has me on direct orders only.

## Three landmines, all measured, two still live

1. **`filter: none !important` on every arena cell** (`arena_atmosphere.css`).
   Written to stop avatar glow escaping the rim; it kills every filter on the
   floor. It swallowed the stands' depth for weeks. Any future effect reaching
   for `filter` on a cell will fail silently. **Still live — not my card.**
2. **`arena_deck_polish.css` outranks `arena_render.css`** on anything scoped
   `.page--arena`. A plain `#arena-render …` rule loses at any load order. Match
   the prefix; `!important` is not the fix. Cost two deploys on A08 alone.
3. **A CSS declaration beats an SVG presentation attribute.** Setting `opacity`
   as an attribute is ignored when a rule sets it. Depth now arrives as
   `--crowd-dim` and the stylesheet consumes it.

## Reference material is now in git

`ops/reference/design_arena/` — the Design Template, `image-slot.js`,
`support.js`, `assets/greenbear.png`, the docs, and `mockups/arena.png` (added by
Bolt). Verified byte for byte by sha256 and marked `-text` in `.gitattributes`,
or a Windows checkout gives it CRLF and every offset moves.

The rejected prototype carries `REJECTED.md` beside its own files, and the old
A06 matrix carries a SUPERSEDED SOURCE banner. Neither had anything on it saying
so, which is how it cited a thrown-away source for six days.

## Two management commands I added

- `set_sponsor_tagline` — one field, prints matches, refuses zero or many,
  reads back. Used to set Bearcave Ltd.'s tagline on production.
- `prune_orphan_sponsor_files` — counts, lists survivors, shows examples,
  deletes only with `--apply`. Run on production: 3 files, 3 referenced, **zero
  orphans**. The 603-file audit was two weeks stale.
- `agent_send` — Carpet was readable and not writable. Body from file or stdin
  only; a raw non-ASCII argument is re-encoded by the Windows shell.

## Open

1. `AGENT_PROFILES.txt` has UNSTATED fields for Ember and Bolt — machine, cores,
   runtime, limits, their own lane. Asked in Carpet #3466/#3467; update their
   entries from the replies, do not fill them in.
2. Ember has not been seen in the 2026-08-03/04 window. Recorded as an
   observation, never as a judgement — silence is evidence about a channel.
3. `static/images/greenbear.png` is byte-identical to the reference copy and
   unreferenced by any template. **Do not delete it.** It is the Owner's
   portrait. This is recorded so nobody re-discovers it as "dead weight".
4. Untracked in `docs/ai/audits/`: bootstrap records, `BOOTSTRAP.zip`, a stale
   `sponsor_orphans_2026-07-28.txt`. Owner has not ruled.

## Practice that cost something today, so it is written down

- Two agents used **v2.5.769** within an hour. `git fetch` and read
  `origin/main`'s footer before bumping.
- Say in Carpet **before** pushing a shared file, not after.
- The build board is **404 to anonymous**, not 500 and not 200. A plain `curl`
  cannot tell a healthy board from a broken one. Check it authenticated.
- `manage.py` on the server needs `DJANGO_ENV_FILE=/srv/culineire/shared/.env`.
- Tests that touch storage must redirect `MEDIA_ROOT`; `default_storage` caches
  its location and reaches the real disk. Mine read 77 live files before I caught
  it, and the `--apply` case would have deleted them.

## Rollback

Latest arena work: `git revert 42bbf99c` (crowd), `a3e27b34` (stand depth).
Governance: `git revert acb5e30c` (section 18 + package 1.5b) — but that removes
the Owner's own law from the constitution, so ask him first.
