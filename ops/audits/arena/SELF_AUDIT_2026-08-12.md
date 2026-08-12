# Self-directed audit, 2026-08-12 — F67-F75

**Raised by:** Bolt, on the Owner's direct order after F58-F66 shipped —
"ПРОВЕДИ СВОЙ СОБСТВЕННЫЙ ПОЛНЫЙ АУДИТ" — following three rounds of
external independent audits that each found the previous round's fixes
still incomplete, including bugs in the same day's own fixes.

**Method:** five parallel agents, each briefed with everything the three
prior external rounds had already taught this session — do not trust an
"already fixed" comment, read full functions not snippets, state concrete
triggers not hypotheticals, report what was checked-and-confirmed-fine
alongside what was found:

1. Concurrency / locking sweep
2. Payments / Stripe sweep
3. Battle state machine / game-logic sweep
4. Permissions / access-control sweep
5. Dead code / docs / contract-compliance sweep

Every finding below was personally re-verified against the actual code
before being fixed — the same discipline this session applied to every
external report, now applied to my own agents' output too.

**Shipped as v2.5.1016**, commit `802631c2`. 33 new tests, 137 focused
regression tests green, zero regressions. No migration.

---

## CRITICAL

### F67 — `battle_set_ready` had no lock at all

`chef_battle/views.py`. Two chefs pressing "Ready" in the same window —
exactly when both would click — each read the other's flag as still
`False` at their own unlocked fetch and saved it back unchanged.
Whichever request committed second silently overwrote the first chef's
real click back to `False`. Since the view refuses any POST once status
leaves `SCHEDULED`, that chef had no way back in, and the grace period
expired into an unearned walkover for the other side.

**Fix:** wrap the view in `transaction.atomic()`, lock the battle row,
re-read both ready flags from the locked row before deciding anything.

**Test:** `BattleSetReadyLocksTheRowTests` — `FOR UPDATE` asserted on the
battle row via captured SQL (a genuine two-connection race; cannot be
reproduced sequentially, same convention as F39/F40).

### F68 — a battle past its 48h submission clock could skip combat, biathlon and cooking entirely

`chef_battle/services.py` (`handle_no_show_battles`, `reveal_entries_if_ready`).
"Submitted" meant only that a `BattleEntry` row exists — and both are
auto-created (at `accept_challenge` / `battle_recipe_attach`) long before
combat even starts. Once the 48h `submission_deadline` passed while a
battle was still `MENU_LOCKED` or `ACTIVE` — plausible for two humans
playing asynchronously, since combat carries no per-round deadline — both
functions independently jumped the battle straight to `VOTING`, skipping
combat resolution, the ingredient biathlon and cooking. Voting then opened
on a battle with no cooked photo, no biathlon, and a `winner`/`loser`
possibly never set. Near-deterministic, not a race — a leftover from a
simpler recipe-submission format that predates the combat/biathlon/cooking
pipeline and was never updated when that pipeline landed.

**Fix:** `handle_no_show_battles` now cancels a `MENU_LOCKED`/`ACTIVE`
battle past its deadline (no reward, no penalty — both chefs are
genuinely engaged, so it is not theirs to lose), the same call F20's
`void_stalled_battle` already makes for a phase stuck past `end_time`.
`reveal_entries_if_ready`'s `ACTIVE` branch no longer advances on
`deadline_passed` alone — only once both dishes are genuinely submitted.

**Test:** `NoShowSweepDoesNotSkipCombatBiathlonAndCookingTests`.

### F71 — approving a payout only re-checked `payout_blocked`, not `is_suspended` or `fraud_flag`

`chef_battle/services.py` (`approve_payout_request`). `check_payout_eligibility`
gates a **new** request on all three of `is_suspended`, `fraud_flag` and
`payout_blocked`. F60 (earlier the same audit arc) brought the
approval-time re-check up to `payout_blocked` only, following the specific
finding as reported at the time. A chef suspended or fraud-flagged
**after** submitting a request still sitting `PENDING`/`UNDER_REVIEW`
sailed through untouched — at the exact point that sends real money.

