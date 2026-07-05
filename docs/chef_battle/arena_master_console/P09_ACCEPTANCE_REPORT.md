# P09 Acceptance Report — Arena Master Console (final phase)

Produced: 2026-07-05 · Status: complete, pending owner acceptance

## The console, end to end

`/chef-battle/master/` — a single-page operator deck behind the DG-01 gate
(superuser + owner/flag; 404 otherwise; owner always has access). One state
endpoint (`master/state/`, 20 s poll), one audited write endpoint
(`master/action/`).

| Panel | Contents | Writes |
|---|---|---|
| Overview | battle status + countdown, chef cards, live arena ring (shared renderer), audience card, crown | — |
| Phase rail | 7 steps, server-driven active step | — |
| 1 Arena Control | Start Phase, Lock Ingredients, Open Vote, Broadcast, Emergency Stop, Resume, End Battle; Award Crown permanently disabled (audience decides) | owner |
| 2 Live Monitor | battle/challenge counts, live event log (incl. audit entries) | — |
| 3 Combat Engine | rounds, hits, declared actions, biathlon locks/shots, artifacts in use | — |
| 4 Moderation & Safety | cooking queue with per-entry state, DSA reports, live streams with safety data | owner (entry/report/stream) |
| 5 Voting Integrity | percentages, UTC vote series, enforcement evidence, suspicious queue, tie/readiness, pulse | — |
| 6 Economy | token flows by type, gift catalogue+delivery, artifacts, orders | — (none approved) |
| 7 Governance | CBR/LSR matrix, payout queue, battle reports, ledger chain status | operators: report; owner: payout |
| 8 Ranks/Authority | enrolled/online/suspended counts, rankings link | — |

## P09 hardening applied

- Stale-poll guard (monotonic sequence) — late responses cannot overwrite
  newer state.
- `verify_chain()` re-scan only when the LedgerEvent count changed or 60 s
  elapsed (was full-table scan every 20 s poll); added rows are caught
  immediately, in-place edits within 60 s.
- Keyboard focus outlines (`:focus-visible`) on all console controls;
  `role="status" aria-live="polite"` on the system-status line;
  `prefers-reduced-motion` already disables all console transitions.
- No dead placeholders remain: every panel renders real data or an explicit
  honest empty/unavailable state; every button has a real action, permission
  gate, confirm dialog stating consequences, disabled explanation, and
  error surfacing (`#amc-action-error`).

## Verification pass 1

- Focused console suites: Access 12, State 17, Action 22, Monitor 9,
  Moderation 10, VotingAnalytics 9, Economy 8, Governance 9 = **96 console
  tests**, plus post-audit regression tests; `chef_battle` app total
  **245/245**.
- `manage.py check` clean; `makemigrations --check` no drift;
  `node --check` on console JS clean.
- Viewports 1920×1080 / 1440×900 / 1280×800 / 375×812: no body overflow, no
  clipped panels, ring renders 200 cells, no console errors.

## Verification pass 2

- Full project test suite run: **1164 tests, all apps**. The only two
  failures were pre-existing stale tests unrelated to the console, both
  fixed in this phase per the fix-side-issues rule:
  1. `sponsors` — asserted an outdated legal-copy sentence on the public
     sponsor page (copy had been updated in the template);
  2. `accounts` — asserted the pre-ea6a599c contract (superuser may now
     manage other superuser accounts by explicit owner decision; the test
     now asserts the new contract AND that the owner account remains
     untouchable even for superusers).
  Re-run of the affected apps + governance suite after fixes: 230/230 OK.
  chef_battle cross-suites (tokens, Stripe, VAT, fraud, age, ledger, crown,
  ranking, moderation, agreements) included.
- Role matrix enforced by tests: anonymous 404, regular chef 404,
  non-superuser moderator 404, superuser-without-flag 404, flagged operator
  read-only + report-only, owner full; suspended/fraud gates untouched
  (existing suites).
- Public arena regression: byte-frozen JSON keys, mobile check, popup/
  tooltip markup present, no `amc-` leakage.
- Security review: docs/…/P09_SECURITY_REVIEW.md.
- Performance: docs/…/P09_PERFORMANCE_REPORT.md (37 queries / 4.0 KB /
  24 ms at 1 battle).

## Release gate

- `CHEF_BATTLE_ENABLED` remains OFF on production (untouched).
- Rollout/rollback/incident procedures: P09_ROLLOUT_ROLLBACK.yaml.
- Deployed dark: console reachable only by the owner on production.
- **Awaiting owner acceptance of P09 to close the 10-phase plan.**
