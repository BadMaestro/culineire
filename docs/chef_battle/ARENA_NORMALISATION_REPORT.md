# Arena normalisation — engineering report

**2026-08-08.** Production went from **v2.5.910** to **v2.5.940** across eleven
architectural stages, each deployed whole and verified on the live site before
the next began. Stages 1-8 closed AN1-AN11, AN14, AN17, AN19 and AN23-AN25;
stages 9, 10 and 11 closed **AN13**, **AN12** and **AN15**. The BEFORE numbers all come from
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
| Lines in them | 8534 | **7508** |
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
| Tests | 1750 | **1759** |
| Failures | 2 | **0** |
| Duration | 710.7 s | 887.8 s |

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
| 1 | One system owns page-level layout? | **Partly.** The renderer owns the ladder, the caption and the scene. The panels are still laid out by CSS, which is correct, but there is no single page-level authority object. |
| 2 | One system owns octagon geometry? | **Yes.** `ArenaOctagon` + `arena_render.js`. |
| 3 | Ladder position explainable from one source? | **Yes.** `placeRankSpine()`. |
| 4 | Exactly two Arena CSS files? | **Yes.** `arena.css` (shell + renderer) and `arena_atmosphere.css` (effects + hall), AN12. The Owner's ruling of 2026-08-08 is what decides WHERE the split falls — the console loads `arena.css` alone, flat — not whether there are two. |
| 5 | All Arena styles loaded from predictable places? | **Yes.** All four in `<head>`, in both including pages. |
| 6 | Body stylesheet link removed? | **Yes.** Zero links outside `<head>`. |
| 7 | Can an old stylesheet still override the new layout? | **No old stylesheet remains** — five are deleted. Within `arena.css` nothing overrides itself any more: AN13 removed the 584 declarations a later rule with the same selector already beat. |
| 8 | Competing CSS and JS positions? | **No**, for the ladder and the caption. |
| 9 | Timing hacks for initial rendering? | **No.** State only. |
| 10 | Does a cold load ever show a wrong composition? | **No** at the four viewports measured, CLS 0. |
| 11 | Resize == fresh load? | **Yes**, to the pixel at 1280, within 1 px at 1920. |
| 12 | Remaining `!important` justified? | **Yes** — 58, each measured. |
| 13 | `z-index` from a documented layer system? | **Yes.** 21 tokens, 0 raw numbers. |
| 14 | Duplicate implementations removed? | **Partly.** Three stylesheets merged; no duplicate JS implementation was found to remove. |
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
