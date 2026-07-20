# CLAUDE_B Peer Review

Reviewed without merge:

- CODEX initial report commit `99624798` on `audit/arena-2d-codex`.
- CLAUDE_A initial report commit `37f50ae6` on `audit/arena-2d-claude-a`.
- Common source base `726e338076462982185e3caa7564cc37977a18c9` for direct verification.

## Confirmed partner findings

| Finding | Partner evidence | Independent/cross-lane evidence | Conclusion |
|---|---|---|---|
| The future 2D presentation must preserve the public Arena URL, guard and server payload rather than recreate domain rules. | CODEX `FEATURE_MAP`: Arena entry/access; `EVIDENCE`: `_build_arena_payload`; CLAUDE_A FE-01/FE-02. | Base `chef_battle/urls.py:12-17`, `access.py:11-92`, `views.py:976-1190`. CLAUDE_B focused access/payload tests passed 15/15. | Confirmed `KEEP_BACKEND_REPLACE_FRONTEND` at the page boundary and `REUSE_AS_IS` for server enforcement. |
| Challenge, submission/reveal, moderation, voting, scoring, crown, gift and viewer rules already exist and remain server-owned. | CODEX feature/evidence maps provide model/service/view/test sources; CLAUDE_A marks the matching UI actions as delegation points. | Arena popup/deck/render modules call existing endpoints and render payload state; no competing Arena-local business authority was found. | Confirmed `REUSE_AS_IS`; future JS may present errors/state but must not become authoritative. |
| Procedural geometry is isolated presentation data, while rank/profile facts are reusable. | CODEX `EVIDENCE`: `get_arena_geometry` probable 3D-only; CLAUDE_A FE-04 through FE-06 confirmed procedural/perspective boundary. | `_arena_render_ring.html:83-88` loads geometry/render modules; renderer CSS/JS explicitly describes projection, convergence, backdrop calibration and billboard faces. | Confirmed `THREE_D_PRESENTATION_ONLY` for geometry/projection, not for rank/profile data. |
| Wholesale renderer removal would regress the Arena Master Console. | CODEX EVIDENCE/RISKS; CLAUDE_A shared-partial trace. | `arena.html:120` and `arena_master_console.html:89` both include `_arena_render_ring.html`; `views.py:2733-2734` documents the full payload dependency. | Confirmed high regression risk; provide a console-safe replacement or retain legacy partial until decoupled. |
| Six active Arena CSS owners create cascade and duplicate risk. | CLAUDE_A FE-10/RISKS; CODEX accepts frontend lane boundary. | `arena.html:9-15` fixes load order; comments in `arena_command_deck.css:89-93`, `arena_deck_polish.css:2-4`, and `arena_hall.css:81-84` explicitly discuss overlapping ownership. | Confirmed `DUPLICATE_CANDIDATE`, not deletion-safe duplication. |
| Current Arena visuals conflict with the official token-only/no-independent-dark-theme direction. | CLAUDE_A FE-10 and risk register. | CLAUDE_B scan found extensive raw colour use across all active layers; `feedback_colour_scheme_is_law.md` requires base tokens and Playfair Display/Inter. | Confirmed `CONFLICT`; future 2D styling must use the official system. |
| Battle-room behavior is a reusable integration seam but needs accessibility adaptation. | CLAUDE_A FE-08/FE-17; CODEX preserves canonical action routes/context. | `arena_battle_room.js:48-197` is separately loaded and delegates popup/chat/action work; Escape exists, but focus trap/return was not evident. | Confirmed `REUSE_WITH_SMALL_ADAPTATION`. |
| No file is proven confirmed dead. | Both handoffs have empty `confirmed_dead_code`. | Old assets/prototypes lack production callers but retain documentation/history or incomplete runtime/deployment evidence. | Confirmed: cleanup remains unsafe. |

## Disputed findings

| Topic | Position | Counter-evidence | Safest classification |
|---|---|---|---|
| `arena_octant_prototype.js` dead-code status | CLAUDE_A labels it `DEAD_CODE_CANDIDATE`; CLAUDE_B initial inventory treated the pair as documentation-active legacy. | `docs/chef_battle/prototypes/arena_octant_prototype.html:11` directly loads the script. It is not production-loaded, but a documented/manual caller exists. | `THREE_D_PRESENTATION_ONLY` / `ISOLATE_AS_LEGACY`, not a dead-code candidate unless the documentation prototype is formally retired and the full evidence standard is met. |
| Live Arena snapshot/preview classification | CODEX calls the snapshot a valid separate contract reusable with small adaptation; CLAUDE_A calls the privileged preview presentation 3D-only. | These statements address different layers: `arena_snapshot.py` and the guarded endpoint are a broadcast data contract, while `_live_arena_svg.html`/`live_arena.css` are the abandoned visualization. | Backend snapshot: `REUSE_WITH_SMALL_ADAPTATION`; current preview UI: `THREE_D_PRESENTATION_ONLY`. Do not consolidate public and broadcast payloads without permission/data comparison. |
| Battle room future surface | CLAUDE_A raises popup-versus-canonical-room product choice; CODEX says preserve existing room routes/context. | The current popup delegates to canonical endpoints but is not itself the sole business authority. No product decision selects popup retention for 2D. | `UNKNOWN` for final UX; `REUSE_AS_IS` for endpoints and `REUSE_WITH_SMALL_ADAPTATION` for the current popup module. |