**Fix:** added the same `is_suspended` and `fraud_flag` checks at approval
time.

**Test:** `ApprovePayoutRechecksSuspensionAndFraudFlagTests`.

### F74 — a Stripe refund/dispute webhook arriving before its own checkout-completed webhook was silently and permanently dropped

`chef_battle/stripe_services.py` (`_handle_charge_refunded`,
`_handle_charge_dispute`). Stripe does not guarantee webhook delivery
order. Both handlers look up their `TokenOrder` by `stripe_payment_intent_id`,
which is only ever written by `_handle_checkout_completed`. If Stripe
delivers (or redelivers) `charge.refunded`/`charge.dispute.created` before
that event lands, the lookup fails. The old code returned `None`, which
looked like success: `handle_stripe_event` had already recorded the
event's id in `ProcessedTokenStripeEvent` in the same transaction before
calling the handler, so a 200 response permanently marked the event done
and Stripe never resent it. The refund/dispute was dropped forever, and
the customer kept tokens Stripe had already taken the money back on.

**Fix:** both handlers now raise `TokenPaymentVerificationError` instead
of returning `None`. The raise rolls back the whole transaction — the
`ProcessedTokenStripeEvent` dedup row included — so the view returns a
non-2xx response and Stripe's own retry schedule (up to 3 days) gives the
ordering time to resolve.

**Test:** `StripeWebhookOrderingDoesNotSilentlyDropRefundsTests`.

---

## HIGH

### F70 — five places mutated a chef's profile without locking the row first

`chef_battle/services.py` (`refuse_challenge`, `_award_walkover_win`,
`_void_battle_no_show`, `_award_forfeit_win`), `chef_battle/withdrawal_service.py`
(`resolve_withdrawal`). `_score_battle` already locks both chef profile
rows (F27), with its own comment stating why: "a chef can be in more than
one battle at once... two battles finishing at once take different
battle locks... lock both profile rows here." That reasoning never
reached these five call sites, each of which read-modified-and-saved a
`ChefBattleProfile` (rating/reputation/wins/losses/win_streak) with no
lock at all.

**Fix:** new shared helper `_lock_battle_profiles(*authors)` — locks one
or more profile rows, ordered by pk (matching `_score_battle`'s own
pattern to avoid deadlocks), returns them keyed by author id. All five
call sites now fetch through it before mutating.

**Test:** `UnlockedProfileMutationsAreNowLockedTests` — `FOR UPDATE`
asserted against `chef_battle_chefbattleprofile` for all five sites.

### F72 — rejecting one payout could release a reward record reserved for a different payout

`chef_battle/services.py` (`reject_payout_request`). The query used
`status_note__contains=f"PayoutRequest #{payout.pk}"` — an unanchored
substring match. `"PayoutRequest #1"` is a substring of
`"PayoutRequest #10"`, `"#11"`...`"#19"`, `"#100"` and so on. Rejecting
payout #1 could therefore also release reward records reserved for any
other payout whose id happened to start with the same digits, corrupting
the F61 reservation guarantee for a payout the rejection never touched.

**Fix:** exact match against the full note text `create_payout_request`
writes (`"Locked for PayoutRequest #{pk}"`), matching the anchoring
`expire_rewards`/`reverse_reward` already use (`startswith` the full
prefix).

**Test:** `RejectPayoutRequestDoesNotFreeUnrelatedPayoutsTests`.

### F73 — `PayoutRequest.status` was directly editable in Django admin, bypassing every service-layer safeguard

`chef_battle/admin.py` (`PayoutRequestAdmin`). `status`, `reviewed_by`,
`reviewed_at` and `paid_at` were plain editable fields on the change form.
Any staff user with change permission could hand-type `"paid"` straight
into `status`, bypassing `approve_payout_request`/
`_execute_stripe_connect_transfer` entirely: no Stripe transfer, no
`is_suspended`/`fraud_flag`/`payout_blocked` check, no `RewardRecord`
transition, no ledger event — a record could be marked paid with no money
ever having moved, or approved for a chef every other gate would refuse.

