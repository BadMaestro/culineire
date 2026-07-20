# Current Arena Source of Truth

_Closing record of the Arena 2D Existing-System Audit, 2026-07-20. Read this
first; it points to the detail rather than repeating it._

## Where the detail lives

- Full findings: [`MASTER_EXISTING_SYSTEM_AUDIT.md`](MASTER_EXISTING_SYSTEM_AUDIT.md)
  (base `2a28e4b2`, reconciled from the original audit on `726e3380`).
- What changed between those two bases and why it doesn't invalidate the
  audit: [`DELTA_RECONCILIATION.yml`](DELTA_RECONCILIATION.yml) —
  classification `MINOR_AMENDMENT`.
- Per-lane reports and peer reviews:
  `docs/ai/audits/arena_2d/CODEX/`, `docs/ai/audits/arena_2d/CLAUDE_A/`,
  `docs/ai/audits/arena_2d/CLAUDE_B/` (plus a stray backend-content report at
  `docs/ai/audits/arena_2d/BOLT/`, kept per the owner's instruction, treated
  as supplementary CODEX-lane material, not the CLAUDE_B lane's own report).

## The direction

**2D is the approved direction.** The prior cinematic/pseudo-3D presentation
(procedural ring geometry, perspective camera, photographic hall matching,
generated crowd, cinematic depth effects) is retired. Nothing about that
direction is to be carried into a future rebuild as a requirement —
see `docs/chef_battle/arena_mockup_spec.md`, now tagged
`HISTORICAL_CONCEPT_REFERENCE`.

**The backend is the preservation boundary.** Models, domain transitions
(`services.py`), read-model meanings (`selectors.py`), access guards, URLs,
action views, migrations, and security/integrity tests are not to be altered
by a presentation rebuild. The full `arena_data` contract (metrics, phase,
deadline, server_time, center, crown_ladder, recent_gifts) stays as-is.

## What has and has not happened

- **Implementation has not begun.** No 2D Arena code exists yet. This audit
  and its reconciliation are analysis only; no production code, template,
  CSS, JS, or asset was modified by any lane at any stage.
- The six overlapping Arena stylesheets, the shared renderer partial
  (`_arena_render_ring.html`, also consumed by the Arena Master Console), and
  the procedural/perspective renderer code all still exist untouched in the
  repository, exactly as the audit found them.

## Unresolved owner decisions (nothing below has been decided yet)

1. Battle room: embedded popup, canonical page navigation, or both.
2. Whether the privileged Live Arena preview console stays.
3. The 2D information hierarchy and the responsive/accessibility acceptance
   bar for it.
4. Whether `arena_mockup_spec.md`'s retained concepts (rank-ring layout,
   chef-versus-chef centre stage, Crown Holder) still hold for the 2D design,
   or need their own fresh spec.
5. Whether the old, unreferenced hall-background image versions and the
   octant prototype get a deletion pass later, and on what evidence bar.
6. Whether historical production self-votes block migration `0083` from
   running cleanly (not queried; requires an explicit owner-authorised data
   check before that migration is considered safe everywhere).

## Standing rule

No 2D implementation, cleanup, or deletion may begin without explicit owner
approval, per `AUDIT.txt`'s stop rule. This document does not grant that
approval — it only records that the audit is closed and where its findings
live.
