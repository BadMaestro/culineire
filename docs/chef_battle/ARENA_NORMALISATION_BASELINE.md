# Arena normalisation — BEFORE baseline

**Phase 3–7 of the master task. Read-only.** Nothing in the Arena was edited to
produce this file. Every number below was measured on 2026-08-08 against
`a1f40923`, the commit production was serving as **v2.5.910**.

The purpose of this document is to make the "after" comparison possible. A
metric that is not written down here cannot be claimed as an improvement later.

---

## 0. State at the start

| | |
|---|---|
| Repository HEAD | `a1f40923` |
| `origin/main` | `a1f40923` — identical |
| Production version | v2.5.910, confirmed from the live footer |
| Working tree | clean |
| Worktrees | one, the main checkout |
| Local branches | `main`, `arena_agent/c4` (2026-07-27, stale) |
| Remote branches | `origin/main`, `origin/agent/greenbear/ar1-eleven-rings` (2026-07-29, stale) |
| Stash entries | none |
| Untracked Arena files | none |
| Migrations | 218 applied; `chef_battle` at `0085_chefbattleprofile_withdrawals_remaining_and_more` |
| Venv vs production | Python 3.12.3, Django 5.2.13, psycopg 3.3.4, tblib 3.2.2 — identical to the server |

**Agent synchronisation.** Carpet message **#3506** to GreenBear, sent before any
file was opened: the proposed split (Bolt — audit, JS, geometry, lifecycle,
tests; GreenBear — CSS, templates, selector inventory), the two-stylesheet
target, the body-linked stylesheet, and an explicit instruction not to build on
the parked DeckBands patch. **No shared file will be touched before he answers.**

---

## 1. Backup and rollback — verified, not asserted

**Tag:** `backup/arena-pre-normalisation-2026-08-08` → `a1f40923a7e0ca1c978df97843d57b97e3ed3615`
Annotated, and pushed to origin.

`git diff backup/arena-pre-normalisation-2026-08-08 HEAD` is **empty**: the tag is
byte-for-byte the state production was serving.

**The rollback was rehearsed, not described.** A detached worktree was created at
the tag, its footer read `v2.5.910`, its Arena stylesheets were all present, and
`manage.py check` passed inside it. The worktree was then removed. The rehearsal
had to be run at a short path (`E:/rb`): the deep scratchpad path exceeded
Windows' filename limit on `docs/archive/…`, which is worth knowing before an
emergency, not during one.

**Procedure:**

```
git checkout main
git reset --hard backup/arena-pre-normalisation-2026-08-08
git push --force-with-lease origin main      # only with the Owner's word
bash /srv/culineire/scripts/deploy.sh
```

**Uncommitted work preserved separately.** The unverified `DeckBands` coordinator
is **not** in the tree. It is `.agent-chat/bolt-deckbands-wip.patch`, 482 lines,
md5 `a4f98f28e2f035c364cce56e422c5480`, and `git apply --check` confirms it still
applies to this HEAD. It was removed from the working tree because it was
contaminating the test baseline — see section 6.

---

## 2. The Arena as it actually is

### 2A. Stylesheets

Ten files match `arena*.css` on disk. **Seven are loaded by the Arena page**; the
other three belong to the Master Console and its plan board and are out of scope.

| # | File | Lines | Rules on the live page | `!important` | `z-index` |
|---|---|---:|---:|---:|---:|
| 8 | `arena.css` | 780 | 117 | 4 | 4 |
| 9 | `arena_command_deck.css` | 747 | 146 | 2 | 10 |
| 10 | `arena_effects.css` | 134 | 22 | 0 | 2 |
| 11 | `arena_hall.css` | 257 | 32 | 7 | 0 |
| 12 | `arena_deck_polish.css` | **4345** | 556 | **31** | **43** |
| 13 | `arena_atmosphere.css` | 955 | 70 | **85** | 9 |
| 15 | `arena_render.css` | 1316 | 167 | 7 | 2 |
| | **total** | **8534** | **1110** | **136** | **70** |

The `#` column is the live cascade order, and it carries the first finding.

**`arena_render.css` is loaded LAST, and it is loaded from inside `<body>`.**
Its `<link>` sits in `templates/chef_battle/_arena_render_ring.html`, inside a
`DIV`. Every other sheet is in `<head>`. Comments in `arena_atmosphere.css`
state that *it* is the file that loads last and therefore wins; that is false on
the live page, and decisions have been made on the strength of it.

**Unique `z-index` values in play:** `-1 0 1 2 3 4 5 6 7 8 9 10 11 12 24 27 60
130 200 10000 9998` — twenty-one distinct levels for one page.

