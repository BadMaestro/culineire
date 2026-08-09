# Arena normalisation — engineering report

**2026-08-08.** Production went from **v2.5.910** to **v2.5.952** across fifteen
architectural stages, each deployed whole and verified on the live site before
the next began. Stages 1-8 closed AN1-AN11, AN14, AN17, AN19 and AN23-AN25;
stages 9 to 15 closed **AN13**, **AN12**, **AN15**, AN13 again on the second
sheet, **AN18/AN22/AN21**, **AN20**, **AN16**, and the closing three -
**AN26**, **AN27**, **AN29**. Twenty-nine cards; twenty-six are DONE, and the
three that are not say why in one line each. The BEFORE numbers all come from
`ARENA_NORMALISATION_BASELINE.md`, written before a line was changed.

---

## A. Before

Seven Arena stylesheets, 8534 lines, 1110 rules on the live page. 136
`!important` lines, 70 `z-index` declarations over 21 distinct values from −1 to
10000. 385 Arena selectors, 55 of them written in three or more files, and **585
selector/property pairs where more than one file set the same property on the
same selector**.

`arena_render.css` was linked from inside a `DIV` in the body, which measured
**last in the cascade** — after `arena_atmosphere.css`, whose own comments claim
that role and on which decisions had been made.

`arena_render.js`: 3408 lines, 21 `getBoundingClientRect` calls, 6
ResizeObservers, 20 statements writing position, and **six functions that both
read and write layout in one pass**.

The deck's vertical space had three owners that did not know about each other: a
CSS share for the caption (`top: 8.2%`), a CSS share for the floor (a 0.64 pad
and a 0.51 composition centre), and a JavaScript pass that clawed a band back
after the fact.

Test baseline: **1750 tests, 2 failures, 710.7 s**, PostgreSQL, `--parallel 8`.

Confirmed defects: the rank ladder painted at its stylesheet position and moved
441 px right and 102 px down by JavaScript (one shift at 943 ms, **CLS 0.0255**);
a second cold-load shift of **CLS 0.0111** at 981 ms in which the crowd rail,
gifts, crown ladder, metrics and the whole SVG slid up together.

---

## B. Root causes

**Two systems owned position and neither could see the other.** CSS placed the
ladder in thirteen rules and the caption in seven, as percentages of a deck whose
height was itself a JavaScript variable; `placeRankSpine()` and
`placeFloorCaption()` measured the floor and wrote inline coordinates over all of
them. The user saw both answers, in order.

**The initial render jumped because nothing said it was too early to paint.**
Not an animation defect. The elements existed, the geometry did not, and no state
distinguished the two.

**The second shift was the same fault one level up.** The deck is
`100svh − var(--arena-header-h, 146px)`; 146 is the desktop header and the real
one at 1170×820 is 172, so the first paint was 26 px too tall and the correction
moved everything that sat in it.

**Cascade conflicts came from load order nobody could read in one place.** Which
sheet won was decided by the position of a `<link>` — one of them inside the
body — and `!important` was the tool used to win arguments the order had already
lost.

---

## C. Changes

| Deploy stage | What |
|---|---|
| 1 | Audit, baseline, backup tag, rollback rehearsed, ownership map |
| 2 | Readiness lifecycle: boot -> shell -> geometry -> scene -> interactive |
| 3 | The octagon's sheet moved from the body to the head, same cascade position |
| 4 | Four shell stylesheets merged into `arena.css`; three files deleted |
| 5 | One documented layer ladder, 21 `--arena-z-*` tokens, values unchanged |
| 6 | One owner of position: 31 positional declarations removed |
| 7 | The deck waits for its measured height before it is painted |
| 8 | 81 `!important` removed, 58 kept and each proven necessary |
| 9 | **AN13**: 584 declarations a later rule with the same selector already beat, and the 135 rules left empty with them |
| 10 | **AN12**: seven stylesheets become two; the console mirror keeps only `arena.css` |
| 11 | **AN15**: `arena_page_layout.js` owns the page's geometry; the renderer stops measuring the site header |
| 12 | **AN13 again**: the same 44 unreachable declarations in `arena_atmosphere.css`, and the guard test widened to read both sheets |
| 13 | **AN18, AN22, AN21**: nothing dead, 117MB of static accounted for, the last inline `style` attributes out of the templates |
| 14 | **AN20**: one forced reflow per pass removed; the interleaving that is left is dependent measurement and stays |
| 15 | **AN16**: the octagon behind a public contract - three questions, and `.arena-cell` gone from every placement function |
| 16 | **AN26/AN27/AN29**: the full gate re-run, the before/after comparison, and this report's closing pass |

