# CulinEire Arena Existing-System Audit

## Audit identity

- Original audit base: `726e338076462982185e3caa7564cc37977a18c9`.
- **Current authoritative base: `2a28e4b2c3be0e1baad7340e06aa1f020931e025`**
  (production `v2.5.380`), reconciled 2026-07-20. The audit was originally
  performed against `726e3380`; the reconciliation pass below folds in
  everything that changed between the two commits. See
  `DELTA_RECONCILIATION.yml` for the full machine-readable record and
  `AUDIT_CLOSURE.yml` for the closure status.
- Delta reconciliation classification: **`MINOR_AMENDMENT`** — the base-commit
  change amends this document, it does not invalidate it.
- CODEX initial/peer/delta: `99624798`, `9bf4e0f8`, `8a4085e5`.
- CLAUDE_A initial/peer/delta: `37f50ae6`, `ddf7bc53`, `89605cbd`.
- CLAUDE_B initial/peer/delta: `64452639`, `35d991f5`, `82d30aad`.
- Analysis only; no production code or assets were modified by the audit or
  by this reconciliation pass.

## Executive conclusion

CulinEire already contains a substantial working Chef Battle system and real Arena data/action layer. The failed direction is the presentation shell: procedural ring geometry, perspective fitting, generated crowd, photographic hall/floor calibration, cinematic effects and a six-stylesheet cascade. The minimum safe future change is a frontend reconstruction around existing server contracts, not a second Arena implementation.

The backend remains authoritative for access, challenges, phases/deadlines, submission secrecy/reveal, moderation, voting integrity, results, ratings, crown state, gifts/tokens/artifacts, notifications and viewer presence. Reusable frontend concepts include phase/deadline/metrics, chef identity/rank/stats/actions, battle-room endpoint delegation, crown/gift/empty states and canonical navigation.

**This conclusion is unchanged by the reconciliation to `2a28e4b2`** — see
"Amendments from the `2a28e4b2` reconciliation" below for what specifically
changed and why none of it moves the boundary.

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

---

## Amendments from the `2a28e4b2` reconciliation (2026-07-20, `MINOR_AMENDMENT`)

Everything above is the original audit, preserved as written against
`726e3380`. The items below are what changed by `2a28e4b2` and what each one
means for the conclusions above. Full detail: `DELTA_RECONCILIATION.yml`.

1. **Dark-launch access is broader than audited.** Any authenticated user
   with a `RecipeAuthor` profile can now view the Arena while
   `CHEF_BATTLE_ENABLED=False` — not staff/superuser/bearseeker only.
   Anonymous users and authenticated users without an author profile are
   still denied. This does not change "Backend that must remain untouched"
   or the required 2D data contracts; it only changes who reaches them.
2. **Vote integrity gained a database-level constraint.** `BattleVote` now
   has a `voter_author` field and a `CheckConstraint` enforced by Postgres,
   on top of the existing Python fraud/validation gates. Does not change
   the "voting integrity" preservation boundary — it strengthens it.
3. **Request fingerprints are now versioned HMAC**, not bare SHA-256
   (`hash_scheme` `v1`=legacy / `v2`=current, never cross-compared). Same
   preservation-boundary status as (2).
4. **Arena styling is flatter and more tokenized, but the core presentation
   conclusion is unchanged.** Raw-hex counts dropped substantially
   (`arena.css` 108→6, `arena_command_deck.css` 48→0, `arena_deck_polish.css`
   31→5, `arena_hall.css` 8→3, `arena_render.css` 8→3;
   `arena_master_console.css` untouched at 8) and the CSS `perspective`/
   camera-tilt declaration plus the occupant `scaleY` stretch-compensation
   hack were both removed. This **confirms**, rather than reverses, the
   "Abandoned-presentation code" and "Duplicate/dead-code conclusions"
   sections above: the six-stylesheet cascade still loads as one unit and
   is still not deletion-safe; tokenizing colors did not consolidate
   ownership of it.
5. **No dead-code or rebuild-boundary classification changed.** No file was
   promoted to `CONFIRMED_DEAD_CODE`; "Smallest safe rebuild boundary" and
   "Duplicate/dead-code conclusions" stand as originally written.
6. **The internal Arena build board gained archive/live/frozen stage
   grouping with acceptance criteria.** This is operational project-status
   documentation, not implementation authority or browser evidence — it
   does not satisfy any item in "Test protection" above.

### New risks introduced by the reconciled state

- Migration `0083` (the self-vote constraint) intentionally aborts if
  historical self-votes exist in production; this was not checked against
  production data during reconciliation and needs an owner decision if it
  is ever triggered.
- `voter_author` is nullable — any future vote-writing code path that
  doesn't set it weakens the new DB constraint for that path.
- `SECRET_KEY` rotation changes HMAC fingerprint outputs; the `v2` scheme
  label does not itself encode which key generation produced a given hash.
- The new global `--hall-*` design tokens could be mistaken for canonical
  2D-implementation tokens by a future session — they are compatibility
  aids for the legacy dark hall palette, not a recommended foundation (see
  the retained/prohibited split now recorded in `arena_mockup_spec.md`).
- `docs/agents/GOLDEN_RULES.md` described Arena visibility as
  staff/superuser-only; this was stale relative to the implementation and
  has been corrected as part of this same closure pass.

### Unresolved conflicts carried forward unchanged

- `docs/chef_battle/arena_mockup_spec.md`'s 56-degree camera target
  conflicted with the "simple 2D interface" direction — resolved in this
  closure pass by marking that document `HISTORICAL_CONCEPT_REFERENCE`
  (see that file for exactly what is retained vs. prohibited).
- The stale proto-gate test conflict is unchanged — not touched by this
  reconciliation or this closure pass.
- The probable initial `crown_ladder`/`recent_gifts`/`crown_streak` template
  context mismatch is unchanged — logged, not fixed, per the audit's own
  stop rule (see `owner_decisions_to_record.confirmed_template_context_defect`
  in `AUDIT_CLOSURE.yml`).
- Whether old candidate assets (`hall-bg-v1.webp`, `hall-bg-v2-plan.webp`,
  `arena_octant_prototype.js`) get a later deletion-proof audit remains an
  open owner decision, not resolved by this pass.
