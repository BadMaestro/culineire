# P08 Ledger Audit — CBR, LSR, payout, ranks, crown and arena authority

Produced: 2026-07-05

## What shipped

- **Read models** (`get_master_governance_detail`, `governance` section of the
  console state): CBR/LSR status matrix across the full 11-status lifecycle,
  recent reward rows, payout request queue with actionable flags, battle
  reports, and a live `LedgerEvent.verify_chain()` result displayed in the
  panel (event count + intact/broken with the first broken pk).
- **BattleReport** (migration `chef_battle/0058`) — the DG-06 workflow: any
  console operator submits summary + flags + recommendation; the owner is
  notified in-site and by email; the submission is OPERATOR_ACTION-audited.
- **Payout decisions** — owner-only console buttons that delegate to the
  existing owning services `approve_payout_request` / `reject_payout_request`.
  The console never touches payout status, reward records, ledger rows or
  Stripe directly. The approve confirm dialog states the real consequence
  (Stripe Connect transfer; graceful failure leaves APPROVED for retry).

## No direct mutation

Rating, rank, crown, streak, reward lifecycle, ledger rows, wallet balances
and Stripe state have no console write path. The only new write surface is
the BattleReport insert and the two payout wrappers above.

## Hash-chain integrity

`LedgerEvent.verify_chain()` is asserted intact in tests **after** an
owner payout approval (which writes ledger events through the owning
service) — the chain survives every console-reachable action.

## Verification pass 1 — `ArenaMasterGovernanceTests` (9/9)

Read-model contract (matrix, recent rewards, actionable payouts, ledger);
operator submits report (record + audit + owner notification); summary and
recommendation validation; operator gets 403 on payout decisions with no
state change; owner approve via owning service (status, reviewer, service
ledger event, console audit, chain intact); reject requires reason and
returns ISSUED rewards to APPROVED; PAID requests not actionable (409);
discretionary-rewards wording asserted, banned funds-phrases absent;
payout/governance keys absent from public arena JSON.

## Verification pass 2

- Full `chef_battle` suite green with default flags — includes reward
  lifecycle, payout eligibility, agreement, ledger immutability/hash, crown,
  ranking, fraud and suspension suites.
- Live console check: honest empty states, ledger line renders "hash chain
  intact", report button present, no overflow, no console errors.

## Deployment

Migration required: `chef_battle/0058` (new table, safe).
collectstatic required (console JS).