These numbers are DEPLOY STAGES, in the order they shipped. They are not the
AN cards - the board is the register of those, and where a stage closed a card
the card is named in the row. The first eight ran before the block was opened
and the numbering collided by accident, which is worth one line here rather
than a puzzle later.

**Files deleted:** `arena_command_deck.css`, `arena_hall.css`,
`arena_deck_polish.css` — merged, not wrapped in imports.

**Lifecycle introduced:** one attribute on the deck, five states, geometry
counted as valid only when a cell has a real box. No `setTimeout`, no
`animation-delay`, no opacity trick, and a test that fails if a clock is ever put
in front of the first paint.

**Layout owner:** the renderer, on desktop. Below 767 px nothing changed — the
Owner froze the Arena there on 2026-08-03, JavaScript places nothing, and the
static flow rules are untouched.

---

## D. After

| Metric | Before | After |
|---|---:|---:|
| Arena stylesheets | 7 | **2** |
| Lines in them | 8534 | **7279** |
| Declarations a later identical selector already beat | 628 | **0** |
| `!important` (source lines) | 136 | **55** |
| `!important` (live properties) | 338 | **204** |
| `z-index` declarations | 70 | 72 |
| Raw `z-index` numbers | 70 | **0** |
| Layer tokens | 0 | **21** |
| Stylesheet links in `<body>` | 1 | **0** |
| CSS rules placing the ladder | 13 | **0** |
| CSS rules placing the caption | 7 | **0** |
| Layout shifts on load | 1–2 | **0** |
| **CLS** | 0.0255 / 0.0111 | **0** |
| Tests | 1750 | **1775** |
| Failures | 2 | **0** |
| Duration | 710.7 s | 712.9 s |
| `ResizeObserver` in the renderer | 6 | **1** |
| Page-level triggers in the renderer | 4 | **0** |

**Geometry is unchanged.** Measured on production after every stage, against the
baseline boxes:

```
1170 × 820   octagon 311,318,537,426   ladder 878,395,139,220   caption 274,261,383,49
1280 × 800   octagon 364,293,542,430   ladder 935,372,147,220   caption 350,235,416,51
1920 × 1080  octagon 534,300,843,670   ladder 1391,463,168,220  caption 747,235,416,53
```

**Initial render (§24):** temporary centre ladder positions 0, visible jumps 0,
CSS-default → JS-final transitions 0, timeout-based hiding 0.

**Resize (§25):** 1280 → 1920 → 1280 returns to identical numbers, and a fresh
load at 1280 is byte-identical to arriving there by resizing.

---

## D2. Performance, before and after — AN27, §23

> **SUPERSEDED for the browser metrics by section L.** Those numbers were
> taken on the harness at 1280x800 and compared against a baseline measured
> on production at 1440x900. Not the same conditions, so not a valid
> comparison. The CODE metrics here are read from the repository and stand.


Two kinds of number, and they are not interchangeable. The CODE metrics are
read from the repository and are exact. The BROWSER metrics come from a harness
carrying the real arena DOM, the real stylesheets and the real renderer over
HTTP: honest for before-and-after, and not a statement about production, which
is staff-only and answers 404 to this browser.

| Code metric | Before | After |
|---|---:|---:|
| Arena stylesheets | 7 | **2** |
| Lines across them | 8534 | **7279** |
| CSS rules across the two sheets | 1110 | **988** |
| Declarations a later identical selector already beat | 628 | **0** |
| `!important` source lines | 136 | **55** |
| Raw `z-index` numbers | 70 | **0** |
| Layer tokens | 0 | **21** |
| Stylesheet `<link>`s in `<body>` | 1 | **0** |
| Inline `style` attributes in the arena templates | 2 | **0** |
| CSS rules positioning the ladder / the caption | 13 / 7 | **0 / 0** |
| `ResizeObserver` in the renderer | 6 | **1** |
| Page-level triggers owned by the renderer | 4 | **0** |
| Placement functions reading the octagon's internals | 3 | **0** |
| Forced reflows in `placeFloorCaption` per pass | 1 | **0** |

| Browser metric, harness at 1280×800 | Before | After |
|---|---:|---:|
| Layout shifts on load | 1–2 | **0** |
| **CLS** | 0.0255 / 0.0111 | **0** |
| Ladder position in the first painted frame | 441 px off, then corrected | **final, and visible** |
| FCP | not captured before the phase | 544 ms |
| LCP | — | 544 ms |
| DOMContentLoaded / load | — | 283 ms / 406 ms |
| Long tasks | — | 4 |
| DOM nodes | 2524 | 2486, of which 1759 are the octagon's SVG |

