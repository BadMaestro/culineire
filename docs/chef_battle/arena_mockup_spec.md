# Arena mockup — measured specification

> **STATUS: HISTORICAL_CONCEPT_REFERENCE** (set 2026-07-20, per the owner's
> Arena 2D audit closure — see `docs/ai/audits/arena_2d/SHARED/CURRENT_ARENA_SOURCE_OF_TRUTH.md`).
> The owner has since decided the future Arena direction is a simpler 2D
> interface, not the perspective camera measured below. This document is no
> longer implementation acceptance criteria.
>
> **Still valid to read from here:** the original product hierarchy (ranks,
> rows, HUD panel layout intent), the rank-ring concept, the chef-versus-chef
> centre-stage concept, and the Crown Holder concept.
>
> **No longer valid — do not implement from this document:** the 56-degree
> camera perspective (§1), any 3D geometry requirement, photographic hall
> matching, or a generated/procedural crowd requirement. These describe the
> abandoned cinematic direction, retired by the owner and confirmed removed in
> the Arena 2D audit (`docs/ai/audits/arena_2d/SHARED/MASTER_EXISTING_SYSTEM_AUDIT.md`).

Source: the owner's arena mockup, delivered 2026-07-18 (1280 × 720).
Measured 2026-07-19 by GreenBear, off the image itself.

This file exists because there was no such measurement anywhere. Ember's handoff
(`60cbe789`, `feature/arena-proto-grid`) delivered the procedural grid and
nothing about the picture; the arena's look was then built by eye, and three
passes in a row missed. Every number below is taken from the mockup so the next
pass argues with measurements instead of taste.

All values are given twice: raw pixels at 1280 × 720, and normalised to the
frame width (`W`) or to the floor's own outer radius (`R_floor`) so they survive
any canvas size.

---

## 1. Camera — the single biggest gap

**The mockup is drawn in perspective. Our arena renders a strict plan view.**
No amount of colour work closes that; it is the reason the two pictures do not
read as the same place.

The floor's outer octagon measures:

| Axis | Pixels | Normalised |
|------|--------|------------|
| Width (horizontal span) | ~800 px | 0.63 W |
| Height (vertical span) | ~450 px | 0.35 W |

Vertical compression = 450 / 800 = **0.56**.

For a flat plane tilted away from the viewer, the foreshortening factor is
`cos(θ)`, so:

> **θ ≈ 56° from vertical** — i.e. the camera looks down at roughly 34° above
> the floor plane, not straight down.

Implementation note: this is one transform over the whole scene
(`perspective` + `rotateX`), not a change to the geometry contract. The ring and
segment maths from `get_arena_geometry` stays exactly as it is; only the
projection changes. Hit testing survives a CSS 3D transform, but the far rows
become shallow — see §6.

## 2. Proportions — the floor is small, the hall is large

| Element | Pixels | Normalised |
|---------|--------|------------|
| Frame | 1280 × 720 | 1.00 W |
| Floor outer radius (horizontal half-span) | ~400 px | 0.31 W · **1.00 R_floor** |
| Stands outer radius (horizontal half-span) | ~640 px | 0.50 W · **1.60 R_floor** |
| Centre stage (crown octagon) radius | ~52 px | 0.04 W · **0.13 R_floor** |

So the crowd occupies a band **0.6 × the floor radius wide**, wrapping it on all
sides and running off the frame edges. In our current build the stands are a
narrow rim and the floor fills nearly the whole canvas — inverted from this.

Centre of the composition sits at ~(645, 370) px = **(0.50 W, 0.51 H)**: the
arena is centred, not offset.

## 3. Rings and rows

Rank floor (matching `get_arena_geometry`, confirmed by Bolt 2026-07-18):

- ring 1 `culinary_master` innermost → ring 8 `kitchen_porter` outermost
- segments: 8, 8, 16, 16, 24, 24, 32, 32

Stands, as drawn in the mockup: **4–5 visible rows** of faces, deepening away
from the floor, consistent with our 4 spectator rings (9–12, segments
40/48/56/64 = 208 seats).

The mockup's rows are *staggered* — each row offset by roughly half a seat from
the one in front, so faces sit in the gaps rather than in columns. Our rings
already differ in count (40/48/56/64), which produces this naturally; no extra
offset is needed.

## 4. Faces