## Missing evidence

| Gap | Why it matters | Required follow-up before implementation/cleanup |
|---|---|---|
| Browser runtime at desktop/mobile breakpoints and assistive-technology behavior | Server tests do not validate cascade, SVG hit targets, focus order, focus return, reduced motion or responsive composition. | Run an approved browser matrix against the future implementation baseline; record keyboard and screen-reader behavior. |
| Full backend lifecycle runtime suite | CODEX's runtime attempt was inconclusive; CLAUDE_B executed only 15 focused integration tests. | Run focused challenge/submission/reveal/vote/scoring/gift/security suites in a correctly configured isolated test environment. |
| Runtime/deployment/static request evidence for old hall assets | Static searches cannot prove no dynamic, collected-static or operational use. | Review Git history, collected-static/deployment references and runtime access before removal review. |
| Explicit product choice for popup versus navigation to canonical battle detail | Determines accessibility, duplication and maintenance surface. | User decision after shared audit; do not infer it from current cinematic UI. |
| Exact compatibility plan for the operator console renderer | Public 2D replacement can otherwise blank or distort the console. | Define and test a temporary console-safe renderer boundary before retiring shared legacy files. |

## Cross-lane dependencies

| Consumer lane | Provider lane | Contract/evidence needed | Resolution |
|---|---|---|---|
| Frontend/Integration | Backend | Full `Battle.Status` and public phase/unknown-state semantics | CODEX confirms 17-state domain model and server phase mapping; preserve server values/fallbacks. |
| Frontend | Backend | Payload authority for ranks, center, crown, gifts, metrics, deadline and viewer presence | CODEX confirms `_build_arena_payload` and selectors as source of truth. |
| Backend/Integration | Frontend | Exact extraction boundary inside renderer/deck/battle-room modules | CLAUDE_A identifies scalar deck updater and battle-room integration as reusable; geometry/fitting/crowd are presentation-only. |
| Integration | Frontend | Accessibility and responsive behavior | Static findings exist, but runtime remains unresolved. |
| Public Arena | Operator console | Shared `_arena_render_ring.html` compatibility | Both lanes confirm direct shared dependency; must be planned before removal. |
| Public Arena | Live broadcast preview | Whether shared facts may be consolidated | CODEX confirms different contracts/audiences; share primitives only after field and permission comparison. |

## Classification conflicts

1. **Top-level ladder/gifts/streak context is a confirmed current defect risk, not an absent backend feature.** CLAUDE_A FE-12 suspected that the template reads `crown_streak`, `crown_ladder`, and `recent_gifts` as top-level variables. Direct base verification confirms `views.py:1095-1107` places them only inside `arena_data`, while `arena.html:58,127,143` reads top-level variables. `arena_deck.js:109-114` repairs them only after client update/init. Classify the backend data as `REUSE_AS_IS`, the initial render binding as `REUSE_WITH_SMALL_ADAPTATION`, and the defect as confirmed. Do not fix during audit.

2. **Prototype-gate tests are stale/weak rather than evidence of an active dual implementation.** CLAUDE_A FE-13 is confirmed: `tests.py:2392-2411` describes legacy-default/proto-opt-in behavior, but `arena.html:120` always includes the unified renderer and `arena()` has no `proto` branch. The first assertion matches the incidental class `arena-puzzle-label`, so it can pass without protecting the described legacy renderer. Classify test intent versus implementation as `CONFLICT`; correction belongs to a later authorized phase.

3. **Challenge expiry and battle events are not missing.** CLAUDE_A marks their Arena-specific presentation as `UNKNOWN`, while CODEX confirms the canonical services/events and tests. Resolve the business capabilities to `REUSE_AS_IS`; whether 2D needs dedicated display remains `UNKNOWN` product/presentation scope.

4. **Crown duration/streak authority exists, but visibility differs.** CODEX confirms domain fields/selectors; CLAUDE_A notes expiry/duration is not clearly visible. Resolve backend as `REUSE_AS_IS`, current presentation as `REUSE_WITH_SMALL_ADAPTATION` if duration is required.

5. **Old hall v1/v2 assets remain only `DEAD_CODE_CANDIDATE`.** All lanes agree static production references were not found, but no lane met the full runtime/deployment/history standard. `CONFIRMED_DEAD_CODE` remains empty.

## Recommended resolution

1. Freeze the existing URL, permission, payload, lifecycle, vote, scoring, crown, gift, artifact, notification and viewer-presence contracts as the future 2D do-not-touch boundary.
2. Treat `arena_geometry.js`, projection/fitting/crowd portions of `arena_render.js`, cinematic hall/floor assets, and perspective/effect CSS as an isolated legacy presentation package.
3. Before replacing that package, separate or reproduce the console-safe renderer contract and retain reusable deck/battle-room behavior behind tests.
4. Build any approved future 2D presentation from native links/buttons/cards, official base colour/font tokens, normal document flow and server-provided state; do not port coordinates or dark-theme tokens.
5. Add contract/browser tests for initial payload binding, stale response handling, popup focus lifecycle, responsive behavior and the operator console dependency before legacy retirement.
6. Record the top-level context mismatch and stale proto-gate assertions as defects for a later authorized implementation phase; do not repair them in this audit.
7. Keep every dead/duplicate claim provisional. No cleanup, deletion or 2D implementation is safe until user approval and the shared synthesis are complete.

No production file was edited or merged during this review.