**Not measured, and it is a tool limit rather than an omission:** cold cache,
CPU throttling and network throttling. All three need CDP and a browser that
can open the production arena. Recorded on the board against AN7, AN9 and AN28
rather than quietly dropped.

---

## E. Deleted

| What | Why it was safe |
|---|---|
| `arena_command_deck.css`, `arena_hall.css`, `arena_deck_polish.css` | Merged into `arena.css` in the exact order the browser already applied them. Every page that loaded them loaded all four together. Geometry compared pixel-for-pixel afterwards. |
| 31 positional CSS declarations | The renderer overwrote every one of them on desktop; removing them changed nothing measurable. Verified at four viewports. |
| 81 `!important` declarations | Proven on the live page: stripping the 40 rules that cannot reach the nine elements affected by `!important` changed **0 of 76 632** measured values. |
| `arena_render.css`, `arena_effects.css` | AN12. Merged in the order the browser already applied them, after the sixteen declarations they shared with another sheet were removed - each of those already lost where it stood. Proved over the rendered DOM in a real engine: 2435 elements x 544 computed properties, plus the octagon's 1759 nodes at four forced stage states, zero differences. |
| 584 superseded declarations and the 135 rules they emptied | AN13. Each was overwritten by a later rule with the IDENTICAL selector, so it could never win for any element. 2550 winning declarations before and the same 2550 after, 0 changed. |

**Nothing else was deleted.** No JavaScript module, no template, no static asset
and no database field. Nothing was classified DEAD.

---

## F. Preserved

- **The emulation bots and their switch.** Disabled is not dead: the accounts,
  profiles, history and the Master Console that drives them are intact, and
  `ARENA_SHOW_EMULATION_BOTS` brings them back.
- **`hydrateFixtures()`** — deliberately disconnected in v2.5.782 and held in
  place by three tests, one of which exists to stop it being tidied away.
- **`god_mode.css`** — never referenced by a template and never to be removed.
- **The Master Console mirror's flat look.** The Owner ruled on 2026-08-08 that
  it keeps neither the tilt nor the effects. That is why the split falls where
  it does — `arena.css` holds the shell and the renderer, because those are what
  the mirror needs, and `arena_atmosphere.css` holds the effects and the hall,
  which it must not get. It decides the SHAPE of the two files, not their
  number: §8 asked for two and there are two.
- **Every `z-index` value.** The ladder gave them names, not new numbers.

---

## G. Rollback

```
tag     backup/arena-pre-normalisation-2026-08-08
commit  a1f40923a7e0ca1c978df97843d57b97e3ed3615
```

Pushed to origin, and rehearsed rather than described: checked out into a
detached worktree, footer verified as v2.5.910, `manage.py check` green, worktree
removed.

```
git checkout main
git reset --hard backup/arena-pre-normalisation-2026-08-08
git push --force-with-lease origin main      # only on the Owner's word
bash /srv/culineire/scripts/deploy.sh
```

Note for an emergency: rehearse at a short path. The deep scratchpad path
exceeds Windows' filename limit on `docs/archive/…`.

---

## H. The assertions of §26

