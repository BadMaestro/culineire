# Arena Master Console P00–P05 compliance audit worklog

## 2026-07-04 — Start

Status: in progress.

Owner direction:

- Stop P06.
- Verify completed phases P00, P01, P02, P03, P04, and P05 against their
  authoritative phase prompts, master-plan decisions, contracts, and acceptance
  criteria.

Audit rules:

- Read-only audit first; do not repair findings during the audit.
- Separate implemented evidence from claims in handoffs/roadmap entries.
- Verify code, migrations, templates, permissions, privacy boundaries, tests,
  query budgets, and deployment claims where local evidence exists.
- Classify each requirement as PASS, PARTIAL, FAIL, NOT VERIFIABLE, or OUT OF
  SCOPE, with exact file/test evidence.
- Treat the current uncommitted rejected-vote correction as a proposed change,
  not evidence of the deployed P00–P05 baseline. Compare baseline at commit
  `856dfe68` where this distinction matters.

Planned action 1:

- Stop the obsolete full-suite process.
- Inventory all P00–P05 prompt, decision, contract, handoff, and verification
  documents; map each acceptance criterion to implementation and tests.

Planned action 2:

- Inspect and run focused verification per phase without changing product code.
- Record findings here before moving to the next phase.

Planned output:

- A consolidated compliance report with severity-ranked gaps, unsupported claims,
  regression risks, and an ordered remediation plan. No fixes unless separately
  authorised after review.

## 2026-07-04 — Audit paused by owner

- Owner authorised completing and committing the rejected-vote evidence defect
  before continuing the broader P00–P05 audit.
- No phase compliance conclusions have been issued yet; only the requirements
  inventory was started.

## 2026-07-05 — Audit resumed

- Rejected-vote evidence fix was completed separately in commit `5fd9dc8e`.
- Resume against current HEAD while distinguishing that post-P05 correction from
  the deployed P00–P05 baseline at `856dfe68`.

Planned action 3:

- Build a requirement/evidence matrix from phase prompts and claimed reports.
- Verify P00 and P01 first, record findings before proceeding to P02–P05.
- Use repository and test evidence; deployment/prod claims without reproducible
  local evidence remain `NOT VERIFIABLE`.

## P00 findings — Discovery, baseline, contract freeze

Overall: PARTIAL.

- FAIL — acceptance required no production-code changes. Commit `dbc027db`
  changed `chef_battle/views.py`, `config/release_journal.py`, and
  `templates/base.html`. These were roadmap/release-version changes rather than
  domain behavior, but they still contradict the explicit criterion.
- FAIL — P00 approved DG-04 on the claim that existing presence tracking could
  count users on a battle-detail page. P02 later proved no per-page presence
  source exists. The discovery phase should have caught this before freezing the
  contract; current code correctly reports the metric unavailable.
- PASS — all eight mockup panels and visible actions are represented in the reuse
  matrix with proposed authority/audit treatment.
- PASS — both verification passes and query/payload baselines are recorded.
- PASS — P01 received explicit contracts and resolved decision records.
- WAIVED — required public Arena baseline screenshots were not captured. The
  owner later explicitly waived them in `00_MASTER_PLAN.yaml`; no screenshot
  artifacts exist for independent comparison.
- NOT VERIFIABLE — production deployment claim is documentary only in this local
  audit.

## P01 findings — Visual shell and access gate

Overall: PARTIAL / functionally credible.

- PASS — current access guard implements owner override plus superuser+profile
  flag+feature-flag for non-owner operators; unauthorized roles receive 404.
- PASS — dedicated console template/CSS and URL are additive and scoped; no
  shared stylesheet was changed by the P01 shell.
- PASS at P01 baseline — shell used explicit empty states and disabled risky
  controls. Later phases intentionally enabled owner controls, so current HTML is
  not evidence of a P01 regression.
- PASS — focused access/template tests exist. Current test class has evolved with
  later phases but still covers role separation and public Arena separation.
- NOT VERIFIABLE — reports claim checks/screenshots at 1920, 1440, 1280 and
  mobile, keyboard traversal, clipping/overflow and SVG dimensions, but no
  generated screenshot or machine-readable DOM artifact is retained.
- PARTIAL — P01 could not compare against the missing P00 public baseline; this
  was later owner-waived, but the original verification step did not occur.
- DOCUMENTATION DRIFT — `P01_VISUAL_REPORT.md` still describes the original
  “flag off blocks everyone” test, while follow-up commit `db3d97b6` changed the
  approved contract so the owner always bypasses the flag. The handoff/current
  code are correct; the report and test-class docstring are stale.
- NOT VERIFIABLE — production deployment and live-browser claims cannot be
  independently established from the repository.

Planned action 4:

- Audit P02 read models/query claims and public-field isolation, then P03 action
  services/audit/idempotency, before recording the next checkpoint.

## P02 findings — Read-only live data adapters

Overall: PARTIAL.

- PASS — a single guarded POST state endpoint and documented JSON-safe selector
  exist; public Arena response keys remain isolated by tests.
