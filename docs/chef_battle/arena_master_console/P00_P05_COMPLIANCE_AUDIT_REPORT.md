# Arena Master Console P00–P05 compliance audit

Date: 2026-07-05  
Baseline reviewed: P00–P05 commits through `856dfe68`; current code at
`5fd9dc8e` used for regression evidence.  
Method: phase prompts, deliverables, commit diffs, implementation and tests.
Production/deployment and historical browser claims are not independently
verifiable from this repository.

## Executive result

| Phase | Verdict | Main reason |
|---|---|---|
| P00 | PARTIAL | Changed production files despite prohibition; froze an invalid presence assumption |
| P01 | PARTIAL | Functional gate/shell credible; visual evidence not retained and report is stale |
| P02 | PARTIAL | Real read model, but intentional N+1 queries and incomplete required data/edge coverage |
| P03 | PARTIAL / HIGH RISK | Timer pause corrected; concurrency, rollback, CSRF and rejected-action audit remain missing |
| P04 | PARTIAL / HIGH RISK | Read-only monitor works; incomplete metrics and insufficient hidden-information authorization/tests |
| P05 | PARTIAL / HIGH RISK | Complaint count corrected; required granular safety/state coverage remains incomplete |

None of P00–P05 fully satisfies every requirement in its phase prompt. This does
not mean the console is unusable: the current 215-test Chef Battle suite is green,
and substantial core behavior is implemented. It means the completion claims are
broader than the reproducible evidence.

## Critical and high-priority gaps

### 0. P05 cooked-photo moderation queue could not see cooked photos — RESOLVED

`get_master_moderation_detail()` selects only `INGREDIENT_PENALTY` battles,
while `cooking_submit()` accepts uploads only in `COOKING`. The transition to
COOKING removes the battle from the queue before submission is possible.

Resolution (`2026-07-05`): COOKING is now the pending-review state. Upload resets
review evidence to PENDING and never auto-publishes. Presentation opens only after
both confirmed photos receive owner approval. Queue/action tests cover the flow.

### 1. Emergency Stop did not stop server-authoritative time — RESOLVED

Evidence: `operator_emergency_stop()` stores pause state and the UI displays
`PAUSED`; `operator_resume()` restores status without extending
`submission_deadline`, `voting_deadline`, or `end_time` by the paused duration.

Impact: a battle can lose submission/voting time or become eligible for expiry
while supposedly paused. This conflicts directly with DG-03.

Resolution (`2026-07-05`): resume now shifts submission, voting and end deadlines
atomically by the measured pause duration and records the shift in its audit
payload. Focused action/moderation tests pass.

### 2. Live complaint count was not sourced from complaints — RESOLVED

Original evidence: P05 serialised `LiveBroadcast.report_count`; repository search
found no write path synchronising it with `LiveBroadcastReport` creation.

Impact: the safety console can display zero reports while report records exist.

Resolution (`2026-07-05`): P05 now aggregates `Count("broadcast__reports")` from
real report rows. Regression coverage proves a stale legacy counter is ignored.

### 3. Hidden combat data has an under-specified authority boundary

Evidence: P04 exposes unlocked `BattleCombatAction` declarations and secret lock
indices to every flagged console operator. Tests do not cover an operator who is
also a participant or the full anonymous/spectator/participant/moderator/operator
matrix required by the prompt.

Impact: a participating operator could potentially see an opponent's hidden move.

Required remediation: obtain an explicit owner decision, normally restrict hidden
pre-resolution data to the owner/non-participant safety role, and add the complete
role matrix including operator-participant conflict.

### 4. Operator rejection and concurrency evidence is incomplete

Evidence: applied actions have OPERATOR_ACTION events, but rejected/stale/
unauthorized requests are not audited. P03 has sequential double-click tests but
no real concurrent-request or induced rollback test. Broadcast has no idempotency
key and duplicates on replay. CSRF is not tested with enforcement enabled.

Impact: investigation cannot reconstruct rejected high-risk attempts, and the
documented concurrency/idempotency guarantees exceed tested behavior.

Required remediation: add a private rejected-action audit record, idempotency key
storage/constraint for replayable actions, `TransactionTestCase` concurrency and
rollback tests on a database supporting row locks, plus enforced-CSRF tests.

### 5. P05 safety checklist is not granular evidence

Evidence: one `checklist_confirmed` boolean is presented as coverage for age,
minors, kitchen safety, copyright, alcohol, recording, and prohibited claims.

Impact: operators cannot determine which safety assertions were actually made;
the panel implies more evidence than the data model stores.

Required remediation: versioned per-item checklist evidence, current agreement
version verification, and explicit `Unavailable` states until each signal exists.

## Cross-phase engineering gaps

- P02–P05 retain per-battle queries. The current budget accepts roughly four
  additional queries per battle, contrary to P02's “avoid N+1” constraint.
- Required screenshot/DOM evidence is described in reports but not retained;
  historical viewport, keyboard, clipping, and live-production claims cannot be
  independently reproduced.
- P04 lacks explicit misses/defended/surviving-ingredient metrics and the required
  authoritative-log link.
- P05 lacks recording state, last action and integrated submission/stream review;
  focused verification covers only a subset of required statuses and scenarios.
- P00 modified production-facing roadmap/version files despite its no-production-
  code acceptance criterion.
- RESOLVED (`2026-07-10`, v2.5.172) — P01 stale flag semantics corrected:
  P01_VISUAL_REPORT.md and P01_HANDOFF.yaml no longer claim "flag off => 404 for
  everyone including owner". Both now state the authoritative god-level owner rule
  (owner always retains access regardless of flag), matching
  `chef_battle/access.py` and `test_console_flag_off_blocks_operators_but_never_the_owner`.
- Still stale: P02 automatic suspicious-vote wording no longer matches the
  authoritative behavior.
- RESOLVED (`2026-07-05`) — malformed action identifiers now return JSON 400.
- RESOLVED (`2026-07-05`) — cancelling a paused battle clears every pause field,
  including `paused_reason`.

## Verified strengths

- Console access is strongly isolated behind owner/operator rules and 404 failure.
- Public Arena JSON does not expose console sections in existing tests.
- P03 state-changing paths are service-based, transactional and row-locked.
- Applied owner actions carry actor, state transition, reason, correlation and
  outcome evidence.
- P04 polling is demonstrably side-effect free.
- P05 does not pretend a stream provider was terminated.
- Private moderation-note leakage has focused regression coverage.
- Rejected vote attempts were separately corrected in `5fd9dc8e`; they do not
  affect vote totals and have 90-day retention.
- Current `chef_battle` suite: 215/215 passing with the baseline feature flag off.

## Ordered remediation plan

1. Resolve and enforce hidden-combat operator/participant permissions.
2. Add rejected operator-action audit, broadcast idempotency, concurrency,
   rollback and enforced-CSRF coverage.
3. Make P05 checklist/agreement evidence granular and complete its required
   status/scenario matrix.
4. Bulk-load P02–P05 per-battle data and restore a battle-count-independent query
   ceiling.
5. Add missing P04 combat metrics and authoritative log link.
6. Correct stale P00/P01/P02 documentation and retain reproducible visual-test
   artifacts for future phases.

P06 should remain paused until items 1–5 are resolved or explicitly accepted by
the owner as documented residual risks.
