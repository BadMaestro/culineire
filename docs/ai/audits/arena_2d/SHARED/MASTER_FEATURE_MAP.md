# Master Feature Map

| Feature group | Status | Source of truth | Classification | Confidence | Future action |
|---|---|---|---|---|---|
| Entry/access | Implemented, gated | URLs/access/views | REUSE_AS_IS | confirmed | Preserve |
| Profiles/ranks/placement | Implemented | profile/ranking selectors | REUSE_WITH_PRESENTATION_CHANGE | confirmed | 2D cards/list |
| Challenges | Full lifecycle implemented | forms/views/services | REUSE_AS_IS | confirmed | Link actions |
| Battle room/actions | Implemented | views/services/popup endpoints | REUSE_WITH_SMALL_ADAPTATION | confirmed | Owner chooses UX |
| Phases/timers | Implemented | Battle/status/selectors | REUSE_AS_IS | confirmed | Server state only |
| Submission/reveal/moderation | Implemented | entries/services/gates | REUSE_AS_IS | confirmed | Preserve secrecy |
| Voting/integrity | Implemented | vote model/fraud/view | REUSE_AS_IS | confirmed | Server validation |
| Results/ratings/W-L/crown | Implemented/idempotent | scoring/profile/battle | REUSE_AS_IS | confirmed | Display only |
| Gifts/artifacts/tokens | Implemented | models/services/ledger | REUSE_AS_IS | confirmed | Delegate |
| Events/notifications | Implemented | events/messages/services | REUSE_AS_IS | probable | Preserve |
| Viewer metrics/reactions | Implemented | presence/reactions/selectors | REUSE_WITH_PRESENTATION_CHANGE | confirmed | Drop crowd geometry |
| Empty/auth/restricted states | Implemented | payload/access/template | REUSE_WITH_PRESENTATION_CHANGE | confirmed | Preserve semantics |
| Responsive scene | Perspective-bound | CSS/renderer | THREE_D_PRESENTATION_ONLY | probable | Replace |
| Procedural geometry | Active | selector/JS/SVG/CSS | THREE_D_PRESENTATION_ONLY | confirmed | Legacy after AMC decoupling |
| Broadcast snapshot | Implemented | `arena_snapshot.py` | REUSE_AS_IS | confirmed | Keep distinct |
| Live SVG preview | Active privileged UI | preview assets | THREE_D_PRESENTATION_ONLY | confirmed | Owner decision |
| Future 2D | Not begun by design | N/A | MISSING only as future UI | confirmed | Approval required |
