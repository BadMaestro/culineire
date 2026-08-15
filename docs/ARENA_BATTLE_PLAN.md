# Arena Battle Plan — Design Arena integration onto `main`

**Status:** ACTIVE. This file and the moderation build board are the dispatch
contract for the Arena. The Owner gives an agent **one card at a time**. The
agent returns its exact commit, files, visible result, checks and evidence.

Last reconciled: 2026-08-15 · Production baseline: **v2.5.1068**

## Ember handoff closure — 2026-08-15

- T18 release target: `v2.5.1037`; the former local-only handoff is closed by
  this release.
- `39bcad61` corrects T11 by Owner ruling: both chefs place two hidden blocks
  before Stage 1; only the Stage 1 winner gets three shots; the loser never
  shoots. The old sequential 48-hour windows are superseded.
- `4c2bc842` implements T18, GreenBear-only Mute/timed Block/Delete controls on
  Arena chef cards. Delete removes login and personal data while anonymising
  mandatory history. Migration `0096` is additive. Local PostgreSQL regression:
  33/33 PASS; Django, migration, JS, image-weight and diff checks green.
- T11 documentation and T18 are shipped together in `v2.5.1037`; T11 remains a
  corrected specification, not a claim that the combat mechanic is implemented.
- T18 does not yet implement the separate Owner-avatar contract: GreenBear may
  appear and join clans/alliances cosmetically, adds only a clan reputation
  blessing, and must be excluded from challenges, battles and every competitive
  aggregate. Record/build that invariant separately rather than expanding T18.

**OWNER BRIEF, 2026-08-12 — seventeen tickets, T01–T17, on the board and mine
alone.** Delivered on the Carpet as message #3509 and dispatched by him with
one instruction: create every card first, then start. They close the classes
his last audit named — illegal `Battle.status` transitions, stale-object
resurrection, lost concurrent updates, money and reward-ledger integrity,
stored XSS and unsafe uploads, runtime drifting from the rulebook, and dead
code — in five packages, critical and security first.

**His rulings that bound this work, stated once here so nothing is re-litigated
in a ticket:** `CHEF_BATTLE_ENABLED` is a **one-way launch latch** — False
until launch, True after it, and never back — so **F65 is REVIEWED, NOT A BUG**
and nothing is designed around switching it off again. Stripe Dashboard work is
outside the brief; everything on OUR side of the webhook is inside it. Where he
has previously corrected the old ТЗ, the code is the decision — **but a
required feature that was simply never built is not a decision to cancel it**:
build it, or stop and ask him.

**A NUMBERING COLLISION, named so nobody trips on it.** His brief calls these
F67–F83. The board already carries F67–F75 from Bolt's self-directed audit of
the same day, and they are **different findings** — his F67 is the scorer
accepting any status, the board's F67 is `battle_set_ready` having no lock. The
cards are therefore keyed **T01–T17** to his ticket numbers, and each one cites
the brief rather than an F number.

