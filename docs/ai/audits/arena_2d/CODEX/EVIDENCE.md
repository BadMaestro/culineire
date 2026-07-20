# CODEX Backend Evidence

| Conclusion | File and symbol/line | Reachability | Dependants | Classification | Confidence | Reasoning |
|---|---|---|---|---|---|---|
| Profile/rank/crown state is canonical domain data | `chef_battle/models.py:18-97`, `ChefBattleProfile` | ORM, services, selectors, templates | rankings, Arena, results, profiles | REUSE_AS_IS | confirmed | Persisted indexed fields plus service/test consumers |
| Battle lifecycle is broader than a simple active/completed switch | `models.py:149-245`, `Battle.Status` | all battle services/views | phase rail, timers, actions, AMC | REUSE_AS_IS | confirmed | Includes waiting/walkover/void/paused/disputed states that 2D must represent safely |
| Challenge acceptance creates the real battle | `services.py:154`, `accept_challenge`; `views.py:1334` | `challenge_respond` URL | battle room, Arena, notifications | REUSE_AS_IS | confirmed | Transactional source rather than UI-local state |
| Submission secrecy is server-owned | `models.py:247-318`; `services.py:542,561` | submit/reveal services | battle detail/voting | REUSE_AS_IS | confirmed | Unique participant entry and explicit reveal flag |
| Vote integrity is enforced below presentation | `models.py:321-380`; `views.py:1535-1647` | vote endpoint | results, analytics, audit evidence | REUSE_AS_IS | confirmed | DB uniqueness, self-vote validation and rejected-attempt evidence |
| Result scoring and crown updates have one source | `services.py:605-840` | lifecycle/operator completion | profile stats, events, ledgers, rewards | REUSE_AS_IS | confirmed | Idempotency is explicitly tested; frontend must not calculate winners |
| Public Arena reads real data through a stable composition boundary | `views.py:783,976,1068,1165`; `selectors.py:1070-1200` | Arena page/state endpoints | current template/JS and future 2D | KEEP_BACKEND_REPLACE_FRONTEND | confirmed | Center, metrics, gifts, crown, phase and deadline are server-generated and empty-safe |
| Arena geometry is presentation-coupled but isolated | `selectors.py:1250-1305`, `get_arena_geometry` | `_build_arena_payload` | procedural renderer | THREE_D_PRESENTATION_ONLY | probable | Rank data is reusable; ring/segment geometry should not constrain 2D |
| Public and master access are deliberately separate | `access.py:11-66` | decorators on routes | Arena, Live Arena, AMC | REUSE_AS_IS | confirmed | Dark-launch staff visibility does not grant console authority |
| Gifts are ledger-backed business actions | `services.py:1529-1700`; `models.py:490-686` | gift endpoints | wallet, chests, Arena panels, AMC economy | REUSE_AS_IS | confirmed | Transactions, balance and artifact constraints are server-side |
| Viewer metrics use privacy-preserving heartbeats | `models.py:383-416`; `services.py:3347`; `selectors.py:1116` | ping/state | Arena metrics, AMC | REUSE_AS_IS | confirmed | Distinct hashed viewers within a 180-second window |
| Live Arena snapshot is a separate valid presentation contract | `arena_snapshot.py:65-109`; `views.py:3141` | master snapshot endpoint | live preview JS | REUSE_WITH_SMALL_ADAPTATION | confirmed | It overlaps conceptually with public Arena but serves broadcast data; not duplicate proof |
| The procedural renderer cannot be removed wholesale without affecting the operator console | `templates/chef_battle/arena.html:120`; `templates/chef_battle/arena_master_console.html:89`; `views.py:2733-2734` | both templates include `_arena_render_ring.html` | public Arena and AMC | REUSE_WITH_SMALL_ADAPTATION | confirmed | Direct base-commit references corroborate CLAUDE_B's cross-lane finding; isolate reusable polling/battle-room behaviour before replacing presentation |

## Test execution evidence

| Command | Result | Relevant failures | Predates audit | Confidence effect |
|---|---|---|---|---|
| `python manage.py check` plus migration dry-run and selected backend tests | Infrastructure run did not produce output and was terminated after extended wait | No application failure captured; local PostgreSQL test setup appeared blocked | Unknown | Static and existing-test source evidence remains strong, but this session adds no fresh runtime confirmation |
| Static symbol, URL, caller and test-class searches | Passed | None | N/A | Confirms reachability and extensive existing coverage |
| CLAUDE_B focused run: `ArenaDarkLaunchTests`, `ArenaPayloadWiringTests`, `ArenaGeometryTests`, `ArenaDataSelectorsTests` | Passed 15/15 | None | N/A | Independent lane runtime evidence confirms the shared access/payload/selector subset; it does not cover all backend lifecycle tests |

No write query was run against production or the local application database.