**Fix:** `status`/`reviewed_by`/`reviewed_at`/`paid_at` added to
`readonly_fields`. The existing actions (which call the service
functions) remain the only way to move a payout forward.

**Test:** `PayoutRequestAdminStatusIsReadOnlyTests`.

---

## MEDIUM

### F69 — `submit_cooked_photo` was the one function in its phase with no battle lock

`chef_battle/services.py`. Every sibling function in the cooking phase
(`declare_menu`, `place_ingredient_lock`, `fire_ingredient_shot`,
`approve_cooking_phase`) locks the battle row and rechecks status under
it; this one never did. Not game-outcome corrupting on its own — the
later moderation transition re-checks status under its own lock — but a
real, reachable precondition-checked-against-stale-object gap.

**Fix:** lock the battle row inside the existing `transaction.atomic()`
block, recheck `status == COOKING` under the lock before writing the
entry.

**Test:** `SubmitCookedPhotoLocksAndRechecksBattleStatusTests`.

---

## LOW

### F75 — the profile edit page's "Become a Chef" prompt had no visibility gate

`templates/authoring/profile_form.html`. Offered "Become a Chef... join
Chef Battles" to every un-enrolled author with no `chef_battle_enabled`
check at all — unlike the identical prompt in the site header
(`recipes/context_processors.py`), which already gates on it. Same drift
class already closed four times this session (F8/F16/F22/F26/F31): a
hand-written copy of the audience rule instead of a call to the
centralised one.

**Fix:** wrapped the existing `{% if not author.battle_profile.enrolled_at %}`
block with `and chef_battle_enabled`.

**Test:** `ProfileFormBecomeAChefIsGatedTests`.

---

## Checked and confirmed fine (not filed as findings)

- **Concurrency agent:** combat (`submit_combat_action`), the ingredient
  biathlon, cooking→presentation handoff, cron sweeps, admin bulk actions,
  the withdrawal service's own locking (F51/F46/F36/F29), reveal-flag
  consistency, vote integrity — all confirmed still correctly locked from
  prior rounds.
- **Game-logic agent:** menu declaration, combat's own round resolution,
  the ingredient biathlon's lock/shot count checks, the cooking→presentation
  handoff, every cron sweep, admin bulk actions, the withdrawal service,
  emulation-vs-chef-action serialisation, reveal-flag consistency, vote
  integrity — all independently re-checked and confirmed sound. One
  design note (not a bug): a `SCHEDULED` battle with a future `start_time`
  skips `MENU_LOCKED` by design (`_begin_combat`), confirmed intentional
  by an existing passing test.
- **Dead-code/docs agent:** `docs/ARENA_BATTLE_PLAN.md`'s §3/§5 no longer
  contradict each other (F57/F66 hold); `docs/chef_battle/ARENA_DEAD_CODE_AUDIT.md`'s
  claims about `hydrateFixtures()` and every listed static file checked
  out; zero duplicate CSS/JS loads found project-wide; zero dead
  Python/JS functions found; every contract-number spot check (submission
  deadlines, moves economy, rank thresholds, token packages, withdrawal
  penalty, artifact gift pricing, rank labels) matched the code exactly.

## Left for the Owner, not fixed

- **Unconditional Chef Battle marketing copy on `home.html`/`about.html`/
  `signup.html`** — may be a deliberate teaser rather than a leak; a
  product call, not a bug this audit gets to invent an answer to.
- **Duplicate version number `2.5.850`** in `config/release_journal.py`'s
  own history (two entries, both dated 2026-08-07, both `"commit": ""`).
  Both pre-date this session's commit-hash discipline (every entry from
  v2.5.900 onward carries a real hash); with no hash on either side there
  is no way to determine which is the real v2.5.850, and editing the
  historical record blind would corrupt it further than leaving the
  duplicate stand. Flagged here rather than silently resolved.