**Three of his tickets were already partly answered by work that shipped on
2026-08-12, and the cards say so rather than claiming credit for it:** T03's
lock is in (F67, v2.5.1016) and only its two-thread barrier test is missing;
T06 has its battle lock (F69) and still needs the entry lock and the ordering
proof; T01's caller was scoped at `battle_detail` (F20, v2.5.1010) while the
scorer itself still accepts every status but COMPLETED, which is exactly the
"fixed the symptom, left the class" pattern the brief was written against.
· **G01 signed off by the Owner, 2026-08-10 — Stage 2 (Design Arena visual
integration) is CLOSED.** A18's accessibility gaps and §9 legal/payment move
to Stage 3 (release-readiness), now open. VD1 stays deliberately deferred.
**X06/X07/X08/X11 ruled by the Owner, 2026-08-10 — the running code was right
in all four cases (battle window 48h+2d voting, moves 5/5/10/1, combat moves
1-5, eight token packages); the archived docs are corrected to match, no code
changed.**
**F1-F5 fixed, 2026-08-10 — a full audit against the product contract found
three permission gaps (a stale flag leaking battle data on the public author
page, an unguarded real-money token checkout, unguarded gift/artifact sends)
and two unlocked race conditions (a no-show sweep that could double-award a
forfeit, a reward-issuance wallet update that could lose tokens under
concurrent approval). All five closed same-day.**
**GreenBear's independent audit, v2.5.989 — the menu spoke Russian in one
path, two artifact rows were spelled inconsistently, and F2/F3's guard sat
under require_POST/login_required instead of outermost, letting three URLs
announce their own existence during dark launch. All three closed.**
**F6-F10 fixed, 2026-08-11 — the medium findings from the same 2026-08-10
audit: onboarding (chef_enroll/enroll_success/age_verification) and three
battle-flow pages carried no visibility gate; Chef Battle's own moderation
views trusted a general site-moderator flag that can outlive the staff bit;
challenge rank eligibility was never re-checked at acceptance; and the
reveal flag could desync from what the template already showed under a
forced or scored transition. All five closed same-day; see the F6-F10
cards below.**
**F11/T1/T2 fixed, 2026-08-11 — the rest of the 2026-08-10 audit. F11 (low):
reward_agreement, payout_statement, battle_chest and changing_room now carry
the same visibility gate as every other page in the app. T2: five raw CSS
colour literals in arena.css that restated an existing Arena token's own
value by hand now reference the token instead. T1: user-facing text on the
public VAT/refunds page and the Master Console said "wallet" five times;
all five now say "Token Account", per contract section 9.1. The underlying
TokenWallet model keeps its name — renaming it is a schema migration on the
live Stripe payment path and stays flagged for the Owner, not attempted.
This closes every item from the 2026-08-10 audit except that model rename.**
**F12-F19 fixed, 2026-08-11 — a second full audit, re-run against the fixed
code rather than assuming the first pass still held. Two were CRITICAL: a
chef could submit their dish (and jump the battle straight to VOTING) while
combat was still running, with zero biathlon and zero moderated photo (F12);
and a challenge's opponent — the one action that actually seats a chef in a
real-money arena — was never age-verified, only the challenger was, at
creation time (F13). Three medium: the one moderation transition into
PRESENTATION reached through real photo approval missed the reveal-flag
update F10 added everywhere else (F14); the chef enrolment bonus could be
credited twice by a double-click, no row lock (F15); and the general-purpose
moderation panel showed live battle withdrawal/clan queues to any
site-moderator, the same gap F8 had already closed for the app's own
moderation views but missed here (F16). Three low: cooking_moderation
answered 403 instead of 404, the one gate in the app that confirmed its own
existence to a rejected dark-launch caller (F17); the admin's bulk
disputed-battle reset carried the same vestigial reveal gap as F14 (F18); and
a losing double-accept race surfaced a bare 500 instead of a message, though
the OneToOne constraint meant data was never at risk (F19). All eight closed
same-day. This closes every finding from both the 2026-08-10 and 2026-08-11
audits except the TokenWallet model rename, still the Owner's to authorise.**
**F20-F26 fixed, 2026-08-11 — a third full audit, this time also covering
GreenBear's own G-series work (G1, G3, G6-G12) for the first time. One
CRITICAL: a battle past its end_time was auto-scored by calculate_battle_result
regardless of which phase it was actually in — stuck waiting on a moderator's
cooking-phase approval, a cooked photo, or a presentation vote, it hit the
zero-vote tie-break and was paid a full draw to both chefs for a fight with no
combat and no moderated evidence, and since losing carries no penalty this was
strictly better than an honest loss (F20). One high, in new territory: G1's
one-slot-per-chef rule had a race across two different pending challenges to
the same chef (F21). Three medium: clan moderation gated the same way F8/F16
already closed elsewhere (F22); a written anti-fraud gate on real-money token
purchases that was never wired in (F23); season close/activate with no row
lock, letting a cron self-overlap double-fire season-end rewards (F24). Two
low: F25 was investigated and found NOT to be a bug — GreenBear's own comment
already documents the tradeoff the audit flagged, so nothing changed; artifact
image generation missing the same visibility check as F8/F16/F22 (F26). All
seven closed same-day. This closes every finding from all three audit rounds
except the TokenWallet model rename, gate_dsa_report_threshold (a moderation-
policy question, not a bug), and F24's residual cross-season race (needs a
DB constraint, not row locking) — all three still the Owner's to rule on.**
**chef_battle.css double-load cleanup, 2026-08-11 — the dead-code finding
every audit round noted but none fixed: base.html already loads
chef_battle.css once, gated on is_battle_visible; 40 templates loaded it
again in their own extra_head, on top of that. Removed from all 40 -
36 templates had nothing else in that block and lost it entirely; the four
that had more (arena_master_console.html, chef_battle/home.html,
templates/home.html, messaging/inbox.html) kept the rest. templates/home.html's
copy was additionally unconditional — no is_battle_visible check at all — so
this also stops the site homepage downloading arena CSS for a visitor the
dark launch is hiding it from. Template-only; no Python, no migration.**
**F27-F31 fixed, 2026-08-11 — a fourth full audit, told not to trust the
first three rounds' fixes and to sweep exhaustively for the is_moderator()-
without-is_battle_visible() gap that had recurred four times (F8/F16/F22/F26).
None of the five new findings were access-control gaps — that class appears
fully closed after four rounds. One high: a drawn battle's second-place
shares were saved with no lock on either chef's profile row, unlike the
decisive-win branch three lines below it, which already locks both for
exactly this reason — a chef sharing two battles finishing at once could lose
one side's update (F27). Two medium: operator_resume shifted every paused
deadline except waiting_until, the one WAITING status itself reads, so a
battle paused mid-grace-period and resumed later got walked over on the very
next sweep instead of a restarted grace period (F28); and resolve_withdrawal
read the battle off a plain (and possibly stale, cached) FK before its own
lock, so a battle that finished naturally while a withdrawal sat with a
moderator could be dragged back to CANCELLED on close (F29). Two low: a
combat artifact loadout reservation had a narrow race letting two different
artifacts slip past the three-per-type cap together, game-balance only
(F30); and the inbox's battle section hand-rolled the same check
is_battle_visible() already centralises — not exploitable, closed as
hardening against a fifth instance of the F8/F16/F22/F26 drift (F31). All
five closed same-day; 18 new tests, 62 focused tests green. This closes
every finding from all four audit rounds except the TokenWallet model
rename, gate_dsa_report_threshold, and F24's residual cross-season race —
all three still the Owner's to rule on.**
**F32/F33 fixed, 2026-08-11 — the Owner ruled on both items this same
session. F32: gate_dsa_report_threshold's docstring claimed 'logs only' while
its own implementation already returned passed=False past the threshold; his
ruling was blocking, so it is now wired into token_checkout_create and the
docstring corrected to match the code. dsa_reported_count is moderator-set
only, never automated, so this only ever fires after a human has already
logged reports against the account. F33: F24 locked a season's row against a
cron overlapping itself, but two DIFFERENT seasons activated at once could
each lock their own row and never collide - his ruling was to close it with
a database constraint rather than more application locking, since row locks
cannot serialise two different rows. A partial unique index now lets at most
one Season carry status=active; activate_season/create_season(activate=True)
turn the resulting IntegrityError into the same friendly message the
existing check already gives the common case, same pattern as F19. This
closes every finding from all four audit rounds except the TokenWallet model
rename, still the Owner's to authorise on his own timeline.**
**F34-F42 fixed, 2026-08-11 — an INDEPENDENT audit the Owner supplied found
9 real defects this session's own four internal rounds had missed entirely:
4 CRITICAL, 4 HIGH, 1 LOW, verdict 72%, release not accepted. Every finding
verified against the actual code before anything was touched; all nine held
up, and eight of the nine are concurrency races - the class this session's
own rounds believed was fully swept after F21/F24/F27/F29/F30. CRITICAL:
admin bulk actions force_reveal_entries and cancel_battles (F34/F35) each
fetched their battle queryset once and wrote every row unlocked, so a
battle a scorer completed mid-batch got silently forced back to VOTING or
CANCELLED; resolve_withdrawal (F36) never locked the BattleWithdrawal row
itself - a gap in this session's OWN F29 fix, not a first-time miss - so two
concurrent resolves could double the withdrawal penalty; send_battle_artifact
(F37) checked battle status before its transaction opened, so a battle
finishing in the gap meant a viewer's real tokens were spent for nothing.
HIGH: challenge accept/refuse/expire (F38) were not serialised against each
other, so a chef could be penalised for "refusing" a challenge simultaneously
accepted; award_moves' once-per-object and anti-farm checks (F39) had no
lock; declare_menu (F40) - the worst of the nine - computed both_declared
from two unlocked checks, so two chefs declaring within the same instant
could each fail to see the other's not-yet-committed menu and leave the
battle stuck in MENU_LOCKED forever, with no sweep able to detect or escape
it; approve_cooking_phase (F41) could resurrect a cancelled battle into
COOKING from a stale moderation-queue page. LOW: the four new G13 pages
(F42) reloaded chef_battle.css a second time, reintroducing the exact
pattern the round-3 cleanup removed from 40 other templates, because these
four were written after that cleanup ran. Fixed with the same lock-and-
recheck discipline already established this session, extended for the
first time to admin.py's bulk actions. Two findings (F39, F40) are races
between two SEPARATE connections that no sequential TestCase can reproduce
even with a stale-object simulation - closed on the locking mechanism,
proven via captured SQL. 114 focused tests green, zero regressions.**
**F43-F57 fixed, 2026-08-11 — a SECOND independent audit, run fresh against
origin/main after F34-F42 shipped: 15 more findings (4 CRITICAL, 8 HIGH, 3
LOW), verdict 69%. Two of them (F47, F48) are bugs in my own F39/F40 fixes
from hours earlier - both took the right lock and then discarded what it
returned, still reading the old unlocked object for the check that
mattered. CRITICAL: token_checkout_cancel raced the Stripe webhook's own
locked handlers (F43); approve_payout_request's Stripe transfer ran
unlocked against a concurrent reject, risking a genuine double payout (F44,
the most severe finding of this round - closed with a pre-flight recheck,
a Stripe idempotency key, and a loud CRITICAL log for the unavoidable
residual window); a refund and a dispute on the same order - two different
Stripe events - could each claw back the full amount (F45); decide_
withdrawal could reopen a withdrawal resolve_withdrawal had already closed
(F46). HIGH: F47/F48 above; challenge_create's own slot check was unlocked
unlike F21's mutex on the other side of the same rule (F49); challenge_
respond had its own unlocked expiry writer F38 never touched (F50);
request_withdrawal could open a request against an already-finished battle
(F51); reset_disputed_battles repeats F34/F35's exact shape (F52); battle
emulation had no lock at all, Owner-only exposure (F53); demo_battle --end
repeats F35's pattern, SSH-only exposure (F54). LOW: the recipe-edit
battle-lock message named Chef Battles to an AUTHOR-tier viewer who should
see nothing of it during dark launch - the block stays, only the wording
is now gated (F55); two documentation errors (F56, F57). Same lock-and-
recheck discipline throughout. Owner's ruling on the standing Stripe
deferral: it covers work needing configuration on Stripe's own dashboard,
not pure code bugs that happen to live in Stripe-adjacent files - F43/F44/
F45 are the latter and were fixed now, not deferred. 42 new tests, 227+
focused tests green, zero regressions across the full sweep.**
**F58-F66 fixed, 2026-08-11 — a THIRD independent audit found the previous
round's fixes still incomplete: 9 findings (5 CRITICAL, 1 HIGH, 1 MEDIUM, 2
LOW). Different in kind from the first two rounds: not new territory, but
proof the lock-and-recheck pattern had been applied narrowly. CRITICAL:
F58 - the paid Stripe webhook still refused to complete an order F43's own
cancel-page fix had marked CANCELLED/EXPIRED first; now a confirmed-paid
event overrides both (not REFUNDED/DISPUTED, where money already came back
out). F59 - F44 only reduced the double-payout window and logged CRITICAL
instead of preventing it; a durable PayoutRequest.PROCESSING status (one
migration, choices-only) now makes reject/hold structurally unable to act
while a transfer might be in flight. F60 - a chargeback never touched an
already-open payout request; it now holds the chef's own open payouts
directly, and approval re-checks the compliance flag as a second gate.
F61 - a reward 'locked' for a payout was reserved in name only; expire/
reverse now honour the reservation. F62 - submit_combat_action's ACTIVE
check was never re-verified under any lock, in code predating this whole
audit arc. HIGH: F63 - the identical gap, independently pre-existing in
place_ingredient_lock/fire_ingredient_shot. MEDIUM: F64 - F49 locked one of
challenge_create's two preconditions (the slot) but not the other (moves).
LOW: F65 - a sitewide cache could leak the Chef Battle promo for up to 5
minutes after the flag went off, since is_battle_visible() depends on the
viewer and can never be safely baked into a cache keyed on nothing but
time; F66 - the same doc-drift class as F57, one section earlier. Given the
pattern this round exposed, ran a full codebase sweep for every
select_for_update().get() call whose return value goes unused - found
exactly this round's set, nothing more; the season/observer/accept_
challenge mutex locks were confirmed correctly scoped (their real checks
are fresh post-lock queries, not stale field reads). 27 new tests, 73+
focused tests green, zero regressions.**
**F67-F75 fixed, 2026-08-12 — my own self-directed audit, ordered directly
after F58-F66 ("ПРОВЕДИ СВОЙ СОБСТВЕННЫЙ ПОЛНЫЙ АУДИТ"): five parallel
agents (concurrency, payments, game-logic/state-machine, permissions,
dead-code/docs), every finding personally re-verified before being fixed.
Nine held up. CRITICAL: F67 - battle_set_ready had no lock at all, so two
chefs pressing Ready together could have one click silently erased by the
other's save. F68 - a battle still genuinely being fought could be
teleported straight to VOTING once its 48h submission clock ran out,
skipping combat, the ingredient biathlon and cooking entirely - near-
deterministic, not a race, since combat carries no per-round deadline; now
cancelled instead, matching F20's own precedent. F71 - approving a payout
only re-checked payout_blocked, never is_suspended or fraud_flag, at the
exact point that sends real money. F74 - Stripe does not guarantee webhook
order; a refund/dispute event arriving before its own checkout-completed
event was silently and permanently dropped, since the old code marked it
processed before finding out it had nowhere to apply. HIGH: F70 - the F27
profile-locking pattern never reached five more places a battle's outcome
mutates a chef's profile (walkover, forfeit, void-no-show, a refused
challenge, an upheld withdrawal penalty). F72 - reject_payout_request's
unanchored substring match could release a reward record reserved for a
DIFFERENT payout. F73 - PayoutRequest.status was directly editable in
Django admin, bypassing every service-layer safeguard. MEDIUM: F69 -
submit_cooked_photo was the one function in its phase with no battle lock.
LOW: F75 - the profile page's Chef Battle prompt had no visibility gate,
the same drift class closed four times already. Two items left for the
Owner: unconditional marketing copy on home/about/signup (may be a
deliberate teaser, not a leak) and a duplicate version number found in this
project's own release history (no commit hash on either side to judge which
is real). 33 new tests, 137 focused tests green, zero regressions. NO
MIGRATION.**
Next assignable card: none in Stage 2 — it is finished.

