# P07 Reconciliation Report — Economy, gifts, tokens and artifacts

Produced: 2026-07-05

## Read-only by design

No operator economy write was approved, so none was built. The console
cannot: edit wallet balances, mark Stripe orders paid, replay webhooks,
grant/deduct tokens, or alter gift/artifact records. A test posts five
invented economy mutation verbs (`credit_tokens`, `adjust_wallet`,
`mark_order_paid`, `grant_tokens`, `refund_order`) to `master_action` and
asserts every one is rejected with 400.

## Reconciliation evidence (`ArenaMasterEconomyTests`, 8/8)

- **Ledger reconciliation:** transactions created through the real
  `credit_tokens`/`debit_tokens` services show up in `flows_by_type` with
  exact counts and signed sums; headline `tokens_in_24h`/`tokens_out_24h`
  agree with the same ledger; **wallet invariant** asserted:
  `wallet.balance == sum(ledger amounts)`.
- **Window honesty:** a transaction back-dated to 30h ago disappears from
  the 24h flows.
- **Gift catalogue:** costs come from the `APPRECIATION_GIFT_COST` source of
  truth; delivered counts from real `AppreciationGift` rows; per-chef totals
  match.
- **Artifacts:** inventory by lifecycle status and catalogue rarity
  distribution match created records.
- **Orders:** counts by status match; only DISPUTED/REFUNDED ids surface in
  the attention list.
- **Closed-loop wording:** the rendered console contains "closed-loop
  virtual items" and none of: "withdrawable", "e-money", "cash out",
  "your earnings".

## Verification pass 2

- Full `chef_battle` suite green with default flags — includes the existing
  token, Stripe webhook, VAT/consent, gift, artifact, fraud, age, ledger and
  chargeback suites.
- Query budget re-measured: 41 queries at 2 battles (operator-only, 20 s
  poll); bound raised to 50 with a documented per-phase breakdown in the
  budget test.
- Live console check: honest empty states on all four new lists, no
  overflow, no console errors; public endpoints untouched by this phase.
