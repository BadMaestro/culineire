# P02 Query Report — Arena Master Console read models

Produced: 2026-07-04 · Measured on local dev DB (6 enrolled chefs, 1 scheduled battle) and test DB.

## Operator endpoint

| Measurement | Value |
|---|---|
| `get_master_state()` queries (1 battle) | **12** |
| `get_master_state()` payload (1 battle) | 1,929 bytes |
| Test-enforced budget (2 battles) | ≤ 20 queries (`test_master_state_query_budget`) |
| Poll cadence | 20 s (matches public arena) |

Per-battle marginal cost: 2 queries (vote counts + suspicious count). Everything
else is fixed-cost aggregates; participants' profiles are bulk-fetched (no N+1).

## Public arena after the shared-selector refactor

`arena()` and `arena_state()` now both call `_build_arena_payload()`
(previously duplicated line-for-line). Contract unchanged:

| Measurement | P00 baseline | P02 |
|---|---|---|
| `arena_state()` JSON keys | rings, spectators, center, latest_result | identical (test-enforced) |
| `_build_arena_payload()` queries | — | **5** |
| `arena_state()` total queries (P00: 7) | 7 | 5 shared + session/auth = unchanged envelope |

## Fixes shipped alongside (found during P02 verification)

1. **Latent public-arena crash:** `_arena_center` used `active_battle.status.value`,
   which raises `AttributeError` for any battle loaded from the DB (TextChoices
   values are plain `str` after a fetch). The public arena would have 500'd the
   moment a real battle went active. Fixed to `str(active_battle.status)`;
   covered by the P02 battle-state tests.
2. **Multi-line `{# #}` Django comment** rendered as literal text in the new
   ring partial (same bug class as v2.5.86) — replaced with `{% comment %}`.

## Verification summary

- Pass 1: 17 new `ArenaMasterStateTests` + 12 `ArenaMasterConsoleAccessTests`
  green; battle-state matrix (none/scheduled/active/ingredient_penalty/voting/
  completed/cancelled/paused); query budget test; leak tests.
- Pass 2: live browser checks at 1920/1280/mobile (no overflow, no clipping,
  ring SVG renders 200 cells inside the console, countdown ticks, poll 200);
  public arena re-verified (200 cells, tooltip/popup present, no `amc-`
  markup, no comment leak, console clean); full `chef_battle` suite:
  **171/171 OK** with default flags.
