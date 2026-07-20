# P06 Worklog — Voting integrity and audience analytics

## 2026-07-04 — Start

Status: in progress.

Baseline:

- P05 is present in commit `856dfe68` (`v2.5.102`).
- The working tree was reported clean before P06 started.
- Authoritative scope: `phase_06_voting_integrity.yaml`.
- P06 is read-only analytics work. It must not create a second vote engine or
  change eligibility, deadlines, winner calculation, or tie resolution.

Planned action 1 — audit before implementation:

- Inspect the existing Arena Master Console selectors, view/context, panel 5,
  styles, JavaScript, vote/presence/chat/gift models, and relevant tests.
- Confirm the exact DG-05 approved suspicion rules and authoritative vote APIs.
- Identify bounded/indexed query shapes and existing query-budget expectations.

Planned action 2 — implementation (only after the audit is recorded here):

- Add read-only P06 selectors and extend panel 5 with authoritative totals,
  percentages, time-window series, tie/completion state, DG-05 flags, and
  privacy-safe community summaries where supported by real records.
- Add investigation links only to authoritative operator/admin records.

Planned action 3 — verification and documentation:

- Add focused P06 tests, privacy/permission/query-count/rendering coverage.
- Run both verification passes and the complete `chef_battle` suite.
- Produce `P06_METRIC_DEFINITIONS.yaml`, `P06_PRIVACY_REPORT.md`, and
  `P06_HANDOFF.yaml`.

No implementation or exploratory code changes have been made yet.

## 2026-07-04 — Audit checkpoint 1

Observed before implementation:

- `BattleVote` stores `is_suspicious`, `ip_hash`, `user_agent_hash`, and a
  moderation note; sensitive hashes/identity must remain operator-only.
- P02 already exposes total votes, suspicious count, and the DG-05 tie flag in
  `get_master_state()`.
- Existing admin registration provides the authoritative investigation surface
  for `BattleVote`.
- The current panel 5 is a compact totals list and needs P06 analytical depth.
- The first batched audit command used a nonexistent `static/chef_battle` path;
  its search returned useful matches but the rest of that batch must be read
  again explicitly. No product code was changed.

Planned action 1a — complete the audit:

- Read exact selector/model/service/view/template/test code and current static
  asset locations.
- Record approved DG-05 rules, data availability, privacy boundaries, and the
  proposed bounded query shape here before implementing anything.

## 2026-07-04 — Audit complete / implementation contract

Authoritative findings:

- Authenticated uniqueness is enforced by DB constraint
  `one_authenticated_vote_per_battle`; anonymous device uniqueness is enforced
  by `one_anonymous_vote_per_battle_device`.
- The vote endpoint also runs duplicate-device, IP velocity, self/participant,
  suspension, and fraud-flag gates before saving.
- Documentation drift found: DG-05 says rejected duplicates are saved with
  `is_suspicious=True`, but `battle_vote()` currently rejects them before any
  `BattleVote` is created. P06 will not repeat that unsupported claim and will
  not change vote behavior in this phase.
- `is_suspicious` is a real stored/manual review flag. There is no approved risk
  score and no persisted record of rejected attempts, so the UI must say exactly
  that and show only stored flags.
- No per-page viewer-presence source exists. P06 will not fabricate viewers,
  audience reach, or unique-device analytics.
- Privacy-safe community pulse can use aggregate vote/chat/gift counts only; no
  voter, sender, IP, user-agent, or session identifiers will enter console JSON.
- The Django admin `BattleVote` changelist is the authoritative investigation
  surface; the console may link to it with a battle filter.

Implementation contract (next action):

- Replace per-battle vote count queries with bounded bulk aggregates for all
  console battles.
- Produce per-participant totals and percentages with zero-vote handling;
  authenticated/anonymous aggregate counts; tie and deadline-based completion
  readiness; stored suspicious count and a newest-first queue capped at 20.
- Produce a UTC, 15-minute vote series for the trailing 24 hours. Aggregate in
  the database by minute, then fold to 15-minute buckets; never fetch raw voters.
- Add aggregate chat and battle-gift counts as community pulse. Mark unavailable
  metrics explicitly rather than estimating them.
