# GreenBear handoff — 2026-08-13, mid-brief

Written to survive a context compaction. Production **v2.5.1019**, commit
`61ec3186`, equal to `origin/main`, tree clean, deploy lock free.

## What I am doing

The Owner's direct brief, delivered on the Carpet as **message #3509** and
dispatched with one instruction: **create every card first, then start — and I
am the only agent on it.** Seventeen tickets, five packages, closing the classes
his last audit named rather than their symptoms.

**The brief itself is the specification.** Read it from the Carpet, not from a
summary:

```bash
ssh deploy@80.85.84.156 "cd /srv/culineire/current && set -a && . /srv/culineire/shared/.env && set +a \
  && ./venv/bin/python -c \"import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();\
from coworking.models import CoworkingMessage;print(CoworkingMessage.objects.get(id=3509).body)\""
```

The cards carry his acceptance criteria and his forbidden list verbatim:
`recipes/views.py` → `ARENA_DESIGN_TASKS`, ids **T01–T17**, live at
`/recipes/moderation/arena-build-plan/`.

## His rulings that bound this work

- **`CHEF_BATTLE_ENABLED` is a one-way launch latch** — False until launch, True
  after, never back. **F65 is REVIEWED, NOT A BUG**; do not design around
  switching it off, and do not turn the latch into a kill switch.
- **Stripe Dashboard work is outside the brief**; everything on our side of the
  webhook — TokenOrder, wallets, ledgers, refunds, chargebacks, the payout state
  machine, reconciliation, handler idempotency — is inside it.
- Where he has corrected the old spec, **the code is the decision**. But **a
  required feature that was never built is not a decision to cancel it**: build
  it, or stop and ask him one concrete question.
- **Migrations are ordinary work.** He overruled me on 2026-08-11: «НЕ ТРЕБУЮТ,
  Я НИКОГДА НЕ ЗАПРЕЩАЛ МИГРАЦИИ». AGENTS.md §8 still lists them among the
  exclusions and **only he may correct that line** — do not edit the
  constitution.
- **Numbering collision, do not re-derive it:** his brief calls these F67–F83;
  the board already carries F67–F75 from Bolt's self-audit of the same day and
  they are **different findings**. The cards are keyed T01–T17 for that reason.

## Where the work stands

| Ticket | State |
|---|---|
| **T01** scorer accepts only a locked VOTING status | **DONE**, v2.5.1019 |
| **T02** atomic reveal, no resurrection | **NEXT** — `reveal_entries_if_ready` still has neither `transaction.atomic` nor a lock |
| **T03** two Ready flags survive | lock shipped as F67 (v2.5.1016); **only the two-thread barrier test is missing** |
| **T04** stored XSS in the combat log | not started |
| **T05** cooked-photo upload validation | not started |
| **T06** atomic cooked-photo commit | battle lock shipped as F69; **entry lock and ordering proof missing** |
| **T07** chargeback during PROCESSING | not started |
| **T08–T10** token lots, partial refunds, one profile-locking helper | not started |
| **T11–T12** biathlon deadlines, one transition contract | not started |
| **T13–T16** CSP nonce, delete `recalculate_owner_moves`, board/spec sync, dead code | not started |
| **T17** acceptance gate | last |

## Two things about T01 that cost time and would cost it again

**The caller's object must be the thing scored.** `_score_battle` points
`challenger.battle_profile` / `opponent.battle_profile` at the rows it just
wrote, and `battle_detail.html` renders the champion's crown straight off
`battle.challenger.battle_profile.has_crown`. Scoring a private locked copy — or
calling `refresh_from_db()` on the caller's instance, which drops its cached
author objects — leaves the page showing a **new champion with no crown**. What
ships copies the authoritative **status** from the locked row and scores the
caller's object.

**Adapting a test's precondition is not weakening it.** Eighteen older tests
scored a battle straight out of `accept_challenge`; the real flow is in VOTING
when the deadline passes. Supplying that state is legitimate. What is NOT
legitimate — and I broke it once before catching it — is inserting the
precondition before a *second* scorer call in an idempotency test: that
resurrects a completed battle and destroys the point of the test.

## Inherited reds on main, so they are not mistaken for new damage

Fixed on the way past in v2.5.1019: six classes drove real views without forcing
`CHEF_BATTLE_ENABLED` (so the guard answered 404 on any workstation whose `.env`
leaves the flag at its default, which is what the latch requires), and
`test_refuse_challenge_records_reputation_penalty` read a cached profile instead
of the row `refuse_challenge` writes.

**Still red and deliberately not patched around:**
`ArenaMasterGovernanceTests.test_owner_reject_requires_reason_and_returns_rewards`
— a rejected payout is expected to return its reward records to APPROVED and
finds them ISSUED. That is reward-reservation behaviour; it belongs with the
money package, **T07–T10**, and is to be fixed there.

## Working rules that apply to every remaining ticket

- Focused tests before each commit; a real `TransactionTestCase` with a barrier
  for every concurrency claim — **captured SQL is not an interleaving test**.
- No DB transaction held open across a network call to Stripe.
- Never trust a stale model instance after waiting on a lock; always assign and
  use what `select_for_update()` returned.
- Lock several profiles only in ascending pk order.
- Nothing touches the Owner's account; no production writes to demonstrate a
  result.
- One logical commit per package; the board moves only on real evidence.

## Rollback

Each release reverts individually; see `config/release_journal.py` from
v2.5.1017 (the cards) and v2.5.1019 (T01).