**Contested ownership, counted rather than estimated:** 385 distinct Arena
selectors; **55 are written in three or more files**; and there are **585
selector/property pairs where more than one file sets the same property on the
same selector**. The worst are the structural ones — `.arena-render-container`
(18 contested properties across 5 files), `.arena-command-deck__phase-card` and
`.arena-command-deck__metrics` (16 each), `.arena-command-deck__ladder` and
`__gifts` (14 each).

### 2B. JavaScript

Six Arena scripts are loaded: `arena_render.js` (154 891 B, **3408 lines**),
`arena_deck.js`, `arena_geometry.js`, `arena_octagon.js`, `arena_battle_room.js`,
`arena_lamp_console.js`.

Inside `arena_render.js`:

| | |
|---|---:|
| `getBoundingClientRect` calls | 21 |
| ResizeObservers | 6 |
| MutationObservers | 0 |
| `addEventListener` | 7 |
| `setTimeout` | 2 |
| `setInterval` | 5 |
| `requestAnimationFrame` | 3 |
| statements writing `.style.*` | 32 |
| statements writing position (`top/left/right/bottom/width/transform`) | 20 |
| `querySelector*` | 82 |

**Functions that both read and write layout: six.** The heaviest are
`measureHeader` (10 reads / 5 writes), `placeRankSpine` (6 / 9), `fitScene`
(1 / 9) and `placeFloorCaption` (1 / 7). Read-write-read-write in one pass is
the layout-thrash pattern the master task names in section 13.

**Call graph, from the source:**

```
measureHeader ──► fitScene ──► billboardFaces
                     ├──► placeRankSpine
                     └──► placeFloorCaption
billboardFaces ──► measureHeader        (mutual recursion between the two)
stampFloorCentre                        (entry point, driven by state)
attachEvents                            (binds the triggers)
```

**Triggers:** 1 window `resize`, 6 ResizeObservers, 3 `document.fonts.ready`,
1 `DOMContentLoaded`, 5 `setInterval`, 2 `setTimeout`, 3 `requestAnimationFrame`.

### 2C. Templates and backend

| | |
|---|---:|
| `templates/chef_battle/*.html` | 59 |
| `arena.html` | 498 lines |
| `_arena_render_ring.html` | 224 lines |
| `chef_battle/views.py` | 3898 lines |
| `chef_battle/selectors.py` | 1612 lines |
| `chef_battle/services.py` | 3690 lines |
| `chef_battle/tests.py` | 11 622 lines, 130 test classes |

`arena.html` carries one inline `style=` and two `<script>` blocks. No duplicate
`id` attributes.

---

## 3. The initial-render defect, measured

The Owner reported the Rank Ladder appearing in the centre of the page before
the Octagon exists, then jumping right. It is now a number rather than a
description.

Recorded with a buffered `PerformanceObserver` on `layout-shift`, 1440×900,
reload:

```
layout shifts on load:        1
CLS:                          0.0255
shift time:                   943 ms
```

The single shift, and its sources:

| Element | From | To | Moved |
|---|---|---|---|
| `DIV.arena-rank-spine` | x 635, y 312 | x 1076, y 414 | **441 px right, 102 px down** |
| `P.arena-floor-caption` | y 210 | y 227 | 17 px down |
| three `LI.arena-rank-spine__item` | 0×0 | 159×24 at x 1076 | appear |

**This is exactly the transition the master task forbids in section 24:** a
CSS-default position painted first, a JavaScript-final position written after.
The ladder is not animated into place — it is drawn wrong and then corrected.

The mechanism is visible in the code: `placeRankSpine()` writes
`style="top: …; left: …"` inline, and until it runs the element is positioned by
its stylesheet default near the centre of the deck. On this load the correction
landed at 943 ms while first paint was 960 ms, so a fast warm load can hide it;
the Owner's cold load does not.

---

## 4. Performance baseline

1440×900, warm cache, production. Numbers not available with the current
tooling are named rather than invented.

| Metric | Value |
|---|---|
| domInteractive | 564 ms |
| DOMContentLoaded | 1131 ms |
| load | 1483 ms |
| First paint | 960 ms |
| First contentful paint | 960 ms |
| LCP | not available in this harness |
| **CLS** | **0.0255** (one shift, the ladder) |
| Layout shifts | 1 |
| Document transfer | 85 495 B |
| Total requests | 138 |
| Stylesheets on the page | 16 (7 Arena) |
| JS requests | 15 |
| DOM nodes | 2524 |
| Nodes inside `#arena-render` | **1931** (76% of the page) |
| Style recalculation / layout time | not available without DevTools protocol |
| Cold-cache and CPU-throttled runs | not available in this harness — must be repeated by hand or with CDP before final acceptance |

