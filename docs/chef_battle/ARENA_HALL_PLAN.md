# Arena As The Hall — Battle Lifecycle Choreography Plan

**Status: LARGELY SHIPPED, RECONCILED 2026-08-17 (see "Work plan" below for the
row-by-row record). Owner decisions recorded 2026-07-02; this header is the
original approval note and is kept as history, not as a current claim that
nothing has been built.**
**Supersedes** the Phase 2/3 sections of the deleted `HANDOFF_CRESTEDTEN.md`
(recoverable at commit `9badb2ca`); Phase 1 (two-cell VS centre) is already live.

## Owner decisions (2026-07-02, verbatim intent)

1. **APPROVED: avatar relocation** (chefs move cells through the battle lifecycle).
   Shipped as T29/T25; see Stage B below.
2. **APPROVED: spectator popup embedded ON the arena** (option A from the old
   handoff — not a link to a separate page). **REVERSED by his own later
   ruling, 2026-08-06** (`ARENA_BATTLE_PLAN.md` §2c): the popup stays a
   placeholder pointing at a separate page and must not grow broadcast
   content. Kept verbatim here as the historical decision, not as current
   direction; see Stage C below.
3. **APPROVED: Battle Room page becomes the "прихожая" (antechamber)** — rules,
   ratings, statistics, chef comparison — with a transition to the arena, where
   all the action happens. Shipped as T30; see Stage D below.

## The vision (owner's spec)

*Verbatim original spec, kept as written. See "Work plan" below for what
actually shipped and where it diverged (blue/grey cells superseded by the
11-ring/spirit-balcony model; the popup built here was later deleted).*

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

**RECONCILED 2026-08-17.** This table is an early draft; almost everything in
it has since shipped, but under different card IDs and sometimes a different
mechanism than originally sketched here. Never marked as such until now, so a
fresh reader saw an apparently-open backlog. Each row below carries a status
verified against the running code, not assumed from the row's own age.

### Stage A — Arena as the hall (frontend, no new models)

| # | Item | Notes |
|---|------|-------|
| A1 | Chef popup on cell click | **DONE**, as a tooltip rather than a popup. `_arena_render_ring.html`'s `#arena-tooltip` carries stats, `atk_band`/`def_band` (AA7's indicative range, never the artifact list), a View Profile link and a Challenge button. |
| A2 | Blue spectator cells for registered users | **SUPERSEDED.** Real interactive seats now belong to authors under the 11-ring/spirit-balcony model (`ARENA_BATTLE_PLAN` §2a, Owner 2026-07-29), not the "blue cells" scheme sketched here. |
| A3 | Grey standing fields for anonymous visitors | **SUPERSEDED**, same ruling as A2: anonymous visitors are the "bodiless spirits in the balconies" the §2a model already built, not a separate grey zone. |

### Stage B — Relocation choreography (approved Phase 2)

