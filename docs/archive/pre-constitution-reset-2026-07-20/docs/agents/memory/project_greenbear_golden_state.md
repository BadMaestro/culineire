---
name: project_greenbear_golden_state
description: "GreenBear mascot — locked golden state for position, roam range, and animation architecture (before sprite replacement)"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

## Golden format — locked as of 2026-07-03

### CSS (`static/css/hero_chef.css`)
- `bottom: -0.8%` — bear sits slightly below hero bottom edge
- `--chef-size: clamp(112px, 8.5vw, 154px)` — responsive size
- `left: 72%` — initial spawn position
- Only shown at `@media (min-width: 1024px)`
- Three sprite rules via `data-pose` + `data-walking`:
  - idle/walk: `hero-chef-walk.webp`, `background-position: 33.333% 0` (neutral frame 2)
  - walking: `--walk-frame` CSS custom property, 4 frames `0 0 / 33.333% / 66.666% / 100%`
  - sharpen trick: `hero-chef-sharpen.webp`, `--trick-frame`
  - egg trick: `hero-chef-egg.webp`, `--trick-frame`

### JS (`static/js/hero_chef.js`)
- Roam range: `randomBetween(62, 88)` — stays between slider dots and right hero edge (~3cm margins)
- Walk frame interval: 250ms (4 frames cycling via `setInterval`)
- Trick frame interval: 220ms (4 frames cycling via `setInterval`)
- Facing direction: `nextX < previousX ? -1 : 1` (sprites face RIGHT naturally)
- `chef.dataset.pose = "walk-a"` reset at start of every `startWalk()` — critical bug fix
- `previousX` starts at 72 (matches initial `left: 72%`)
- `WALK_FRAMES = ["0 0", "33.333% 0", "66.666% 0", "100% 0"]`

### Sprite files (`static/images/mascot/`)
- `hero-chef-walk.webp` — 4-frame horizontal strip, 310×496px per frame (1240×496 total)
- `hero-chef-sharpen.webp` — 4-frame strip, same dimensions
- `hero-chef-egg.webp` — 4-frame strip, same dimensions
- All transparent background (WebP lossless-ish, quality 85)

### Planned replacement
- 18 new images, 4 animation types (to be defined by owner)
- Architecture to be extended from current 3-sprite system
- Logic, positions, and roam range stay identical

**Why:** Owner calibrated position and roam range live on production. Do not change these values when swapping sprites.
