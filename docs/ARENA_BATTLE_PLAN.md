# Arena Battle Plan — Design Arena integration onto `main`

**Status:** ACTIVE. This file and the moderation build board are the dispatch
contract for the Arena. The Owner gives an agent **one card at a time**. The
agent returns its exact commit, files, visible result, checks and evidence.

Last reconciled: 2026-07-29 · Production baseline: **v2.5.692**
(`53c93e93`) · Next assignable card: **A06**.

## 1. Current team and ownership

| Role | Responsibility |
|---|---|
| **Owner** | Final authority; assigns one atomic card and accepts visible results. |
| **Ember** | Integration, JS, templates, backend wiring and focused PostgreSQL tests. |
| **GreenBear** | Visual CSS. |
| **Bolt** | Measurements and independent visual/regression checks. |

**There are no fixed roles and no deploy gate-holder.** The column above is a
typical focus, not a lock, and the §5 "suggested owner" is a suggestion. Any
agent may deploy their own work — one at a time, by the full Gate in §3.
Director, Cursor and ArenaFront are retired. Master Console is outside this
plan. One file has one owner during an active card; agents do not create
parallel long-lived branches.

## 2. Immutable Owner contract

- The site's gold/brass palette is authoritative. **Do not change floor colours.**
- Keep the existing octagon render method and `rotateX(42deg)`.
- Preserve the existing backend, grid, eight rings, real seats, SVG, polling,
  effects and interactions. Build on the scene; do not rebuild it.
- Dust, gifts, rays, shimmer and crown light stay. Master Console stays untouched.
- Do not add the reference K banner. Reuse existing CulinEire branding where a
  mark is required.
- Dark Launch stays intact: unauthorised and anonymous Arena requests remain 404.
- Never put fake fighters, rankings, gifts, viewers, streams or results in production.
- Mobile Arena is frozen and is not a blocker for this desktop plan.

## 3. Slice gate

1. Start from current `origin/main` in one disposable worktree.
2. Implement one card only; check overlap before editing.
3. Run focused PostgreSQL tests, `manage.py check`, diff hygiene and the
   card-specific visual check. The full suite belongs to final gate G01, not
   every small slice.
4. Commit and push the exact slice. The deploy gate verifies origin commit,
   production version, recent deploys, rollback safety and postflight.
5. After a deployed slice, close its temporary branch/worktree. The shared
   repository truth is `origin/main`.
6. Update the card evidence and status in the same change.

**Slices run strictly one at a time, in the §5 table order (sequential
dependency).** Slice N+1 is not started until slice N is **DONE** (merged,
deployed and verified). Only one slice is ever in flight, and each agent holds
at most one card. Nobody starts the next card before the current one is DONE.

**Before taking a new card, go to the board first.** Confirm the previous card is
marked **DONE** in both §5 here and `ARENA_RELEASE_STAGES`/`ARENA_DESIGN_TASKS`
(`recipes/views.py`), and that the closing change is **deployed** to production.
Only then move to the next card. Closing the board is part of finishing a card,
not a separate afterthought — a card whose board row is not DONE-and-deployed is
not finished.

**No roles: any agent may deploy, one at a time, by the full Gate.** Before
shipping, the deploying agent proves three things: (1) **production is current**
— the base is `origin/main` and nothing is unshipped ahead of the served
version; (2) **nobody else is deploying right now** — claim the turn (shared
`deploy.lock`, or tell the Owner and wait for his word); (3) **it breaks nothing
and erases no important files** — focused PostgreSQL tests, `manage.py check` and
`git diff --check` are green, and no paid or approved asset is deleted.

## 4. Completed production foundation

