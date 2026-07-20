# CODEX Peer Review

Reviewed without merge:

- `audit/arena-2d-claude-a` initial report at `37f50ae6f1764f7f76ec161a9acca9fbfb1999e4`
- `audit/arena-2d-claude-b` initial report at `6445263989dd2c1fb69ff759b36d1d46bd90411e`

## Confirmed partner findings

| Finding | Partner evidence | CODEX verification | Resolution |
|---|---|---|---|
| The public Arena always loads the procedural renderer/hall stack | CLAUDE_A FE-01/04; CLAUDE_B E04/05 | `arena.html:9-15,120` directly loads six sheets and `_arena_render_ring.html` | Confirmed `KEEP_BACKEND_REPLACE_FRONTEND` |
| Geometry, projection, crowd, billboard and photographic hall code is presentation-only | CLAUDE_A FE-05/06/09; CLAUDE_B E10/12 | Backend payload exposes isolated `get_arena_geometry`; no business transition depends on coordinates | Confirmed `THREE_D_PRESENTATION_ONLY`, except underlying rank/presence data |
| Phase, deadline, metrics, crown, gifts and identity data are reusable | Both reports | `selectors.py:1070-1200`, `_build_arena_payload` and backend tests establish authoritative values | Confirmed; presentation can change without business-rule changes |
| Popup/chat/vote/gift/challenge actions delegate to existing endpoints | Both reports | Named URLs and guarded views/services exist | Confirmed; server endpoints remain authoritative |
| Six active CSS layers create cascade/duplicate risk and an independent palette conflict | Both reports | Active template links and repository design rules support the finding | Confirmed `DUPLICATE_CANDIDATE`/`CONFLICT`, not permission to consolidate now |
| Renderer removal affects the Arena Master Console | CLAUDE_B risk/E05 | `_arena_render_ring.html` is included at `arena_master_console.html:89`; `views.py:2733-2734` documents the dependency | Confirmed high regression risk |
| Old hall assets are not proven dead | Both reports | Static non-reference cannot satisfy the audit's full dead-code standard | Confirmed `DEAD_CODE_CANDIDATE` only |
| Focused Arena backend tests pass | CLAUDE_B E17/E18 | 15/15 reported with exact classes and isolated test DB; consistent with source inspection | Accepted as partner runtime evidence |

## Disputed findings

| Finding | Position | Evidence | Safest classification |
|---|---|---|---|
| `arena_battle_room.js` is `REUSE_AS_IS` | CLAUDE_B says as-is; CLAUDE_A finds missing focus trap/return and `innerHTML` coupling | The endpoint delegation is reusable, but browser accessibility was not runtime-tested | `REUSE_WITH_SMALL_ADAPTATION` |
| Current responsive behaviour is wholly `THREE_D_PRESENTATION_ONLY` | Partners classify scene breakpoints as legacy | Reduced-motion and ordinary responsive/accessibility principles remain useful even if scene-fitting rules do not | Split: scene geometry `THREE_D_PRESENTATION_ONLY`; reduced-motion/principles `REUSE_AS_IS` |
| `arena_deck.js` is a duplicate candidate | CLAUDE_B points to ported behaviour; CLAUDE_A treats updater semantics reusable | One active module is not duplication by itself; overlap must be symbol-by-symbol proven | `REUSE_WITH_SMALL_ADAPTATION`, with `DUPLICATE_CANDIDATE` limited to proven overlapping functions/selectors |

## Missing evidence

- No browser runtime matrix proves keyboard focus, screen-reader naming, mobile flow, CSS cascade outcome or reduced-motion behaviour.
- No collected-static, deployment, runtime-request or complete Git-history proof exists for deleting old hall assets.
- The alleged initial crown/gifts/streak context mismatch is strongly supported by template/view shape but needs a render assertion or browser/runtime confirmation.
- The stale `?proto=1` test conflict needs an exact current test run; it must not be repaired during the audit.
- CODEX's broad lifecycle test selection did not complete locally; only CLAUDE_B's 15-test integration subset has fresh runtime confirmation.

## Cross-lane dependencies

- The 2D frontend must consume the server phase/deadline/metrics and never infer battle transitions.
- Frontend extraction of battle-room/deck behaviour must preserve CSRF, credentials, endpoint URLs, stale-response handling and server error states.
- Any legacy renderer isolation must provide continued compatibility for the Arena Master Console.
- Accessibility and responsive acceptance tests are required before classifying extracted UI blocks as reuse-as-is.

## Classification conflicts

- Popup module: resolve to `REUSE_WITH_SMALL_ADAPTATION`.
- Phase/deadline updater: data contract `REUSE_AS_IS`; DOM-selector implementation `REUSE_WITH_SMALL_ADAPTATION`.
- Geometry: rank and real-presence data `REUSE_AS_IS`; ring coordinates, projector and generated crowd `THREE_D_PRESENTATION_ONLY`.
- Live Arena/operator preview: active and privileged, therefore not dead; presentation may be legacy but product scope is unresolved.
- Old hall assets and octant prototype: `DEAD_CODE_CANDIDATE`, never `CONFIRMED_DEAD_CODE`.

## Recommended resolution

1. Freeze backend URLs, access guards, payload meanings, lifecycle services and action endpoints.
2. Define the replacement boundary at the public Arena template/renderer presentation layer, not at models/services/selectors.
3. Before removing the shared renderer, split or preserve operator-console compatibility and extract endpoint-oriented battle-room behaviour.
4. Treat all historic cinematic plans as superseded for layout authority while retaining them as evidence.
5. Run an approved future browser/accessibility test matrix and targeted context-contract tests before implementation or cleanup.
6. Keep every dead-code claim below confirmed status until the full evidence standard is met.