**MC01 was built and then DELETED on the Owner's order the same day (v2.5.842).** It walked the withdrawal through the Master Console as step cards — three columns of text per step. Nothing in it was factually wrong; being a description was the problem. His words: he wants the steps seen LIVE ON THE ARENA, not read. The panel, its module, its stylesheet, its stepper and its tests are gone — no dead code left behind. What replaces it is MC02 and `docs/chef_battle/ARENA_EMULATION_VISUAL_STEPS.md`, which is a specification and never a screen: nine rows naming the one thing he must be able to SEE at each step, driven by the existing `emulation.py` (`start_emulation`, `emulation_step`) through the real services. Most rows are TO SPEC and stay that way until he says what they look like. That blocker is gone: A09 closed on 2026-08-06 - the approach in v2.5.844 and the fighter who stayed visible in v2.5.847 - so an emulated bout now has two chefs standing in it.

**Bolt's session of 2026-08-05/06, in order.** X04: the roadmap advertised five
token packages topping out at Executive 1400T/EUR80 while `token_config.py` has
eight, to Legend Chef 12800T/EUR768 — the row is derived from the catalogue now
(v2.5.819). X01: the upcoming-battles list, absent from the payload, the
selectors and the template, built and then rebuilt twice to the Owner's design —
a sub-line under the phase steps, then pills of two halves with a face and a
name in each, three to a row, two rows, soonest climbing to the top right
(v2.5.822 → v2.5.825). `?demo=next` fills both rows from real enrolled chefs for
inspection (v2.5.827) and is now largely redundant, see the repeal below.
**AGENTS.md 2.10.0** (v2.5.829): the Owner repealed the line forbidding
data-writing on production to prove a visual result — arena functionality is
exercised on production, continuously and across all of it, with his words
recorded verbatim in section 8. Console mirror (v2.5.831): the console built its
own `arena_data` from a hand-listed copy that had lost `vip_sponsors`,
`spirit_count` and `upcoming`, and loaded one stylesheet where the arena loads
five — one assembly and one set of sheets now, flat and effect-free by his
instruction, twelve panels each carrying an `i` that explains itself after a
two-second rest.

