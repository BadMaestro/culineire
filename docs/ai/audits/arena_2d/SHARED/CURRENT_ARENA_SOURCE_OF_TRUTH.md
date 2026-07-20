# Current Arena Source of Truth

Read this first for the Arena/Chef's Battle 2D rebuild. It supersedes any
older summary of the audit that doesn't cite this file.

- **Full audit:** `MASTER_EXISTING_SYSTEM_AUDIT.md` in this folder —
  authoritative base `2a28e4b2`, classification `MINOR_AMENDMENT`.
- **Reconciliation record:** `DELTA_RECONCILIATION.yml` in this folder —
  the exact diff between the original audit base (`726e3380`) and the
  current base (`2a28e4b2`), with every amended conclusion, new risk, and
  contract change.
- **Closure record:** `AUDIT_CLOSURE.yml` in this folder — machine-readable
  status of this closure pass.

## What is decided

- **Direction: proceed with a simple, responsive 2D Arena.** The 3D/
  cinematic mockup direction is cancelled as an implementation target (see
  `docs/chef_battle/arena_mockup_spec.md`, now `HISTORICAL_CONCEPT_REFERENCE`
  — it still holds the rank-ring, chef-vs-chef, and Crown Holder concepts;
  it no longer holds the 56-degree camera, 3D geometry, photographic hall
  matching, generated crowd, or any implementation acceptance criteria).
- **The backend is the preservation boundary.** Domain logic, models,
  services, selectors, URLs, permissions, voting, crown, ranking, gifts,
  notifications, and state transitions are not to be rewritten for the 2D
  frontend — a 2D UI is a new consumer of the same contracts.
- **Implementation has not begun.** No 2D template, CSS, or JS has been
  written. No legacy file has been deleted. Nothing has been deployed under
  this direction.
- **Legacy files are not deleted yet.** Suspected dead/legacy code is
  isolated and classified in the audit, not removed — a separate deletion
  audit happens after the new interface is stable.
- **The shared renderer stays until decoupled.** `_arena_render_ring.html`
  is not removed until the Arena Master Console has a compatible
  replacement or has been decoupled from it.

## Owner decisions still required before implementation

1. Popup, canonical battle-room navigation, or both, for the 2D battle-room
   experience.
2. Whether the privileged Live Arena SVG/CSS preview remains as-is.
3. The 2D information hierarchy and the responsive/accessibility acceptance
   matrix (no browser/a11y test matrix has been run yet).
4. Timing of two confirmed-but-unfixed defects: the initial
   `crown_streak`/`crown_ladder`/`recent_gifts` template-context mismatch,
   and the stale proto-gate test.
5. Whether the old candidate assets (`hall-bg-v1.webp`, `hall-bg-v2-plan.webp`,
   `arena_octant_prototype.js`) get a later deletion-proof audit.

Ready for 2D implementation **planning**. Not ready for 2D **code** — see
`AUDIT_CLOSURE.yml`.
