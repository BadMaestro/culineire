# G01 — release gate evidence, against contract §14

**Card:** G01, Release gate. **Prerequisites** (A19, B03, R02) all DONE.
**This document is evidence, not a sign-off.** Per the card's own acceptance
criteria, closure needs the Owner's word — nothing here grants that.

Gathered 2026-08-09/10, against production v2.5.976, commit `e5a022ac`.

## 0. Base and regression

- `origin/main` HEAD = production HEAD = `e5a022ac`, footer v2.5.976. Verified
  by footer curl and server `git rev-parse`, not assumed.
- `manage.py makemigrations --check --dry-run`: no changes detected.
- Full suite, PostgreSQL, `--parallel 8`: **1797/1797 non-skipped tests green**,
  2 skipped. First run was RED — one real defect, not a flake:
  `test_the_arena_boards_baseline_matches_the_footer_too` caught the
  `design-arena` stage's commit field six releases stale (v2.5.960 shown
  against v2.5.974 shipped) and the markdown board's own baseline two
  releases stale. Both fixed (v2.5.976), full class rerun green. This is
  itself G01 evidence: the gate found a real drift before being asked to.

## 1. Access policy

`chef_battle/access.py::is_battle_visible` — Chef Battles is visible when
`CHEF_BATTLE_ENABLED` is True (not yet — public launch switch) OR the user is
`is_staff` (superuser accepted defensively). `chef_battle_guard` decorator
raises `Http404` otherwise and is applied to every chef_battle view.
`CHEF_BATTLE_ENABLED = env_bool("CHEF_BATTLE_ENABLED", default=False)` in
`config/settings.py:342` — confirmed off by default. Test coverage:
`ArenaBuildPlanTests.test_anonymous_gets_404`,
`test_plain_author_still_gets_404`, plus the chef_battle access-gate suite.

## 2. Responsive / keyboard / screen-reader / reduced motion

A18 (`recipes/views.py` `ARENA_DESIGN_TASKS`): measured on production at
1280x800 and 1920x1080, 2026-08-07. No horizontal overflow at either width.
One overflow defect found and fixed in v2.5.861 (header-height measurement).
**Open, named honestly in that same record and not fixed since:** only 2 of
the first 6 focusable deck controls show a focus ring, and rank chips render
at 9.2px, both flagged as too small for a legibility/contrast check. Reduced
motion is covered by `@media (prefers-reduced-motion:reduce)` rules audited
in the AN normalisation report but not re-measured here.

**This category is not clean.** The two A18 gaps above are real and
unresolved; G01 does not fix them, it reports them.

## 3. State and action parity

A17 (`docs/chef_battle/ARENA_TRUTHFUL_STATE_MATRIX.md`): seven states measured
on live production (not read off code) between v2.5.848 and v2.5.873 - no
battle, PENDING, ACCEPTED, both Ready, BEGUN, CANCELLED/VOID, no-battle
fighter-pads. Two deliberate payload/screen splits documented rather than
hidden (a begun battle still lists both chefs in the `rings` payload,
client-side `isDisplaced` removes them; `in_battle` is true from acceptance,
not from start - the Owner's own ruling, not a defect).

## 4. Vote and reveal integrity

Real, layered test coverage in `chef_battle/tests.py`: self-vote blocked at
validation (`test_gate_self_vote_fails`) AND at the database constraint
(`test_database_rejects_a_self_vote_written_straight_through_save` -
survives a write that skips validation entirely). Duplicate authenticated
vote raises an IntegrityError. Anonymous vote cannot be created and is
rejected without recording anything. Combat entries stay hidden
(`is_revealed=False`) until both sides have submitted
(`test_entries_hidden_before_reveal`,
`test_reveal_entries_if_ready_reveals_when_both_submitted`,
`test_reveal_does_not_trigger_with_only_one_entry`).

## 5. Moderation

`ArenaMasterModerationTests` (chef_battle), `ModerationPanelRoleTests`
(recipes) - role gating (staff/superuser tiers, `is_moderator()`), deployment
journal visibility restricted to staff, panel links verified reachable.

## 6. Production migration readiness

`makemigrations --check --dry-run`: no changes detected against the current
model state. `migrate --noinput` runs clean on every deploy this session
(v2.5.962 through v2.5.976, six deploys, zero migration failures).

## 7. Staff console compatibility

Covered by the AN normalisation closure (v2.5.960): the Master Console mirror
is the SAME Arena camera component, differing only by two configuration
values (`--arena-camera-tilt`, `--arena-camera-perspective`). Guarded by
`ArenaOwnershipGuardTests`, `ArenaCameraIsOwnedByTheOctagonTests`,
`ConsoleArenaMirrorTests`, `ArenaMasterConsoleAccessTests` - all green in this
session's full-suite run.

## 8. Feature flags

`CHEF_BATTLE_ENABLED` (settings.py:342) is the public-launch flag, off by
default, independent of the Arena Master Console flag noted in the adjacent
comment. No other flag widens Chef Battles access; AGENTS.md section 8
records the one incident where this gate was accidentally widened
(`has_bearseeker_privileges` admitted too, corrected v2.5.798) and forbids a
repeat without the Owner's explicit word every time.

## 9. Legal / accounting gates — NOT CLEARED, NEEDS THE OWNER'S WORD

Real money moves through this product: `chef_battle/stripe_services.py`,
`TokenOrder`, `ProcessedTokenStripeEvent` (webhook idempotency),
`docs/chef_battle/token_economy.md` (packages purchased with real EUR via
Stripe). Technical safeguards exist and are tested
(`TokenOrderVatConsentTests`, `PayoutEligibilityTests`, both green), but
AGENTS.md section 8 excludes payment/payout/Stripe/legal from every standing
authorisation this project has ever granted an agent - explicit word, every
time, no exception. **This report does not, and cannot, close this
category. It is the Owner's alone.**

## 10. Rollback

No rollback *tag* has been cut since `rollback/pre-ar1-v2.5.708` - that
convention lapsed. The mechanism used successfully six times this session
(v2.5.962 -> v2.5.976), every time, is:

    ssh -i ~/.ssh/culineire_linode root@80.85.84.156 \
      "cd /srv/culineire/current && git reset --hard <prior-good-commit> && sudo systemctl restart unit"

Verified reachable: the prior commit at each step is named in the matching
`config/release_journal.py` entry.

## Where this leaves G01

Ten of twelve §14 categories have real, checked evidence. Two are not clean:
**A18's two open accessibility gaps** (focus rings, chip contrast) and
**§9, legal/payment, which is not an agent's to clear at all.** G01 cannot be
marked DONE on this report alone - the acceptance criteria says the Owner
signs off, and that is unchanged here.
