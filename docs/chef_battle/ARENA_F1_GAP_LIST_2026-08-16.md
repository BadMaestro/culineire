# F1 — Arena frontend gap list vs the design template

Reference: `ops/reference/design_arena/Chef Battles Arena v2.dc.html`. Compared
by grep against the live renderer (`static/js/arena_render.js`), the arena CSS
(`static/css/arena.css`) and `templates/chef_battle/arena.html` — not by eye.
Owner-approved plan: F1 (this list) → F2 (static relocation choreography) →
F4 (battle page becomes the antechamber). F3 (animating the relocation) and
T22 were explicitly not taken today.

Frozen and out of scope for any card below: the octagon geometry (11 rings,
not the template's 6), the camera (`rotateX(42deg)`, not the template's 57deg),
and every colour already shipped from the mockup. These are the Owner's own
decisions, not gaps.

## Already present and matching

Verified in code, not assumed: the four pulse metrics (active viewers, public
votes, battle gifts, crown streak), the crown ladder with its "View Full
Ladder" link, Recent Battle Gifts with "Send a Gift", the 7-step phase rail,
chef country + flag on the fighter card, the rank tier key, the lantern ring.
The header, the authoritative clock and "Welcome back" panel exist too, in a
deliberately different form from the template — `arena.html`'s own comments
record why the clock reads a real deadline instead of a refresh countdown.
None of this is a gap.

## Missing — ambient atmosphere, not function

The hall has the same panels and the same data as the template. What it does
not have is any sense of the room being alive. Six items, each checked as an
absence in the renderer/CSS rather than assumed from a screenshot:

| # | Item | Template source | Our state |
|---|---|---|---|
| G1 | Three swaying light shafts from above | `shaftSway` keyframe, `.shafts` in `renderVals()` | Absent — zero hits for "shaft" in `arena_render.js` or `arena.css` |
| G2 | Floating dust motes | `moteFloat` keyframe, 34 particles | Effectively absent — one incidental hit, no motion |
| G3 | Gift emojis rising from the crowd | `giftRise` keyframe, 6 emitters | Absent — zero hits |
| G4 | A running ticker of crowd messages | `tickerRun` keyframe, continuous marquee | Ours is three static spans (`arena-activity-ticker`); it does not scroll |
| G5 | Crown-holder badge pulse | `crownPulse` keyframe | Absent — zero hits |
| G6 | Blinking "Live Now" dot | `liveDot` keyframe | Absent — zero hits |

Each is small, CSS/JS-only, additive to the existing DOM rather than a
restructure, and does not touch the frozen geometry or camera. `prefers-reduced-motion`
must disable all six, same as the template's own
`@media (prefers-reduced-motion: reduce)` rule.

## Not gaps — frozen by earlier Owner decisions

- Octagon ring count (11 vs the template's 6) — 2026-07-29 ruling.
- Camera angle (`rotateX(42deg)` vs the template's 57deg) — frozen 2026-08-09.
- Colour palette — already shipped from the mockup, cited separately from this
  template per `ops/reference/design_arena/README.md`.