| Card | Result | Evidence |
|---|---|---|
| A00 | Reference authority and immutable constraints reconciled | Plan/Deployment Project audit |
| A01 | Real 290-seat oval connected; one viewer count; stands visible | v2.5.676–v2.5.678 |
| A02 | Chef identity inside existing fighter plinths | v2.5.682 |
| A03 | Correct rank order and approved bevelled labels | v2.5.684–v2.5.685; non-interactive plinth correction v2.5.695 |
| A04 | Cell ripple and chef card anchored to any clicked cell | v2.5.687, v2.5.691; close control v2.5.695 |
| A05 | Independent left Cooking Widget; lifecycle rail separated; compact metrics | v2.5.689–v2.5.692; complete Cooking Widget corrected v2.5.699–v2.5.703 |
| A06 | Production vs Design-Arena measurement matrix (read-only) | ops/audits/arena/A06_measurement_matrix_2026-07-29.md |

## 5. Atomic dispatch queue

The build board contains the full action, files, visible result, acceptance,
forbidden changes and evidence for every row below.

| ID | Surface | Task | Suggested owner | Depends on | Status |
|---|---|---|---|---|---|
| A00 | Arena Hall | Reference authority and immutable constraints | Ember | — | DONE |
| A01 | Arena Hall | Recovered live scene baseline | Ember + GreenBear | A00 | DONE |
| A02 | Arena Hall | Chef identity inside existing floor plinths | Ember | A01 | DONE |
| A03 | Arena Hall | Rank spine order and approved plinth shape | Ember | A01 | DONE |
| A04 | Arena Hall | Cell click ripple and chef-card anchoring | Ember | A01 | DONE |
| A05 | Arena Hall | Broadcast ribbon, phase rail, metrics and identity | Ember | A00 | DONE |
| A06 | Arena Hall | Fresh production/reference measurement matrix | GreenBear | A05 | DONE |
| **A07** | Arena Hall | Stage framing and full-octagon composition | GreenBear | A06 | **NEXT** |
| A08 | Arena Hall | Crowd bowl depth and atmospheric population | GreenBear | A06 | PENDING |
| A09 | Arena Hall | Live challenger/opponent composition | Ember | A07 | PENDING |
| A10 | Arena Hall | Crown-holder hub composition | GreenBear | A07 | PENDING |
| A11 | Furniture | Phase panel reference pass | Ember | A06 | PENDING |
| A12 | Furniture | Crown ladder panel reference pass | GreenBear | A06 | PENDING |
| A13 | Furniture | Recent gifts panel reference pass | GreenBear | A06 | PENDING |
| A14 | Furniture | Bottom ticker and Join the Crowd composition | GreenBear | A06 | PENDING |
| A15 | Arena Hall | Effects and artifacts preservation pass | GreenBear | A07–A10 | PENDING |
| A16 | Arena Hall | CulinEire branding and K-mark audit | Ember | A11–A14 | PENDING |
| A17 | Integrity | Truthful visual state matrix | Ember | A09–A16 | PENDING |
| A18 | Integrity | Desktop accessibility and responsive gate | Bolt + Ember | A17 | PENDING |
| A19 | Arena Hall | Owner visual acceptance — Arena Hall | Owner | A18 | PENDING |
| B01 | Battle Broadcast | Broadcast shell and confrontation header | Ember + GreenBear | A19 | PENDING |
| B02 | Battle Broadcast | Streams, countdown and support furniture | GreenBear | B01 | PENDING |
| B03 | Battle Broadcast | Broadcast chat and composer | Ember | B02 | PENDING |
| R01 | Result / Winner | Champion and runner-up result shell | Ember + GreenBear | B03 | PENDING |
| R02 | Result / Winner | Result metrics, status and chat | Ember | R01 | PENDING |
| G01 | Release gate | Complete Design Arena regression and production evidence | Team + Owner | A19, B03, R02 | PENDING |

## 6. How to assign a card

Copy one expanded card from the build board. It is complete only when the agent
has returned:

- exact commit and changed files;
- the stated visible result;
- every acceptance statement checked;
- confirmation that every forbidden change was avoided;
- focused PostgreSQL/check/diff results and screenshot evidence when visual.

Do not assign a dependent card before its prerequisites are DONE.

## 7. Rollback

Pinned recovery tag `rollback/2026-07-28-stable-v2.5.675` resolves to
`3b4f88ad`. The former backup branch is no longer on origin; do not claim it as
rollback evidence. A board-only rollback is `git revert cb613759` followed by
the approved deploy procedure.
