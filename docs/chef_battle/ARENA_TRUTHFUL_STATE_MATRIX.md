# A17 — the arena's truthful visual state matrix

**Measured on production**, not read off the code, between 2026-08-06 and
2026-08-07, at v2.5.848 through v2.5.873. Every row was produced by putting the
arena into that state and looking at the live page through
`/chef-battle/preview/arena/<token>/`.

A17 exists because this arena has repeatedly said one thing in its payload and
shown another. The point of the card is not to describe the design; it is to
record what the screen actually does, so the Owner's acceptance (A19) is given
against something measured.

## The states, and what the arena really shows

| State | Centre | The two chefs | Next Battle board | Verified |
|---|---|---|---|---|
| No battle at all | Crown holder, or empty | In their own rank rings, scattered by slug hash | Empty | v2.5.848 |
| Challenge PENDING | unchanged | Scattered like anyone else; they vanish when offline | Empty — a pending challenge is not a booking | v2.5.844 |
| Challenge ACCEPTED, hours out | Crown, unchanged | **Adjacent cells**, each in his own ring, keyed to the battle id so leaving and returning does not move them | The pill appears, ordered by time remaining | v2.5.844 |
| Both pressed Ready | **Still the crown** | Still in the rings | Start pulled in to 30 minutes (Owner, 2026-08-15, T20 — was 15); the pill climbs the queue | v2.5.844 + v2.5.849, value corrected v2.5.1045 |
| Battle BEGUN | The pair, facing, on the two floor pads | Removed from the rings by the renderer (`isDisplaced`) | The battle leaves the board — it has started | measured 2026-08-06 |
| Battle CANCELLED / VOID | Crown returns | Back in their rings, `in_battle` false | Empty | measured 2026-08-07 |
| Any state, no battle | The two fighter pads are **still drawn**, muted | — | — | v2.5.848 + v2.5.850 |

### Two things the payload and the screen do not agree on

Recorded rather than fixed, because both are deliberate:

1. **A battle that has begun still lists both chefs in `rings`.** The renderer
   removes them client-side through `isDisplaced(chef, center)`. The truth lives
   in two places. It works, and it is the kind of split that has bitten this
   arena before, so it is written down here rather than left to be rediscovered.
2. **`in_battle` is true from ACCEPTANCE, not from the start.** `ACTIVE_STATUSES`
   includes SCHEDULED, so a pair with a battle ten hours away is flagged as
   fighting. Whether an accepted challenge should read as "in battle" is the
   Owner's call, not a defect to patch.

## Desktop gate — A18

Swept on production at four widths on 2026-08-07, after v2.5.858.

| Width | Deck overflow | Horizontal overflow | Clipped text in the deck |
|---|---|---|---|
| 1920 × 1080 | 0 px | 0 px | none |
| 1440 × 900 | 0 px | 0 px | none |
| 1280 × 800 | 0 px | 0 px | the first phase label, by design |
| 375 × 812 | 0 px | 0 px | six labels — **below the 901px freeze** |

**Keyboard.** Thirty tab stops walked with real Tab presses, five of them inside
the deck. Every deck stop matched `:focus-visible` and drew a ring — 3px on the
chef link, 2px on the buttons. No focusable element anywhere on the page matched
`:focus-visible` without a visible ring.

**Names.** Every focusable in the deck has an accessible name. No `<img>` without
an `alt` attribute. No `<svg>` that is neither labelled nor `aria-hidden`. Two
live regions.

### What A18 fixed to get there

The deck ran **twelve pixels past the bottom of the screen at every desktop
width**, and A07 promises the whole arena on one screen. `--arena-header-h` read
134 while the header measured 146. Two separate faults:

- the corrected number from v2.5.861 was never asked for a second time
  (v2.5.856 added window resize, `document.fonts.ready` and a late pass);
- and the ResizeObserver watched the **content** box, while the header grows by
  twelve pixels of **padding** after first paint — identical content box, silent
  observer, about a change of exactly the size that was wrong (v2.5.858,
  `{ box: 'border-box' }`).

The second was found only by looking at the live page after the deploy. Asserting
that the code contained the fix would have passed.

## Not fixed, and why

- **Phase label truncation at 1280.** The rail is seven equal columns and each
  step is clipped so a long label truncates instead of printing over its
  neighbour. Documented behaviour; belongs in the Owner's acceptance.
- **Everything below 901px.** He froze the arena there on 2026-08-03 and mobile
  is a separate scene.
- **The sponsor logo is 8311 × 8333** — sixty-nine megapixels for a mark that
  renders a couple of hundred pixels wide. WebP siblings were added so the media
  guard is green and the page is lighter (2,651,461 → 1,087,482 B, originals
  md5-identical before and after). A **sized** version is the real fix and that
  is a decision about his company's asset.

## The gate this stands on

Full project suite, `--parallel 8`, **with `CHEF_BATTLE_ENABLED` in its default
state** — the state the flag actually ships in, not the state a workstation
`.env` happens to set: **1711 tests, zero failures**, 2026-08-07.
