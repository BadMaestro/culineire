# A06 — Production vs Design-Arena measurement matrix

> **SUPERSEDED SOURCE — 2026-08-04.** Every figure below was measured against
> `ops/prototypes/arena_visual_shell/`, which the Owner had REJECTED. The
> provenance is wrong, not necessarily the numbers — and that is worse, because a
> figure from a rejected source may happen to be right and nobody can prove it
> either way. Do not build to anything here until it is re-measured against
> `ops/reference/design_arena/Chef Battles Arena v2.dc.html`. This applies in
> particular to the octagon aspect delta handed to card A07 (2.05 against
> production 1.30), which was one instruction away from being built.

**Card:** A06 (Fresh production/reference measurement matrix). Read-only ticket —
no CSS/JS/template/DB/production change. Owner-assigned to GreenBear 2026-07-29.

- **Reference source:** vendored Design-Arena prototype in the repo,
  `ops/prototypes/arena_visual_shell/index.html` + `prototype.css`, rendered
  exactly as `arena_preview_prototype` serves it (fonts + inline CSS injected).
- **Production source:** authenticated live Arena, `https://culineire.ie/chef-battle/arena/`.
- **Viewports:** 1280×720 and 1920×1080. All numbers are `getBoundingClientRect`
  in CSS px, `x,y = top-left`.

## Structural finding first (drives every delta below)

1. **The reference is a FIXED ~1350 px composition** — the floor, the four
   panels, the two fighter plinths, the crown and the rank zone do **not** scale
   with the viewport; they stay one pixel size and centre. At 1280 the floor
   slightly overflows (x −35 … 1315). **Production SCALES the octagon with the
   viewport** (octagon 623 wide at 1280 → 1001 wide at 1920). Two different
   layout models.

2. **The octagon aspect ratio is wrong — this is the "whole octagon" the Owner
   felt, not one cell.** Reference floor-grid ≈ **2.05** (wide and shallow);
   production octagon ≈ **1.30** (too narrow, too tall / too round) at BOTH
   viewports. Production must become wider and shallower to sit like the
   reference.

3. **There is no fighter composition in production.** The reference places two
   fixed plinths — **green Challenger left, red Opponent right** — flanking the
   crown at mid-floor height, symmetric about centre. Production has no such
   plinths: the live chefs are tiny (~40–70 px) octagon cell-avatars scattered
   at different heights and asymmetric. Only the avatar that happens to land on
   an interactive cell reacts; the rest read as dead "stickers". This is the
   Owner's reported bug, and it is geometric, not per-cell.

## 1280 × 720

| Block | Reference | Production | Delta / note |
|---|---|---|---|
| Octagon / floor | grid **740×363** @ (270,326), aspect 2.04 | octagon **623×476** @ (324,284), aspect 1.31 | −117 w, +113 h; too narrow & tall |
| Fighters | 2 plinths **283×85**: L(281,351) R(716,351), symmetric, mid-height | 3 cells ~**40 px**: (373,417),(613,427),(852,604), asymmetric | no green/red flank; scattered |
| Crown | **115×104** @ (582,341) | **98×74** @ (586,453) | prod smaller, +112 lower |
| Rank spine | rank-zone **184×165** @ (548,181) top-centre | spine present, vertical | position parity pending A07 |
| Phase rail | phase-track **775×32** @ (267,64) top | rail present | — |
| Panel — top-left | **230×123** @ (22,139) edge-pinned | Phase/Cooking **248×225** @ (20,163) | prod +102 taller |
| Panel — bottom-left | **230×183** @ (22,453) | Crown ladder **222×273** @ (16,541) | prod +90 taller |
| Panel — top-right | **230×153** @ (1027,139) | Arena pulse (top-right) | — |
| Panel — bottom-right | **230×220** @ (1027,416) | Battle gifts **222×324** @ (1032,490) | prod +104 taller |
| Metrics | metric-grid **203×88** @ (1041,191) | inside signals panel | compact strip parity pending |
| Ladder | neutral-ladder **203×74** @ (36,505) | inside ladder panel | — |

## 1920 × 1080

| Block | Reference (fixed, centred) | Production (scaled) | Delta / note |
|---|---|---|---|
| Octagon / floor | grid **740×359** @ (590,533), aspect 2.06 | octagon **1001×777** @ (455,370), aspect 1.29 | prod scales up but stays too round |
| Fighters | 2 plinths **284×85**: L(600,534) R(1036,534) | 3 cells 61–71 px scattered: (547,563),(920,578),(1313,863) | same missing composition |
| Crown | **115×104** @ (902,525) | **157×117** @ (876,618) | prod bigger at 1920, lower |
| Panels | fixed 234 w, edge-pinned (x22 / x1664), 123–220 tall | scale/reflow with viewport | different layout model |

## What this means for the queue

- **A07 (Stage framing / full-octagon composition)** owns delta #1 and #2 —
  widen and flatten the octagon to the reference aspect and frame the whole
  floor. Everything else waits on this.
- **A09 (Live challenger/opponent composition)** owns delta #3 — the green-left /
  red-right fighter plinths flanking the crown. The "dead sticker" symptom
  disappears when the fighters become anchored plinths instead of scattered
  cell-avatars.
- Floor **colour** is NOT a delta: the Owner contract freezes the site
  gold/brass palette; the reference's darker gold is not to be copied.

## Method / reproducibility

Reference served locally from the repo prototype on `127.0.0.1:8791`; production
measured live while authenticated. Bounding boxes captured via
`getBoundingClientRect`. No production, CSS, JS, template or database change was
made (read-only ticket honoured).
