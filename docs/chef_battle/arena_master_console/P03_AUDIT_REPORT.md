# P03 Audit Report — Arena control and battle-flow orchestration

Produced: 2026-07-04

## What shipped

- **Model:** `Battle.paused_at`, `paused_reason`, `paused_from_status`
  (migration `chef_battle/0056`) per DG-03.
- **Services** (`chef_battle/services.py`): `operator_force_status`,
  `operator_emergency_stop`, `operator_resume`, `operator_cancel`,
  `operator_broadcast`, plus `OperatorActionError`. All owner-only
  (`_require_owner`), transactional with `select_for_update`, stale-state
  guarded via `expected_status`, audited via `BattleEvent OPERATOR_ACTION`
  with correlation id and before/after state.
- **Endpoint:** `POST /chef-battle/master/action/` — console gate + early
  403 for non-owners + CSRF; JSON errors 400/403/404/409.
- **UI:** owner sees 8 controls with consequence-stating confirm dialogs;
  Award Crown permanently disabled ("crown is decided only by audience
  voting"); non-owner operators see an explicit "Read-only access" panel
  with the DG-02 explanation — no dangerous control is ever rendered as
  apparently usable. Countdown shows PAUSED for paused battles.

## Reuse audit results (no duplicate logic)

| Needed capability | Reused implementation |
|---|---|
| ingredient_penalty → cooking | `approve_cooking_phase` (called by the force path) |
| voting/active → completed | `calculate_battle_result` (votes, rating, crown, rewards) |
| Cancellation semantics | `handle_no_show_battles` pattern (CANCELLED + result_reason + event) |
| Chef notification | existing `_notify_chef` (in-site Message + email) |
| Stream termination | `LiveStreamSession` state machine (TERMINATED + reason + terminated_by) |
| Audit trail | existing `create_battle_event` + OPERATOR_ACTION type (migration 0054) |

No console view mutates `Battle.status` directly — all writes go through the
operator services; direct assignment exists only inside
`operator_force_status` for transitions no service owns, per DG-02.

## Verification pass 1

- `ArenaMasterActionTests`: **22/22** — permissions (anon 404, flagged
  operator 403 with no state change, GET 405), force transition + full audit
  payload assertions, stale `expected_status` 409, repeated click produces
  exactly one audit event, same-status and invalid targets rejected,
  service-owned transitions verified (`service_used` in payload), Emergency
  Stop full behavior (PAUSED + fields + stream TERMINATED + 2 chef messages
  + audit), reason required, paused/completed guards, resume restores
  pre-pause status and clears fields, cancel semantics, broadcast public
  event, per-role console rendering.
- `manage.py check` clean; migration 0056 applied.

## Verification pass 2

- **Live end-to-end (local dev, owner session):** Emergency Stop via the real
  endpoint → state poll showed `is_paused=true`, `paused_battle_count=1` →
  Resume → battle back to `scheduled`. No console errors.
- **Full suite:** `chef_battle` **193/193** with default flags — all
  participant/spectator flows intact.
- **CSP finding fixed in passing:** inline `window.AMC_OPERATOR` (and the
  ring partial's `ARENA_VIEWER`) lacked the CSP nonce, so strict-CSP
  environments silently dropped them. Both now carry
  `nonce="{{ request.csp_nonce }}"` like every other inline script on the site.

## Post-audit correction (2026-07-05)

Emergency Stop now preserves server-authoritative time: on resume,
`submission_deadline`, `voting_deadline`, and `end_time` are extended by the
measured pause duration inside the locked transaction. The resume audit payload
records that duration and the shifted fields. Focused P03/P05 regression suite:
32/32 passing; no migration required.

## Deployment

- Migration required: `chef_battle/0056` (3 nullable/blank columns — safe).
- collectstatic required (console JS changed).
- Production risk: controls unreachable for everyone except the owner;
  console itself still 404 for all non-owner users.
