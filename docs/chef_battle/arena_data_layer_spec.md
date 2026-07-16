# Arena Data Layer Spec (Layer 2 of the procedural arena)

Owner directive 2026-07-16: the arena is rendered procedurally (polar math,
SVG/Canvas, no sprites). This document maps the **existing public read-model**
(`arena()` context / `arena_data` / `POST /chef-battle/arena/state/`) onto the
procedural grid so the data layer never invents structure and the geometry
layer never hardcodes content.

Author: bolt (backend). Geometry layer: `static/js/arena_geometry.js`
(chord-lerp flat-top octagon, accepted 2026-07-16, commit 9686d5c7).

## 1. Single source of structure: `payload["geometry"]`

```
geometry = {
  "sides": 8,
  "rings": [ {"index": 0..12, "kind": "stage"|"rank"|"spectator",
              "key": str, "label": str}, ... 13 items, contiguous ]
}
```

- `index 0` — centre stage. `index 1..8` — chef ranks, **1 = culinary_master
  (innermost) … 8 = kitchen_porter (outermost)**. `index 9..12` — spectator
  rings (`spectator_1..4`).
- The renderer derives ring count, ordering and labelling from this object
  only. Rank labels for the ring legend come from `rings[i].label` — never
  hardcode "Culinary Master" etc. in JS.
- Static per deploy; safe to read once per page load (it does not change
  between polls).

## 2. Content sources per ring kind

| Ring kind | Payload key | Shape | Notes |
|---|---|---|---|
| `rank` (1..8) | `rings` (top-level payload key) | `{rank_value: [chef, ...]}` | Keyed by the **same `key`** as `geometry.rings[i].key`. Only chefs online in the last heartbeat window appear; offline chefs vanish until the next poll. |
| `spectator` (9..12) | `spectators` | `[{name, avatar_url, ...}]` | Flat list; distribute across the 4 spectator rings the same way `buildSpectatorPolarSlots()` already does (fill inner spectator ring first). |
| `stage` (0) | `center` | `{type: "active_battle"\|"facing_pair"\|"crown_holder"\|"open", ...}` | See §3. |

Chef record (unchanged contract, do not rename):
`{name, slug, avatar_url, rank, rank_label, rating, wins, losses, win_streak,
atk, def, in_battle, battle_id, battle_phase, battle_url, is_online}`.

- **Identity:** `slug` is the stable identity for cell diffing between polls.
  Re-render a cell only when its occupant slug or `in_battle` changes.
- **Placement rule:** a chef occupies a cell in the ring whose
  `geometry.rings[i].key == chef.rank`. Cell assignment within the ring must
  be deterministic (e.g. stable ordering by the payload list order) so chefs
  do not jump between cells on every poll.
- **In-battle rule (existing behaviour, keep):** chefs whose `battle_phase`
  is in the centre/facing phases vacate their ring cell (move, not duplicate).

## 3. Centre stage (`center`)

`center.type` decides the stage rendering:

- `active_battle` — two-cell VS layout; fields include both chefs, `battle_id`,
  `battle_url`, `battle_phase`, `status_display`, `theme`.
- `facing_pair` — pre-combat facing cells (SCHEDULED / MENU_LOCKED).
- `crown_holder` — the crown occupant (name/slug/avatar, `crown_until`).
- `open` — honest empty stage; render the empty state, never a fake battle.

## 4. Command deck / HUD (not positioned by geometry)

These ride the same payload and refresh on the same poll; they live in the
deck around the arena, not in ring cells:

- `metrics = {active_viewers, public_votes, battle_gifts}` (ints, 0-safe)
- `phase = {key, label, step 1..7} | null`
- `deadline = {deadline_iso, seconds_remaining, kind, label} | null`
- `server_time` — ISO, always present; reconcile client clock drift against
  it before animating any countdown from `deadline`.
- `crown_streak` (int), `crown_ladder` (list), `recent_gifts` (list),
  `latest_result` (most recent completed battle, for the blast celebration).

## 5. Polling contract

- Initial render: server-rendered context of `arena()`.
- Refresh: `POST /chef-battle/arena/state/` (CSRF token required) on the
  existing ~20s arena cycle. The JSON mirrors the context keys 1:1.
- The poll is side-effect-free except the presence heartbeat; never mutate
  battle state from the renderer.

## 6. Layer boundaries (trio lanes)

- **Geometry (Ember):** `arena_geometry.js` — pure math, no payload access.
- **Data binding (this spec):** maps payload → cells; owns text/avatars/labels
  positioned at the geometric centre each cell exposes.
- **Effects (GreenBear):** CSS/SVG filters only (glow, atmosphere, phase
  transitions); reads phase/state via data attributes the data layer stamps
  on cells (`data-ring`, `data-cell`, occupancy/state attributes) — no
  payload parsing inside the effects layer.