| Property | Pixels | Normalised |
|----------|--------|------------|
| Face diameter in the stands | ~24 px | **0.06 R_floor** |
| Face diameter, front row | ~28 px | 0.07 R_floor |
| Face diameter, back row | ~20 px | 0.05 R_floor |

Faces are **round portraits, framed on the face** — head and shoulders, eyes
around the upper third. They are not cropped by the seat's polygon.

> Current defect: we scale the avatar to the seat's larger dimension and clip it
> to the cell, so a slice of hair and forehead lands in the seat. The portrait
> should be fitted, centred on the face, and drawn as a circle sitting *in* the
> seat rather than filling it.

Front rows are brighter and more saturated; back rows fall toward the hall's
dark. Roughly a 35% brightness drop from the near row to the far row.

## 5. Palette (sampled from the mockup)

| Role | Hex | Notes |
|------|-----|-------|
| Floor, outer rings | `#e8e0d0` | warm parchment, light |
| Floor, inner rings | `#d9c9a8` | deepens toward the centre |
| Floor seam / mortar | `#b09a72` | visible but not white |
| Spectator band (slate ring) | `#9aa8b4` | the cool grey-blue band between floor and stands |
| Hall / stands base | `#0d1a12` | deep green-black |
| Hall rim (darkest) | `#050d08` | edges of frame |
| Gold accent (rim lights, crown, HUD) | `#d9a441` | |
| Gold bright (spotlight core) | `#f0c46a` | |
| Chef panel, challenger side | `#1d4d33` | green |
| Chef panel, opponent side | `#7a1f24` | red |

The floor stays inside the brand's warm parchment family; the hall is where the
dark lives. This matches the owner's decision of 2026-07-16 and the brand sheet
(`warm parchment + ink + muted bronze`, `--brand #8b7355`).

## 6. Lighting

- A warm spotlight pools over the centre, brightest at the stage and gone by
  roughly **0.55 R_stands**.
- The hall darkens continuously toward the frame edge — a vignette, not a hard
  edge.
- Gold rim lights trace the boundary between the floor and the stands, and again
  at the top of the stands.
- The crown at the centre carries a visible bloom.

## 7. HUD (positions normalised to the frame)

| Panel | Position | Contents in the mockup |
|-------|----------|------------------------|
| Arena title block | top-left, (0.02 W, 0.10 H) | "CHEF BATTLES ARENA", hall name, live state |
| Phase panel | left, under the title | current phase, countdown, next phase |
| Phase rail | top-centre, (0.33–0.69 W, 0.12 H) | 7 steps, CHALLENGE → CROWN, active one lit |
| Live counters | top-right, (0.75–0.99 W, 0.11 H) | viewers, votes, gifts, crown streak |
| Rank ladder | centre-top, (0.47–0.54 W, 0.20–0.44 H) | CULINARY MASTER → KITCHEN PORTER, top-down |
| Crown ladder | bottom-left, (0.02 W, 0.76 H) | today's crown holders |
| Recent gifts | bottom-right, (0.86 W, 0.76 H) | last gifts, "Send a Gift" |
| Supporter ticker | bottom strip, full width, 0.95 H | scrolling messages, "Join the Crowd" |

Note the rank ladder in the mockup reads **top-down from KITCHEN PORTER at the
top to CULINARY MASTER at the bottom**, i.e. the label column is the mirror of
the ring order (ring 1 = Culinary Master is innermost). The labels are a legend,
not a map of the rings — do not "fix" one to match the other without asking.

## 8. Fighters

The two chefs stand in **coloured hexagons flanking the crown**, not in ring
cells: challenger left (green, with country flag), opponent right (red). Each
carries name and country. This matches the existing renderer behaviour of
vacating a chef's ring seat when they take the centre.

---

## Gap list — mockup vs production (v2.5.330)

Ordered by how much each one costs the resemblance:

1. **No perspective.** Plan view vs a 56° tilt. Biggest single difference.
2. **Inverted proportions.** Our floor is ~0.9 of the canvas; it should be ~0.63
   of the width with the stands twice as deep.
3. **Faces cropped, not framed.** Avatars are sliced by the seat polygon instead
   of being fitted round portraits.
4. **No depth falloff across the stands** beyond a flat brightness step.
5. **No gold rim lights** at the floor/stands boundary.
6. **No slate band** between the floor and the stands.
7. **HUD** — most panels exist elsewhere on the page rather than framing the
   arena as they do in the mockup.
