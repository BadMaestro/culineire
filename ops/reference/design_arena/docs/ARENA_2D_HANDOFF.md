# Arena 2D — build handoff

```yaml
document:
  id: "arena-2d-handoff"
  status: "DRAFT_FOR_OWNER_APPROVAL"
  authority: "subordinate to /AGENTS.md and /docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md"
  prepared_by: "Sinus"
  source_of_truth: "Owner-approved Arena mockups (arena.png + master console render)"
  last_updated: "2026-07-27"
```

This document exists so that two agents building different parts of the Arena
produce one interface. It carries **numbers**, not adjectives. Where it disagrees
with `AGENTS.md` or the product contract, those win.

---

## 0. Read before you touch anything

Contract §12 and Technical Standards §7 already decide the palette direction:
**dark hall, gold accents, light parchment floor, green challenger, red opponent.**

The `CulinEire_colour_font_scheme` PDF is the **site-wide** palette (parchment +
ink + bronze). It is *not* the Arena palette and must not be applied to the
Arena — that mistake was made once and cost a rebuild. The Arena has its own
official named tokens, derived from the approved mockup, defined centrally.

Standards §7: **no raw colour literals in templates.** Every value below is a
token. Define them once, in the Arena stylesheet, and reference the name.

---

## 1. Official Arena tokens

Add these as one block. Names are proposed; the Owner may rename, but they must
be central and named — not scattered.

### Hall

| Token | Value | Use |
|---|---|---|
| `--arena-hall-1` | `#164a33` | centre of the hall glow |
| `--arena-hall-2` | `#0f2a1d` | mid dome |
| `--arena-hall-3` | `#0a1410` | outer dome, page background |
| `--arena-hall-backdrop` | `radial-gradient(ellipse at 50% 42%, var(--arena-hall-1) 0%, var(--arena-hall-2) 45%, var(--arena-hall-3) 78%)` | stage backdrop |

### Floor (parchment, lightest at the centre)

| Token | Value | Ring |
|---|---|---|
| `--arena-floor-outer` | `#9fb0b5` | outermost band — cool blue-grey, **not** parchment |
| `--arena-floor-1` | `#dfd3ba` | ring 1 |
| `--arena-floor-2` | `#e9dfc9` | ring 2 |
| `--arena-floor-3` | `#efe6d4` | ring 3 |
| `--arena-floor-4` | `#f3ece0` | ring 4 |
| `--arena-floor-core` | `#f7f1e4` | centre plate |
| `--arena-floor-seam` | `rgba(10,20,16,0.14)` | tile seams |

### Gold

| Token | Value | Use |
|---|---|---|
| `--arena-gold` | `#d4af5f` | rims, icons, eyebrow labels |
| `--arena-gold-light` | `#f0d68a` | active text, crown glow, borders |
| `--arena-gold-line` | `rgba(240,214,138,0.22)` | panel borders |

### Combatants — these two are contractual, not decorative

| Token | Value | Use |
|---|---|---|
| `--arena-challenger` | `#4ea86f` | **left** chef: ring, name plate, support bar |
| `--arena-challenger-glow` | `rgba(78,168,111,0.55)` | podium glow, left |
| `--arena-opponent` | `#e05a4a` | **right** chef: ring, name plate, support bar |
| `--arena-opponent-glow` | `rgba(224,90,74,0.5)` | podium glow, right |

Challenger is always left/green, opponent always right/red (contract §12).

### Panels and text

| Token | Value |
|---|---|
| `--arena-panel-bg` | `linear-gradient(180deg, rgba(15,42,29,0.88), rgba(10,20,16,0.94))` |
| `--arena-panel-border` | `1px solid var(--arena-gold-line)` |
| `--arena-panel-radius` | `18px` (`--radius-md`) |
| `--arena-panel-shadow` | `0 18px 40px rgba(4,10,7,0.55)` |
| `--arena-panel-blur` | `blur(8px)` |
| `--arena-ink-on-dark` | `#f3ece0` |
| `--arena-ink-muted` | `#9fb0b5` |
| `--arena-live` | `#4ea86f` (live dot, "LIVE" pill) |

