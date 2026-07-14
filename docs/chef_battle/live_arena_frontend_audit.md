# Live Arena — Phase 0 FRONTEND Presence Audit (GreenBear)

**Scope:** frontend presence only — does a template / CSS / JS surface exist for each
stage, and what renders today on real routes. Backend presence (models / services /
endpoints / transport / permissions) is Bolt's column. Reference-conformance scoring
(against the 1280×720 mock) comes after the shell exists — this pass is PRESENCE.
**Rule followed:** no invented facts; every claim cites a real repo path. Unknowns are
marked. No implementation code changed (Phase 0).

## Current arena surfaces (what actually exists)
| Route | Template | What it is | Relation to reference |
|-------|----------|------------|-----------------------|
| `chef_battle:arena` (`/chef-battle/arena/`) | `templates/chef_battle/arena.html` + `_arena_ring.html` + `static/js/arena_puzzle.js` | A **ring/lobby**: every enrolled chef placed around an SVG ring by rank; centre shows the active battle as a two-cell VS. | NOT the reference. Different concept (overview lobby, not a single-battle broadcast). |
| `chef_battle:arena_battle_popup` | `templates/chef_battle/arena_battle_popup.html` (`.abp`) | Compact **single-battle popup**: LIVE badge, theme, timer, VS (avatars/names/votes/artifacts), gifts, **live chat (poll)**. | Closest existing broadcast surface. Compact popup, not a full 1280×720 shell. |
| `chef_battle:battle_detail` | `templates/chef_battle/battle_detail.html` | Fuller **battle room**: versus, phase panels, voting, **completed/winner state** (`battle.winner`, 🏆 Battle Complete). | Has a winner/complete surface (partial vs the champion ceremony). |

**Transport today = POLLING, no websockets/SSE.** `arena_state` (20s), `arena_ping` (60s),
`battle_chat_poll` (chat), driven from `arena_puzzle.js` and the `.abp__chat-form`
`data-poll-url`. `asgi.py` exists but chat/state are polled.

## Stage-by-stage FRONTEND presence