- PASS — unavailable viewer data is represented honestly after correcting P00's
  false presence assumption.
- PASS — explicit 24-hour economy window, online threshold, tie definition,
  deadlines, and other principal values are documented.
- FAIL — architecture required avoiding N+1 queries. P02 explicitly accepted two
  vote queries per battle, and later combat/moderation extensions increased the
  marginal count. The query test with two battles permits linear growth rather
  than proving a bounded bulk-query design.
- PARTIAL — required read model requested country (when available), support
  totals, current battle artifacts/drop summaries and broader author context.
  The P02 payload did not deliver/document all of these; some artifact detail was
  deferred to P04.
- PARTIAL — required matrix included disputed state and verification of stale or
  deleted authors, missing avatars/wallets, no sponsor/crown/gifts, and multiple
  active battles. The focused P02 tests do not provide explicit coverage for the
  full listed edge-case set.
- NOT VERIFIABLE — live browser/viewport and deployment claims have no retained
  artifact. The 171/171 historical suite claim is documentary; current combined
  suite is green but is not proof of the exact P02 commit state.
- DOCUMENTATION DRIFT — P02 data dictionary still describes
  `BattleVote.is_suspicious` as “DG-05 automatic flags”; accepted-vote flags are
  manual review state, while rejected attempts are now separate evidence.

## P03 findings — Battle-flow orchestration

Overall: PARTIAL with high-risk gaps.

- PASS — console views do not directly mutate battle state; owner-only services
  use transactions and row locks, and applied actions create OPERATOR_ACTION
  evidence with actor/status/reason/correlation/outcome.
- PASS — service-owned cooking/completion transitions reuse domain services;
  stale expected state and sequential double-click are tested.
- PASS — role rendering, POST-only endpoint, owner authorization, reason checks
  for emergency/cancel, pause/resume/cancel paths and local stream termination
  have focused tests.
- FAIL — prompt required concurrent-request and rollback tests. No
  `TransactionTestCase`, threaded concurrency test, or induced rollback assertion
  exists. The class docstring/report claim rollback coverage without such a test.
- FAIL — prompt required explicit CSRF tests. Django's normal test client does
  not enforce CSRF, and no `Client(enforce_csrf_checks=True)` test exists.
- FAIL — rejected operator attempts produce no audit event, so the audit trail
  contains only `outcome=applied`; rejected/stale/unauthorized attempts and their
  outcomes are not auditable despite the prompt's outcome requirement.
- FAIL — broadcast has no idempotency key/constraint or stale guard; repeating
  the same request creates duplicate public events. Thus “every action” is not
  protected against repeated clicks.
- FAIL — Emergency Stop freezes the client countdown by status but does not
  shift `submission_deadline`, `voting_deadline`, or `end_time` on resume. Real
  server deadlines continue expiring during a pause, contradicting DG-03 “all
  timers stop”.
- PARTIAL — local `LiveStreamSession` rows are marked terminated, but no provider
  stream termination exists. Later P05 documentation correctly admits this;
  P03's “stream signal disconnected” language overstates actual behavior.
- NOT VERIFIABLE — live end-to-end and deployment claims are not reproducible
  from retained artifacts.

Planned action 5:

- Audit P04 hidden-information/read-side correctness and P05 moderation/safety
  state/action coverage. Then produce the consolidated severity-ranked report.

## P04 findings — Live battle monitor and combat console

Overall: PARTIAL.

- PASS — monitor selector is read-only; three-poll test proves no creation of
  rounds/actions/events/transactions or battle-status changes.
- PASS — counts, round outcomes/hits, declared actions, biathlon locks/shots,
  recent events and reserved artifacts are backed by real records.
- PASS — operator fields are absent from public Arena JSON, and anonymous access
  to the operator endpoint is denied.
- PARTIAL — prompt required misses, defended ingredients and surviving
  ingredients. The monitor exposes round outcome/hit totals/log text but no
  explicit authoritative fields for those required metrics.
- FAIL — prompt required hidden-information tests for anonymous, spectator,
  participant, moderator and operator. Focused tests cover public JSON,
  anonymous and flagged operator only; they do not exercise the complete role
  matrix or participant battle-room visibility.
- HIGH-RISK PARTIAL — full unlocked declarations and secret ingredient lock
  indices are exposed to every flagged console operator. The visibility matrix
  records this inside P04, but no independent owner decision for this expansion
  of hidden-information access is evident, and no test prevents an operator who
  is also a participant from viewing an opponent's locked move.
- FAIL — required link to the full authoritative log is absent from the console
  template; only the capped 20-event summary is rendered.
- PARTIAL — unresolved/disputed battles are counted but excluded from the listed
  battle set and therefore from the event/detail timeline.
- PARTIAL — per-battle detail functions retain N+1 query behavior inherited from
  P02.
- NOT VERIFIABLE — live viewport and deployment claims lack retained artifacts.

## P05 findings — Moderation, safety and live streams