Typography stays Playfair Display (display) + Inter (UI). No third face except
Dancing Script for GreenBear, which already exists in `god_mode.css`.

---

## 2. Arena Hall — layer stack

Build in this z-order. Each layer is independent; do not merge them.

```
z 0   backdrop            --arena-hall-backdrop, full stage
z 1   dome vignette       radial gold wash from below, opacity .13
z 2   hall ellipses       2 concentric ellipses, 1px --arena-gold-line at .06/.08
z 3   FLOOR               perspective block — see §3
z 4   crowd               atmospheric figures, tiered — see §4
z 6   rank ladder         8 pills, vertical column, centred, top 13%
z 8   combatants + crown  chef octagons L/R + crown hexagon centre
z 20  corner panels       phase / signals / ladder / gifts
z 20  ticker              bottom centre pill
```

### §3 Floor geometry — copy these numbers

```
wrapper:   width 1020px, height 840px, perspective 1000px,
           left 50%, top 53%, translate(-50%,-50%)
plane:     transform rotateX(58deg); transform-origin 50% 50%
octagon:   clip-path polygon(29% 0%, 71% 0%, 100% 29%, 100% 71%,
                             71% 100%, 29% 100%, 0% 71%, 0% 29%)
```

Six nested octagons, same clip-path, decreasing inset:

| Layer | inset | fill |
|---|---|---|
| gold rim | `0` | `linear-gradient(180deg, var(--arena-gold-light), var(--arena-gold))` + `0 0 70px` gold glow |
| dark bezel | `13px` | `--arena-hall-3` |
| outer band | `19px` | `--arena-floor-outer` |
| ring 3 | `8%` | `--arena-floor-3` |
| ring 4 | `18%` | `--arena-floor-4` |
| ring 5 | `29%` | `--arena-floor-2` |
| core | `39%` | radial `--arena-floor-core` → `--arena-floor-1`, inset gold glow |

Radial tiling on every parchment ring:

```
repeating-conic-gradient(from 0deg at 50% 50%,
  var(--arena-floor-seam) 0deg 0.28deg, transparent 0.28deg 4.5deg)
```

Step the seam angle up (4.5deg → 5.5deg) on inner rings so tiles stay visually
equal in width as the radius shrinks.

### §4 Crowd — atmospheric only

Contract §12 is hard on this: atmospheric figures **must not** impersonate real
users, and the 290 interactive viewer seats are a separate system with real
users only, front rows filled first, logged-in viewer sees themselves.

Atmospheric generation, 4 elliptical tiers around the floor:

| Tier | rx / ry (% of stage) | share of N | figure width | opacity mult |
|---|---|---|---|---|
| 1 | 40.5 / 24.5 | 19% | 9px | 0.55 |
| 2 | 44.5 / 28 | 24% | 10px | 0.72 |
| 3 | 49 / 31.5 | 27% | 11px | 0.88 |
| 4 | 54 / 35.5 | 30% | 13px | 1.00 |

Per figure: angle `a = (i/count)·2π + tier·0.21`; depth `= (sin a + 1)/2`;
scale `= 0.74 + depth·0.4`; opacity `= (0.42 + depth·0.52) · tierMult`;
y compressed to `·0.74` behind the floor. Head = circle, body = 5px-radius
rounded rect at 82% width. N default 200, range 40–420.

### §5 Rank ladder

Eight pills, **vertical column**, centred horizontally, `top: 13%`, `gap: 4px`,
z-index 6 — above the floor, below the combatants. Order, top to bottom:

`KITCHEN PORTER · PREP CHEF · COMMIS CHEF · CHEF DE PARTIE · SOUS CHEF · HEAD CHEF · EXECUTIVE CHEF · CULINARY MASTER`