- Extend panel 5 and polling renderer without adding write actions.
- Add focused selector/API/render/privacy/query tests, then documentation.

Expected query shape: fixed vote aggregate queries plus fixed chat/gift aggregate
queries, independent of battle count; the suspicious queue is globally capped.

## 2026-07-04 — Scope correction requested: rejected vote evidence

Status: P06 implementation remains paused while the DG-05 persistence gap is
fixed.

Problem:

- Rejected duplicate/rate-limit attempts never create `BattleVote`, so the
  promised automatic integrity evidence does not exist.
- Saving a rejected attempt as `BattleVote(is_suspicious=True)` is invalid: it
  would violate the same uniqueness constraints and could affect authoritative
  totals/winner calculation.
- Marking the previously accepted vote suspicious would misrepresent which
  action was rejected and would lose attempt-level evidence.

Planned corrective action (before any product-code change):

1. Audit existing private audit/event models and migrations for a reusable,
   privacy-safe rejected-attempt record.
2. If none fits, add a dedicated vote-integrity event model that is excluded
   from vote totals, stores only hashed request metadata, and has indexed/bounded
   investigation fields.
3. Record failed fraud gates transactionally from `battle_vote()` without
   changing public messages, eligibility, deadlines, or winner calculation.
4. Add admin visibility, retention/privacy documentation, and tests proving
   rejected attempts are recorded but never counted as votes or exposed publicly.
5. Update DG-05 documentation to describe the implemented behavior exactly,
   then resume P06 against that authoritative source.

### Corrective audit checkpoint

- No existing rejected-vote/audit model was found.
- `BattleEvent` is a general battle activity stream; overloading it with request
  fingerprints would mix security evidence with product events and lacks an
  explicit retention/privacy contract.
- Decision: add a dedicated `VoteIntegrityEvent` model. It will not reference a
  counted `BattleVote`, will store gate code plus request hashes, will be private
  to Django admin/console operators, and will use indexed battle/time/gate fields.
- The initial repository search included two invalid Windows glob paths and
  exited non-zero after returning matches; no files were changed by that command.

Next action: read the exact surrounding model/admin/migration/test conventions,
then add the model, migration, admin, endpoint recorder, and focused tests.

### Corrective implementation checkpoint

Implemented before testing:

- Added private `VoteIntegrityEvent`, separate from authoritative votes.
- Added indexed battle/time and gate fields plus hashed IP/UA/session metadata;
  no user foreign key, raw address, user agent, or internal gate reason is stored.
- Added read-only Django admin registration (no manual add/change).
- `battle_vote()` now records pre-save gate rejection and save/validation
  constraint rejection; accepted vote flow and public messages are unchanged.
- Wrapped `vote.save()` in a savepoint so an `IntegrityError` can roll back before
  the audit row is written.
- Added migration `0057_voteintegrityevent.py`.

Planned verification action:

- Add endpoint tests for anonymous duplicate and authenticated duplicate.
- Assert each rejection creates one event, accepted totals remain one, hashes are
  pseudonymised, and the public battle response does not contain audit fields.
- Run migration drift check and focused anti-abuse tests; fix failures before
  updating DG-05 documentation.

### Corrective verification checkpoint 1

- `manage.py makemigrations --check --dry-run`: PASS, no drift.
- `VoteIntegrityEvidenceTests` + `ChefBattleAntiAbuseTests`: PASS, 7/7.
- Verified authenticated duplicate -> `constraint_rejected`, one counted vote.
- Verified anonymous duplicate -> `duplicate_device`, one counted vote.
- Verified stored IP and user-agent values are 64-character hashes and neither
  gate code nor hash appears in the followed public battle response.

Planned action before full-suite verification:

- Correct DG-05 and reuse-matrix wording so documentation no longer claims a
  rejected attempt becomes a suspicious `BattleVote`.
- Add a dedicated privacy/retention note. Retention automation is not yet wired,
  so the note must not claim automatic deletion; it will identify that remaining
  requirement explicitly.
- Run the full `chef_battle` suite and Django checks after the documentation
  update. No commit or deployment is authorised.