| # | Item | Notes |
|---|------|-------|
| B1 | Arena payload: battle context per in_battle chef | **DONE.** `battle_id`, `battle_phase`, `battle_url` on every chef record. |
| B2 | Challenge accepted → teleport to facing pair | **REVERSED by Owner ruling, 2026-08-06** (`_arena_center()`'s own comment): a pair stands in their own rings through the whole approach stage and the centre stays empty until combat actually begins - "facing pair" cells at the centre were tried and explicitly undone. `facing_pair` is a dead payload value; see `arena_data_layer_spec.md` X22. |
| B3 | Battle time → teleport to centre (two cells + VS) | **DONE** (T29, 2026-08-16): a fighter vacates his ring cell only once his own battle reaches the centre stage - moved, not duplicated. |
| B4 | Completion → return to original ring cells | **DONE**, same T29 change: position is derived from state on every poll, so return is automatic once the battle leaves the centre. |
| B5 | Teleport animation | **DONE** (T25, Bolt, 2026-08-17): chefs travel between cells via a CSS transition scoped to the moving occupant, rather than jumping. The cadence naming this row used ("20s polls") was already stale - it is 10s; see `arena_data_layer_spec.md` §5. |

### Stage C — Battle Room popup on the arena (approved Phase 3, option A) — WHOLE STAGE CANCELLED

**Option A itself was not taken.** `ARENA_BATTLE_PLAN.md` §2c (Owner, 2026-08-06)
named the popup a placeholder pointing at the battle's own broadcast page and
forbade it growing a second copy of the broadcast - the opposite of C1-C5
below. The popup was trimmed to match that ruling (AA2, 2026-08-15) and then
deleted outright once the centre click pointed straight at the real battle
page and nothing referenced it any more (AA6, 2026-08-16). C1-C5 are listed
here only as the record of the path not taken.

| # | Item | Notes |
|---|------|-------|
| C1 | Centre VS cell = one big link opening the popup | Not built - the centre click goes to `battle_broadcast` directly. |
| C2 | Popup layout: chef left vs chef right + their artifacts | Not built - popup deleted (AA6). |
| C3 | Battle chat in the popup | Not built - chat lives on `battle_detail`/`battle_broadcast` only. |
| C4 | Voting in the popup (Voting stage) | Not built - voting lives on `battle_detail` only. |
| C5 | Gifts in the popup | Not built - gifts live on `battle_detail` only. |

### Stage D — Battle Room page becomes the antechamber

| # | Item | Notes |
|---|------|-------|
| D1 | Rework battle_detail into the "прихожая" | **DONE** (T30, 2026-08-17). Chef comparison and the arena transition already existed; T30 added the two real gaps found by audit - a head-to-head record between this specific pair, and a rules link, both present on every phase. |
| D2 | Where do the CHEFS act? | **SETTLED, not by a fresh ruling but by C1-C5's cancellation:** combat actions (moves, locks, shots) happen on `battle_detail`/`battle_broadcast`, the only surface left once the popup was deleted. |

### Stage E — Combat & economy rule changes (backend)

| # | Item | Notes |
|---|------|-------|
| E1 | Mandatory use of spectator-gifted artifacts | **DONE** (T24, Bolt, 2026-08-16). Enforced per effect type; public rules section 13 updated. |
| E2 | Appreciation gifts "sellable" after the battle | **DONE** (v2.5.1792, Bolt, 2026-09-05). The Owner ruled the rate and waived the legal check this row had been waiting on: "Проверки не нужно, стройте". A gift is the Chef's to keep; selling it back returns 25% of what the viewer paid, as a PENDING record that still passes the arena's closing checks. Flowers 80 -> 20, in his own worked example. **COMBAT ARTIFACTS AND BATTLE PRIZES ARE NOT SOLD BACK** - his words, 2026-09-05: "их не сдают". That is not a missing mechanism and no agent builds one; they are equipment, used or kept. |
| E3 | Scheduled battle time + readiness gate | **DONE.** `Battle.challenger_ready`/`opponent_ready` plus the 30-minute pull-in (T20, superseding this row's original 15-minute sketch, Owner 2026-08-15). |

---

## Open questions for the owner — RECONCILED 2026-08-17

Five of six are closed, by a later ruling superseding the question rather
than by an answer to it as originally framed:

1. ~~A2: who sits in blue cells~~ — CLOSED. Superseded by the 11-ring/
   spirit-balcony model; "blue cells" were never built.
2. ~~A3: anonymous grey fields~~ — CLOSED, same ruling as A2.
3. ~~A1: format of the "approximate potential"~~ — CLOSED. AA7 (2026-08-15)
   answered it: a range, `"40–60"`.
4. ~~D2: chef combat actions — popup or antechamber~~ — CLOSED by the
   popup's deletion (AA6): the antechamber is the only surface left.
5. ~~E2: sell-back rate for appreciation gifts and the legal green
   light~~ — **CLOSED 2026-09-05.** He set the rate at 25% of what the viewer
   paid, made it the Chef's own decision rather than automatic, and waived the
   legal check: "Проверки не нужно, стройте". Shipped in v2.5.1792. He also
   settled what is NOT sellable, unprompted: combat artifacts and battle
   prizes — "их не сдают".
6. ~~E3: who sets the battle time~~ — CLOSED. Automatic: `accept_challenge`
   sets it; readiness (`challenger_ready`/`opponent_ready`) pulls the start
   in, it does not set it.

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