| # | Question | Answer |
|---|---|---|
| 1 | One system owns page-level layout? | **Yes**, since AN15. `arena_page_layout.js` owns the page's own geometry - `--arena-header-h` and the four triggers that can change it. The renderer subscribes and re-fits, and the string `.ce-header` no longer appears in it. The panels are laid out by CSS grid, which IS the page's layout system and is now the only other one. |
| 2 | One system owns octagon geometry? | **Yes**, and since AN16 it is also the only thing allowed to READ it: `ArenaOctagon.region / rankRegion / sponsorsCorner` are the three questions the page may ask, and neither `.arena-cell` nor `data-ring-kind` appears in any placement function. |
| 3 | Ladder position explainable from one source? | **Yes.** `placeRankSpine()`. |
| 4 | Exactly two Arena CSS files? | **Yes.** `arena.css` (shell + renderer) and `arena_atmosphere.css` (effects + hall), AN12. The Owner's ruling of 2026-08-08 is what decides WHERE the split falls — the console loads `arena.css` alone, flat — not whether there are two. |
| 5 | All Arena styles loaded from predictable places? | **Yes.** Both sheets in `<head>`; the console loads one of them and nothing else. |
| 6 | Body stylesheet link removed? | **Yes.** Zero links outside `<head>`. |
| 7 | Can an old stylesheet still override the new layout? | **No old stylesheet remains** — five are deleted. Within `arena.css` nothing overrides itself any more: AN13 removed the 584 declarations a later rule with the same selector already beat. |
| 8 | Competing CSS and JS positions? | **No**, for the ladder and the caption. |
| 9 | Timing hacks for initial rendering? | **No.** State only. |
| 10 | Does a cold load ever show a wrong composition? | **No** at every viewport measured, CLS 0 with not one layout-shift entry, and in the FIRST animation frame the page paints the ladder is already at its final box. A genuinely cold cache and a throttled CPU remain unmeasured - see AN7. |
| 11 | Resize == fresh load? | **Yes.** A fresh load at 1920 is byte-identical to arriving there by resize, and a tour through 1920, 1440, 1280x520 and 1024 returns the exact fresh-load numbers at 1280x800. |
| 12 | Remaining `!important` justified? | **Yes** — 55 across the two sheets, each measured on the live page in AN8. |
| 13 | `z-index` from a documented layer system? | **Yes.** 21 tokens, 0 raw numbers. |
| 14 | Duplicate implementations removed? | **Yes.** Five stylesheets merged away, 628 declarations that a later rule with the identical selector already beat, and three copies of the octagon-measuring loop folded into one contract. The dead-code audit (AN18) found no duplicate JS module to remove - it found two disconnected files and both are deliberate. |
| 15 | Disabled test functionality preserved? | **Yes.** |
| 16 | Can the whole task be rolled back? | **Yes**, and the rollback was rehearsed. |

---

## I. Remaining debt — named, not hidden

1. **`arena.css` is internally layered where the two files legitimately meet.**
   AN13 resolved everything inside the file — 0 declarations are now overwritten
   by the same selector — and AN12 removed every cross-file clash between sheets
   whose order changed. What remains is `arena_atmosphere.css` deliberately
   overriding the shell it loads after, which is what that file is for.
2. **Cold-cache, CPU-throttled and network-throttled loads are not measured.**
   This harness cannot clear the cache or throttle; §24 asks for both. Every CLS
   figure here is from an uncached load of a newly-hashed stylesheet, which is
   close but is not the same thing.
3. **Three functions in `arena_render.js` still read and write layout in one
   pass, and they should.** AN20 removed the one that was accidental and left
   the three where each read depends on the write above it - a caption's
   natural width cannot be measured without first clearing the width it was
   given. One ResizeObserver remains, on the frame the scene is fitted into;
   the page-level triggers moved to `arena_page_layout.js` in AN15.
4. **The `.page--arena` prefix is still the specificity lever** throughout the
   shell. It works, and it is why the remaining `!important` count is as low as
   it is, but it is a convention rather than a system.
5. **AN16 is open** - the octagon is not yet behind a public contract, and the
   page-level placement code still reaches into its `.arena-cell` elements to
   find the floor's edges. **AN26, AN27 and AN29** are the closing three: the
   full test gate re-run, the performance comparison, and this report's final
   pass. **AN7, AN9 and AN28** need a browser on the PRODUCTION arena, which is
   staff-only and answers 404 here; ten of the twelve scenarios were measured
   on the harness instead and are labelled as harness numbers on the board.

## J. The camera boundary — Owner's acceptance repair, 2026-08-09

His acceptance audit found the octagon's vertical position had two owners. The
first repair pass gave the writing a grid row and took the compensation out of
the renderer, and it left three things wrong. He named all three and this
section records how each was closed and with what evidence.

### J1. The camera was owned by the page

The camera viewport was `inset: 0` on the page region, so the region's height
WAS the camera's coordinate space, and three optical quantities followed it: the
scene's side at 172% of it, the perspective origin at 40% of it, and the
transform origin at 62% of the scene.

Measured, with the scale held fixed and the placement owner not running: taking
80px off the page region moved the scene 978.672 to 841.078, the perspective
origin 227.594 to 195.594, the transform origin 606.777 to 521.468, and the
projected octagon 658x440 to 557x375 — with the proportion, 0.669 to 0.673. Page
furniture redefined the optics.

The camera itself is unchanged. Its four values — perspective 1500px,
perspective-origin 50% 40%, rotateX(42deg), transform-origin 50% 62% — are the
accepted ones and were not touched, on his instruction not to redesign the
camera. What changed is what they are measured against: the viewport has an
intrinsic side of its own, and the page scales and moves the COMPLETE component
into its region with a 2D transform outside the perspective.

Proof after: the region was moved and resized by up to 120px, the deck-top
furniture changed twice, the caption's lead row tripled and the caption's type
doubled in size. The octagon stayed 659.00 x 454.00, the proportion stayed
0.688923 to six decimal places, and the perspective, perspective-origin and
camera box did not move.

