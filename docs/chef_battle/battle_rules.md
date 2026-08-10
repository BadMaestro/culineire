# BATTLE RULES — Participation & Scheduling

## Author note
Defined by project creator.

> **RESTORED TO ACTIVE STATUS 2026-08-05** (AGENTS.md section 10, v2.7.0). This
> file was archived, and an archived document defines nothing — which is how the
> code and these rules drifted apart unopposed. It is binding again, and it is
> NOT yet reconciled: parts of it lost an argument to the Owner months ago and
> were never updated. Where it contradicts the code, say so and ask him; do not
> change code to match it.
>
> **CORRECTED BY THE OWNER, 2026-08-05 — silence is not an offence.** The tables
> below charge a chef for letting a challenge expire unanswered. He overturned
> that: a chef who never answered may be busy, away, or may simply never have
> seen it, and the site cannot tell that from contempt. An unanswered challenge
> frees the slot and costs the non-responder NOTHING. What IS paid for is
> **accepting and then not turning up** — already handled by the walkover,
> forfeit and both-absent paths. The struck-through rows below are kept, not
> deleted, so the change stays legible.
>
> **SETTLED, X05, Owner 2026-08-06: THE ACCEPTANCE WINDOW IS TWELVE HOURS.**
> This file said 12 in its slot lifecycle and 48 in its own first table, while the
> code and the live rules page both said 48. Twelve is now the rule and the code:
> `CHALLENGE_ACCEPTANCE_WINDOW` in `chef_battle/forms.py`, shipped v2.5.837. An
> unanswered challenge expires and costs the challenged chef nothing.
>
> **SETTLED, X06, Owner 2026-08-10: THE DOCUMENT MATCHES THE CODE.** This file's
> single 24-hour `battle_deadline` never existed as a field. The real shape,
> already live in `accept_challenge()` (`chef_battle/services.py:325`) and the
> public rules page, is two separate deadlines: **48 hours to submit**
> (`submission_deadline`), then **2 more days of public voting**
> (`voting_deadline`). No code changed; this document is corrected below to say
> what has been running all along.

---

## Battle count & progression

| Outcome | Effect on battle count |
|---------|----------------------|
| Win | +1 `wins` (counts toward level) |
| Loss | +1 `losses` (display only, does not affect level) |
| Refuse a challenge (manual) | **−1 battle** (floor at 0) |
| ~~Auto-refuse (48h timeout)~~ | ~~−1 battle~~ — **NO PENALTY** (Owner, 2026-08-05) |
| ~~Slot auto-expire (no response)~~ | ~~−1 battle~~ — **NO PENALTY** (Owner, 2026-08-05) |
| Accepted, then failed to appear | loss, streak reset, reputation — this is the irresponsibility |

**Floor rule**: battle count can never go below 0. If a chef has 0 battles
and incurs a penalty, it stays at 0.

### Withdrawing from an accepted battle — Owner, 2026-08-05

A chef who pulls out of a battle he has already accepted is **not punished by
the site**. The reasons can be anything, force majeure included, and no machine
can tell one from an excuse — so the responsibility is shared between the other
chef and a human, and the site itself decides nothing.

1. The withdrawing chef presses **Withdraw** and writes his reason, in his own
   words, on a page shaped like the contact form. The reason is required.
2. The other chef answers: **without a penalty**, or **with one — up to 15
   rating and 3 reputation**. Both are floored at zero by `penalise()`, so a
   chef who has none loses nothing; the figures are a ceiling, not a fine.
   (Caught by Bolt on 2026-08-06, cross-checking his console panel against
   the service: every surface here had stated a flat 15.) Asking for it obliges him to say why; waiving it needs no
   explanation, because nobody has to justify letting someone off.
3. **Either answer goes to a moderator, who is the final judge.** He may uphold
   the chef's answer or replace it with his own.

The allowance is **three per account, for the life of the account**. When they
are gone the button goes dark and a no-show is answered for as before.

A withdrawal is **not a defeat**: no loss, no broken streak, no win for the
other chef. The battle is CANCELLED. Only the moderator's word moves any number,
and the penalty passes through `penalise()`, so section 18 holds here too.

Code: `chef_battle/withdrawal_service.py`, model `BattleWithdrawal`, allowance on
`ChefBattleProfile.withdrawals_remaining`.

**STILL HIS TO SETTLE:** the other chef loses their battle through no fault of
their own and currently receives nothing for it. Whether they should take the
second-place share is not decided.

### Losing a fought battle is not a penalty — Owner, 2026-08-05

