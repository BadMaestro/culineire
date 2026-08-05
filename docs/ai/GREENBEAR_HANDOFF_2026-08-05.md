# GreenBear handoff — 2026-08-05 (end of day)

Production **v2.5.823**. Constitution **AGENTS.md v2.9.0**. Onboarding package
**1.5d**. Read everything from `origin/main`, never from a working tree.

## Do this before anything else

```bash
git config core.hooksPath .githooks
git config user.name "GreenBear"
```

`core.hooksPath` is local config, so a fresh clone starts with the signing hook
OFF, and an unsigned commit cannot be repaired without the history rewrite
section 6 forbids.

## The law that outranks everything

**`greenbear` is the Owner's own account.** Section 18 was rewritten today to
say it in one line: **touching that account without his permission is
FORBIDDEN.** The account, his presence on the site, his page. Indirect changes
count. Nothing the game does may take anything from it — no loss, no rating
drop, no reputation hit, no broken streak, no counter, no rank recomputation, no
Battle Move.

Enforced in `chef_battle/services.py` by `is_immortal()` and `penalise()`. Every
path that subtracts from a chef goes through them. **The marker is
`OWNER_SLUG`, never `infinite_moves`** — that flag is on three production
accounts, and keying on it froze two ordinary chefs' ranks in v2.5.820.

Do not refactor `"greenbear"` into `settings.OWNER_SLUG`. **§20**: privileges are
his alone. **§19**: a reply ends the work run.

## How he wants to be worked with — read this before doing anything

Every line was earned today, most of them the hard way.

- **Answer in about three sentences.** Measurements, reasoning and near-misses
  go in the commit and the journal, never in his window.
- **Detail him ONLY when the Arena visibly changed.** No visual change is one
  line. He does not read code and never has — that is what agents are for.
- **Never ask him anything until the whole corpus has been searched** — archive,
  journal, board, Carpet JSON, code. He has said most of it already, and a menu
  of options reads as "I did not look".
- **Never run the whole app suite for a small change.** Name the classes that
  cover it; `manage.py test chef_battle` is eight and a half minutes of his
  allowance.
- **Never spawn parallel subagents to go faster.** Eight of them burned the
  session limit today and returned nothing; a grep answered the same question in
  two minutes.
- **Scanning is read-only.** A sweep opens files and reports; it never edits.
- **Claim `.agent-chat/deploy.lock` BEFORE the version bump.** A lock written
  after the bump reserves nothing — a number was taken out from under me twice
  today, and his ruling is that it was my failure to check the queue, not a
  collision.
- **Do not put another agent in the account of your own missed check.**
- Orphaned file → bin it. Batch small fixes into one deploy. Short journal rows.

## Where the board stands

**A09 is NEXT and unassigned** — the approach stage inside the rings. A07 closed
at v2.5.812; X01 closed by Bolt at v2.5.822.

The audit cards **X01–X12** are in group "Audit 2026-08-05". Done: X01, X02
(withdrawn on his ruling), X03, X04, X09, X12. **Still his to rule: X05, X06,
X07, X08, X10, X11** — the acceptance window, the battle window, moves earned,
combat moves per round, the matchmaking axis, the token packages. Four touch
money. **No agent changes code towards an archived document.**

## What changed today

- **Section 10 amended (2.7.0); nineteen rule documents restored** from the
  archive into `docs/chef_battle/`. They had governed nothing, which is why the
  code drifted from them. An archived document is not a weaker document, it is
  one that has been switched off.
- **Section 18 rewritten (2.9.0)** to the plain prohibition, and his own remarks
  on the subject removed from the documents, the code, the tests, the journal
  and the board.
- **Wins promote rank** (X09), thresholds 0/3/6/9/12/15/18/21 — the three-win
  step is `chef_levels.md`'s own cadence. `rating` stays a statistic.
- **A07**: the arena fits one screen at every width.
- **`?demo=vs` is stable** — it used to be wiped by its own first poll, which is
  what he saw as chefs appearing and vanishing.

## Landmines, measured on the live page

1. `arena_render.css` does **not** own the camera —
   `arena_deck_polish.css:3666` sets it last and wins; two blocks above it drop
   `rotateX` entirely.
2. It does not own the floor container's height either — `arena_atmosphere.css`
   wins on specificity, and the container is absolute with `top/bottom: 0`.
3. `filter: none !important` on every arena cell kills any filter on the floor.
4. A CSS declaration beats an SVG presentation attribute.
5. **Indentation in the Arena stylesheets does not imply a media scope** — 668
   lines sit indented at top level as bodies of removed `@media` wrappers.
6. `arena_render.css` loads from **inside the body**
   (`_arena_render_ring.html:201`), after every head stylesheet.
7. PowerShell `Get-Content | Set-Content` double-encodes UTF-8.
8. A heredoc mangles regexes containing backslashes — write the script to the
   scratchpad and run it, do not pipe it through `bash -c`.

## Open

- **A09**, unassigned, and the six rulings above.
- **Drop `level` and `ignored_battles`** — both dead, both need his word,
  because a column drop is a migration (section 8).
- **The nineteen restored documents are binding but not reconciled.** Each is a
  mixture of live rule, superseded rule and open question. Where one contradicts
  the code, the code is not automatically wrong.
- **A flaky test, not mine:** `ArenaMasterMonitorTests
  .test_event_log_append_only_ordering` fails under `--parallel`, passes alone.
  Three events created in a loop, ordered by `-created_at` with no tiebreak, so
  ties are undefined. Until it is fixed, a green suite is a coin toss.
- Narrow-viewport verification of A07 was never possible — the browser would not
  resize below the desktop window.

## Rollback

`rollback/2026-07-28-stable-v2.5.675` — annotated tag, commit `3b4f88ad`.
Today's releases revert individually; see journal rows v2.5.807–823.
