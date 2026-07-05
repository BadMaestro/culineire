# P09 Performance Report — Arena Master Console

Produced: 2026-07-05 (local dev, SQLite, 1 battle / 6 enrolled chefs)

## master_state (the single console endpoint, 20 s poll)

| Metric | Value |
|---|---|
| Queries (1 battle, ledger check cached) | **37** |
| Response assembly time | **24.4 ms** |
| Payload size | **4.0 KB** |
| Test-enforced query bound | 50 (documented per-phase breakdown in the budget test) |
| Poll concurrency | 1–2 operators expected; endpoint is owner/operator-gated |

Marginal cost per additional battle: ~9 queries (votes, UTC series,
integrity aggregates ×2, suspicious, chat ×2, gift aggregate, combat detail).

## P09 optimizations applied

1. **LedgerEvent.verify_chain() cache (60 s per process).** The chain scan
   is O(all ledger rows) and was running on every 20 s poll; now at most
   once per minute. Tamper-detection latency ≤60 s is acceptable for an
   operator dashboard; `checked_at` is included in the payload for honesty.
2. **Stale-poll guard (JS).** Monotonic sequence counter — a slow response
   arriving after a newer one can no longer overwrite fresher state.
3. No new indexes added: every filtered column used by the console
   (`created_at`, `status`, `tx_type`, `sent_at`, gate/battle indexes) is
   already indexed; measurements showed no evidence requiring more.

## Public arena (regression)

`arena()`/`arena_state()` unchanged since the P02 dedup (5 assembly
queries); P00 baseline envelope maintained; public payload keys frozen and
test-enforced.

## DOM / assets

8 panels, one SVG ring (200 cells, same renderer as the public arena),
no images beyond avatars (native lazy loading via browser defaults),
console CSS+JS ~30 KB combined un-minified, served via hashed static
pipeline (collectstatic post-processing).
