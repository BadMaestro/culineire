# P00 Baseline Report — Arena Master Console

Produced: 2026-07-04 · Verified against commit `8c74f678` (main) · Phase: P00 (Discovery)

No production code, migrations, or production data were touched in this phase.
Deliverable set: this report + `P00_REUSE_MATRIX.yaml` + `P00_CONTRACTS.yaml` + `P00_DECISIONS.yaml`.

---

## 1. Query-count and payload baselines (required by phase prompt)

Measured with Django test client + `CaptureQueriesContext` on an isolated **test database**
(12 enrolled chefs, no active battle). No production reads or writes.

| Endpoint | Scenario | Queries | Payload | Status |
|---|---|---|---|---|
| `arena()` GET | anonymous | **15** | 47,438 bytes | 200 |
| `arena()` GET | authenticated chef | **21** | 51,531 bytes | 200 |
| `arena_state()` POST | anonymous | **7** | 4,473 bytes | 200 |

`arena_state` JSON keys confirmed: `center`, `latest_result`, `rings`, `spectators`.

Regression rule for later phases: console work must not increase these counts for the
**public** endpoints. The operator endpoint gets its own budget measured in P02.

## 2. Baseline screenshots — blocked, needs owner input

The phase prompt requires screenshots of the current Arena at 1920×1080, 1440×900,
1280×800 and one mobile viewport. This is blocked in the current environment:

- Project rule: no local dev server (owner tests on production only).
- On production, `CHEF_BATTLE_ENABLED` is dark-launched; the arena requires an
  authenticated session, and the agent may not log in with credentials.

**Proposed resolution:** owner captures the four screenshots (or grants a session),
or accepts the reference image + this code-level baseline as sufficient for P01.
Everything else in P00 is complete without them.

## 3. Verification pass 1 — implementation paths re-opened

Every capability cited in `01_CAPABILITY_MAP.yaml` was re-verified against the live repo:

- **Views** — all 19 cited views exist at verified lines (`arena`:888, `arena_state`:1027,
  `arena_ping`:1014, `arena_battle_popup`:749, `battle_vote`:1363, `battle_combat_action`:1558,
  `battle_state_poll`:1598, `biathlon*`:1651–1698, `cooking_moderation*`:1700–1758,
  `battle_chat_*`:1771–1817, `battle_set_ready`:2291, `rankings`:1430, `hall_of_fame`:1760,
  `chef_battle_profile`:1932). Helpers `_arena_center`:710, `_arena_latest_result`:840,
  `_get_spectators`:862 confirmed.
- **Services** — all 28 cited service functions exist (see reuse matrix line references).
- **Models** — all 29 cited models exist, including `LiveBattleAgreement`,
  `ProcessedTokenStripeEvent`, hash-chained `LedgerEvent`.
- **Vote integrity** — both `UniqueConstraint`s confirmed at `models.py:289-300`;
  `is_suspicious` + `moderation_note` fields confirmed.
- **Operator foundations** — `BattleEvent.EventType.OPERATOR_ACTION` (migration 0054)
  and `Battle.Status.PAUSED` (migration 0055) both committed and deployed.
- **Test coverage** — all 20 focused test classes from the capability map exist in
  `chef_battle/tests.py`. **Gap recorded:** no focused tests for live-stream termination.

## 4. Verification pass 2 — scenario walk-through

| Scenario | Current behavior | Console impact |
|---|---|---|
| Anonymous visitor | Arena readable when flag on; ping → 401; cannot vote twice per device (constraint) | Console URLs → 404 |
| Spectator (authenticated, not enrolled) | ping updates nothing (enrolled filter); appears via `_get_spectators` | 404 |
| Chef (enrolled) | full arena + battle participation | 404 unless superuser+flag |
| Moderator without flag | cooking moderation only | 404 on console (DG-01) |
| Superuser without flag | Django admin only | 404 on console (DG-01) |
| Operator (superuser + flag) | n/a today | read-only console + reports |
| GreenBear | owner protections in recipes moderation | full console authority |
| Suspended chef | excluded from rings (`is_suspended=False` filter, views.py:1049) | shown in console with suspended state |
| Feature flag off | `chef_battle_guard` blocks all | console flag independently 404s everything |

Duplicate-implementation search (admin.py, services.py, views.py, signals, management
commands, templates): no duplicates found; live-stream controls exist **only** in admin —
confirmed the capability map's warning.

## 5. Stale assumptions identified

1. **`battle_lifecycle.md` status table is outdated.** Real `Battle.Status` has 13 values
   (`scheduled`, `menu_locked`, `active`, `awaiting_submissions`, `revealed`, `cooking`,
   `presentation`, `voting`, `completed`, `ingredient_penalty`, `paused`, `cancelled`,
   `disputed`). `declared`/`accepted` belong to `BattleChallenge`, not `Battle`. Code wins.
2. `P00_DECISIONS.yaml` noted migration 0055 as "pending" — it is now deployed.
3. Capability map omits `arena_blast` view (views.py:882) and `DISPUTED` status.
4. Mockup numbers (viewer counts, token totals, percentages) are illustrations only —
   every displayed count now has a real-query definition in `P00_CONTRACTS.yaml`.

## 6. Decision gates

All six gates **resolved** in `P00_DECISIONS.yaml` (owner-recorded 2026-07-04):
DG-01 access model · DG-02 GreenBear-only transitions · DG-03 Emergency Stop spec ·
DG-04 real presence viewers · DG-05 automatic suspicion + tie rule · DG-06 review-and-report.

## 7. Feature-flag and permission boundary proposal

- New `ARENA_MASTER_CONSOLE_ENABLED` flag, default **False**; independent of
  `CHEF_BATTLE_ENABLED`; off ⇒ 404 for everyone.
- Access gate: superuser AND (OWNER_SLUG OR `has_arena_console_access`); failure = 404.
- Public arena contract frozen (section 1 of `P00_CONTRACTS.yaml`) — console is additive only.

## 8. Readiness status for P01

**READY**, with one open item:

- ✅ Reuse matrix complete (8 panels, every metric/action mapped or marked gap).
- ✅ Contracts frozen (public + operator read model + write map).
- ✅ All decision gates resolved.
- ✅ Both verification passes recorded.
- ✅ No production code or migration added in P00.
- ⚠️ Baseline screenshots pending owner action (section 2). P01's visual work should
  not start its screenshot comparison step until this is resolved.

Token usage estimate for P00 (both sessions): ~90k of 100k working budget.
