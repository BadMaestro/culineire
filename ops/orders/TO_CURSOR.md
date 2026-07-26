# ORDERS → CURSOR

Written by Bolt, Production Director. Tracked in git on `main`. Keep this file
open in your window: every order lands here, newest at the top, and the Owner
watches it arrive.

Your lane is the ARENA and nothing else. Site-wide work — privileges, gates,
weight, infrastructure — belongs to Bolt and never to you.

Answer in CoWork to `bolt`, one line, with a hash and a number. "Done" is not a
report. Unpushed work does not exist.

---

## ORDER A2 — G6-FIX: faces belong to seats

**Status: OPEN. Issued 2026-07-26 12:30 Dublin.**

Crowd portraits scatter across the floor octagon while the seat rings stay
empty. This is the defect that makes the stands look abandoned.

Cause, already located — do not re-diagnose:

- `static/js/arena_render.js:372` creates a separate layer,
  `el('g', {'data-arena-layer': 'crowd'})`
- `static/js/arena_render.js:586` `appendCrowdFigure()` reads the seat polygon
  with `getBBox()` and appends the face to that crowd layer instead of to the
  seat itself
- the seats live in the `spectator-oval` layer, built around line 194

A face positioned from a bounding box does not inherit the seat's transform, so
when the camera tilts the seats move and the faces stay behind on the floor.

**Required.** Each portrait becomes a CHILD of the SAME element as its seat and
inherits the identical transform chain. Deterministic assignment is unchanged:
seat N always gets the same face.

**Do not touch** geometry, seat counts, `get_arena_geometry`, any CSS, or the
parchment plate. Each is its own order.

**Acceptance test you must RUN, not assert.** With the camera transform changed,
a seat and its face move together. Record the screen position of one seat and
its face, change the camera, record both again, and show that the seat's delta
equals the face's delta.

**Deliver** a commit on `impl/arena-bolt`. Do not push, do not deploy, do not
bump a version string.

Report: `G6-FIX | commit=<hash> | seat_delta=<dx,dy> | face_delta=<dx,dy> | files=<n>`

---

## QUEUED, in order. Do not start these before A2 lands.

| # | Order | Done when |
|---|-------|-----------|
| A3 | Restore 290 seats — the client draws 208 while the backend serves 290 | 290 drawn, row depth and falloff kept, `get_arena_geometry` untouched |
| A4 | Delete `.arena-floor-stage::before`, the parchment plate | The rule is deleted, not resized |
| A5 | Retarget the crowd to `round/` (96 files, 400 KB), not `tiers/` (288 files, 1,124 KB) | Depth comes from a CSS filter off `rowDepth` |
| A6 | The load budget — **nothing merges before this** | Requests, bytes, time-to-last-face, crowd on versus off, and your recommendation |

---

## Measured state of the Arena, 2026-07-26, production v2.5.596

Read this before arguing about what is wrong. Every number was measured, not
observed:

- the scene overflows its container — container 1244px, scene 1273px, clipped
  left, right and below the fold
- the rank label column renders BELOW the arena on the page; the spec puts it on
  the floor as a legend
- the crown-holder card is drawn three times, overlapping, one copy clipped
- seats are grey dots: no faces, because A2 is not done
- the scene is NOT off-centre. Scene centre 635, container centre 635. Bolt
  claimed otherwise from a screenshot and the measurement refuted him.

## Rules that cost us a day

- Screenshot the WHOLE page, never your own slice. A slice showed success exactly
  where the page showed breakage.
- Never present a local render as evidence. A local harness silently applied 0 of
  35 rules from `arena_atmosphere.css` and produced screenshots of a pale page
  that were reported as real. Production is the only test environment.
- Report a hash and a number.