### J2. The camera's two intrinsic constants

440px and 0.79308. Neither is tuned and neither is copied off a screenshot: the
camera has exactly two intrinsic quantities — the side of its viewport and the
fit of the scene inside it — and two accepted facts pin them.

The first is the octagon's own proportion, 659 by 454. Each viewport side gives
exactly one fit that reproduces it, so that fact alone is a curve, not a point.
The second picks the point: where the rank ring lands INSIDE that box, which is
what the ladder is measured from — so the ladder's accepted left edge, 935, is a
statement about the camera and not about the ladder. At 440px the fit is
0.79308, the octagon comes back 659.00 x 454.00 and the ladder at 935. At 284px,
which satisfies the proportion alone, the outline still matches and the ladder
lands at 941.

`--arena-fit` is now DECLARED in the stylesheet and written by nobody. It used to
be the output of an iterative solve against a box the page handed over.

### J3. The product layout contract replaces REGION_FILL_X

`REGION_FILL_X = 0.5197` was 659/1268 read off the accepted composition while
claiming descent from the Owner's 2026-07-27 rule that the floor stands inside
its frame at 64%. It could not have that descent: the accepted geometry was
never produced by a clean 0.64 relationship — it emerged from fitScene's
iterative multiplication, reserveCaptionBand's multiplication on top of it, and
the old camera/container relationship.

His decision of 2026-08-09 settles it: the accepted composition IS the contract.
Three named constants carry it, each with its provenance beside it, all
region-relative so they hold at every viewport:

    OCTAGON_VISUAL_WIDTH_SHARE   659 / 1268
    OCTAGON_VISUAL_CENTRE_X      0.5          (structural — centred)
    OCTAGON_VISUAL_CENTRE_Y      276 / 564

The distinction he drew and this section keeps: an unexplained number copied
from a screenshot is a defect; an Owner-approved design proportion promoted to
the product specification, named and provenanced, is a contract.

### J4. Moving the region no longer resizes it

`--arena-octagon-offset-y` was a `margin-top`, so +40 pushed the region down AND
took 40 off its height; the octagon re-fitted into the shorter box and 40 arrived
on the screen as 21. It is a `translate` on the finished region now, which
changes no track and no dimension.

Measured 0 / +40 / -40 / 0: the octagon moved 284 -> 324 -> 244 -> 284, stayed
659 x 454 throughout, and the region stayed 564 tall. Exact, and no accumulation.

### J5. The caption's lost gap

`CAPTION_GAP = 6` was a real layout-spacing decision that lost its owner when
`placeFloorCaption()` was deleted, and the caption came to rest six pixels high.
It is a grid row now — `--arena-caption-lead` — because spacing between two
page-layout regions is page layout's decision. No `top`, no `translateY`, no
margin chosen to hit a number.

One further pixel came from elsewhere and is worth recording, because it was
invisible to every reading of the caption: `--arena-deck-top-h` is the first row
of the FLOOR's grid and was measured from the DECK's box, and the deck carries a
1px border. The row was one pixel too tall and everything under it sat one pixel
low.

### J6. The placement is affine, so the solve is exact

The old owner wrote inside the camera — `--arena-fit` and `--arena-shift-*` on
the SVG, inside rotateX under a perspective — which is why it needed a 100px
probe and two refinement passes: a translation asked for in CSS pixels does not
arrive on the screen at that size, and a scale under a perspective does not grow
the box linearly. Every one of those passes was the code apologising for having
crossed a boundary.

Placement is now a plain 2D scale and translate on the viewport. Two writes, one
measurement, no probe, no loop, no accumulation.

### J7. Acceptance, at 1280x800, offset 0

| | target | measured |
|---|---|---|
| Octagon | 305, 284, 659, 454 | 305.5, 284.00, 659.00, 454.00 |
| Rank Ladder | 935, 372, 148, 220 | 935, 372, 148, 220 |
| Caption | 350, 235, 416, 51 | 350, 235, 416, 51 |

Caption overlaps with any page panel: none. Resize converges to the same numbers
by every path — a fresh 1920x1080 and 1280 -> 1920 agree to the pixel
(octagon 459, 306, 992, 683), and 1920 -> 1280 returns to the accepted
composition exactly.

## K. Phase closure — the Owner's ten items, 2026-08-09

The phase is closed here. Sections A to J describe how the architecture got to
where it is; this section is the evidence that nothing was left PARTIAL.

### K1. BEFORE vs AFTER

