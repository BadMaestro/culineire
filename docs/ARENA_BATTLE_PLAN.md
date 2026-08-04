# Arena Battle Plan — Design Arena integration onto `main`

**Status:** ACTIVE. This file and the moderation build board are the dispatch
contract for the Arena. The Owner gives an agent **one card at a time**. The
agent returns its exact commit, files, visible result, checks and evidence.

Last reconciled: 2026-08-04 · Production baseline: **v2.5.801**
· Next assignable card: **A07**. (A08 ran ahead of it and is DONE, v2.5.775–779.)

**A07 was built and reverted on the same day.** v2.5.792 put the Design
Template's own camera on the Arena — `rotateX(57deg)`, `perspective 1600px`,
centred origins — and the Owner reverted it within the hour. The camera stays
`rotateX(42deg)`. What the attempt established stands and is worth reading
before anyone re-opens the card: the reference floor is a 1120×1120 **square**,
the same as this SVG's viewBox, so its aspect of 2.375 is produced by its camera
and not by a wider octagon. A07 cannot be reached by scale and placement alone,
and the 2.375 target is not available at 42°. See v2.5.792/793 in the journal.

## 1. Current team and ownership

| Role | Responsibility |
|---|---|
| **Owner** | Final authority; assigns one atomic card and accepts visible results. |
| **GreenBear** | Visual CSS. |
| **Bolt** | Measurements and independent visual/regression checks. |

**Ember was retired by the Owner on 2026-08-04.** Its name stays on the DONE
rows in §4 and §5 — attribution is history and is not rewritten — and every
open card that suggested it is now **unassigned**: A09, A16, A17, A18, B01, B03,
R01, R02. A suggestion pointing at a retired agent reads as an owner and stops
the next agent from asking. Integration, JS, templates and backend wiring have
no standing owner; the Owner assigns them.

**There are no fixed roles and no deploy gate-holder.** The column above is a
typical focus, not a lock, and the §5 "suggested owner" is a suggestion. Any
agent may deploy their own work — one at a time, by the full Gate in §3.
Director, Cursor and ArenaFront are retired. Master Console is outside this
plan. One file has one owner during an active card; agents do not create
parallel long-lived branches.

## 2. Arena structure contract (v2 — 11-ring octagon)

