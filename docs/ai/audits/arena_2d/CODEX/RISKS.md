# CODEX Backend Risks

| Risk | Evidence | Impact | Safe treatment |
|---|---|---|---|
| A 2D client may invent a smaller phase model | `Battle.Status` has 17 states; `_ARENA_PHASE_RAIL` maps public semantics | Incorrect actions, hidden pauses/walkovers/disputes | Preserve server status/phase contract and unknown-state fallback |
| Unrevealed or moderated entries may leak | `BattleEntry.is_revealed` and moderation fields are server gates | Fairness/privacy failure | Consume only public payload; never serialize model rows directly in JS |
| Voting rules may be duplicated client-side | DB uniqueness, `clean`, fraud gates and evidence model | Duplicate/self/farm votes or inconsistent error UX | Keep existing POST endpoint authoritative |
| Result/rating/crown logic may be reimplemented for animation | `_score_battle` updates many records and ledgers | Double scoring and corrupt rankings | Frontend renders outcomes only |
| Arena and Live Arena may be incorrectly consolidated | `_build_arena_payload` vs `build_arena_snapshot` have different audiences | Permission/data leak or lost broadcast fields | Share primitives only after contract comparison; retain separate endpoints |
| Wholesale removal of the shared renderer would regress the Arena Master Console | `_arena_render_ring.html` is included by both public Arena and `arena_master_console.html` | Operator UI loses geometry/deck/battle-room integration | Extract or provide a console-safe replacement before retiring the renderer |
| Geometry data may survive as accidental architecture | `get_arena_geometry` exposes rank/spectator rings | New 2D layout constrained by abandoned hall | Isolate geometry as legacy; retain underlying ranks and counts |
| Dark-launch 404 may be mistaken for missing functionality | `is_battle_visible`, `ArenaDarkLaunchTests` | Unauthorized weakening of access | Treat as product gate and preserve |
| Fresh runtime verification is incomplete | Selected test command stalled without output | Some conclusions rely on repository test evidence | Re-run focused tests with working local PostgreSQL before implementation |
| Monolithic `views.py`, `services.py`, `tests.py` increase change blast radius | 175 KB, 148 KB, 337 KB respectively | Accidental unrelated changes during UI rebuild | Future phase should avoid backend edits unless a named contract gap is proven |
| Historical specifications conflict with current direction | Hall/3D documents vs current `AUDIT.txt` | Old plan may be treated as authority | Mark presentation conclusions as superseded, never delete business requirements silently |

No deletion, cleanup, refactor, redesign, or production-code correction is authorised by this audit.