## 2026-07-04 — P06 stopped by owner

- Owner cancelled P06 implementation and redirected work to a specification and
  prompt compliance audit of phases P00 through P05.
- The full `chef_battle` suite started for the rejected-vote correction had not
  completed when the direction changed; it will be terminated as no longer the
  active verification target.
- Existing rejected-vote correction remains uncommitted and will be evaluated as
  an audit finding. It must not be committed, migrated, or deployed until the
  owner decides whether to retain it after the P00–P05 audit.

## 2026-07-04 — Rejected-vote correction authorised for completion

- Owner authorised finishing and committing the discovered defect separately.
- P06 remains cancelled; this work is limited to making DG-05 rejected-attempt
  evidence truthful and production-ready.

Planned finalisation before commit:

- Add an explicit 90-day retention timestamp and purge management command.
- Add retention/purge tests and update the privacy report from draft/blocking to
  the implemented contract.
- Re-run migration drift, focused tests, Django checks, and the full
  `chef_battle` suite.
- Review the diff, then stage and commit only this defect and its audit journals.

### Finalisation verification checkpoint

- Added 90-day `expires_at` retention and
  `purge_vote_integrity_events [--dry-run]`.
- `makemigrations --check --dry-run`: PASS, no drift.
- `manage.py check`: PASS.
- `VoteIntegrityEvidenceTests` + `ChefBattleAntiAbuseTests`: PASS, 8/8,
  including expiry precision and purge isolation.

Next action: run the complete `chef_battle` suite. If it passes, inspect the
final diff/status, update this journal with the result, stage the scoped files,
and create the authorised commit. If it fails, record the failure before fixing.

### Full-suite attempt 1

- Command: `manage.py test chef_battle --verbosity=1`.
- Result: FAIL, 210/215 passed; 5 pre-existing feature-gate expectation failures.
- Failures expected anonymous/regular users to receive 404 with Chef Battles
  disabled, but the local environment enabled `CHEF_BATTLE_ENABLED`, producing
  200/302. The failing tests are `ChefBattleAccessTests` (4) and
  `NotificationsPollViewTests.test_poll_requires_login` (1).
- None of the failures exercise `VoteIntegrityEvent`, vote persistence, the new
  migration, admin, or purge command. No product-code change will be made for
  these environment-dependent failures.

Next action: rerun the same complete suite with the intended baseline explicitly
set as `CHEF_BATTLE_ENABLED=False`. Record that result before diff review/commit.

### Full-suite attempt 2

- Command used explicit `CHEF_BATTLE_ENABLED=False` baseline.
- Result: FAIL, 213/215 passed. Both failures were in the newly added endpoint
  tests because their class did not explicitly enable Chef Battles; requests
  were correctly guarded with 404 and no vote was created.
- Product behavior is correct. Test isolation must be fixed by applying
  `override_settings(CHEF_BATTLE_ENABLED=True)` to the new test class.

Next action: add the missing test override, rerun the focused class under the
disabled baseline, then run the complete suite once more before commit.

### Test-isolation correction

- Added explicit `CHEF_BATTLE_ENABLED=True` to `VoteIntegrityEvidenceTests`.
- Focused class under process baseline `CHEF_BATTLE_ENABLED=False`: PASS, 3/3.

Next action: final complete suite under the disabled baseline. Commit is allowed
only after this run and final diff review succeed.

### Final verification result

- Complete command: `CHEF_BATTLE_ENABLED=False manage.py test chef_battle`.
- Result: PASS, 215/215 tests in 420.083 seconds.
- Django system check: no issues.
- Expected fraud-gate warnings were emitted by negative-path tests only.

Next action: final `git diff --check`, scoped diff/status review, then stage and
commit the rejected-vote evidence fix. No deployment or P06 implementation.

### Final diff review

- `git diff --check`: PASS (line-ending conversion warnings only).
- Scope contains only vote-integrity model/migration/admin/endpoint/retention,
  focused tests, corrected DG-05 documentation, privacy report, and worklogs.
- No P06 panel/read-model implementation and no unrelated user changes found.

Next action: stage the reviewed scope and create the owner-authorised commit.
