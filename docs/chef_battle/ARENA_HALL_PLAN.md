# Arena As The Hall — Battle Lifecycle Choreography Plan

**Status: APPROVED PLAN — no code started. Owner decisions recorded 2026-07-02.**
**Supersedes** the Phase 2/3 sections of the deleted `HANDOFF_CRESTEDTEN.md`
(recoverable at commit `9badb2ca`); Phase 1 (two-cell VS centre) is already live.

## Owner decisions (2026-07-02, verbatim intent)

1. **APPROVED: avatar relocation** (chefs move cells through the battle lifecycle).
2. **APPROVED: spectator popup embedded ON the arena** (option A from the old
   handoff — not a link to a separate page).
3. **APPROVED: Battle Room page becomes the "прихожая" (antechamber)** — rules,
   ratings, statistics, chef comparison — with a transition to the arena, where
   all the action happens.

## The vision (owner's spec)

The arena is the hall: spectators, fanfare, seated and standing places.

- **Registered users "sit" in blue cells.**
- **Anonymous visitors occupy grey fields** — these grey standing zones do not
  exist yet and must be created (owner-approved geometry extension).
- Two online chefs appear in random cells.
- **Clicking a chef's cell opens a chef popup**: all stats, an *approximate*
  attack and defence potential (derived from artifacts, but the artifacts
  themselves are NOT shown — only indicative info), a link to the profile, and
  a **Challenge button right in the popup**.
- **Challenge accepted → "teleportation"** into two random cells facing each
  other:
  - different ranks → each chef stays in his OWN ring → a **vertical** facing
    pair across rings;
  - same rank → both in their ring, facing each other.
- **Battle time reached → both teleport to the ring centre**: two cells with
  `VS` (VERSUS) between them (Phase 1 rendering already exists — reuse).
- The whole centre cell becomes **one big link opening the Battle Room popup**
  over the arena: chef left vs chef right, **their artifacts visible** (the
  battle is open — no secrets at this point), battle stages live, and a
  **dedicated chat window that exists only for this battle**, visible to all.
- Chefs **may** use artifacts they own, and **MUST use artifacts gifted to them
  by spectators** during the battle.
- **Gifts (Appreciation) do not affect the battle** — and after the battle they
  can be **"sold"** (new economy mechanic).
- On completion chefs return to their original ring cells.

---

## Work plan

### Stage A — Arena as the hall (frontend, no new models)

| # | Item | Notes |
|---|------|-------|
| A1 | Chef popup on cell click | Stats, approximate attack/defence potential (aggregate of owned artifact effect values, shown as indicative range — never the artifact list), View Profile, Challenge button. Extends the existing arena tooltip. |
| A2 | Blue spectator cells for registered users | Today spectators = authors with a token wallet (`_get_spectators`). Owner to confirm: all logged-in users or wallet-holders only. |
| A3 | Grey standing fields for anonymous visitors | NEW zone in the arena SVG (owner-approved geometry extension). Needs a lightweight anonymous presence signal (session-based ping) — none exists today. |

### Stage B — Relocation choreography (approved Phase 2)

| # | Item | Notes |
|---|------|-------|
| B1 | Arena payload: battle context per in_battle chef | battle_id, phase, scheduled start — so the client knows who is where and why. |
| B2 | Challenge accepted → teleport to facing pair | Same rank: both in own ring, opposite cells. Different ranks: each in own ring, vertically aligned pair across rings. Random cell selection. |
| B3 | Battle time → teleport to centre (two cells + VS) | Reuse Phase 1 centre rendering. Chefs DISAPPEAR from their ring cells while centre-staged (move, not duplicate). |
| B4 | Completion → return to original ring cells | Placement derived from state each poll. |
| B5 | Teleport animation | SVG transitions between 20s polls are non-trivial: ship static relocation first, animate second (per original handoff advice). |

### Stage C — Battle Room popup on the arena (approved Phase 3, option A)

| # | Item | Notes |
|---|------|-------|
| C1 | Centre VS cell = one big link opening the popup | Replaces today's navigation to battle_detail. |
| C2 | Popup layout: chef left vs chef right + their artifacts | Battle is open information at this stage. Live stages via existing `battle_state_poll`. |
| C3 | Battle chat in the popup | Existing per-battle chat API (`chat/poll`, `chat/send`) — chat already exists only per battle, visible to all incl. anonymous. |
| C4 | Voting in the popup (Voting stage) | Existing `battle_vote` endpoint. |
| C5 | Gifts in the popup | Appreciation + artifact gifts via existing endpoints. 18+/token/legal affordances must carry over unchanged. |

### Stage D — Battle Room page becomes the antechamber

| # | Item | Notes |
|---|------|-------|
| D1 | Rework battle_detail into the "прихожая" | Rules, ratings, statistics, chef comparison, then a prominent transition to the arena. |
| D2 | Where do the CHEFS act? | Open owner decision: chef combat actions (moves, locks, shots) from the arena popup too, or from the antechamber/battle page. |

### Stage E — Combat & economy rule changes (backend)

| # | Item | Notes |
|---|------|-------|
| E1 | Mandatory use of spectator-gifted artifacts | Combat logic change + public rules update (/chef-battle/rules/). |
| E2 | Appreciation gifts "sellable" after the battle | NEW economy mechanic. MUST be checked against the closed-loop token model (rules s14) and anti-gambling wording (s17) before build — token-back conversions are legally sensitive. Rate/flow TBD with owner + solicitor. |
| E3 | Scheduled battle time + readiness gate | "Battle time" concept: today battles start on accept. Needs scheduling (who sets the time?) and a both-ready gate. |

---

## Open questions for the owner (ask before building the stage)

1. **A2:** who sits in blue cells — every logged-in user, or token-wallet
   holders as today?
2. **A3:** anonymous grey fields — real headcount (needs anonymous session
   ping) or symbolic/decorative occupancy?
3. **A1:** format of the "approximate potential" — range (e.g. 40–60), stars,
   or a single rounded number?
4. **D2:** chef combat actions — from the arena popup or from the antechamber?
5. **E2:** sell-back rate for appreciation gifts and the legal green light.
6. **E3:** who sets the battle time — chefs agree, challenger proposes, or
   automatic?

## Ground rules for whoever builds this

- One stage at a time; verify each on prod; owner reviews before the next.
- Do NOT create fake battles in the prod DB to test — mock render client-side
  (see the verification technique in commit `9badb2ca`'s handoff).
- Reuse existing endpoints and components; the arena SVG helpers
  (`octagonPoints`, `svgEl`, avatar clip pattern) already exist.
- Per-rank fill colours, `#arena-cell-shadow`, existing ring geometry stay
  untouched — grey anonymous fields are an owner-approved ADDITION, not a
  change to existing rings.
- 18+ / token / gift legal affordances must never be weakened by the popup.
- Log every step in the Deployment Journal, the Chef Battle Roadmap and CoWork.