Pill: `bg rgba(10,20,16,0.8)`, `border 1px var(--arena-gold-line)` at .3 alpha,
text `--arena-gold-light`, 9.5px/700, `letter-spacing .15em`, uppercase, pill
radius, `4px 13px` padding, a `✦` flanking each side.

**Contract §12 requires recorded numeric contrast evidence of ≥ 7:1 for this
column.** `#f0d68a` on `#0a1410cc` measures ≈ 11.4:1 — record the measurement,
do not assume it.

The column ends at ≈ 42% of stage height. The crown hexagon starts at ≈ 45%.
That gap is deliberate; anything that grows the column must shrink the gap
budget first, not overlap.

### §6 Combatants and crown

```
challenger   left: 33%   top: 66%   translate(-50%,-100%)
opponent     left: 67%   top: 66%   translate(-50%,-100%)
crown        left: 50%   top: 60%   translate(-50%,-100%)
```

Chef tile: 118×136, octagon clip
`polygon(50% 0%, 93% 22%, 100% 62%, 50% 100%, 0% 62%, 7% 22%)`,
`2px solid` accent ring, outer glow `0 0 26px` accent-glow. Real photo of the
real participant (contract §12).

**Flags (Owner, 2026-07-27):** flags render now. **Every flag is Irish** until a
country-data source is approved — do not read a country off a profile field and
do not vary the flag per chef. Flag assets are **ArenaFront's** to produce via
the OpenAI image API, against Cursor's written specification, one or two images
for the task in hand and never a speculative batch (AGENTS.md §1). Flag chip:
14×10px, `2px` radius, sits left of the country label in the name plate.

Name plate: pill, overlaps the tile bottom by 10px, accent border, 12px/600
`--arena-ink-on-dark`.

Podium glow: 112×18 ellipse, `radial-gradient(accent-glow → transparent 70%)`.

Support/vote bar appears from phase 5 (Voting) onward: 5px track, accent fill,
percentage in `--arena-gold-light`.

Crown: 132×118 hexagon
`polygon(50% 0%, 93% 25%, 93% 75%, 50% 100%, 7% 75%, 7% 25%)`,
radial `#1c6a4a → #0f2a1d`, `♛` at 26px in gold-light, holder name in Dancing
Script 23px. Breathing glow, 3.4s ease-in-out, disabled under
`prefers-reduced-motion`.

### §7 Phases

Seven, in order, driven by the server — the frontend displays, never infers:

`1 CHALLENGE · 2 COMBAT · 3 BIATHLON · 4 COOKING · 5 MOD REVIEW · 6 VOTING · 7 CROWN`

Stepper pill, active state: `bg rgba(212,175,95,0.24)`, border gold at .55,
number chip filled gold with `--arena-hall-3` text. Inactive: `rgba(10,20,16,0.68)`,
`--arena-ink-muted`. Each phase carries its own caption line and floor line.

**One row, never two.** Both mockups show seven pills on a single line
(≈1050px). Do not clamp the container width — a wrapped second row lands on the
rank ladder. Below 1280px the stepper may scroll horizontally; it may not wrap.

### §8 Corner panels

All four use the panel tokens, `22px` from the viewport edge.

| Panel | Position | Width | Contents |
|---|---|---|---|
| Phase | left, top | 300px | phase name, clock, progress bar, next phase |
| Signals | right, top | auto | active viewers · public votes · battle gifts · crown streak |
| Crown ladder | left, bottom 82px | 262px | top 4 by crowns, "View full ladder" |
| Recent gifts | right, bottom 82px | 268px | last 3 gifts, "Send a gift" |
| Ticker | bottom centre | ≤ min(900px, 62vw) | top supporter · crowd messages · "Join the Crowd" |

---

## 3. Other surfaces (same tokens, different composition)

Both are built in the reference file (§6) and follow the same tokens.

