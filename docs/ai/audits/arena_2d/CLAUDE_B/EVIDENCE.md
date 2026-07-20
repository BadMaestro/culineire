# CLAUDE_B Evidence

| ID | File and symbol/lines | Reachability | Dependants | Classification | Confidence | Reasoning |
|---|---|---|---|---|---|---|
| E01 | `chef_battle/urls.py:12-17` | Project URL include reaches public Arena endpoints | Templates, poller, popup/reaction UI | REUSE_AS_IS | confirmed | Concrete named URLs exist for page and live interactions. |
| E02 | `chef_battle/access.py:11-92` | Decorators and direct endpoint checks | Public page, ping/state/blast/reaction, console | REUSE_AS_IS | confirmed | Server-side visibility/suspension gates are independent of presentation. |
| E03 | `chef_battle/views.py:976-1061`, `1068-1190` | URL views call shared payload builder | Arena template, state poll, console shared renderer | REUSE_AS_IS | confirmed | One payload assembly is already shared across initial render and polling. |
| E04 | `templates/chef_battle/arena.html:9-15` | Rendered by `arena()` | Browser cascade | DUPLICATE_CANDIDATE | confirmed | Six Arena-related stylesheets load in a fixed order; later files intentionally override earlier selectors. |
| E05 | `arena.html:120`; `_arena_render_ring.html:12-88` | Included in public Arena and console | Geometry/deck/battle-room/render modules | KEEP_BACKEND_REPLACE_FRONTEND | confirmed | Shared partial cleanly identifies the renderer boundary and embeds JSON. |
| E06 | `static/js/arena_render.js:627-1050` | Loaded by renderer partial | Tooltip, challenges, polling, scene fitting | REUSE_WITH_SMALL_ADAPTATION | probable | Interaction code is valuable but currently coupled to SVG polygon geometry. |
| E07 | `static/js/arena_battle_room.js:48-197` | Loaded by renderer partial | Popup, chat polling/submission, blast dismissal | REUSE_AS_IS | confirmed | Module is separately loaded and endpoint-oriented, not geometry-authoritative. |
| E08 | `static/js/arena_deck.js` header and DOM update functions | Loaded before renderer | Phase, metrics, deadline, crown/gifts | DUPLICATE_CANDIDATE | probable | Explicitly ported from legacy renderer; should be consolidated only after contract tests. |
| E09 | `static/css/arena_command_deck.css:89-93`; `arena_hall.css:81-84`; `arena_deck_polish.css:2-4` | All active on Arena page | Same HUD/layout selectors | DUPLICATE_CANDIDATE | confirmed | Source comments explicitly document repeated rule ownership and cascade coordination. |
| E10 | `arena_render.css:342-439`; `arena_render.js` geometry/projector functions | Shared renderer | SVG rings, crowd faces, backdrop placement | THREE_D_PRESENTATION_ONLY | confirmed | Perspective, projection, convergence, billboard faces and backdrop fitting implement the abandoned direction. |
| E11 | Active Arena CSS files | Template stylesheet links | Full Arena presentation | CONFLICT | confirmed | Raw-colour scan: `arena.css` 108, command deck 48, polish 31, effects 19, hall 8, render 8 occurrences; official rule requires existing tokens and no independent dark theme. Some are fallbacks/alpha values, so each future edit needs contextual review. |
| E12 | `arena_command_deck.css:85-86`; `arena_hall.css` | Active cascade | Floor/backdrop | THREE_D_PRESENTATION_ONLY | confirmed | Current hall and floor image geometry are presentation assets, not data/action dependencies. |
| E13 | `hall-bg-v1.webp`, `hall-bg-v2-plan.webp` | No active production filename reference found | None found | DEAD_CODE_CANDIDATE | probable | Static search is insufficient for confirmed dead status; Git/runtime/deployment evidence remains incomplete. |
| E14 | Prototype HTML line 11 and `arena_octant_prototype.js` | Documentation prototype directly references script | Manual prototype only | THREE_D_PRESENTATION_ONLY | confirmed | Not production-loaded, but still deliberately reachable as documentation. |
| E15 | `base.html:62-63,754,1029`; `battle_cursor.js` header | Global feature-flag/static load | Arena and battle CTA classes | REUSE_WITH_SMALL_ADAPTATION | confirmed | Despite a “safe to remove” source comment, current references prove it active. |
| E16 | `chef_battle/tests.py` Arena classes at 5151, 6533, 6582, 6887, 6918 | Django test runner | Access, selectors, payload, spectators, geometry | REUSE_AS_IS | confirmed | Substantial server-side coverage exists; browser visual behaviour remains outside these tests. |
| E17 | `manage.py check` | Audit venv with isolated audit settings/log path | Entire Django configuration | REUSE_AS_IS | confirmed | Result: no issues (0 silenced). |
| E18 | Focused Django tests | `ArenaDarkLaunchTests`, `ArenaPayloadWiringTests`, `ArenaGeometryTests`, `ArenaDataSelectorsTests` | 15 tests | REUSE_AS_IS | confirmed | Result: 15/15 passed in 26.761 seconds; test DB created and destroyed. |

## Static graph summary

`chef_battle:arena` → `arena()` → `_build_arena_payload()` → `arena.html` → `_arena_render_ring.html` → `arena_geometry.js` + `arena_deck.js` + `arena_battle_room.js` + `arena_render.js`. The renderer polls `arena_state`; actions delegate to existing profile, challenge, popup/chat, voting, gift and artifact endpoints.

## Test commands

| Command | Result | Relevant failures | Predates audit | Confidence effect |
|---|---|---|---|---|
| `python manage.py check` (repository venv, audit-only environment variables) | Pass: 0 issues | None | N/A | Configuration confidence increased. |
| `manage.py test chef_battle.tests.ArenaDarkLaunchTests chef_battle.tests.ArenaPayloadWiringTests chef_battle.tests.ArenaGeometryTests chef_battle.tests.ArenaDataSelectorsTests` | Pass: 15/15 | None | N/A | Confirms server integration subset; not visual/browser coverage. |

The first check attempts failed before Django execution because the global interpreter lacked Django, then because required environment/log paths were absent. These were environment bootstrap failures, not application failures; the successful commands used the repository virtual environment and isolated audit settings.