**Open, and his to rule on: browser zoom.** Above 100% the arena appears to
shrink while everything else grows, and below 100% the reverse. Measured on the
same window, 966×918 against 644×612 (what 1.5× zoom leaves of it): the deck
goes 746px → 660px physical, −11%, while a `rem`-sized phase step goes 35 → 52,
+50%. The cause is A07 itself — the deck is `calc(100svh - header)`, and a box
measured by the viewport cannot scale with zoom because the viewport does not.
He has parked it as-is for now. The candidate fix is
`min(100svh - header, N rem)`: zoom works until the arena fills the screen, then
stops, and A07's no-scroll rule still holds.

**X01 is DONE (v2.5.822 → v2.5.825, Bolt).** The arena now shows who is fighting whom next.
The Owner named the upcoming-battles list as half of what the arena is for and
nothing answered it — no payload key, no selector, no template block. Upcoming
is narrower than "not finished": `SCHEDULED` **and** `start_time` still ahead.
A scheduled battle whose time has passed is one the arena is already showing,
and `WAITING` is a battle that started and is late, not one that is coming. The
key is in `PUBLIC_ARENA_STATE_KEYS`, or the poll would have emptied the panel
thirty seconds after load. Its placement — left rail, under the crown ladder —
is provisional: the approved reference has no such panel, so there was nothing
to measure against, and moving it is CSS only.

**A07 is DONE (v2.5.812) and it was one multiplier.** The Owner defined the card
on 2026-08-05: *the arena fits the screen whole, on every screen.*
`arena_command_deck.css` was sizing the deck at `(100svh − header) * 1.28` with a
`min-height: 42rem`, deliberately growing the stage past one viewport so the
octagon stayed large and the page scrolled. That trade is reversed. Measured live
on production at 2133×958 — deck bottom **1187 → 959**, crowd rail **1186 → 958**
against a 958 viewport — at the cost he chose: the octagon goes 848×665 → 671×520.

**Its earlier attempt, kept because it settles the camera.** v2.5.792 put the
Design Template's camera on the Arena — `rotateX(57deg)`, `perspective 1600px` —
and the Owner reverted it within the hour. The camera stays `rotateX(42deg)`. The
reference floor is a 1120×1120 **square**, the same as this SVG's viewBox, so its
2.375 aspect is produced by that camera and not by a wider octagon; the target is
not available at 42°, which is why A07 shipped as a framing card and not a
geometry one. See v2.5.792/793 in the journal.

**THE FROZEN ARCHITECTURE — the current source of truth, and it replaces the
cascade note that stood here.** That note told a future agent that the camera is
set by `arena_deck_polish.css:3666` and that the floor container's height comes
from `arena_render.css`. Both files were merged away in AN12 and neither exists.
A board that hands out deleted file paths as current instructions is how the old
architecture gets rebuilt by accident, so here is what is actually true, frozen
by the Owner on 2026-08-09 at v2.5.960:

```
PAGE LAYOUT        .arena-command-deck__floor
                   owns the furniture, the caption's region and its gap,
                   the octagon's region, and the region's movement
      |
OCTAGON REGION     .arena-floor-stage
      |
OCTAGON LAYOUT     placeOctagon(svg, camera) in arena_render.js
OWNER              scales and moves the COMPLETE camera component into
                   the region it is given
      |
CAMERA VIEWPORT    .arena-render-container
                   its own intrinsic side (440px) and scene fit (0.79308)
      |
SCENE              #arena-render
                   perspective 1500px, origin 50% 40%, rotateX(42deg),
                   transform-origin 50% 62%
```

Exactly **two** Arena stylesheets (`arena.css`, `arena_atmosphere.css`) and
exactly **one** camera. The Master Console mirror is the SAME component and
differs only by configuration values it sets on it. The camera knows nothing of
the caption, the furniture, the grid rows or the page offsets, and page layout
redefines none of the camera's optics.

**What this means for every card below.** A card adapts to these facts; the facts
do not adapt to a card. Page composition is changed through PAGE LAYOUT. Moving
the octagon means moving its REGION, never editing the camera. Nothing writes
`--arena-fit` or `--arena-shift-*`; nothing positions the ladder or the caption
from CSS; nothing adds a third stylesheet.

## 1. Current team and ownership

| Role | Responsibility |
|---|---|
| **Owner** | Final authority; assigns one atomic card and accepts visible results. |
| **GreenBear** | Visual CSS. |
| **Bolt** | Measurements and independent visual/regression checks. |

**Ember was retired by the Owner on 2026-08-04.** Its name stays on the DONE
rows in §4 and §5 — attribution is history and is not rewritten — and every
open card that suggested it is now **unassigned**: A09, A16, A17, A18, B01, B03,
R01, R02. A suggestion pointing at a retired agent reads as an owner and stops
the next agent from asking. Integration, JS, templates and backend wiring have
no standing owner; the Owner assigns them.

**There are no fixed roles and no deploy gate-holder.** The column above is a
typical focus, not a lock, and the §5 "suggested owner" is a suggestion. Any
agent may deploy their own work — one at a time, by the full Gate in §3.
Director, Cursor and ArenaFront are retired. Master Console is outside this
plan. One file has one owner during an active card; agents do not create
parallel long-lived branches.

## 2. Arena structure contract (v2 — 11-ring octagon)

