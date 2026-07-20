# CLAUDE_A — Evidence (Frontend and Presentation Audit)

## 1. The 3D/perspective boundary — exact functions and rules

This is the section the whole audit hinges on: which existing frontend code exists
*only* to serve the abandoned photographic/perspective direction, versus which code
is the real ring/occupant renderer that survives into any 2D rebuild.

### 1.1 Confirmed retired: camera tilt itself

`static/js/arena_render.js:86` — `var CONVERGENCE = 0;`

Comments at `arena_render.js:64-91` state directly: "We never had perspective. The
scene was a flat octagon tilted by a CSS `perspective`... CONVERGENCE is the single
number that describes it... converges to 0.51. A parent `perspective` did not change
that at any value." — i.e. the code's own comments assert the tilt was already
proven cosmetic and removed. `CONVERGENCE = 0` makes `projector()` return points
untouched (per this agent's own prior-session work, confirmed again this pass).

**Classification: THREE_D_PRESENTATION_ONLY, already fully retired — zero live
effect. Safe to delete the CONVERGENCE branch logic entirely in a 2D rebuild**,
though the surrounding ring/segment math it wraps (`arena_geometry.js`) must stay.
Confidence: confirmed.

### 1.2 Live and load-bearing: backdrop-matching subsystem

Despite the camera being flat, a second subsystem exists to make the flat SVG
floor visually match a *photographic* painted hall image
(`static/images/chef_battle/arena/hall-bg-v3-final.webp`):

- `arena_render.js` — `placeBackdrop()`-equivalent logic (per prior-session memory;
  reconfirmed via `arena_render.css:421-422` consuming `--arena-backdrop-size`/
  `--arena-backdrop-x`/`--arena-backdrop-y`) measures the rendered floor's on-screen
  bbox and sizes/positions the background photo to match it.
- `arena_render.js:939-950` sets those three custom properties and toggles
  `document.body.classList.toggle('has-arena-backdrop', ...)`.
- `arena_render.css:496-513` — `.page--arena.has-arena-backdrop #arena-render
  .arena-crowd-figure`, `[data-ring-kind="spectator"][data-occupancy="empty"]`,
  `[data-ring-kind="spectator"][data-occupancy="spectator"]` — these rules only
  activate when the backdrop photo is present, changing crowd-figure opacity and
  seat fill/stroke so the painted crowd in the photo isn't double-drawn under the
  SVG's own spectator seats.
- `arena_render.js:1005-1017` — `function billboardFaces(svg) { ... }` — a *separate*,
  still-necessary correction that keeps the painted filler crowd's faces
  (`.arena-crowd-figure image`) round despite the octagon ring's non-uniform cell
  aspect ratios. Comment at `arena_render.css:441` confirms: "billboardFaces() in
  arena_render.js is unaffected — it only touches `.arena-crowd-figure` and
  self-corrects."

**Classification: THREE_D_PRESENTATION_ONLY.** This entire subsystem exists for one
purpose: matching a flat render to a *photographic* hall background so the two look
like the same physical place — precisely the "Photographic hall backgrounds" /
"Decorative depth layers" pattern named in `three_d_specific_audit.inspect_for`. It
is currently live and functioning correctly (this agent verified the 8-corner
match and the crowd-billboard fix in the prior session), but it is presentation
infrastructure for a look the owner's current instruction (AUDIT.txt) retires in
favour of "a simpler 2D interface." Confidence: confirmed (code is live, its purpose
is unambiguous from its own comments, and the direction change is stated directly
in the governing task).

**Important distinction for the synthesis stage:** "no camera tilt" (§1.1) and "no
photographic backdrop" (§1.2) are two *different* retirements. The project's own
history retired the tilt in isolation first (`CONVERGENCE=0`) while *keeping* the
photo-matching machinery (§1.2) as the presentation direction through 2026-07-20.
The current AUDIT.txt instruction appears to retire the photographic-hall direction
too — this should be confirmed explicitly with the owner before deleting §1.2's
code, since it was the single largest and most recently-finished piece of visual
work this session (8/8 corner match, billboard fix, v2.5.379).

### 1.3 Real occupant/ring rendering — not 3D-specific, keep

- `arena_geometry.js` (82 ln) — pure ring/segment position math. No camera
  reference of any kind. Confidence: confirmed reusable.
- `arena_deck.js` (358 ln) — HUD panel wiring (phase rail, metrics, deadline,
  crown ladder, gift list). Reads `arena_data` JSON directly; no SVG/camera
  coupling found. Confidence: confirmed reusable.
- `arena_battle_room.js` (208 ln) — popup lifecycle; the one `backdrop` reference
  here (`arena_battle_room.js:194,196`) is the **popup's own modal backdrop
  overlay** (`#arena-popup-backdrop`), unrelated to the arena-floor photographic
  backdrop in §1.2 — a naming coincidence, confirmed by reading both call sites.
  Confidence: confirmed reusable, not a 3D artifact.
- Within `arena_render.js`, the occupant-placement, click/tooltip wiring, and the
  `arena/state`+`arena/ping` polling loop (`arena_render.js:790,1044`) are
  independent of §1.1/§1.2 and should be extracted rather than rewritten.
  Confidence: probable (not exhaustively line-range-mapped this pass, but no
  contradicting evidence found).

## 2. Duplicate/legacy predecessor confirmation

`templates/chef_battle/_arena_render_ring.html:2-4` (Django comment, verbatim):
> "Unified arena fragment — the merge of the legacy ring (`_arena_ring.html`) and
> the procedural prototype (`_arena_proto_ring.html`). Requires the same context
> as the legacy fragment..."

Git evidence: `_arena_ring.html` was deleted at commit `b17508d3` ("v2.5.321 - full
arena merge phase 2 + Issue a Challenge CTA"), the same commit that deleted
`static/js/arena_puzzle.js`. Both file names are referenced only as historical
predecessors in the comment above — **neither exists in the working tree at
`2a28e4b2`**. `_arena_proto_ring.html` is not found anywhere in git log for the
current file's history search performed, but is named in the same merge comment as
a second predecessor.

Corroborating evidence the merge is real and complete, not a stale claim:
`chef_battle/tests.py:2406-2407` —
```
self.assertContains(resp, "arena_render")
self.assertNotContains(resp, "js/arena_puzzle")
```
This test directly asserts the current page does NOT load `arena_puzzle.js`.

**Classification: not a duplicate-candidate.** This is a completed, tested merge.
The only lingering references to `arena_puzzle.js`/`arena_puzzle` are: a stale
comment in `static/js/battle_cursor.js:10`, and two roadmap-detail strings in
`chef_battle/views.py` (l.303-323) that narrate *historical* work already marked
`"status": "done"` — both are inert text, not code paths. Confidence: confirmed.

## 3. Dead-code candidates — evidence against the full checklist

Per `dead_code_evidence_standard`, nothing is promoted past DEAD_CODE_CANDIDATE
without exhausting all 13 checklist items; this audit checked the items feasible
from a static repo pass (Python import/caller, URL, template include, static
import, CSS import, JS dynamic reference, git history) and explicitly leaves
settings/admin/migration/deployment references unresolved.

### 3.1 `static/js/arena_octant_prototype.js` (103 ln)
- No Python import/caller: not searched exhaustively via AST, but no `.py` file
  references its filename (grepped).
- No URL reference: confirmed, `chef_battle/urls.py` has no route serving it.
- No template include under `templates/`: confirmed via Explore agent grep — the
  **only** load site is `docs/chef_battle/prototypes/arena_octant_prototype.html`,
  which lives under `docs/`, not `templates/`, and is not Django-rendered.
- Static import: none (no other JS `import`s or concatenates it).
- Settings/admin/migration/deployment: **not checked this pass.**
- Git history: its own commits ("Bind arena payload fixture to procedural sandbox
  grid", "Derive procedural arena capacity from geometry segments", "Stamp
  procedural arena grid layer data attributes") describe a self-contained
  prototype track, not a compatibility shim for older code.
- Corroborating signal: `recipes/views.py:2926-2943` (a moderation hex-literal
  cleanup tracker, Bolt's lane) explicitly still lists this file as containing "2
  remaining hex" literals — meaning the file is known and tracked, not forgotten,
  but nothing in that tracker treats it as load-bearing production code either.

**Classification: DEAD_CODE_CANDIDATE** (strong evidence, checklist not
exhaustive). Confidence: probable.

### 3.2 `static/images/chef_battle/arena/hall-bg-v1.webp`, `hall-bg-v2-plan.webp`
- No CSS `url(...)` reference found in any arena stylesheet (only
  `hall-bg-v3-final.webp` is referenced, at `arena_render.css:419`).
- No template reference found.
- Fixture/migration/admin reference: **not checked.**

**Classification: DEAD_CODE_CANDIDATE.** Confidence: probable — these are almost
certainly superseded version artifacts sitting next to the live file (`v1`, `v2`,
`v3-final` naming makes the intent self-evident), but per protocol this is not
promoted to CONFIRMED_DEAD_CODE without the remaining checklist items.

## 4. Documentation-vs-code drift confirmed

`docs/chef_battle/arena_rebuild_plan.md` (2026-07-16) states as a hard constraint:
> "`arena_puzzle.js` remains owner of SVG cells, active-centre choreography,
> `arena/state/` polling, `/arena/ping/`, tooltip and battle popup loading."

This is now **false** as written — per §2 above, `arena_puzzle.js` was deleted at
`b17508d3` and its responsibilities were assumed by `arena_render.js` +
`arena_deck.js` + `arena_battle_room.js`. The plan document itself is not being
"silently resolved" here per the `repository_truth_rule` — it is flagged as a
conflict in `BOOTSTRAP.yml` and repeated here as evidence. The *ids* it also names
(`#arena-puzzle`, `#arena-cells`, `#arena-centre`, `#arena-tooltip`,
`#arena-battle-popup`, `ARENA_VIEWER`) were partially preserved: `#arena-tooltip`,
`#arena-battle-popup`, and `ARENA_VIEWER` still exist (confirmed via grep in
`arena_render.js:555,630,635`); `#arena-puzzle`, `#arena-cells`, and `#arena-centre`
were **not found** anywhere in the current templates or JS — the current mount
point is `#arena-render` (`_arena_render_ring.html:14`), and the live-centre element
is `#arena-live-stage` (`arena.html:62`), both different ids than the plan
specified. This is additional evidence the 2026-07-16 plan's specific implementation
names are stale, even though its higher-level data-contract requirements
(`metrics`, `phase`, `deadline`, `center`, `crown_ladder`, `recent_gifts` — all
confirmed present in `arena.html`'s actual template variables) were honoured.

## 5. Design-token duplication (flagged for CLAUDE_B, evidence recorded here since found in this lane)

`static/css/base.css` (l.50-62, per Explore agent) documents a single `--arena-*`
custom-property namespace intended to be shared by `arena_hall.css`,
`arena_render.css`, `arena_master_console*.css`, `arena_command_deck.css`,
`arena_deck_polish.css`, and `chef_battle.css`. However, `chef_battle.css`'s
`.site-battle-widget` block (starting ~l.3852) declares its **own** local
`--arena-s0/-s1/-s2/-text/-muted/-border/-green/-red/-gold/-gold-light` properties
(l.3854-3863) scoped to that selector — a second, independent set of `--arena-*`
names that shadow rather than extend the documented namespace within their scope.
Confidence: confirmed (both blocks read directly this session). Classification:
DUPLICATE_CANDIDATE — not proven unsafe, since CSS custom properties scoped to a
selector are a valid pattern, but it means "the `--arena-*` namespace" is not
actually singular across the codebase as `base.css`'s own comment claims.
