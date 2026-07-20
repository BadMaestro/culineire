# CulinEire Arena Existing-System Audit

## Audit identity

- Common base: `726e338076462982185e3caa7564cc37977a18c9`.
- CODEX initial/peer: `99624798`, `9bf4e0f8`.
- CLAUDE_A initial/peer: `37f50ae6`, `ddf7bc53`.
- CLAUDE_B initial/peer: `64452639`, `35d991f5`.
- Analysis only; no production code or assets were modified.

## Executive conclusion

CulinEire already contains a substantial working Chef Battle system and real Arena data/action layer. The failed direction is the presentation shell: procedural ring geometry, perspective fitting, generated crowd, photographic hall/floor calibration, cinematic effects and a six-stylesheet cascade. The minimum safe future change is a frontend reconstruction around existing server contracts, not a second Arena implementation.

The backend remains authoritative for access, challenges, phases/deadlines, submission secrecy/reveal, moderation, voting integrity, results, ratings, crown state, gifts/tokens/artifacts, notifications and viewer presence. Reusable frontend concepts include phase/deadline/metrics, chef identity/rank/stats/actions, battle-room endpoint delegation, crown/gift/empty states and canonical navigation.

## What already works

- Dark-launch Arena and separate owner/operator console access.
- Profiles, eight ranks, rating, placement, W/L and crown statistics.
- Challenge create/accept/refuse/expiry, eligibility and cooldown.
- Lifecycle including readiness, waiting, walkover, void, pause and dispute.
- Timers, submissions, hidden entries, reveal, moderation and voting.
- Duplicate/self-vote protection and idempotent result scoring.
- Rating, crown, event, ledger, reward and notification updates.
- Gifts, artifacts and token-backed transactions.
- Viewer heartbeats, metrics, reactions, chat and broadcast snapshots.

## Backend that must remain untouched

`models.py`, domain transitions in `services.py`, read-model meanings in `selectors.py`, access guards, URLs, action views, migrations and security/integrity tests form the preservation boundary. Sensitive contracts include `Battle.status`, deadlines, `BattleEntry.is_revealed`, moderation, vote uniqueness, scoring/crown idempotency, wallet/ledger rules and hashed presence.

## Reusable frontend blocks

- Shared Arena CTA and canonical URLs.
- Phase/deadline/metrics semantics and update flow.
- Chef identity, avatar, rank, stats, profile and challenge actions.
- Crown, gifts and explicit empty/auth states.
- `arena_battle_room.js` endpoint delegation with focus adaptation.
- `arena_deck.js` data-update concepts rebound to 2D selectors.
- Reduced-motion principle and safe server delegation.

## Abandoned-presentation code

- Procedural SVG rings/octants, seats and coordinate maps.
- Projection, convergence, perspective and viewport fitting.
- Generated crowd/billboard correction.
- Hall/floor imagery and backdrop calibration.
- Cinematic depth/effects and independent dark palette.
- Current privileged Live Arena SVG/CSS preview; its backend snapshot remains reusable.

## Active entry points and dependencies

`arena()` builds `_build_arena_payload()`, renders `arena.html`, then includes `_arena_render_ring.html`. That partial loads geometry, deck, battle-room and render JavaScript. The Arena Master Console also includes the same partial, so wholesale removal would regress operator UI. Live Arena snapshot is a separate broadcast contract.

## Duplicate/dead-code conclusions

Six active Arena stylesheets have overlapping ownership and are consolidation candidates. Public and broadcast payloads overlap in facts but have different audiences and are not proven duplicates. No file meets `CONFIRMED_DEAD_CODE`.

`hall-bg-v1.webp` and `hall-bg-v2-plan.webp` are candidates only. The octant prototype is presentation-only legacy with a documented manual caller, not confirmed dead.

## Genuinely absent

No required backend business feature was proven missing. Browser accessibility acceptance, responsive 2D behaviour and the future 2D layout are intentionally not implemented by this audit.

## Required 2D data contracts

- Center type/identity and active battle IDs.
- Rank groups, profile/action URLs and capability fields.
- Phase `{key,label,step}` and deadline `{deadline_iso,seconds_remaining,kind,label}`.
- Metrics `{active_viewers,public_votes,battle_gifts}`.
- Crown, gifts, result and honest empty shapes.
- Poll/action URLs, CSRF/credentials and server errors.
- Visibility, participant, moderation and operator boundaries.

## Smallest safe rebuild boundary

Replace public Arena composition, presentation CSS and geometry renderer with normal-flow 2D UI. Adapt endpoint-oriented popup/deck behaviour. Do not alter domain layers unless a separately tested defect is approved. Before retiring the shared renderer, decouple or replace its Master Console consumer.

## Owner decisions before implementation

1. Embedded popup, canonical battle-room navigation, or both.
2. Whether privileged Live Arena preview remains.
3. 2D information hierarchy and responsive/accessibility acceptance matrix.
4. Timing of the confirmed crown/gift/streak context fix and stale proto-gate tests.
5. Whether old assets receive a later deletion-proof audit.

## Test protection

`chef_battle/tests.py` covers services, access, challenges, integrity, expiry, timers, submissions, crown, gifts, moderation, snapshots, payload, metrics, phase, deadlines, readiness and spectators. CLAUDE_B freshly passed `manage.py check` and 15 focused Arena integration tests. Browser visual/accessibility behaviour remains untested.

## Recommended implementation split

- Backend/domain guardian: contracts and only approved defect fixes.
- 2D frontend owner: one scoped, semantic, token-compliant presentation.
- Integration/QA owner: browser/accessibility, action parity, AMC compatibility and regression evidence.

Implementation remains blocked until owner approval.