> **SUPERSEDED for the browser metrics by section L.** Those numbers were
> taken on the harness at 1280x800 and compared against a baseline measured
> on production at 1440x900. Not the same conditions, so not a valid
> comparison. The CODE metrics here are read from the repository and stand.


| Metric | Before | After |
|---|---|---|
| Arena-specific stylesheets | 7 | 2 |
| Arena stylesheet lines | 8534 | 7488 |
| Arena CSS rules | 1110 | 1074 |
| `!important` across both sheets | 136 | 42 |
| Geometry `!important` on the camera path | 7 | 0 |
| Raw `z-index` numbers | 70 | 0, against 50 layer tokens |
| Stylesheet link inside the body | 1 | 0 |
| Inline style attributes in the arena templates | 2 | 0 |
| Declarations a later identical selector already beat | 628 | 0 |
| Competing owners of the octagon's vertical position | 2 | 1 |
| Camera declarations | 6, one with `!important` | 1 |
| `perspective` declarations | 3 | 1 |
| `perspective-origin` declarations | 3 | 1 |
| `rotateX` declarations | 5 | 1 |
| Rules sizing the camera viewport | 4 | 1 |
| Files able to decide floor-layer geometry | 2 | 1 |
| Writers of `--arena-fit` and `--arena-shift-*` | 2 functions, 5 passes | 0 |
| Iterative placement passes per fit | up to 5, accumulating | 0 |
| Camera probes per fit | one 100px probe plus 2 refinements | 0 |
| CSS rules positioning the ladder and the caption | 20 | 0 |
| `ResizeObserver` in the renderer | 6 | 1 |
| Page-level triggers owned by the renderer | 4 | 0 |
| Forced reflows per caption pass | 1 | 0 |
| Layout shifts on load | 1 to 2 | 0 |
| CLS | 0.0255 / 0.0111 | 0 |
| The rank ladder's first painted position | 441px from final | its final position |
| The known initial-render defect | ladder centred, then jumps | not reproducible in six load profiles |

### K2. AN28 — the original startup defect, six load profiles

The defect: the shell appears, the ladder appears in the CENTRE, the octagon is
still absent, the octagon loads, the ladder JUMPS.

Measured on the harness that carries the real arena DOM, the real stylesheets
and the real renderer over HTTP, through an observer that watches the page from
before its first paint. Six profiles at 1280x800:

| Profile | Shell | Octagon | Ladder | Ladder first and stable | Changes | Octagon first and stable | Changes |
|---|---|---|---|---|---|---|---|
| A normal | 471ms | 471ms | 471ms | 935,372,148,220 both | 0 | 305,284,659,454 both | 0 |
| B hard reload, every asset cache-busted | 120ms | 777ms | 777ms | same | 0 | same | 0 |
| C cold, renderer requested last | 67ms | 707ms | 707ms | same | 0 | same | 0 |
| D CPU blocked in 120ms bursts for 1.5s | 605ms | 605ms | 605ms | same | 0 | same | 0 |
| E renderer arrives 900ms late | 91ms | 1256ms | 1256ms | same | 0 | same | 0 |
| F CPU plus late renderer | 206ms | 1299ms | 1299ms | same | 0 | same | 0 |

B, C, E and F are the rows that matter: the shell stands alone for 656ms, 640ms,
1164ms and 1093ms with NEITHER geometry-dependent element shown. A second batch
on the final candidate reproduced every geometry figure, one profile holding the
shell alone for 7.3 seconds.

Against the PASS criteria: temporary centre ladder 0, visible ladder jump 0,
known-wrong geometry displayed 0, geometry-dependent elements visible before
readiness 0 - they appear at the `interactive` transition and not before -
timeout-based hiding 0, arbitrary opacity delay 0. The one remaining
`setTimeout` in the renderer is a 900ms ripple cleanup and gates nothing.

**AN28 is PASS on the harness and NOT VERIFIED on production.** The production
Arena answers 404 to everyone but staff; no browser extension is connected, and
creating a staff session is not something an agent may do - section 20 of the
constitution reserves `is_staff` to the Owner and section 17.10 forbids a
service login under a privileged account. That gate needs the Owner's own
browser, and it is the only item in this closure that does.

### K3. Master Console mirror — classification A, the SAME component

Answered from the code, not from intent:

