# CulinEire Arena Existing-System Audit — Master (reconciled)

## Audit identity

- **Original audit base:** `726e338076462982185e3caa7564cc37977a18c9`, performed
  by the three lanes (CODEX = Ember, CLAUDE_A = GreenBear, CLAUDE_B = Bolt) per
  `AUDIT.txt`.
- **Authoritative base as of this document:** `2a28e4b2c3be0e1baad7340e06aa1f020931e025`,
  reconciled via `docs/ai/audits/arena_2d/SHARED/DELTA_RECONCILIATION.yml`
  (overall classification: `MINOR_AMENDMENT`, not audit invalidation).
- Analysis only; no production code or assets were modified by any lane at any
  stage of this audit or its reconciliation.

**Commit-reference discrepancy (flagged, not silently resolved):** the prior
version of this document (`audit/arena-2d-codex` @ `b147843c`) recorded
`CLAUDE_A initial/peer: 37f50ae6, ddf7bc53`. Neither hash resolves to a real
object in this repository as verified by CLAUDE_A directly (`git cat-file -e`
on both, against `origin` fully fetched) at the time this consolidation was
written. CLAUDE_A's actual, verifiable report/peer-review/delta commits are:
`ebb6cbaf` (initial report), `5b73015e` (peer review of CLAUDE_B), `89605cbd`
(delta review) on branch `audit/arena-2d-claude-a`. This discrepancy is
recorded here rather than quietly corrected in place, per the standing rule
against silently resolving conflicts between agent-produced documents — the
synthesis's other conclusions are not affected by it (none of them depend on
the specific commit hash, only on the reviewed content), but the identity
record itself was wrong and should not be propagated further without noting
that it was wrong once.

## Executive conclusion

CulinEire already contains a substantial working Chef Battle system and a real
Arena data/action layer. The failed direction is the presentation shell:
procedural ring geometry, perspective fitting, generated crowd, photographic
hall/floor calibration, cinematic effects, and a six-stylesheet cascade. The
minimum safe future change is a frontend reconstruction around existing
server contracts, not a second Arena implementation.

The backend remains authoritative for access, challenges, phases/deadlines,
submission secrecy/reveal, moderation, voting integrity, results, ratings,
crown state, gifts/tokens/artifacts, notifications, and viewer presence.
Reusable frontend concepts include phase/deadline/metrics, chef
identity/rank/stats/actions, battle-room endpoint delegation, crown/gift/empty
states, and canonical navigation.

## What already works

- Dark-launch Arena and separate owner/operator console access.
- Profiles, eight ranks, rating, placement, W/L and crown statistics.
- Challenge create/accept/refuse/expiry, eligibility and cooldown.
- Lifecycle including readiness, waiting, walkover, void, pause and dispute.
- Timers, submissions, hidden entries, reveal, moderation and voting.
- Duplicate/self-vote protection and idempotent result scoring — **now also
  enforced at the database level** (see "Conclusions amended" below).
- Rating, crown, event, ledger, reward and notification updates.
- Gifts, artifacts and token-backed transactions.
- Viewer heartbeats, metrics, reactions, chat and broadcast snapshots.

## Backend that must remain untouched

`models.py`, domain transitions in `services.py`, read-model meanings in
`selectors.py`, access guards, URLs, action views, migrations, and
security/integrity tests form the preservation boundary. Sensitive contracts
include `Battle.status`, deadlines, `BattleEntry.is_revealed`, moderation,
vote uniqueness, scoring/crown idempotency, wallet/ledger rules, and hashed
presence.

## Reusable frontend blocks