Turning up and cooking is experience whichever way the vote goes: this is a
battle of chefs for the fun of it, not Mortal Kombat. **Second place is paid,
not fined** — half of everything first place takes, the same shape the prizes
already use:

| | Winner | Second place |
|---|---|---|
| Rating | +25 | +12 |
| Reputation | +15 | +7 |
| Seasonal score | +10 | +5 |
| Battle Moves | 11 | 6 |

Nothing is deducted for a result. `losses` and the broken win streak stay,
because they are records of what happened rather than fines. **A DRAW pays both
chefs that same second-place share** — until v2.5.828 it paid them nothing at
all. This does not touch the no-show paths above: accepting and then failing to
appear is the irresponsibility, and it is still answered for.

Only victories count toward level progression (10 wins = level up, not 10 participations).

---

## Slot system — 1 slot per chef

Each chef has **one battle slot**. Only one active battle at a time.

### Slot lifecycle

```
Challenge issued → occupies challenger's slot
  ├─ Accepted within 12h → submission window starts for both chefs
  └─ Not accepted within 12h → slot freed; no penalty to non-responder (X02)

Battle completes → slot freed; chef can accept or issue a new challenge
```

### Key rules

- **Acceptance window**: 12 hours from challenge issue (X05)
- ~~**Battle window**: 24 hours from acceptance — both chefs complete
  combat + cooking + submission within this window~~ — **corrected, X06,
  Owner 2026-08-10**: there is no single combined window. **48 hours to
  submit** (`submission_deadline`), then a further **2 days of public
  voting** (`voting_deadline`) — matches `accept_challenge()` and the
  public rules page.
- **Occupied slot**: a chef with an active battle cannot accept or issue
  new challenges until the slot is free
- Manual refuse → −1 battle (floor 0)
- ~~Slot auto-expires → −1 battle~~ — **no penalty**; silence is not an offence (Owner, 2026-08-05)

### "Ready" button — CORRECTED to the code, X18, Owner's standing rule 2026-08-10

What runs is the Owner's own scenario A6 of 2026-08-06 — «оба готовы - таймер
до матча 15 минут» — and it is simpler than the handshake below: when **both**
chefs have pressed Ready, the start is pulled in to **15 minutes from now**
(`READY_HEAD_START`, `pull_start_forward_when_both_ready()`), which also lifts
the pair up the Next Battle queue, because that board is ordered by time
remaining. The start is never pushed later. A chef who is ready alone waits out
`START_RITUAL_GRACE` — ten minutes — and then takes the walkover.

The three-step handshake below was never built. `proposed_combat_time` and
`combat_time_confirmed` exist on the model and **nothing writes them**; they are
the residue of this paragraph and are the only two dead fields the audit of
2026-08-10 found.

- ~~1. Chef A presses "Ready" — signals preparation is complete~~
- ~~2. Chef B presses "Ready" and proposes a specific combat time~~
- ~~3. Chef A confirms the proposed time → combat begins at that time~~

---

## Summary of automated actions

| Trigger | Action |
|---------|--------|
| Challenge not accepted in the window | Slot freed. **No penalty** (Owner, 2026-08-05) |
| Manual refuse | −1 battle to refuser; slot freed |
| `submission_deadline` passes without a submission | Auto-cancel; non-compliant party −1 battle |
| `voting_deadline` passes | Voting closes; result recorded |
| Win recorded | +1 battle count; recalculate level |

---

## Implementation notes

### ChefBattleProfile fields
- `battles_completed` IntegerField default=0 (wins only)

### Battle model fields
- `accepted_at` DateTimeField null=True
- ~~`battle_deadline` DateTimeField null=True — `accepted_at + 24h`~~ — does not
  exist; the real fields are below (X06, Owner 2026-08-10)
- `submission_deadline` DateTimeField — `start_time + 48h`
- `voting_deadline` DateTimeField — `submission_deadline + 2 days`
- `challenger_ready` BooleanField default=False
- `opponent_ready` BooleanField default=False
- `proposed_combat_time` DateTimeField null=True
- `combat_time_confirmed` BooleanField default=False

### Slot occupied check
```python
def has_active_battle(profile):
    active_statuses = [
        "accepted", "menu_locked", "active",
        "cooking", "presentation", "voting", "ingredient_penalty"
    ]
    return Battle.objects.filter(
        models.Q(challenger=profile) | models.Q(opponent=profile),
        status__in=active_statuses
    ).exists()
```

### Auto-tasks (cron / celery beat — run every 30 min)
- Find `declared` battles past their window → expire. No penalty to anyone.
- Find active battles where `submission_deadline < now()` and no submission → auto-cancel; −1 to non-compliant party
- Find battles where `voting_deadline < now()` → close voting, record result