- **Battle Broadcast** — three-column header: challenger block (green, octagon
  96×112, `2px` accent ring) / centre wordmark + `VS` with a green→gold→red rule
  / opponent block (red), mirrored right-aligned. Theme pill under the centre.
  Below: two stream panes, 300px tall, `18px` radius, accent border per side,
  `LIVE` chip top-left in the accent, viewer count top-right, a vertical rail of
  likes / comments / rank on the right edge, and a footer with stacked supporter
  avatars (−8px overlap) plus the accent `Support chef` button. The countdown
  sits centred and overlaps the panes by 14px: hexagon-clipped, Playfair 30px,
  `--arena-gold-light`, tabular numerals. Live chat is a 3-column grid of rows
  (avatar / name + text / timestamp) with a composer strip at the bottom.
- **Result / Winner** — champion photo left, detail column right; gold
  hexagon `CHAMPION` badge, `Congratulations,` in gold above the name in
  Playfair 30px, rank / clan / flag rows, runner-up card in a red-ringed
  octagon. Full-width `WINNER` band across the card bottom: green gradient wash,
  gold `letter-spacing .18em`, gold rule ends. Then a 6-up metrics row (final
  result, likes, comments, viewers, supports, confirmed), a green
  `✓ Battle finished` pill, and the chat grid.
- **Master Console** — already implemented at `/chef-battle/master/`. It is
  **not** the public Arena (contract §4.3). Do not restyle it under an Arena
  ticket; it keeps its own dense operator grid. `_arena_render_ring.html` stays
  until the console is decoupled (contract §13).

---

## 4. Acceptance — every Arena ticket

```yaml
acceptance:
  tokens_only: true            # zero raw hex in the template diff
  palette: "dark hall, gold, parchment floor, green L / red R"
  challenger_left_green: true
  opponent_right_red: true
  flags: "Irish only until a country-data source is approved"
  rank_column_contrast: ">= 7:1, measured and recorded"
  crowd_not_impersonating_users: true
  viewport_classes_checked: [1280, 1920]   # §17.8 — never one width
  below_1280: "out of scope — the Arena stage is designed for >= 1280px"
  keyboard_operable: true
  reduced_motion_respected: true
  states_present: [loading, empty, hidden, unauthorised, error, active]
  no_duplicate_listeners: true
  server_authoritative: true   # no winner/phase inference in the frontend
```

---

## 5. Order templates

§17.5: one action, one acceptance test, fits on a phone screen. Copy, fill, send.

```
ARENA-<n> — <one action>
File: <exact path>
Do: <one sentence>
Numbers: <the values from this doc>
Accept: <one observable check>
Not in scope: everything else. Defects elsewhere → /ops/deferred_fixes.json
```

Suggested split, in dependency order:

1. `ARENA-01` — define the token block. One file. Nothing else changes.
2. `ARENA-02` — backdrop + dome layers.
3. `ARENA-03` — floor geometry (§3). Highest visual value.
4. `ARENA-04` — crowd generator (§4).
5. `ARENA-05` — rank ladder + contrast evidence (§5).
6. `ARENA-06` — combatants + crown (§6).
7. `ARENA-07` — corner panels + ticker (§8).
8. `ARENA-08` — phase wiring to real server state (§7).

01 → 03 → 06 is the shortest path to something the Owner can see change on his
screen. 04 and 07 can run in parallel with 06 if the files are split.

---

## 6. Reference implementation

`Chef Battles Arena v2.dc.html` in this design project renders every number above
in one self-contained HTML file — **Arena, Battles, Chefs, Rankings, Battle
Broadcast and Result** screens, all seven phases clickable, portraits as
drop-in image slots. It is a **visual target**, not code to be pasted:
it is a single-file design component, not Django templates, and it is not
subject to the deploy gate. Port the geometry and the tokens; write the markup
in the project's own template and CSS architecture.
