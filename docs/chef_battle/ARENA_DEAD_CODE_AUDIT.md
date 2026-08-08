# Arena dead-code audit — AN18, master task section 12

**2026-08-08, at v2.5.944.** Twenty-four arena assets examined: fifteen
JavaScript modules and nine stylesheets. **Nothing is classified DEAD, and
nothing was deleted under this card.**

The method is the one section 12 asks for and section 27 spells out: for every
asset, collect who names it — templates, Python, other static files, tests —
and who uses the symbols it exports, then classify from that evidence. A single
`grep` decides nothing here. Two of these files are called by nobody and are
still not dead, and no search could have told you that; their own first
paragraph could.

---

## The eight categories, and what fell into each

| Category | Assets |
|---|---|
| **ACTIVE** | `arena.css`, `arena_atmosphere.css`, `arena_render.js`, `arena_page_layout.js`, `arena_octagon.js`, `arena_geometry.js`, `arena_deck.js`, `arena_battle_room.js`, `arena_lamp_console.js`, `arena_master_console.js/.css`, `arena_master_console_plan.js/.css`, `arena_console_mirror.css`, `chef_battle.css`, `battle_vfx.js/.css`, `battle_cursor.js/.css`, `battle_widget.js`, `sponsors_puzzle.js` |
| **DUPLICATED** | none. Five stylesheets were merged away in AN4 and AN12; what is left is two files with no shared selector/property pair. |
| **SUPERSEDED** | none still loaded. |
| **FEATURE-FLAGGED** | the emulation bots behind `ARENA_SHOW_EMULATION_BOTS`; `live_arena.css` behind the Live Arena preview |
| **TEST-EMULATION** | `hydrateFixtures()` inside `arena_render.js` — disconnected in v2.5.782 and held by three tests, one written for the sole purpose of stopping a tidy-up |
| **LEGACY BUT REQUIRED** | `octagon_floor_template.js`, `arena_octant_prototype.js` |
| **DEAD** | **none** |
| **UNKNOWN** | none — every asset resolved to a category with evidence |

---

## The two nobody calls, and why they stay

**`arena_octant_prototype.js`** (4.7 KB). No template loads it, no module uses
`ArenaOctantPrototype`, no test names it. On the evidence of callers alone it is
the clearest DEAD candidate in the tree. Its own first line settles it:

> *"Isolated Arena geometry prototype — intentionally not loaded by production."*

It is the geometry sandbox one octant of the ring was worked out in, kept
deliberately outside the load path. That is FEATURE-FLAGGED's cousin, not
DEAD — the same shape as `hydrateFixtures()`, which an earlier pass nearly
removed for the same reason.

**`octagon_floor_template.js`** (5.0 KB). Named only by a comment in
`_arena_render_ring.html` explaining that it is **no longer loaded**, and by a
comment in `arena_octagon.js` recording that the renderer used to read
`OctagonFloorTemplate` live. Disconnected on the Owner's instruction of
2026-07-30 — the arena is to share NO code with the sponsors puzzle, only the
product relationship of sponsors sitting in the VIP ring. Disconnected on his
order is not dead; it is a decision.

---

## What this audit found that is NOT code

**35 files, 3.2 MB, of stylesheets that no longer exist** sit in the server's
`staticfiles/css`: every historical hash of `arena_command_deck.css`,
`arena_hall.css`, `arena_deck_polish.css`, `arena_render.css` and
`arena_effects.css`. `collectstatic` copies and never deletes, and the manifest
references none of them — `curl` still serves them 200.

This is not dead *code*; it is deployment residue, and removing it is a
deletion on production outside this card. It belongs to **AN22** (section 15,
the static asset inventory) and is recorded there rather than acted on here.

---

## What was NOT done, and why

No file was deleted. Section 12 permits deletion only with proof, and the two
files that could have been argued for both turned out to be deliberate. The
value of this card is the classification and the evidence behind it: the next
agent who meets `arena_octant_prototype.js` in a cleanup pass will find the
answer here instead of rediscovering it, or worse, not rediscovering it.
