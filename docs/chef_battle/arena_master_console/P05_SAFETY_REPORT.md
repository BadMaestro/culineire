# P05 Safety Report — Moderation, safety and live-stream operations

Produced: 2026-07-04

## What shipped

- **Read models** (`get_master_moderation_detail`, merged into the
  `moderation.detail` section of the console state): cooking queue with
  per-entry moderation state, pending content reports, live-stream sessions
  with broadcast safety state (moderation status, safety delay, report count,
  checklist confirmation, Live Battle Agreement presence).
- **Owner-only actions** (via the existing `master_action` endpoint):
  - `moderate_entry` — approve/flag/reject/needs_changes on BattleEntry,
    reason mandatory for adverse outcomes, chef notified.
  - `review_report` — reviewed/actioned/dismissed on ContentReport, note
    mandatory.
  - `end_stream` — LiveStreamSession → TERMINATED + LiveBroadcast
    `stopped_by_staff`, reason mandatory, chef notified. **Honest about the
    provider:** no provider API exists (ENABLE_LIVE_VIDEO off), so the
    response, the audit payload and the UI prompt all state
    `provider_side_terminated: false`. Nothing is simulated.
- **UI:** panel 4 shows the three lists with per-row owner action buttons;
  non-owners see the same data read-only (no buttons rendered).

## No fabricated detection

The safety checklist display uses only real fields: `checklist_confirmed`,
`safety_delay_enabled`, `agreement_signed`, `report_count`. No automated
minors/copyright/alcohol detection exists in the repository and none is
claimed.

## Verification pass 1 — `ArenaMasterModerationTests` (10/10)

Read-model contract (queue/reports/streams incl. agreement flag); owner
approve with audit payload; adverse action requires reason + notifies chef;
invalid/same status 409; flagged operator 403 with no state change; report
review requires note, sets reviewer fields; invalid report status 409;
end_stream updates session+broadcast, honest provider flag in response AND
audit, chef notified; ended/reason-less stream rejected; **privacy test**:
moderation note text absent from public arena JSON and battle page.

## Verification pass 2

- Full `chef_battle` suite green with default flags (212 tests: moderation,
  content report, age, fraud, suspension, agreement, permission, flag
  regressions included).
- Query budget test updated with documented history (20 fixed + ~4/battle,
  bound 35 — operator-only endpoint).
- Live console check: honest empty states for queue/reports/streams, no
  overflow, no console errors; public arena unchanged.

## Post-audit correction (2026-07-05)

The console no longer trusts the unsynchronised `LiveBroadcast.report_count`
counter. It aggregates the authoritative `LiveBroadcastReport` relation for each
listed broadcast. A regression test sets the legacy counter to 99, creates two
real reports, and verifies that the console displays 2.

Cooked-photo moderation now follows the real lifecycle: uploads remain in
COOKING with PENDING review state, the console queue includes those battles, and
PRESENTATION begins only after both confirmed photos are owner-approved. Malformed
action identifiers return JSON 400, and paused cancellation clears all pause
fields. Verification: 36 P03/P05 plus 20 timer/voting/state tests passed.

## Deployment

No migrations. collectstatic required (console JS/CSS).