Approved by the Owner 2026-07-29. This **supersedes** the former freeze
("eight rings", "do not change the existing octagon render method", "do not
change floor colours"): the eleven-ring structure below is now the target, and
the renderer may change to build it.

The octagon is **eleven rings**, centre outward:

| # | Ring | Fill (reference; implemented as tokens) |
|---|------|------|
| 1 | **Crown Holder** — crown + current holder's name (already live) | `#52422E` |
| 2 | **Moat** — service ring: `border:0`, no visible cells; a glowing lantern at each cell centre casts glints onto the gold ring | base `#52422E` |
| 3 | Culinary Master | `#7C674D` |
| 4 | Executive Chef | ↓ eight rank rings, one monotonic |
| 5 | Head Chef | gradient from `#7C674D` (ring 3) |
| 6 | Sous Chef | to `#EEE1CA` (ring 10): the six named |
| 7 | Chef De Partie | palette tans/beiges + two logically |
| 8 | Commis Chef | interpolated steps |
| 9 | Prep Chef | ↑ |
| 10 | Kitchen Porter | `#EEE1CA` |
| 11 | **VIP Guests** (Sponsors) | `#535252` steel |

Around the floor: **two rows of seats top and bottom** = authorised guests who
are **authors** (not chefs); behind them, **balconies** for unauthorised users —
bodiless spirits. The seat contract is rewritten for this new grid (drafted
separately, §2a).

Still in force (unchanged by v2):

- Camera `rotateX(42deg)`.
- Design **tokens** only, no raw hex — the palette above lands in tokens.
- Dark Launch intact: unauthorised and anonymous Arena requests remain 404.
- Never put fake fighters, rankings, gifts, viewers, streams or results in production.
- Effects (dust, gifts, rays, shimmer, crown light) preserved; Master Console untouched.
- No reference K banner; reuse existing CulinEire branding where a mark is required.
- Mobile Arena is frozen and is not a blocker for this desktop plan.
- **A screenshot is a single-use diagnostic, not a stored artifact (Owner,
  2026-08-04).** Take it, read the problem off it, delete it. Do not commit it.
  A stored screenshot ages into a confident lie: it keeps looking authoritative
  long after the page stopped looking like that, and 6.87 MB of exactly that
  was removed from `ops/audits/` in v2.5.806. Evidence of a visual state is the
  MEASUREMENT — a JSON of bounding boxes, diffable and re-runnable — plus the
  command that reproduces the view. Paid or approved imagery is not a
  screenshot and is never covered by this.
- **The media layer is CLOSED (Owner, 2026-08-03): below 901px the Arena stays
  exactly as it is.** One visual style, the desktop one, at every width. The 86
  `min-width: 901px` wrappers removed in v2.5.729/730 stay removed. Two scopes
  came back in v2.5.772 and only those two, because `placeRankSpine()` still
  tested both breakpoints and cleared the rank column's inline geometry while no
  stylesheet stood up to take over. There is no stage 2. Note also that
  indentation in the four Arena stylesheets no longer implies a media scope: 668
  lines sit indented at top level as the bodies of the removed wrappers, and
  reading one of them as scoped is how that defect stayed invisible for six days.
- **Never put fake anything in production, and that includes the audience.** The
  arena deck's `hydrateFixtures()` was disconnected in v2.5.782 after production
  measurement showed the server sending zeros while the page showed 2.4K viewers,
  3.7K votes, 620 gifts and a battle between two chefs who do not exist. It is
  switched off, not deleted, and three tests keep it that way — including one
  that keeps the function present, so it is not dead code to be tidied away.

## 2a. Seat & spectator contract (v2)

Approved by the Owner 2026-07-29. Replaces the "290 real-viewer oval" model.

- **Real interactive seats belong to authors** (authorised users who are not
  chefs): two rows top and two rows bottom around the floor. Front rows fill
  first; a logged-in author sees themselves seated.
- **VIP Guests** (ring 11) are reserved seats for **sponsors**.
- **Balconies** behind the author rows hold **unauthorised users as bodiless
  spirits** — atmospheric only, never impersonating a real/online user, with no
  interactive seat identity.
- The former fixed **290**-seat oval is superseded; capacity follows the two-row
  geometry, front rows first.
- Chefs occupy rank rings 3–10 by rank; the Crown Holder holds ring 1; the
  **Moat (ring 2) has no occupants** — lanterns only.

## 2b. Battle lifecycle choreography — where a chef stands, and when

**Owner, 2026-08-05, restating decisions he first recorded on 2026-07-02.** They
were written down all along, in
`docs/archive/pre-constitution-reset-2026-07-20/docs/chef_battle/ARENA_HALL_PLAN.md`
("Status: APPROVED PLAN — Owner decisions recorded 2026-07-02"). That file is
ARCHIVED, and §10 says an archived document cannot define current scope — so the
rules existed and governed nothing, which is why stage B2 below was never built
and why an agent asked him to repeat himself. They are moved here to be law
again. The same failure hid §18 for two weeks.

**1. Standing.** A chef who enters the arena stands in **his own ring**, the one
labelled with his rank. That is what the rank ladder beside the cells is for.

**2. Challenge.** A challenge may only be thrown at your **own rank or one rank
above or below** — already enforced server-side by
`check_rank_matchup()` in `chef_battle/services.py`, with the site Hero
unrestricted. When it is accepted, the two avatars **move towards each other
inside their own rings**: same rank — opposite cells of that ring; different
ranks — a vertically aligned pair across the two rings. They have NOT reached
the centre yet.

**3. Battle time.** Only when the battle's time arrives do both avatars leave
the ring for **two placeholders beside the centre**, and they stay there for the
duration. The centre carries **VS** and a **link to the battle page** — a
separate page the spectators go to in order to watch the fight. Chefs move, they
are never drawn twice.

**4. On completion** both return to their own ring cells.

**What the arena is for, and it is only this:** so that chefs, sponsors,
spectators, VIPs and spirits can **see each other**, and to show the **list of
upcoming battles**.

### One superseded line, named so nobody restores it

The 2026-07-02 record approved the centre opening a **popup embedded on the
arena**, explicitly "not a link to a separate page". **His instruction of
2026-08-05 reverses that: it is a link to a separate battle page.** The later
word wins (§2 of the constitution, source-of-truth order). `_arena_center()`
already emits both `battle_url` and `popup_url`; the link is the one that counts.

### The delta against the code, measured 2026-08-05

| Stage | Specified | Code today |
|---|---|---|
| Standing in own rank ring | yes | **holds** |
| Challenge limited to rank ±1 | yes | **holds** — `check_rank_matchup()` |
| Approach INSIDE the rings on accept | yes | **MISSING** |
| Move to the centre at battle time | yes | holds |
| Return to ring cells after | yes | holds |

`_arena_center()` returns `facing_pair` for `SCHEDULED`/`MENU_LOCKED` and
`active_battle` otherwise — but `stampFloorCentre()` handles both in **one
identical branch**, drawing both at the centre, and `isDisplaced()` empties a
chef's ring cell as soon as `chef.battle_id === center.battle_id`. So a chef
leaves his ring the moment a battle is scheduled and jumps straight to the
centre. **The approach stage was missing; it landed in v2.5.844 (A09).**

## 2c. The arena is a tabloid; the battle has its own page

**Owner, 2026-08-06.** The arena is **a board, not the show**: it says who is
here, who is fighting whom and what is coming. The fight itself happens on a page
of its own.

**The entry point is the centre cell.** When a battle STARTS, a click on the
centre takes every spectator off the arena and onto the battle's own page. Today
that click opens `ArenaBattleRoom` — an overlay popup over the arena floor
(`arena_render.js`, `stageCentre.popup_url`). That is a placeholder, and the
target is a page.

**The approved reference for that page already exists and is served:**

    /chef-battle/master/live-arena/preview/
    templates/chef_battle/live_arena_preview.html   (added 5c457b98, 2026-07-14)

It is console-gated and its data is a **labelled DEV FIXTURE** — invented chefs,
invented viewer counts — because it is a build canvas, not a live surface. **It
is not an orphan and it is not to be tidied away.** It carries the composition:
the CHEF #1 / VS / CHEF #2 header with rank, clan and country; two live stream
panes with viewer, like and comment chips; the supporter strip and Support Chef
buttons; the central TIME REMAINING countdown; and the three-column live chat
with its composer.

That composition is what cards **B01, B02 and B03** build against, with real
battle data replacing the fixture field by field. B02 is GreenBear's; B01 and B03
are unassigned.

What follows from "the arena is a tabloid": the arena keeps the ladder, the
upcoming board, the seats and the octagon, and does NOT grow a second copy of the
broadcast. Anything that belongs to watching a fight belongs on the battle page.

## 2d. The pre-battle timeline — the 48 hours, and the NEXT BATTLE queue

**Owner, 2026-08-15.** Discussed with Ember on the same day; Ember went into a
weekly limit before writing any of it down, so it is recorded here by Bolt on
the Owner's instruction. **Nothing below is implemented by this entry — it is
the board taking the ruling, and the cards T19/T20/T21 in §5 carry the work.**

**1. The challenge carries a task.** When two chefs see each other on the Arena,
one throws a challenge at the other, and the challenge states what is being
fought over: either a **contest of an existing recipe of the chef being
challenged** (a check on that recipe), or a **completely new recipe**. The
challenger writes a **message** saying which of the two he is proposing.

**2. Nothing runs until the challenge is accepted.** There is no timer before
acceptance.

**3. Acceptance starts 48 hours of preparation.** The window is for creating and
uploading the recipes, buying the ingredients, preparing the workplace and the
products, placing the two hidden ingredient blocks, and everything else the fight
needs. This is the preparation window; it is not the biathlon, whose own rule the
Owner corrected the same week (`39bcad61`: both chefs place two hidden blocks
before Stage 1, only the Stage 1 winner shoots, and the old sequential 48-hour
combat windows are superseded).

**4. The pair is on the Arena from that same moment**, in the **NEXT BATTLE**
strip — the band immediately above the **THE KITCHEN FLOOR** caption. That strip
is the **starting position**, and it is not the centre of the octagon and not
where the current fight happens: it is the pre-start queue above the floor.
**Distance from the starting position is the timer:** at 48 hours remaining the
pair stands furthest away, and as the clock runs down the pair moves visibly
closer.

**5. Ready is the early exit.** If both chefs are ready before the window ends,
each presses **Ready**. On the second Ready the remaining timer is replaced by
**30 minutes**, and the pair takes the nearest place in the queue at the starting
position.

**6. The timer ends, the pair leaves NEXT BATTLE**, walks out onto the Kitchen
Floor, and **Stage 1** begins.

### The delta against the code, measured 2026-08-15

| Stage | His ruling | Code today |
|---|---|---|
| Challenge names a task: existing recipe or a new one | yes | **partly** — `BattleChallenge.theme_recipe` (nullable FK) and `message` already carry it; nothing states the choice explicitly or requires it |
| No timer before acceptance | yes | **holds** |
| Acceptance opens a 48-hour preparation window | yes | **MISSING** — `accept_challenge()` sets `start_time = proposed_start_time or now`, so an accepted challenge with no proposed time starts **immediately** (`MENU_LOCKED`). The 48 hours in the code is `submission_deadline = start_time + 48h`, which is the window **after** the start, a different thing |
| The pair appears in NEXT BATTLE at once | yes | holds — X01's upcoming board, `get_upcoming_battles()` |
| Position in the strip tracks the remaining time | yes | **MISSING** — the pills are ordered soonest-first; position is list order, not distance |
| Both Ready pulls the start in to **30 minutes** | yes | **WRONG VALUE** — `READY_HEAD_START = timedelta(minutes=15)`, `chef_battle/services.py:878` |
| Timer ends → Kitchen Floor → Stage 1 | yes | holds |

**The 15 minutes is superseded, not a defect of SA-A6.** SA-A6 shipped what the
Owner said on 2026-08-06 («оба готовы — таймер до матча 15 минут»); he changed
the number to 30 on 2026-08-15 and the later word wins. `battle_rules.md` §"Ready"
and `docs/chef_battle/ARENA_TRUTHFUL_STATE_MATRIX.md` both still print 15 and are
corrected by T20, not by hand here.

## 3. Slice gate

1. Start from current `origin/main` in one disposable worktree.
2. Implement one card only; check overlap before editing.
3. Run focused PostgreSQL tests, `manage.py check`, diff hygiene and the
   card-specific visual check. The full suite belongs to final gate G01, not
   every small slice.
4. Commit and push the exact slice. The deploy gate verifies origin commit,
   production version, recent deploys, rollback safety and postflight.
5. After a deployed slice, close its temporary branch/worktree. The shared
   repository truth is `origin/main`.
6. Update the card evidence and status in the same change.

**Slices run strictly one at a time, in the §5 table order (sequential
dependency).** Slice N+1 is not started until slice N is **DONE** (merged,
deployed and verified). Only one slice is ever in flight, and each agent holds
at most one card. Nobody starts the next card before the current one is DONE.

**F66, 2026-08-11: this paragraph described Stage 2's (Design Arena
integration) own dispatch queue, which closed with G01 - §5's table now
holds only historical, already-shipped rows (see §5's own note), so there
is no live "table order" left to run slices against. Any execution
ordering for CURRENT work is governed by declared `depends_on` values on
each finding/card and, where one exists, the dependency matrix in
`docs/chef_battle/ARENA_BOARD_SYNC_2026_08_09.md` - not by a fixed row
position in a now-finished table. Kept here as a record of how Stage 2
itself was run, not as a rule still in force.**

**Before taking a new card, go to the board first.** Confirm the previous card is
marked **DONE** in both §5 here and `ARENA_RELEASE_STAGES`/`ARENA_DESIGN_TASKS`
(`recipes/views.py`), and that the closing change is **deployed** to production.
Only then move to the next card. Closing the board is part of finishing a card,
not a separate afterthought — a card whose board row is not DONE-and-deployed is
not finished.

**No roles: any agent may deploy, one at a time, by the full Gate.** Before
shipping, the deploying agent proves three things: (1) **production is current**
— the base is `origin/main` and nothing is unshipped ahead of the served
version; (2) **nobody else is deploying right now** — claim the turn (shared
`deploy.lock`, or tell the Owner and wait for his word); (3) **it breaks nothing
and erases no important files** — focused PostgreSQL tests, `manage.py check` and
`git diff --check` are green, and no paid or approved asset is deleted.

## 4. Completed production foundation

| Card | Result | Evidence |
|---|---|---|
| A00 | Reference authority and immutable constraints reconciled | Plan/Deployment Project audit |
| A01 | Real 290-seat oval connected; one viewer count; stands visible | v2.5.676–v2.5.678 |
| A02 | Chef identity inside existing fighter plinths | v2.5.682 |
| A03 | Correct rank order and approved bevelled labels | v2.5.684–v2.5.685; non-interactive plinth correction v2.5.695 |
| A04 | Cell ripple and chef card anchored to any clicked cell | v2.5.687, v2.5.691; close control v2.5.695 |
| A05 | Independent left Cooking Widget; lifecycle rail separated; compact metrics | v2.5.689–v2.5.692; complete Cooking Widget corrected v2.5.699–v2.5.703 |
| AR2 | Floor palette settled — Owner ramp, moat/VIP tokens, neutral ink | v2.5.704–707, 709–722, 728 |
| A06 | Production vs Design-Arena measurement matrix (read-only) | ops/audits/arena/A06_remeasure_2026-08-04.md — reference floor aspect **2.375**, production **1.266**. The 2026-07-29 matrix is SUPERSEDED: it was measured against the rejected prototype and is kept as evidence only, not as a source. |
| AR0 | Arena CSS/JS dead-code inventory (read-only) | ops/audits/arena/AR0_dead_code_inventory_2026-07-29.md |
| AR1 | Arena owns its eleven-ring geometry; Sponsors grid no longer borrowed | v2.5.709–v2.5.710 |
| AR3 | Moat lit by eight lanterns; glint on the Crown plate | v2.5.736 |
| A08 | Crowd bowl depth, and the hall behind the seats populated | v2.5.775–779 |
| A07 | The arena fits the screen whole — deck bottom 1187 → 959 at 958 viewport | v2.5.812 |
| AR4 | Author seats: two rows top, two bottom; capacity 290 → 114 | v2.5.769 |
| AR5 | VIP sponsor ring; spirit balconies driven by a real anonymous count | v2.5.765–768, v2.5.778 |

## 5. Atomic dispatch queue

**Cleaned and synchronised 2026-08-09**, on the Owner's instruction, after
Architecture Normalisation closed. At the time, the queue held four
actionable cards (A19, VD1, MC02, G01); all four have since closed - A19 and
G01 DONE (Owner acceptance, 2026-08-09/10), VD1 DONE (Owner accepted the
visual debt as-is, 2026-08-09, no code changed), MC02 DELETED (Owner's
order, 2026-08-09, no longer needed). Fixed 2026-08-11 (F57): this section
had not been updated to say so, and kept calling all four "actionable" long
after every one of them closed - see §1 and the individual rows in the
table below for each one's real status. The queue now holds only the
historical rows of what shipped. The twenty-nine AN cards are off it
entirely - see §5a - and no card depends on an AN number any more, because a
card blocked by a finished foundation is blocked forever. The per-card
classification, the dependency matrix, the cross-card pass and the
execution order are in `docs/chef_battle/ARENA_BOARD_SYNC_2026_08_09.md`.

The build board contains the full action, files, visible result, acceptance,
forbidden changes and evidence for every row below.

| ID | Surface | Task | Suggested owner | Depends on | Status |
|---|---|---|---|---|---|
| A00 | Arena Hall | Reference authority and immutable constraints | Ember | — | DONE |
| A01 | Arena Hall | Recovered live scene baseline | Ember + GreenBear | A00 | DONE |
| A02 | Arena Hall | Chef identity inside existing floor plinths | Ember | A01 | DONE |
| A03 | Arena Hall | Rank spine order and approved plinth shape | Ember | A01 | DONE |
| A04 | Arena Hall | Cell click ripple and chef-card anchoring | Ember | A01 | DONE |
| A05 | Arena Hall | Broadcast ribbon, phase rail, metrics and identity | Ember | A00 | DONE |
| A06 | Arena Hall | Fresh production/reference measurement matrix | GreenBear | A05 | DONE |
| AR1 | Arena Hall | Eleven-ring octagon geometry (Crown, Moat, 8 ranks, VIP) | GreenBear | A06 | DONE |
| AR2 | Arena Hall | Eleven-ring palette tokens | GreenBear | AR1 | DONE |
| AR3 | Arena Hall | Moat ring (ring 2) with lanterns + gold-ring glints | GreenBear | AR1 | DONE |
| AR4 | Arena Hall | Author seat rows (two top, two bottom) | Bolt | AR1 | DONE |
| AR5 | Arena Hall | Spirit balconies + VIP sponsor ring | GreenBear + Bolt | AR4 | DONE |
| A07 | Arena Hall | Stage framing and full-octagon composition | GreenBear | AR5 | DONE |
| A08 | Arena Hall | Crowd bowl depth and atmospheric population | GreenBear | A06 | DONE |
| A09 | Arena Hall | Live challenger/opponent composition | Bolt + GreenBear | A07 | DONE |
| A10 | Arena Hall | Crown-holder hub composition | GreenBear | A07 | DONE |
| A11 | Furniture | Phase panel reference pass | Bolt | A06 | DONE |
| A12 | Furniture | Crown ladder panel reference pass | Bolt | A06 | DONE |
| A13 | Furniture | Recent gifts panel reference pass | GreenBear | A06 | DONE |
| A14 | Furniture | Bottom ticker and Join the Crowd composition | GreenBear | A06 | DONE |
| A15 | Arena Hall | Effects and artifacts preservation pass | GreenBear | A07–A10 | DONE |
| A16 | Arena Hall | CulinEire branding and K-mark audit | unassigned | A11–A14 | DONE |
| A17 | Integrity | Truthful visual state matrix | Bolt | A09–A16 | **DONE** — `docs/chef_battle/ARENA_TRUTHFUL_STATE_MATRIX.md`, measured on production |
| A18 | Integrity | Desktop accessibility and responsive gate | Bolt | A17 | **DONE** — 1920/1440/1280/375 swept, 0px overflow, keyboard verified with real Tab. Two named gaps (focus rings, rank-chip contrast) **deferred by the Owner, 2026-08-10, to Stage 3 (release-readiness)** |
| A19 | Arena Hall | Owner visual acceptance — Arena Hall. **Architecture prerequisite satisfied** (normalisation closed at v2.5.960). Owner-only; nothing to implement. | Owner | architecture prerequisite satisfied | **DONE — Owner accepted 2026-08-09, no punch list returned** |
| VD1 | Arena Hall | **Final Arena visual/layout cleanup** — the large-desktop composition the Owner reported on 2026-08-09. Full brief and the four defects that must be told apart first: `docs/chef_battle/ARENA_VISUAL_DEBT.md`. | unassigned | A19 | **DONE — Owner accepted the debt as-is, 2026-08-09. NO CODE CHANGED: this closes by his decision, not by a fix. The composition is unchanged from what A07/AN normalisation left; nothing in PAGE LAYOUT or OCTAGON_REGION was touched.** |
| MC01 | Master Console | Battle Cancellation Simulation — the withdrawal, step by step | Bolt | v2.5.830 | **DELETED by the Owner** |
| MC02 | Arena | The withdrawal seen LIVE on the arena, not described — `docs/chef_battle/ARENA_EMULATION_VISUAL_STEPS.md`. | unassigned | A09 | **DELETED by the Owner, 2026-08-09 — no longer needed** |
| SA-A2 | Arena | An accepted challenge seats the pair in adjacent cells, each in his own ring | Bolt | — | DONE v2.5.844 |
| SA-A4 | Arena | That pairing is stable across leaving and returning | Bolt | SA-A2 | DONE v2.5.844 |
| SA-A6 | Arena | Both Ready pulls the match in to 15 minutes and the pill climbs the queue | Bolt | — | DONE v2.5.844 — **the 15 minutes was superseded by the Owner's 30 on 2026-08-15 (§2d); shipped as 30 in T20, v2.5.1045** |
| B01 | Battle Broadcast | Broadcast shell and confrontation header | Bolt | A19 | **DONE v2.5.874** |
| B02 | Battle Broadcast | Streams, countdown and support furniture | GreenBear | B01 | DONE |
| B03 | Battle Broadcast | Broadcast chat and composer | GreenBear | B02 | DONE |
| R01 | Result / Winner | Champion and runner-up result shell | GreenBear | B03 | DONE |
| R02 | Result / Winner | Result metrics, status and chat | GreenBear | R01 | DONE |
| G01 | Release gate | Complete Design Arena regression and production evidence. Full evidence against contract §14: `docs/chef_battle/G01_RELEASE_GATE_EVIDENCE.md`. | Bolt + Owner | A19, B03, R02 | **DONE — OWNER SIGN OFF, 2026-08-10.** 12/12 §14 categories accounted for: 10 checked and green, 2 (A18's accessibility gaps, §9 legal/payment) deferred to Stage 3. **Stage 2 (Design Arena visual integration) is CLOSED.** |
| T18 | Owner Authority | GreenBear controls every chef account from its Arena card | Ember | T12 | **DONE v2.5.1037** (commit `4c2bc842`, shipped `2ef0a87e`; migration 0096 applied on production) |
| T19 | Battle lifecycle | **Acceptance opens the 48-hour preparation window, and the challenge names its task.** Owner's ruling of 2026-08-15, §2d. `accept_challenge()` starts a battle immediately when no start time was proposed; it must instead schedule the start 48 hours out and keep the pair in NEXT BATTLE for that window. The challenge states which task it carries — contesting an existing recipe of the challenged chef, or a new recipe — with the challenger's message. | Bolt | — | **DONE v2.5.1042** — `PREPARATION_WINDOW` in `chef_battle/services.py`; `task_kind` + `contested_recipe` with migration 0097; the challenged chef sees the task before he accepts. Two defects found by the card and fixed with it: `_begin_combat` wrote ACTIVE straight from SCHEDULED/WAITING (illegal under T12 — a ready pair could not start, invisible until acceptance stopped skipping SCHEDULED), and T18's `owner_arena_account_action` carried no `chef_battle_guard`. 1053/1053 green. |
| T20 | Battle lifecycle | **Both Ready pulls the start in to 30 minutes, not 15.** `READY_HEAD_START` in `chef_battle/services.py`, plus the two documents that print the old number (`docs/chef_battle/battle_rules.md`, `docs/chef_battle/ARENA_TRUTHFUL_STATE_MATRIX.md`) and the SA-A6 row above. | unassigned | T19 | **PENDING** |
| T21 | Arena | **A pair's place in the NEXT BATTLE strip is its remaining time.** Furthest from the starting position at 48 hours, moving visibly closer as the clock runs down; on the second Ready it takes the nearest place in the queue. Today the pills are ordered soonest-first and carry no distance. §2d names the strip: the band directly above THE KITCHEN FLOOR caption, not the octagon centre. | Bolt | T19, T20 | **DONE v2.5.1048** — the gap ahead of each pill is written into `--arena-next-offset` and transitioned; the distance is spent out of the room the pills leave over, measured at paint time, so nothing overflows. At a 790px track: 47.5h → 590px from the label, 12h → 152px, 12min → 2px. A full board of six falls back to the old two-row queue rather than hiding a departure. Appearance on production is the Owner's to judge (17.14). |

## 5a. Architecture Normalisation — CLOSED

**Opened 2026-08-08, CLOSED by the Owner 2026-08-09 at production v2.5.960.**
Twenty-nine cards, AN1 to AN29, all DONE; the engineering acceptance gates are
satisfied. It is **not active work** and it is **not a dependency**: a completed
foundation, not an open blocker. Nothing on the queue above may be blocked by an
AN number, and no future card may reopen the block.

The record is preserved in full and lives outside the active queue:

| What | Where |
|---|---|
| The twenty-nine cards with their per-card evidence | `docs/chef_battle/ARENA_NORMALISATION_CARDS_ARCHIVE.md` |
| The engineering report, before/after metrics, the closure gates | `docs/chef_battle/ARENA_NORMALISATION_REPORT.md` |
| The final full-suite output | `docs/chef_battle/ARENA_NORMALISATION_FINAL_SUITE.txt` |
| Releases and commits | `config/release_journal.py`, v2.5.900 to v2.5.960 |
| The frozen architecture and what may not be used to change it | `docs/chef_battle/ARENA_VISUAL_DEBT.md` |

**AN28's production-page observation is OWNER-ONLY VISUAL ACCEPTANCE**, because
the live Arena is staff-gated. It does not keep the engineering task open.

Three items were carried OUT of the block, each with its own owner: **VD1** the
large-desktop composition, **MC02** the withdrawal seen live, and the
static-asset residue as maintenance debt. They are cards in their own right
above; they are not AN work.

## 6. How to assign a card

Copy one expanded card from the build board. It is complete only when the agent
has returned:

- exact commit and changed files;
- the stated visible result;
- every acceptance statement checked;
- confirmation that every forbidden change was avoided;
- focused PostgreSQL/check/diff results and screenshot evidence when visual.

Do not assign a dependent card before its prerequisites are DONE.

## 7. Rollback

Pinned recovery tag `rollback/2026-07-28-stable-v2.5.675` resolves to
`3b4f88ad`. The former backup branch is no longer on origin; do not claim it as
rollback evidence. A board-only rollback is `git revert cb613759` followed by
the approved deploy procedure.