| Question | Answer |
|---|---|
| Renders the actual Arena octagon | Yes |
| Uses `#arena-render` | Yes, the same `_arena_render_ring.html`, included whole |
| Uses `arena_render.js` | Yes, loaded by `base.html` for both pages |
| Same SVG generation | Yes, the same `drawGrid` from the same payload |
| Independent geometry rules | It had none, and that was the defect |
| Independent camera rules | Five selectors' worth, every one of them inert |
| Depends on removed declarations | Yes, it named `arena_deck_polish.css`, deleted in AN12, as the file it had to out-run |
| Could future Arena changes silently break it | It already had: none of its five flatten selectors exists on the console page, so the mirror had been rendering through the full tilted camera against the Owner's own X02 instruction |

So it is the same component and it reuses the authoritative architecture. The
camera viewport rule reaches both surfaces; the mirror sets two VALUES that the
one camera reads - `--arena-camera-tilt: 0deg` and
`--arena-camera-perspective: none` - and declares no geometry of its own. The
ring cell is the component's page region there exactly as `.arena-floor-stage`
is on the Arena.

Measured in the engine with the console's own stylesheet order: viewport 440px,
fit 0.79308, perspective `none`, tilt `0deg`, and the scene's transform a pure
scale with no rotation in it.

This is not a visual redesign. The console renders what the Owner asked for on
2026-08-05 for the first time, rather than being told so for the first time.

### K4. Dead and superseded — the final pass

| Candidate | Class | Action |
|---|---|---|
| `width`, `margin`, `padding` on the floor layer in the EFFECTS sheet | SUPERSEDED | removed; the layout sheet owns the floor's box |
| `width: min(100%, 960px)`, margin and padding on the bare `.arena-render-container` | DEAD | removed; every instance carries `page--arena`, so it could never apply |
| `height`, `width`, `transform`, `transform-style` at `.arena-floor-stage .arena-render-container` | SUPERSEDED | removed; it beat the viewport's own block and produced a 0x0 camera |
| `perspective`, `perspective-origin`, `transform-style`, all `!important`, at the same selector | SUPERSEDED | removed; duplicate optics |
| `transform: none` on the viewport, twice | SUPERSEDED | removed |
| `transform: none !important` on the floor layer under reduced motion | SUPERSEDED | the floor dropped from the selector list |
| `background-color` on the viewport | DEAD | removed; already beaten by `background: transparent !important` |
| The mirror's five-selector flatten block | DEAD | replaced by two values |
| `REGION_FILL_X`, `COMPOSITION_CX`, `COMPOSITION_CY`, `CAPTION_GAP` | SUPERSEDED | removed |
| `writeCamera`, `octagonCells`, `cellsBox` | DEAD | removed; no caller left |
| `reserveCaptionBand`, `placeFloorCaption` | SUPERSEDED | removed in v2.5.954 |
| The 100px probe and both refinement loops | SUPERSEDED | removed; placement is affine |
| Emulation bots, `hydrateFixtures`, `arena_octant_prototype.js`, `octagon_floor_template.js`, `god_mode.css` | INTENTIONALLY RETAINED | untouched |
| 411 unreferenced static assets, 35 files of staticfiles residue | UNKNOWN / reported | untouched, written up in `ARENA_STATIC_INVENTORY.md` |

### K5. Lifecycle, listeners and observers

| Mechanism | arena_render.js | arena_page_layout.js |
|---|---|---|
| `resize` listeners | 0 | 1 |
| `ResizeObserver` | 1, on the region | 1, on the header, border-box |
| `MutationObserver` | 0 | 0 |
| `fonts.ready` | 0 | 1 |
| `DOMContentLoaded` | 1 | 0 |
| `setTimeout` | 1, a 900ms ripple cleanup | 1, the single late pass |
| `setInterval` | 5 - poll, ping and the runway; data, not layout | 0 |
| `init()` | one definition, one registration | — |
| `fitScene` call sites | 5, all on the one subscription path | — |
| `placeOctagon` / `placeRankSpine` | one definition and one call each | — |

Two defects were found by this audit and by nothing else:

1. **A ResizeObserver that could no longer fire.** It observed
   `svg.parentElement`, which used to be the camera viewport stretched over the
   page region, so watching it WAS watching the region. With an intrinsic 440px
   viewport its box is a constant. It watches the region now. A trigger that
   cannot fire is worse than one that is missing: it reads as covered.
2. **The runway countdown appended into the camera viewport**, where the
   octagon's placement scale would have shrunk and moved it. It belongs to the
   region, which is the box it was always positioned against.

`ArenaPageLayout.watch()` is idempotent, so a re-initialisation cannot double a
trigger, and the renderer registers exactly one observer and no page-level
trigger at all.

### K6. The ownership guard

