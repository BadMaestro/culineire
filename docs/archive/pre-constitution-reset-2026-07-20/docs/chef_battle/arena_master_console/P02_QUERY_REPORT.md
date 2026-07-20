# P02 Query Report — Arena Master Console read models

Produced: 2026-07-04 · Measured on local dev DB (6 enrolled chefs, 1 scheduled battle) and test DB.

> **Correction 2026-07-10:** the numbers in the original table below were the
> P02-only baseline and are now STALE. Later phases added per-battle read models
> (P05 moderation detail, P06 voting analytics ~7/battle, P07 economy detail).
> The authoritative, test-enforced figure is now in
> `test_master_state_query_budget`: **41 queries at 2 battles, bound 50**
> (~7 queries per battle marginal cost, not the 2 stated below). This is a
> known, accepted per-battle cost, not an oversight — see "N+1 status" below.

## Operator endpoint (P02 baseline — superseded, see correction above)

| Measurement | P02 baseline value |
|---|---|
| `get_master_state()` queries (1 battle) | 12 (P02-only; now higher with P05–P07 detail) |
| `get_master_state()` payload (1 battle) | 1,929 bytes |
| Test-enforced budget | **50 queries** (`test_master_state_query_budget`, measured 41 at 2 battles) |
| Poll cadence | 20 s (matches public arena) |

## N+1 status (authoritative 2026-07-10)

The endpoint retains per-battle queries (~7/battle: vote counts, UTC vote series,
VoteIntegrityEvent ×2, suspicious count, chat ×2, gift aggregate + P05/P07 detail).
This is a documented deviation from P02's "avoid N+1" constraint, accepted for
these reasons:

- **Operator-only**: `arena_console_guard`, polled every 20 s by at most a couple
  of superuser operators — not a public hot path.
- **Low battle concurrency**: active battles are typically a handful; the 50-query
  bound gives headroom for ~3 concurrent battles.
- **Regression-guarded**: `test_master_state_query_budget` fails if the count
  exceeds 50, so per-battle cost cannot silently grow.

A battle-count-independent bulk-load (aggregate all active battles' analytics in
fixed queries) remains available as a future optimization if active-battle
concurrency ever grows beyond the ~3 the current bound covers. Tracked as audit
remediation item 4.

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