Overall: PARTIAL with correctness gaps.

- PASS — owner-only adverse services require reasons, use row locks/transactions,
  update existing moderation fields, create applied-action audit events and send
  expected chef notifications.
- PASS — end-stream responses/audit/UI explicitly state that no provider-side
  termination occurred; no external provider action is simulated.
- PASS — focused privacy test confirms a moderation note does not appear in the
  public Arena JSON or battle page.
- FAIL — `report_count` is read from `LiveBroadcast.report_count`, but repository
  search finds no code that updates this counter when `LiveBroadcastReport` rows
  are created. The displayed complaint count is therefore not authoritative and
  can remain zero despite real reports.
- FAIL — required queue fields are incomplete: recording status/reference, last
  moderation action, and per-submission related stream/checklist/report context
  are not present.
- PARTIAL — required side-by-side review UI was implemented as three independent
  lists. There is no stream pause control; “needs changes” approximates request
  review for entries but does not cover stream review.
- FAIL — required safety dimensions (age, minors, kitchen safety, copyright,
  excessive alcohol, recording and prohibited claims) are collapsed into one
  `checklist_confirmed` boolean. The panel cannot show which checks were made and
  does not explicitly mark individual dimensions unavailable.
- PARTIAL — `agreement_signed` means any historical LiveBattleAgreement exists;
  it does not verify an approved/current agreement version.
- FAIL — verification prompt required tests for every moderation and stream
  status, CSRF, two/one/recording-only stream layouts, unavailable provider,
  underage/unagreed/suspended/fraud scenarios, and public visibility before and
  after each action. The 10 focused tests cover only a subset.
- FAIL — rejected/unauthorized moderation attempts are not audit-recorded, same
  audit-outcome gap as P03.
- PARTIAL — query budget was raised to 35 while preserving linear per-battle
  behavior rather than eliminating N+1 queries.
- NOT VERIFIABLE — live console and deployment claims lack retained evidence.

Planned action 6:

- Produce `P00_P05_COMPLIANCE_AUDIT_REPORT.md` containing the phase verdicts,
  critical/high/medium findings, evidence, and ordered remediation plan.
- Do not modify product code. Review report and working-tree scope after writing.

## 2026-07-05 — Critical remediation authorised

Owner authorised fixing the two highest-confidence correctness defects before
the remaining weekly budget is exhausted.

Agent-quality finding: prior completion claims were too broad and did not satisfy
the phase prompts' own acceptance requirements. Remediation will be evidence-led;
no phase will be called complete merely because its happy-path tests pass.

Planned remediation A — Emergency Stop time semantics:

- On resume, calculate elapsed pause duration from `paused_at` under the existing
  row lock and atomically extend every non-null battle deadline that governs
  future expiry (`submission_deadline`, `voting_deadline`, `end_time`).
- Preserve status restoration and audit the applied pause duration.
- Test exact deadline movement and prove stale expiry cannot consume paused time.

Planned remediation B — authoritative stream report count:

- Stop trusting the unsynchronised `LiveBroadcast.report_count` field in the
  console selector.
- Annotate selected broadcasts from the real `LiveBroadcastReport` relation and
  expose that aggregate.
- Test a deliberately stale counter against real report rows.

Verification plan:

- Migration drift check (no migration expected), focused P03/P05 tests, Django
  check, diff review, then commit if green. Full 215-test suite is unlikely to fit
  the remaining time budget; this limitation will be stated explicitly.

### Critical remediation checkpoint

- Emergency Stop resume now shifts `submission_deadline`, `voting_deadline`, and
  `end_time` by the measured pause duration under the existing transaction/lock.
- Resume audit payload now records `pause_duration_seconds` and the shifted fields.
- P05 now annotates the real `LiveBroadcastReport` relation and ignores the
  unsynchronised legacy `LiveBroadcast.report_count` value.
- `makemigrations --check --dry-run`: PASS; no migration.
- `manage.py check`: PASS.
- `ArenaMasterActionTests` + `ArenaMasterModerationTests`: PASS, 32/32.

Planned final action:

- Update P03/P05 audit documentation and consolidated report to mark these two
  findings resolved.
- Run related timer/expiry/read-model tests, then diff review and commit if green.

### Critical remediation final verification

- Related `BattleTimerTests`, `AutoCompleteVotingTests`, and
  `ArenaMasterStateTests`: PASS, 20/20.
- Combined focused verification: 52 tests passed (32 P03/P05 + 20 related).
- Full suite was not repeated due the stated weekly-budget constraint; the
  immediately preceding baseline at commit `5fd9dc8e` was 215/215 green.

Next action: `git diff --check`, scoped diff/status review, then commit the two
authorised corrections and audit documents.

Diff-review correction before commit: clamp a future/invalid `paused_at` to zero
pause duration so clock skew can never move deadlines backwards; add regression
coverage, then rerun the focused action class.

- Clock-skew regression: PASS; `ArenaMasterActionTests` 23/23.
- Final verified total across the executed focused groups: 53 passing tests.
