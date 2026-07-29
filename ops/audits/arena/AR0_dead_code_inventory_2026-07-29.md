# AR0 — Arena CSS/JS dead-code inventory (read-only)

Owner-ordered 2026-07-29: audit now, delete together with AR1. **Nothing was
deleted or disabled by this audit.** Method: every candidate was checked against
every surface — templates, all JS, all CSS, Python (views/services/tests) — per
runbook §6 ("do not classify code as dead without evidence from every surface").

## The shape of the problem

The arena page loads **7 stylesheets, 7 638 lines**, in this cascade order:

| # | File | Lines | `!important` |
|---|------|-------|--------------|
| 1 | `arena.css` | 795 | 4 |
| 2 | `arena_command_deck.css` | 735 | 2 |
| 3 | `arena_effects.css` | 134 | 0 |
| 4 | `arena_hall.css` | 267 | 7 |
| 5 | `arena_deck_polish.css` | **3 942** | 32 |
| 6 | `arena_atmosphere.css` | 1 013 | **107** |
| 7 | `arena_render.css` (linked from inside `_arena_render_ring.html`, lands last) | 752 | 1 |

Two structural faults, both measured:

1. **Six files paint, one file un-paints.** `arena_atmosphere.css` carries 107
   `!important` and **20 suppressor rules** (`display:none`/`opacity:0`/
   `content:none` + `!important`) whose only job is to cancel what the other six
   files and the renderer produce. Reading any single file cannot tell you what
   the screen shows.
2. **`arena_deck_polish.css` (3 942 lines) outranks the base layer.** Its rules
   are prefixed `.page--arena`, so they beat `arena_render.css` on specificity
   regardless of load order. Lived proof: the dark-stands fix shipped in
   **v2.5.686 was a silent no-op** — the rule was edited in `arena_render.css`
   while the winning rule sat in `arena_deck_polish.css:2339`. One wasted
   deploy, found only by probing computed styles in the browser.

**CORRECTION (same day, before AR1 shipped).** This section first read "67
functions, 0 never called". That was wrong: the audit script concatenated
`arena_render.js` twice — once directly, once via the `static/js/**` glob — so
every function scored at least two occurrences and nothing could ever be
flagged. Re-checked with the file deduplicated: **7 of 68 functions were
unreachable** — `drawRingSeams`, `drawFloorPad`, `floorOuterRadius`,
`floorRadius`, `radiusStepFor`, `inset`, `appendCrowdFigure`. Six were removed in
AR1 (v2.5.709) together with the orphaned `CELL_INSET`; `appendCrowdFigure` and
`crowdFaceFor` were deliberately **kept, disconnected**, because card A08 is what
turns the atmospheric crowd back on and the paid face assets stay. The CSS
findings below were unaffected by the bug.

## Tier 1 — dead by absence (no creator anywhere; deleting cannot change pixels)

| Candidate | Evidence | Where styled |
|---|---|---|
| `.arena-rim`, `.arena-rim--inner`, `.arena-rim--outer` | no JS/HTML/Python creates these nodes, anywhere | **4 files**, 17 lines (`hall` 3, `deck_polish` 3, `atmosphere` 3, `render` 8) — and `atmosphere:896-901` additionally hides them, i.e. hiding nodes that do not exist |
| `.arena-ring-seam`, `--outer`, `--stage` | creator `drawRingSeams()` is **gutted**: `arena_render.js:334-336` is `{ return; }`. No JS stamps the class | `atmosphere`, `render` |
| `.abp__chat*` (12 names: `-body -empty -form -input -login -messages -msg -send -time -title -who`) | `arena_battle_popup.html` uses 26 `abp__` names; **none** are the chat block. Only hits are `arena.css` + two archived audit docs | `arena.css` (of its 44 `abp__` lines) |
| `.arena-puzzle-container` | unreferenced | `command_deck`, `deck_polish` |
| `.arena-ladder-row` | unreferenced | `deck_polish` |

## Tier 2 — build-then-hide pairs (delete the pair, never one half)

| Pair | Evidence |
|---|---|
| `drawFloorPad()` (`arena_render.js:339`) → `.arena-floor-pad`, `.arena-floor-pad--glow`, `[data-arena-layer="floor-pad"]` | the function runs on **every render** and appends nodes; `atmosphere:895-901` then sets `display:none !important`. Live JS producing permanently invisible DOM |
| `drawRingSeams()` (gutted) → `.arena-ring-seam*` CSS | call site retained, body emptied, styling left behind |
| `.arena-floor-wrapper`, `.arena-floor-plane`, `.arena-floor-ring` | suppressed **twice** (`atmosphere:764-767` mobile and `827-833` all widths) — verify the creator before touching |

## Tier 3 — do NOT touch in cleanup (Owner decision or belongs to an AR card)

- `.arena-live-centre*`, `.arena-live-centre--crown/--quiet`, `#arena-live-stage`,
  `.arena-live-chef--opponent`, `.arena-confrontation-band …` — an entire hidden
  confrontation/centre UI (`atmosphere:943-982`). This is the **old fighter
  composition**; AR/A09 may revive or replace it. Deleting it now would destroy
  the only existing green/red flank markup.
- `.arena-crowd-figure` — atmospheric stand-ins switched off by the Owner; the
  **paid face assets stay** in `static/`. Disconnect stays, asset stays.
- `.arena-floor-fighter--challenger/--crown/--opponent` (`arena_render.css`) —
  unreferenced modifiers, but they are exactly the plinth classes A09 needs.
  Flagged, not dead: this is *why* production has no green-left/red-right
  composition and the second chef reads as a sticker.

## Blocking finding for AR1 — the sponsors-grid borrow

The floor is not drawn on the arena's own geometry. It is drawn on the **Sponsors
puzzle grid**, `OctagonFloorTemplate` (`static/js/octagon_floor_template.js`),
used **11×** in `arena_render.js`. That template has **6 rings** while the arena
has 8 ranks, so `arena_render.js:355-356` documents rings 6–8 sharing the outer
template ring, and `arena-cell--sponsors-tpl` appears in **37 CSS places**
(`deck_polish` 18, `render` 12, `atmosphere` 7).

`RING_RADII`/`RING_COUNTS` are **shared with `sponsors_puzzle.js` and
`sponsors_modal.js`** — the live Sponsors feature. Therefore:

> **`octagon_floor_template.js` must not be edited to add rings.** Widening it to
> 11 would change the Sponsors puzzle. AR1 needs the arena to own its own ring
> table (11 rings, §2 v2) and stop borrowing this one.

A 6-ring borrowed grid cannot express the approved 11-ring structure at all, so
AR1 is the point where the borrow ends — and the dead layers above are identified
**by construction**: whatever the new 11-ring renderer does not use, goes.

## Backup / rollback for the deletion pass (AR1)

Git is the backup — no file copies. Before the deletion commit, pin
`rollback/pre-ar1-<version>` at the current `origin/main`; rollback is
`git reset --hard <tag>` + `deploy.sh`. Existing pinned tag
`rollback/2026-07-28-stable-v2.5.675` (`3b4f88ad`) stays untouched.

**The test suite will not protect this.** There are no visual regression tests:
the suite stays green while the arena is broken (that is how v2.5.686 passed).
The gate for the deletion pass is a measured baseline — screenshots at 1280 and
1920 plus a computed-style probe of the ring fills, captured before and after.