- Shared Arena CTA and canonical URLs.
- Phase/deadline/metrics semantics and update flow.
- Chef identity, avatar, rank, stats, profile and challenge actions.
- Crown, gifts and explicit empty/auth states.
- `arena_battle_room.js` endpoint delegation with focus adaptation.
- `arena_deck.js` data-update concepts, rebindable to a 2D layout's own
  selectors. **Open item, not resolved by either lane or the delta:** CLAUDE_B
  classified `arena_deck.js` `DUPLICATE_CANDIDATE` ("ported from the legacy
  renderer"); CLAUDE_A disputed this in `PEER_REVIEW.md`, reading the file's
  own header comment as documenting a *deliberate, completed* split from the
  now-deleted `arena_puzzle.js`, not an unresolved duplicate. Neither the
  peer-review pass nor the delta reconciliation settled which label is
  correct — recorded here as still open (see `MASTER_UNRESOLVED_CONFLICTS.md`
  if/when produced).
- Reduced-motion principle and safe server delegation.

## Abandoned-presentation code (THREE_D_PRESENTATION_ONLY)

- Procedural SVG rings/octants, seats and coordinate maps.
- Projection, convergence, perspective and viewport fitting.
- Generated crowd/billboard correction.
- Hall/floor imagery and backdrop calibration.
- Cinematic depth/effects and independent dark palette.
- Current privileged Live Arena SVG/CSS preview; its backend snapshot remains
  reusable.

**Unchanged by the delta (726e3380 → 2a28e4b2):** the camera-tilt and
billboarding CSS/JS rules that existed at the original audited base were
*already being retired* mid-session — the delta range captures the completion
of that retirement (perspective/backdrop rules removed, comments left
explaining why), not a reversal of this classification. See
`DELTA_RECONCILIATION.yml`'s `conclusions_unchanged` list, corroborated
independently by both CLAUDE_A's and CLAUDE_B's delta reviews.

## Active entry points and dependencies

`arena()` builds `_build_arena_payload()`, renders `arena.html`, then includes
`_arena_render_ring.html`. That partial loads geometry, deck, battle-room and
render JavaScript. The Arena Master Console also includes the same partial,
so wholesale removal would regress operator UI. Live Arena snapshot is a
separate broadcast contract.

## Duplicate/dead-code conclusions

Six active Arena stylesheets (`arena.css`, `arena_command_deck.css`,
`arena_deck_polish.css`, `arena_hall.css`, `arena_master_console.css`,
`arena_render.css`) have overlapping ownership and remain consolidation
candidates — **not deletion-safe**, unchanged by the delta. Public and
broadcast payloads overlap in facts but have different audiences and are not
proven duplicates. **No file meets `CONFIRMED_DEAD_CODE`.**

- `hall-bg-v1.webp` and `hall-bg-v2-plan.webp` — `DEAD_CODE_CANDIDATE` only
  (zero references found by two independent lanes; full checklist — settings,
  admin, deployment, migration references — not exhausted).
- `arena_octant_prototype.js` — presentation-only legacy with a documented
  manual caller (`docs/chef_battle/prototypes/arena_octant_prototype.html`),
  not confirmed dead. CLAUDE_A and CLAUDE_B independently disagreed on its
  *primary* label (dead-code-candidate vs. three-d-presentation-only); both
  facts are true simultaneously (see CLAUDE_A's `PEER_REVIEW.md`) and are
  recorded together here rather than collapsed into one.

## Genuinely absent

No required backend business feature was proven missing. Browser
accessibility acceptance, responsive 2D behaviour, and the future 2D layout
are intentionally not implemented by this audit.

## Required 2D data contracts

- Center type/identity and active battle IDs.
- Rank groups, profile/action URLs and capability fields.
- Phase `{key,label,step}` and deadline
  `{deadline_iso,seconds_remaining,kind,label}`.
- Metrics `{active_viewers,public_votes,battle_gifts}`.
- Crown, gifts, result and honest empty shapes.
- Poll/action URLs, CSRF/credentials and server errors.
- Visibility, participant, moderation and operator boundaries.

**Confirmed unchanged by the delta:** no Arena payload key, polling URL,
action endpoint, public Arena template, JavaScript contract, or broadcast
snapshot contract changed between `726e3380` and `2a28e4b2`.

## Conclusions amended (by the 726e3380 → 2a28e4b2 delta)

1. **Dark-launch Arena visibility** now includes every authenticated user with
   a `RecipeAuthor` — Chef Battle enrollment, staff, superuser, and bearseeker
   privilege are **not** required for an ordinary registered author.
   Anonymous users and authenticated users without a `RecipeAuthor` remain
   hidden while the public flag is off. (Shipped v2.5.380,
   `chef_battle/access.py`, matches the owner's golden rule recorded in
   `docs/agents/memory/golden_rule_author_can_visit_arena.md`.)
2. **Vote self-protection** now includes a database-level `CheckConstraint`
   via `BattleVote.voter_author`, in addition to the existing Python
   fraud/validation gates (migration `0083_vote_self_vote_constraint_and_hash_scheme.py`).
3. **Request fingerprints** now use HMAC-SHA256 keyed by `SECRET_KEY` and
   carry an explicit hash scheme (`v2`); historical hashes remain labelled
   `v1` and comparisons stay scheme-scoped.
4. **Arena styling is flatter and more tokenized.** Raw-hex literal counts
   dropped substantially across the six stylesheets, re-verified directly
   against `2a28e4b2` (not the stale figures first reported):
   `arena.css` 108→6, `arena_command_deck.css` 48→0, `arena_deck_polish.css`
   31→5, `arena_hall.css` 8→3, `arena_render.css` 8→3,
   `arena_master_console.css` unchanged at 8 (not touched by this pass). This
   reduces, but does **not eliminate**, the independent-palette conflict or
   the six-sheet ownership risk — the cascade-duplication classification
   above is unchanged.
5. **The legacy shell is now flatter and full-bleed** across desktop and
   mobile (previously gated to `min-width: 901px`); removed
   perspective/occupant-stretching CSS does not change the shell's
   legacy-presentation classification.
6. **The Arena build board** now distinguishes archived, live, and frozen
   stages with explicit acceptance criteria (`archive`, `later_stages`,
   `criterion` context added to `templates/moderation/arena_build_plan.html`).
   This is operational/planning documentation, not implementation authority
   or browser evidence.
7. **The `--arena-*` custom-property collision risk** (flagged independently
   in the original audit) was mitigated by giving the arena's dark-hall
   palette a distinct, non-colliding name (`--hall-*` in `base.css`) rather
   than by consolidating the three existing scopes into one. The underlying
   multiplicity (`.site-battle-widget`'s own `--arena-*` set,
   `.arena-command-deck`'s light HUD `--arena-*` set, and now `base.css`'s
   `--hall-*` set) is unchanged; only the naming collision is closed.

## Smallest safe rebuild boundary

Replace public Arena composition, presentation CSS, and the geometry renderer
with normal-flow 2D UI. Adapt endpoint-oriented popup/deck behaviour. Do not
alter domain layers unless a separately tested defect is approved. Before
retiring the shared renderer, decouple or replace its Master Console
consumer.

## Owner decisions still required before implementation

1. Embedded popup, canonical battle-room navigation, or both.
2. Whether the privileged Live Arena preview remains.
3. 2D information hierarchy and responsive/accessibility acceptance matrix.
4. Timing of the confirmed crown/gift/streak context fix and stale proto-gate
   tests.
5. Whether old assets receive a later deletion-proof audit.
6. **Whether `docs/chef_battle/arena_mockup_spec.md`'s original product
   hierarchy (rank-ring concept, chef-versus-chef concept, Crown Holder
   concept) still holds for the 2D direction** — the document is now tagged
   `HISTORICAL_CONCEPT_REFERENCE`; its 56-degree camera, 3D geometry,
   photographic-hall-matching, and generated-crowd requirements are explicitly
   retired and must not be treated as 2D acceptance criteria.
7. **Whether `arena_deck.js`'s classification is `DUPLICATE_CANDIDATE` or a
   completed split** (see "Reusable frontend blocks" above) — requires a
   direct check for DOM-update overlap with `arena_render.js`, not yet
   performed by any lane.
8. Production migration readiness for historical self-votes — migration 0083
   intentionally stops if historical self-votes exist; no production data was
   queried during this audit or its reconciliation.

## Test protection

`chef_battle/tests.py` covers services, access, challenges, integrity,
expiry, timers, submissions, crown, gifts, moderation, snapshots, payload,
metrics, phase, deadlines, readiness and spectators. During reconciliation,
CLAUDE_B and CODEX each independently ran focused Arena test suites against
`2a28e4b2` (17/17 and 20/20 passing respectively, per their delta reviews) in
addition to the original audit's 15/15 pass against the earlier base. Browser
visual/accessibility behaviour remains untested by any lane.

## Recommended implementation split

- Backend/domain guardian (CODEX lane): contracts and only approved defect
  fixes.
- 2D frontend owner (CLAUDE_A lane): one scoped, semantic, token-compliant
  presentation.
- Integration/QA owner (CLAUDE_B lane): browser/accessibility, action parity,
  AMC compatibility and regression evidence.

**Implementation remains blocked until owner approval.**