---

## 5. Geometry baseline

Boxes as `x, y, w, h` in CSS pixels, fresh load, production.

### 1440 × 900

| Element | Box |
|---|---|
| deck | 0, 146, 1430, 754 |
| ribbon | 332, 147, 780, 82 |
| phase rail | 352, 154, 740, 44 |
| caption | 507, 235, 416, 53 |
| octagon | 377, 295, 676, 539 |
| ladder | 1076, 414, 159, 220 |
| metrics | 932, 252, 480, 73 |
| cooking widget | 22, 163, 259, 252 |
| crown ladder | 18, 665, 248, 167 |
| gifts | 1164, 664, 248, 167 |
| crowd rail | 1, 840, 1428, 59 |
| deck overflow | 0 |

### 1920 × 1080

octagon 534, 300, 843, 670 · ladder 1391, 462, 168, 220 · caption 747, 235, 416, 53 · deck overflow 0

### 1280 × 800

octagon 364, 293, 542, 430 · ladder 935, 372, 147, 220 · caption 350, 235, 416, 51 · deck overflow 0

### 1170 × 820 — the Owner's own window

octagon 311, 318, 537, 426 · ladder 878, 395, 139, 220 · caption 274, 261, 383, 49 · deck overflow 0

**Overlaps that exist today** (excluding the deck and floor containers, which
contain everything by design):

| Viewport | Overlapping pair | Area |
|---|---|---:|
| all | ribbon × phase rail | by design — the rail is inside the ribbon |
| 1440 | metrics × octagon | 3 630 px² |
| 1920 | metrics × octagon | 5 250 px² |
| 1170 | metrics × octagon | 2 562 px² |
| 1170 | **ladder × gifts** | **1 575 px²** |
| 1170 | gifts × crowd rail | 2 436 px² |
| 1170 | crown ladder × crowd rail | 2 436 px² |

The metrics card sitting over the octagon's corner is long-standing and may be
intentional; the other three are the composition running out of room at the
Owner's window, and they are candidates for AN sections rather than for a quiet
fix during cleanup.

---

## 6. Resize convergence

Fresh load compared against arriving at the same viewport by resizing:

| Path | Octagon delta | Ladder delta | Caption delta |
|---|---|---|---|
| 1440 → 1920, vs fresh 1920 | 0, 0, 0, 0 | dx 0, dy **−1** | 0, 0 |
| 1920 → 1280, vs fresh 1280 | 0, 0, 0, 0 | 0, 0 | 0, 0 |

**Convergence holds today at these pairs**, within one pixel of rounding. This
matters: it means the resize divergence fixed in v2.5.878 has not returned, and
the "after" state must not lose it. Repeated cycles, and the 1170 window, are
still to be swept — recorded here as an unfinished part of the sweep rather than
claimed as passing.

---

## 7. Test baseline

Authorised once by the master task, section 6. Run on the **clean tree**, on
PostgreSQL, with the production dependency versions.

```
./venv/bin/python manage.py test --noinput --parallel 8
```

**Methodology note, because it changes the number.** The first attempt was
started while the unverified DeckBands patch was still in the working tree, and
it began producing failures from tests that pin the very functions that patch
rewrites. That run was discarded, the tree restored to `a1f40923`, and the
baseline restarted. A baseline taken over unmerged work is not a baseline.

Full output preserved as `ARENA_NORMALISATION_BASELINE_SUITE.txt` beside this
file.

```
Ran 1750 tests in 710.670s
FAILED (failures=2, skipped=2)
```

| | BEFORE |
|---|---:|
| total | 1750 |
| passed | 1746 |
| failed | **2** |
| errors | 0 |
| skipped | 2 |
| duration | 710.7 s (11 min 51 s), `--parallel 8` |

**The two failures are pre-existing on `main` and are in production.** Both are
`chef_battle.tests.EmptyFighterPadIsMutedTests`, and both assert that
`arena_render.css` still contains the muted styling for the empty fighter pad:

```
test_the_empty_pad_has_its_own_rule
    ".arena-floor-fighter--empty .arena-floor-fighter__tile" in arena_render.css
test_it_is_quieter_than_an_occupied_pad
    "stroke-opacity: .5" and "var(--hall-green) 7%" in arena_render.css
```