| # | Stage (key) | frontend_status | Evidence (real paths) | Reference gap |
|---|-------------|-----------------|-----------------------|---------------|
| 1 | state_contract | partial | Templates read `Battle` fields directly (`battle.status`, `.theme`, `time_remaining`) in `arena_battle_popup.html` / `battle_detail.html`. | No single view-model/snapshot the UI binds to; each template hand-picks fields. |
| 2 | realtime_transport | partial | Polling JS: `static/js/arena_puzzle.js` (`arena_state`), `.abp__chat-form[data-poll-url]` → `battle_chat_poll`. | No event-envelope/sequence, no reconnect/stale UI, no "reconnecting" overlay. |
| 3 | permissions | partial | Server-passed flags gate UI: `can_vote`, `has_voted`, `is_participant`, `viewer_token_balance` in `arena_battle_popup.html`. | Pattern exists; new actions (reactions, per-stream) need the same server-gated flags. |
| 4 | page_shell | **absent** | No full-page broadcast shell at 1280×720. `arena.html` is the ring; `.abp` is a popup. | Net-new page (`ChefBattleLiveArenaPage`) behind the feature flag. |
| 5 | matchup_header | partial | `.abp__versus` + `battle_detail.html` versus: avatars, names, votes, artifacts, VS, `battle.theme`. | Missing rank/clan/**country** in the header, portrait cards, green/red edge lighting, gold VS beams/stars, theme strip styling. |
| 6 | dual_live_stage | **absent** | No video element anywhere; only static `display_avatar_url` images. | Biggest gap. Two live video panels + per-stream overlays do not exist. Needs the video-transport decision (WebRTC/HLS vs deterministic fallback art first). |
| 7 | countdown_timer | partial | `.abp__timer` renders server `time_remaining`; `battle_detail.html` phase timers. | Text only. No angular broadcast plate, no client interpolation, no active/paused/critical colour states. |
| 8 | live_chat | partial | `.abp__chat` (messages, `.abp__chat-form` send + poll) → `battle_chat_send`/`battle_chat_poll`. | Single column (ref = 3-col desktop grid), no Top Supporters tab, no moderation states (muted/slow/disabled), no rate-limit feedback. |
| 9 | supporters_support | partial | `.abp__gifts` appreciation-gift forms with token cost → `send_appreciation_gift`. | Support flow exists but no "Support Chef" broadcast CTA, no supporter avatar stack, no supporter count. |
| 10 | reactions | **absent** | Voting exists (`.abp__vote-form`) but that is a vote, not a like/reaction. | Reference 👍 like/reaction counters per stream have no frontend (and likely no distinct backend — verify with Bolt). |
| 11 | viewer_count | partial | Presence tracked (`record_viewer_presence`); `arena.html` shows `spectator_count` on the ring legend. | Not shown as a per-stream 👁 count in a battle broadcast (ref position). |
| 12 | moderation_integration | partial | Moderation console exists; **observer votes** just built (`observer_disputes`, handoff of `get_observer_votes` to Bolt for the console). | No arena-side moderator overlays (stream hidden / chat disabled / moderator notice). |
| 13 | empty_degraded_states | partial | `arena_battle_popup.html` `no_battle` empty state; `battle_detail.html` cancelled/disputed branches. | No reconnecting / paused / technical-interruption / moderator-hidden overlays. |
| 14 | accessibility | unknown→partial | Some `alt` text on avatars; needs a real WCAG pass (focus states, aria-live for timer/connection, icon labels). | Icon-only controls in the ref (like/comment/viewer) will need labels; not yet audited in depth. |
| 15 | cross_device_mobile | unknown | `static/css/arena.css` responsive extent not yet measured against the ref's mobile reflow order. | Ref mandates single-column reading order (title→timer→identity→streams); not verified. |
| 16 | qa_rollout | partial | Feature flag `CHEF_BATTLE_ENABLED` (dark launch) present. | No visual-regression / e2e for a broadcast arena; new page needs its own flag + captures. |

## Frontend reuse matrix (existing / extend / replace / new)
- **Extend:** chat (`.abp__chat` + `battle_chat_*`), support/gifts (`.abp__gifts` + `send_appreciation_gift`), timer text (`time_remaining`), matchup identity (avatars/names/votes), winner/complete (`battle_detail.html`).
- **New:** the broadcast page shell (stage 4), dual live stage (stage 6), reaction counters (stage 10), per-stream viewer badge (stage 11), broadcast timer plate (stage 7 styling), 3-col chat grid + Top Supporters tab (stage 8), degraded-state overlays (stage 13).
- **Replace:** nothing wholesale — reuse the battle engine + existing chat/gift/vote endpoints; the arena is a *view*, per the brief.

## Frontend blockers / questions for the pair (owner + Bolt)
1. **Live video (stage 6)** — there is NO video infrastructure today. Biggest architectural decision: real streaming (WebRTC/HLS/provider) vs deterministic fallback artwork first. Frontend can build the dual-stage shell with fallback art immediately; real playback waits on the transport decision. **Owner/Bolt call.**
2. **Public country field** — the reference shows "Country: Ireland/Italy", but the only country field found is `ChefBattleProfile.country_of_tax_residence` (ISO-2, **tax/DAC7 — private**). Must NOT surface tax residence publicly. Need a separate **public nationality/country** field (backend, Bolt) or omit country until it exists.
3. **Reactions vs votes (stage 10)** — reference likes/reactions are distinct from the existing vote. Confirm with Bolt whether a reaction/like model exists or is net-new.
4. **Transport (stage 2)** — polling works for chat/state today; the ref's event model implies richer real-time. Decide: keep polling (cheapest, already testable) vs add SSE/WebSocket. Frontend is agnostic if a snapshot+poll contract is stable.

## Notes
- Feed my `frontend_status` + `frontend_notes` into Bolt's `LiveArenaStage` tracker once it is live (updates via master console, no deploy).
- Backend column (transport internals, models, endpoints, permissions server-side) is Bolt's audit — this doc is deliberately frontend-only to avoid overwriting his findings.
