# P04 Combat Report — Live Battle Monitor & Combat Engine console

Produced: 2026-07-04

## What shipped

- **Selector:** `get_master_monitor()` (`chef_battle/selectors.py`), merged into
  the existing `master_state` payload as a `monitor` section — no new endpoint,
  same 20 s poll. Contents:
  - `counts` — active / paused / unresolved battles, pending / accepted
    challenges (definitions in P04_VISIBILITY_MATRIX.yaml).
  - `events` — append-only timeline: last 20 `BattleEvent` rows for listed
    battles, newest first, including non-public OPERATOR_ACTION audit entries.
  - `detail` — per ACTIVE battle: rounds (number, outcome, hit totals, log
    message), current round number, current-round declared actions
    (chef, attack/defend, moves invested, locked); per INGREDIENT_PENALTY
    battle: ingredient count, lock indices, shots with bounce flags,
    lock/shot progress vs maxima.
  - `artifacts_in_use` — RESERVED ChefArtifact rows for participants.
- **UI:** panel 2 gained the counts row and live event log; panel 3 renders
  per-round combat detail, declared actions and artifacts-in-use. Server-side
  render + JS re-render on every poll (DOM built with createElement, no
  innerHTML injection of dynamic strings).

## Reuse audit

Rounds/hits use the same `combat_rounds` rows as `get_combat_state`; biathlon
detail mirrors `get_biathlon_state` queries with JSON-safe output; event feed
reuses `BattleEvent`; no second combat engine, no duplicated ledger detail —
the console links to records rather than re-deriving them.

## Verification pass 1

`ArenaMasterMonitorTests` — **9/9**:
counts contract; all four `BattleRound.Outcome` values serialize; declared
actions + hit totals equal direct ORM reads; biathlon lock/shot state equals
ORM (5 ingredients, bounce flags); event ordering newest-first; artifacts
lists RESERVED only; **3 consecutive polls create zero rows** in BattleRound /
BattleCombatAction / BattleEvent / TokenTransaction and change no battle
status; hidden markers (`declared_actions`, `lock_indices`, `moves_invested`)
absent from public `arena_state` JSON; anonymous poll 404; flagged operator
gets the monitor read-only.

## Verification pass 2

- Full `chef_battle` suite green with default flags (202 tests incl. combat,
  energy, permission, anti-abuse, biathlon, ledger regressions).
- Live console check (owner session, 1920×1080): real counts, event log
  showing the P03 operator audit events, honest empty states for combat/
  artifacts, no horizontal overflow, no console errors.
- Public battle room and arena popup untouched by this phase (no template or
  endpoint changes outside the console).