The old guard checked that a declaration is not overwritten by an identical
selector later in the SAME file. Every defect above walked past it. The new one
guards the invariants that actually broke this project: two sheets and no more;
no superseded sheet on disk or linked anywhere; no stylesheet link in a body or
a partial; the effects sheet owning no arena layout geometry; each camera
quantity declared once; one rule sizing and transforming the viewport; no
geometry `!important` on the camera path; no parallel camera in any other
stylesheet; the mirror changing values rather than declaring a camera; no
JavaScript writing a camera variable; and nothing left of the replaced systems.

Both guard classes scan CODE and not comments. That correction was itself made
twice during this pass, when the guard read a comment explaining what had been
removed as the thing itself.

### K7. Known visual debt — NOT fixed here, by instruction

The octagon's containment and composition at large desktop sizes, which the
Owner sees on his own viewport, is recorded as VD1 in
`docs/chef_battle/ARENA_VISUAL_DEBT.md` and on the board. It is deliberately
untouched by this closure and belongs to the later Arena visual/layout cleanup.
AN28's cold-cache and throttling gate against the production page is VD2.

## L. Performance acceptance — the real production measurement, 2026-08-09

Sections D2 and K1 compared harness numbers at 1280x800 against a baseline
taken on **production at 1440x900**. Those are not the same conditions and the
comparison was not valid. This section replaces it.

### L1. How the production measurement became possible

The blocker I reported twice — "the Arena answers 404 to everyone but staff, so
no after-measurement can be taken" — was wrong. The project has its own
token-gated, read-only preview route, `chef_battle:arena_preview_current`, which
renders the real `arena.html` from real data through `_arena_page_context`,
records no presence, creates no profile, and does not widen Arena access. It is
the intended way to look at the production Arena without an account, and it had
been in the codebase the whole time.

Conditions matched to the baseline: production host, 1440x900, warm cache, the
baseline's own buffered `PerformanceObserver` plus navigation and paint timings.
Three reloads; the median is reported.

### L2. Before and after

BEFORE: `ARENA_NORMALISATION_BASELINE.md` sections 3-4, commit `a1f40923`,
production **v2.5.910**.
AFTER: production **v2.5.960**, commit `23b9043e`.

| Metric | Before | After | Change |
|---|---|---|---|
| domInteractive | 564 ms | 304 ms (237-349) | **-46.1%** |
| DOMContentLoaded | 1131 ms | 639 ms (627-669) | **-43.5%** |
| load | 1483 ms | 704 ms (685-723) | **-52.5%** |
| CLS | 0.0255 | 0 | **-100%** |
| Layout shifts on load | 1 | 0 | **-100%** |
| Time-to-stable (the shift settling) | 943 ms | no shift occurs | metric gone |
| Rank-ladder displacement | 441 px right, 102 px down | 0 px | **-100%** |
| Arena stylesheets loaded | 7 | 2 | **-71.4%** |
| Stylesheets on the page | 16 | 13 | -18.8% |
| Nodes inside `#arena-render` | 1931 | 1931 | 0.0% |
| DOM nodes | 2524 | 2656 | **+5.2%** worse |
| Total requests | 138 | 150 | **+8.7%** worse |
| JS requests | 15 | 19 | **+26.7%** worse |
| Document transfer | 85 495 B | 105 091 B | **+22.9%** worse |
| First paint | 960 ms | no after-value | — |
| First contentful paint | 960 ms | no after-value | — |
| LCP, style recalculation, layout time, JS execution time, memory, frame drops | never captured | — | — |

### L3. Verdict, and what it rests on

The baseline set its own acceptance in writing: *"CLS must reach 0 and the
441 px shift must disappear from the trace."* Both are met on production. Every
load timing improved between 44% and 53%.

**PASS**, with four named regressions. The JS request count is explained -
`arena_page_layout.js` was added when page-level layout was taken off the
renderer. The 22.9% larger document is not explained by anything in this phase
and no work here was aimed at it; it is recorded rather than rationalised.

### L4. Limits, stated rather than left to be discovered

- **First paint and FCP have no after-value.** The measuring browser does not
  composite, so Chrome records no paint entry at all. These are the only two
  baseline rows still open.
- **The page measured is the preview route**, not `/chef-battle/arena/` itself:
  the same template, the same context builder, the same production assets and
  host, but anonymous - its pollers 404, which suppresses a few requests a staff
  load would make.
- **The bottom block was never captured in the baseline**, so no percentage can
  exist for it. After-only figures observed in passing: 5-7 long tasks totalling
  738-898 ms, ~2 MB JS heap.
- **Total requests is time-sensitive** - the arena polls - so it is counted at
  the load event rather than whenever the reading was taken.