That CSS was removed in **v2.5.890**, when the Owner ordered the empty pads off
the floor entirely: "скрой ячейки для шефов перед боем". The rule was deleted,
the class that tested the *drawing* of the pads was rewritten to test their
absence, and this second class - which tests the *styling* - was missed. The
tests are stale, not the code; the product behaves as he asked.

They are recorded here as BEFORE failures. They will not be quietly counted as
"fixed by the refactor" - correcting them is a two-line change and belongs to
whichever AN section touches that stylesheet, with the correction named.

---

## 8. Ownership manifest — who decides what, today

The rule the master task sets is one responsibility, one owner. This is what the
code actually does now.

| Responsibility | Owners today | Verdict |
|---|---|---|
| Rank order and identity | `ChefBattleProfile.Rank` (backend) | **single owner already** |
| Ring number | `data-ring` on the cell, emitted by the renderer; the ladder receives the same number from the view | single owner, and it survived the numbering work |
| Ring colour | `--arena-floor-1..8` in `arena_render.css`; repeated as literals in `arena_deck_polish.css`; overridden with `!important` in `arena_atmosphere.css` | **three owners** — the ladder already reads the computed fill instead of a fourth copy, and that is the pattern to generalise |
| Octagon geometry | `ArenaOctagon` / `arena_render.js` | single owner |
| Scene camera | `arena_deck_polish.css:3666`, with two earlier blocks dropping `rotateX` | **contested by three declarations in one file** |
| Page layout, vertical | CSS shares (`top: 8.2%`, composition centre 0.51, pad 0.64) **and** `fitScene`/`placeFloorCaption`/`placeRankSpine` in JS | **two systems, the core defect** |
| Rank Ladder position | stylesheet default, then `placeRankSpine()` inline | **two owners, and the user sees both** |
| z-order | 70 declarations, 21 values, three files | **no owner** |
| Arena state | `_build_arena_payload` + `PUBLIC_ARENA_STATE_KEYS` | single owner, already consolidated |
| Polling | `arena_render.js`, one loop, plus presence | single owner |
| Presence | presence app, 180-second window | single owner |
| Fixture / emulation visibility | `ARENA_SHOW_EMULATION_BOTS`, gated at the enrolled query and the crown ladder | single owner, deliberately off |
| Readiness | **nothing owns it** | the initial-render defect follows from this |

---

## 9. Proposed consolidation and deletion plan

Proposed. Nothing here is executed until the Owner assigns it as an AN section.

**Consolidate, in this order:**

1. **Readiness lifecycle first, before any CSS is touched.** A state that the
   page can be in — shell, geometry, scene, interactive — with geometry-dependent
   elements hidden by *state*, never by time. This is the only change that fixes
   the ladder jump without a timing hack, and it is measurable: CLS must reach 0
   and the 441 px shift must disappear from the trace.
2. **One layout authority for the page's vertical.** Remove the CSS shares
   (`top: 8.2%`, `0.51`, `0.64`) or remove the JS passes — not both, and not a
   third coordinator above them. The parked DeckBands patch is *evidence for*
   this section and, on its own terms, fails the test: it adds an owner rather
   than removing the two that exist. Recommend **discarding it** and keeping only
   the finding it produced — that the band must be decided before the floor is
   fitted, and that the caption's width must be decided before its height.
3. **Two stylesheets.** Octagon/scene and page shell. `arena_render.css` moves
   to `<head>`. The five remaining files are merged into the two and deleted,
   not wrapped.
4. **A layer model** replacing 21 ad-hoc `z-index` values, with each surviving
   `!important` individually justified — today there are 136, of which 85 are in
   one file.
5. **JS pass reduction:** six functions that both read and write layout, and six
   ResizeObservers, collapse into one deliberate read phase and one write phase.

**Delete only with evidence.** Nothing has been classified DEAD yet. Two
candidates are already classified NOT dead and must be preserved: the emulation
bots and their switch (disabled ≠ dead, and the Owner's own instruction), and
`hydrateFixtures()`, which is deliberately disconnected and held in place by
three tests. The stale branches `arena_agent/c4` and
`origin/agent/greenbear/ar1-eleven-rings` are candidates for tidying, and both
predate the roles being abolished.

---

## 10. What this phase did not do

- No Arena code was edited.
- No CSS was rewritten.
- Nothing was deleted.
- Nothing was deployed.
- The DeckBands patch was neither merged nor discarded — it is preserved and
  judged, and the judgement is the Owner's to accept.
- Cold-cache, CPU-throttled and network-throttled loads, repeated resize cycles,
  and the 1170 window resize sweep are **not yet measured** and are named as
  such rather than assumed.
