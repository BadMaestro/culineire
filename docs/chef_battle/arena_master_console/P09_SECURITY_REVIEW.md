# P09 Security Review — Arena Master Console

Produced: 2026-07-05

## Access model (DG-01)

- Console page, state poll and action endpoint all sit behind
  `arena_console_guard`: superuser AND (owner slug OR
  `has_arena_console_access`), failure mode Http404 (existence hidden).
  Owner override: the owner always has access; `ARENA_MASTER_CONSOLE_ENABLED`
  gates non-owner operators only.
- Write authority split (test-enforced at every endpoint):
  - every console operator: `submit_battle_report` only;
  - owner only: phase forcing, emergency stop/resume/cancel, broadcast,
    entry/report/stream moderation, payout approve/reject.

## CSRF / unsafe methods

- All state-changing endpoints are POST-only (`@require_POST`; GET returns
  405, test-asserted). Django CSRF middleware active; JS sends `X-CSRFToken`
  from the cookie; anonymous POST without a token is rejected before the view.
- No GET mutation exists anywhere in the console.

## IDOR / privilege escalation

- Every object id from POST is resolved server-side under the same
  owner/operator gate; there is no per-object ownership ambiguity because
  console authority is global-per-role, not per-record.
- Non-owner operators receive 403 with **no state change** (tests assert the
  record is unchanged after the rejected call) for every owner-only verb.
- Unknown/invented verbs (including economy mutations) → 400.

## Replay / duplicate writes / stale state

- Force transitions carry `expected_status`; the battle row is locked with
  `select_for_update` inside a transaction — repeated or concurrent clicks
  yield 409 and exactly one audit event (test-asserted).
- Payout decisions delegate to owning services that lock the row and
  validate status transitions.
- Frontend: monotonic poll sequence prevents stale responses overwriting
  newer state (P09).

## Hidden-data / privacy leakage

- Public arena JSON keys frozen and test-compared; analytics/moderation/
  governance keys asserted absent from public responses.
- Voter identity and request-hash values never serialized; moderation notes
  asserted absent from public pages; payout amounts operator-only.
- Console page is `noindex, nofollow`; inline scripts carry CSP nonces.

## Payments / legal

- No console code path can mutate wallet balances, Stripe order status,
  reward lifecycle or ledger rows; payout approve/reject go through the
  pre-existing owning services (Stripe transfer failure degrades gracefully).
- Ledger hash chain verified in tests after every console-reachable write.
- Closed-loop wording test-asserted (tokens/rewards never called cash,
  earnings, withdrawable funds).

## Residual risks (accepted, documented)

- Console operators (all superusers) can see unlocked combat declarations
  and biathlon lock indices — deliberate, recorded in P04_VISIBILITY_MATRIX;
  re-evaluate if an operator can also be a battle participant.
- `verify_chain()` result cached 60 s — tampering detection latency ≤60 s.
- Active-viewer counts remain honestly "Unavailable" pending an owner
  presence-design decision (DG-04 gap).