Approved by the Owner 2026-07-29. This **supersedes** the former freeze
("eight rings", "do not change the existing octagon render method", "do not
change floor colours"): the eleven-ring structure below is now the target, and
the renderer may change to build it.

The octagon is **eleven rings**, centre outward:

| # | Ring | Fill (reference; implemented as tokens) |
|---|------|------|
| 1 | **Crown Holder** — crown + current holder's name (already live) | `#52422E` |
| 2 | **Moat** — service ring: `border:0`, no visible cells; a glowing lantern at each cell centre casts glints onto the gold ring | base `#52422E` |
| 3 | Culinary Master | `#7C674D` |
| 4 | Executive Chef | ↓ eight rank rings, one monotonic |
| 5 | Head Chef | gradient from `#7C674D` (ring 3) |
| 6 | Sous Chef | to `#EEE1CA` (ring 10): the six named |
| 7 | Chef De Partie | palette tans/beiges + two logically |
| 8 | Commis Chef | interpolated steps |
| 9 | Prep Chef | ↑ |
| 10 | Kitchen Porter | `#EEE1CA` |
| 11 | **VIP Guests** (Sponsors) | `#535252` steel |

Around the floor: **two rows of seats top and bottom** = authorised guests who
are **authors** (not chefs); behind them, **balconies** for unauthorised users —
bodiless spirits. The seat contract is rewritten for this new grid (drafted
separately, §2a).

Still in force (unchanged by v2):

- Camera `rotateX(42deg)`.
- Design **tokens** only, no raw hex — the palette above lands in tokens.
- Dark Launch intact: unauthorised and anonymous Arena requests remain 404.
- Never put fake fighters, rankings, gifts, viewers, streams or results in production.
- Effects (dust, gifts, rays, shimmer, crown light) preserved; Master Console untouched.
- No reference K banner; reuse existing CulinEire branding where a mark is required.
- Mobile Arena is frozen and is not a blocker for this desktop plan.
- **The media layer is CLOSED (Owner, 2026-08-03): below 901px the Arena stays
  exactly as it is.** One visual style, the desktop one, at every width. The 86
  `min-width: 901px` wrappers removed in v2.5.729/730 stay removed. Two scopes
  came back in v2.5.772 and only those two, because `placeRankSpine()` still
  tested both breakpoints and cleared the rank column's inline geometry while no
  stylesheet stood up to take over. There is no stage 2. Note also that
  indentation in the four Arena stylesheets no longer implies a media scope: 668
  lines sit indented at top level as the bodies of the removed wrappers, and
  reading one of them as scoped is how that defect stayed invisible for six days.
- **Never put fake anything in production, and that includes the audience.** The
  arena deck's `hydrateFixtures()` was disconnected in v2.5.782 after production
  measurement showed the server sending zeros while the page showed 2.4K viewers,
  3.7K votes, 620 gifts and a battle between two chefs who do not exist. It is
  switched off, not deleted, and three tests keep it that way — including one
  that keeps the function present, so it is not dead code to be tidied away.

## 2a. Seat & spectator contract (v2)

Approved by the Owner 2026-07-29. Replaces the "290 real-viewer oval" model.

- **Real interactive seats belong to authors** (authorised users who are not
  chefs): two rows top and two rows bottom around the floor. Front rows fill
  first; a logged-in author sees themselves seated.
- **VIP Guests** (ring 11) are reserved seats for **sponsors**.
- **Balconies** behind the author rows hold **unauthorised users as bodiless
  spirits** — atmospheric only, never impersonating a real/online user, with no
  interactive seat identity.
- The former fixed **290**-seat oval is superseded; capacity follows the two-row
  geometry, front rows first.
- Chefs occupy rank rings 3–10 by rank; the Crown Holder holds ring 1; the
  **Moat (ring 2) has no occupants** — lanterns only.

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
| AR2 | Floor palette settled — Owner ramp, moat/VIP tokens, neutral ink | v2.5.704–707, 709–722, 728 |
| A06 | Production vs Design-Arena measurement matrix (read-only) | ops/audits/arena/A06_remeasure_2026-08-04.md — reference floor aspect **2.375**, production **1.266**. The 2026-07-29 matrix is SUPERSEDED: it was measured against the rejected prototype and is kept as evidence only, not as a source. |
| AR0 | Arena CSS/JS dead-code inventory (read-only) | ops/audits/arena/AR0_dead_code_inventory_2026-07-29.md |
| AR1 | Arena owns its eleven-ring geometry; Sponsors grid no longer borrowed | v2.5.709–v2.5.710 |
| AR3 | Moat lit by eight lanterns; glint on the Crown plate | v2.5.736 |
| A08 | Crowd bowl depth, and the hall behind the seats populated | v2.5.775–779 |
| AR4 | Author seats: two rows top, two bottom; capacity 290 → 114 | v2.5.769 |
| AR5 | VIP sponsor ring; spirit balconies driven by a real anonymous count | v2.5.765–768, v2.5.778 |

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
| AR1 | Arena Hall | Eleven-ring octagon geometry (Crown, Moat, 8 ranks, VIP) | GreenBear | A06 | DONE |
| AR2 | Arena Hall | Eleven-ring palette tokens | GreenBear | AR1 | DONE |
| AR3 | Arena Hall | Moat ring (ring 2) with lanterns + gold-ring glints | GreenBear | AR1 | DONE |
| AR4 | Arena Hall | Author seat rows (two top, two bottom) | Bolt | AR1 | DONE |
| AR5 | Arena Hall | Spirit balconies + VIP sponsor ring | GreenBear + Bolt | AR4 | DONE |
| **A07** | Arena Hall | Stage framing and full-octagon composition | GreenBear | AR5 | **NEXT** |
| A08 | Arena Hall | Crowd bowl depth and atmospheric population | GreenBear | A06 | DONE |
| A09 | Arena Hall | Live challenger/opponent composition | unassigned | A07 | PENDING |
| A10 | Arena Hall | Crown-holder hub composition | GreenBear | A07 | PENDING |
| A11 | Furniture | Phase panel reference pass | Bolt | A06 | DONE |
| A12 | Furniture | Crown ladder panel reference pass | GreenBear | A06 | PENDING |
| A13 | Furniture | Recent gifts panel reference pass | GreenBear | A06 | PENDING |
| A14 | Furniture | Bottom ticker and Join the Crowd composition | GreenBear | A06 | PENDING |
| A15 | Arena Hall | Effects and artifacts preservation pass | GreenBear | A07–A10 | PENDING |
| A16 | Arena Hall | CulinEire branding and K-mark audit | unassigned | A11–A14 | PENDING |
| A17 | Integrity | Truthful visual state matrix | unassigned | A09–A16 | PENDING |
| A18 | Integrity | Desktop accessibility and responsive gate | Bolt + unassigned | A17 | PENDING |
| A19 | Arena Hall | Owner visual acceptance — Arena Hall | Owner | A18 | PENDING |
| B01 | Battle Broadcast | Broadcast shell and confrontation header | unassigned | A19 | PENDING |
| B02 | Battle Broadcast | Streams, countdown and support furniture | GreenBear | B01 | PENDING |
| B03 | Battle Broadcast | Broadcast chat and composer | unassigned | B02 | PENDING |
| R01 | Result / Winner | Champion and runner-up result shell | unassigned | B03 | PENDING |
| R02 | Result / Winner | Result metrics, status and chat | unassigned | R01 | PENDING |
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
