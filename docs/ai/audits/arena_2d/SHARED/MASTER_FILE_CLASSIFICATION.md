# Master File Classification

| File/group | Classification | Future action |
|---|---|---|
| `models.py`, `services.py` | REUSE_AS_IS | DO_NOT_TOUCH |
| `selectors.py` | REUSE_AS_IS / geometry THREE_D_PRESENTATION_ONLY | Preserve data; isolate geometry later |
| `views.py` | KEEP_BACKEND_REPLACE_FRONTEND | Preserve contracts; approved context fix only |
| `urls.py`, `access.py`, `forms.py` | REUSE_AS_IS | KEEP_UNCHANGED |
| snapshot/reaction services | REUSE_AS_IS | KEEP_AND_REUSE |
| `arena.html` | KEEP_BACKEND_REPLACE_FRONTEND | Replace presentation after approval |
| `_arena_render_ring.html` | REUSE_WITH_SMALL_ADAPTATION | DO_NOT_TOUCH until AMC decoupled |
| `arena_battle_room.js` | REUSE_WITH_SMALL_ADAPTATION | Extract with focus tests |
| `arena_deck.js` | REUSE_WITH_SMALL_ADAPTATION | Rebind to 2D selectors |
| geometry/projector renderer code | THREE_D_PRESENTATION_ONLY | ISOLATE_AS_LEGACY |
| renderer interaction code | REUSE_WITH_SMALL_ADAPTATION | Extract contracts |
| Six Arena CSS layers | DUPLICATE_CANDIDATE / CONFLICT | Consolidate in approved rebuild |
| Active hall/floor assets | THREE_D_PRESENTATION_ONLY | Legacy scene |
| Hall v1/v2 assets | DEAD_CODE_CANDIDATE | REVIEW_FOR_REMOVAL later |
| Octant prototype | THREE_D_PRESENTATION_ONLY | Historical/manual caller |
| `tests.py` | REUSE_AS_IS / two CONFLICT items | Preserve; authorised updates only |

`CONFIRMED_DEAD_CODE`: none.
