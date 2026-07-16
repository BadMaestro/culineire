# Chef Battles Arena — Mosaic Rebuild Plan

**Status:** active implementation plan  
**Owner reference:** supplied 2026-07-16  
**Scope:** `/chef-battle/arena/` only. The existing SVG arena, battle popup,
presence heartbeat, state polling, artifact/gift safeguards and public routes
remain the functional source of truth.

## 1. Design intent

The reference is a command view of a living culinary arena, not a static
poster. CulinEire’s version keeps its elegant food-first character: warm
ivory/cappuccino surfaces, deep herb-green structure, muted brown shadows and
golden status accents. It must not introduce a sci-fi/neon palette or fake
players.

The arena is built as responsive layers. Real data continues to populate the
layers; decorative capacity is never presented as a real user count.

## 2. Reference mosaic — measured regions

The source reference is 1674 × 933 px. The following normalized mosaic is the
assembly map; percentages let the same composition scale without hard-coded
screen positions.

| Tile | Bounds (x / y / w / h) | Component | Current contract retained |
|---|---:|---|---|
| A0 | 0 / 0 / 100 / 100 | Cinematic page canvas with quiet depth layers | Existing page, no new route |
| A1 | 1 / 1 / 98 / 7 | Arena command header / navigation band | Site header remains global; arena-specific status moves below it |
| A2 | 30 / 9 / 40 / 6 | Seven-step battle progress rail | Stage is presentational until a live battle supplies state |
| A3 | 73 / 9 / 26 / 6 | Three compact live metrics | Existing `spectator_count`, active battle data; unknown metrics show an em dash |
| A4 | 1 / 10 / 18 / 18 | Current phase card | Active battle state when present; stable empty state otherwise |
| A5 | 18 / 15 / 64 / 77 | Octagonal arena floor, rings and centre | `#arena-puzzle`, `arena_data`, `arena_puzzle.js` |
| A6 | 20 / 15 / 60 / 75 | Audience perimeter around the floor | Existing real spectator payload; generator controls position, not data |
| A7 | 40 / 19 / 20 / 28 | Rank ladder over the top centre | `rank_groups`; labels never replace the SVG rank rings |
| A8 | 31 / 38 / 14 / 22 | Challenger focus card | Active-battle centre data, or quiet “awaiting challenger” state |
| A9 | 55 / 38 / 14 / 22 | Opponent focus card | Active-battle centre data, or quiet “awaiting opponent” state |
| A10 | 43 / 43 / 14 / 16 | Crown / VS centre medallion | Existing centre click opens the battle popup |
| A11 | 1 / 77 / 16 / 19 | Crown ladder panel | Existing rank data only; no invented standings |
| A12 | 84 / 77 / 15 / 19 | Recent gift panel | Existing gift flow retained; empty-safe placeholder until selector exists |
| A13 | 24 / 94 / 58 / 4 | Crowd response ticker / join CTA | Existing battle CTA and click effects |

## 3. Layer order

1. **Canvas:** cream page background, non-interactive warm vignette; no image
   may extend outside its component boundary.
2. **Command deck:** accessible semantic header, phase rail and metrics.
3. **Arena floor:** existing SVG is the single rendering surface for rings,
   chefs, spectators and active centre.
4. **Context panels:** phase, crown ladder and gifts sit beside the SVG on wide
   screens and stack before/after it on narrow screens.
5. **Interaction layer:** tooltip and battle popup retain their existing high
   z-index and keyboard behaviour.
6. **Motion layer:** subtle opacity/gradient breathing only. Respect
   `prefers-reduced-motion`; never use motion to hide state.

## 4. Functional assembly instructions

### 4.1 Preserve existing contracts

- `arena()` keeps constructing `arena_data` and emitting the same JSON script.
- `arena_puzzle.js` remains owner of SVG cells, active-centre choreography,
  `arena/state/` polling, `/arena/ping/`, tooltip and battle popup loading.
- `#arena-puzzle`, `#arena-cells`, `#arena-centre`, `#arena-tooltip`,
  `#arena-battle-popup`, and `ARENA_VIEWER` keep their ids/names.
- Existing `ce-nav__link--battle` and standard button classes retain the site’s
  two established click effects (battle wave + button ripple).

### 4.2 Responsive composition

- **≥ 1200px:** 12-column command grid: phase panel (2), SVG floor (8), metric
  rail/panel (2); lower panels align to the same grid.
- **768–1199px:** phase and metrics share a row; floor spans the full width;
  lower panels become two columns.
- **< 768px:** semantic reading order is phase → stage → floor → CTA → ladder
  → gifts. The SVG remains horizontally complete and uses no tiny fixed side
  panels.

### 4.3 Polar spectator generator

`arena_puzzle.js` already calculates octagonal positions. The rebuild extracts a
small, pure layout helper rather than placing individual spectators in markup:

```text
angle(i, count, offset) = offset + 2π × i / count
radius = ring radius calculated from the current SVG viewport
x = centreX + radius × cos(angle)
y = centreY + radius × sin(angle)
```

The helper receives an array of real spectator records and a ring capacity. It
returns positions plus an empty-cell state. It must never manufacture identities
or counts. When there are fewer records than cells it draws neutral seats; when
there are more, it distributes records across available perimeter rings.

## 5. Frontend generation plan

| Increment | Deliverable | Safety check |
|---|---|---|
| 1 | Command-deck HTML shell and design tokens around the untouched SVG | Existing arena still renders with empty data |
| 2 | CSS grid / responsive panels / warm CulinEire palette | Check desktop + 390px layout; no global selectors |
| 3 | Pure polar-layout module and integration with current SVG renderer | `arena/state/` refresh keeps cells and centre working |
| 4 | Real active-battle cards, phase rail and metrics from selectors | No fabricated metrics; empty state is explicit |
| 5 | Gift/ladders backed by existing selectors; only then optional generated background assets | Legal token/gift wording and popup controls stay intact |
| 6 | Visual QA of interaction states, focus, keyboard and reduced motion | CSS click effects remain on all CTAs |

## 6. Palette and interaction rules

- Surfaces: `#faf6f0`, `#fffdf9`, `#f5eee4`, `#f2eadf`.
- Structure: `#1f2c25`, `#42514a`, `#66746d`.
- Accents: `#8b7355`, `#6e4e2c`, restrained CulinEire gold.
- No pure black hover state; hover brightens the existing surface/border.
- Icons are purposeful kitchen/battle symbols, with text labels retained.
- Buttons have both pre-existing site click systems: standard ripple for local
  actions and battle-wave navigation for `ce-nav__link--battle` CTAs.

## 7. Acceptance checklist

- [ ] All current arena endpoints and popup ids continue to work.
- [ ] No fake battle, chef, gift or audience data is written to production.
- [ ] Real spectator placement is data-driven and polar-coordinate based.
- [ ] All controls remain keyboard reachable with visible focus.
- [ ] Arena is legible at 390px, 768px and 1440px.
- [ ] No shared hero, recipe, article or site-header CSS is changed.
- [ ] `manage.py check`, template smoke check, diff check and production HTTP
      verification pass before each deploy.

