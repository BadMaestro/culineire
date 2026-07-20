# CLAUDE_B Risk Register

| Risk | Evidence | Impact | Classification | Mitigation for future approved phase |
|---|---|---|---|---|
| CSS cascade has multiple intentional owners for identical Arena selectors | Six ordered sheets in `arena.html:9-15`; comments in command-deck/polish/hall CSS | Small changes can silently lose to later layers and create breakpoint regressions | DUPLICATE_CANDIDATE | Define one 2D entry stylesheet and migrate components only with visual/interaction tests; retain legacy sheets isolated until parity is proven. |
| Renderer mixes reusable interactions with procedural projection | `arena_render.js:627-1050` plus geometry/projector code | Deleting renderer wholesale would lose tooltip, challenge and polling behaviour | CONFLICT | Extract/test interaction contracts before retiring geometry. |
| Independent dark/cinematic palette conflicts with official design direction | Raw colours across active Arena CSS; `feedback_colour_scheme_is_law.md` | Future UI could repeat a known brand violation | CONFLICT | Future 2D work must use base tokens, Playfair Display and Inter; audit raw values contextually rather than blind replacement. |
| Dark-launch access could be weakened during template reconstruction | `access.py`, `ArenaDarkLaunchTests` | Premature public disclosure and security regression | REUSE_AS_IS | Keep URL/view guards unchanged and run access suite. |
| Operator console embeds the same renderer partial | `arena_master_console.html:89` | Removing shared renderer can blank an operational surface | REUSE_WITH_SMALL_ADAPTATION | Decouple console renderer dependency or preserve compatibility before any legacy isolation. |
| Static file candidates may be dynamically/deployment referenced | Old hall assets and prototype files | False-positive deletion | UNKNOWN | No deletion; inspect collected static, deployment, Git history and runtime requests in a later authorised cleanup. |
| Server tests do not validate browser cascade, mobile interaction or accessibility | Focused 15 tests are request/data tests | Visual and keyboard regressions remain possible | UNKNOWN | Add browser matrix only in future approved implementation; CLAUDE_A peer evidence required. |
| Documentation contains superseded active-sounding plans | cinematic rebuild/hall/mobile docs versus current audit order | Agents may resume abandoned implementation | CONFLICT | Mark historical plans superseded in shared synthesis; do not edit them during audit. |
| Source comment labels battle cursor removable although it is active | `battle_cursor.js:20`; `base.html` loads it; templates use target classes | Comment-driven cleanup could break interaction affordance | CONFLICT | Trust reachability evidence; review comment in later cleanup, not code now. |
| Polling/live endpoints are part of the data contract | renderer/deck/battle-room fetch paths | A static-only 2D rebuild could show stale state or break chat/actions | REUSE_AS_IS | Preserve endpoint URLs, credentials, CSRF and stale-response semantics. |

## Production/deployment notes

- No production code, settings, database records, or static assets were modified.
- No deployment or live environment checks were performed.
- Collectstatic/cache ordering is a regression surface because active templates use versioned URLs and layered CSS.
- No file is classified `CONFIRMED_DEAD_CODE`.
