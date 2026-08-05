"""Withdrawing from a battle a chef has already accepted.

THE OWNER'S RULE, 2026-08-05. A chef who pulls out of an accepted battle is NOT
punished by the site. The reasons can be anything - illness, a funeral, a
kitchen fire - and no machine can tell a force majeure from an excuse. So the
site decides nothing on its own: the other chef answers first, and a human
moderator has the last word.

    1. The withdrawing chef states his reason, in his own words. Required.
    2. The other chef answers: WITHOUT a penalty, or WITH one - 15 rating and 3
       reputation. Asking for it obliges him to say why; waiving it needs no
       explanation, because nobody has to justify letting someone off.
    3. Either answer goes to a moderator, who is the FINAL judge. He may uphold
       the chef's answer or replace it with his own.

Three withdrawals per account. When they are gone the button goes dark and a
no-show is answered for as it was before.

This lives beside services.py rather than inside it for the same reason
energy_service and faction_service do: it is one self-contained rule with its
own vocabulary, and services.py is already three thousand lines.
"""

from django.db import transaction
from django.utils import timezone

from .models import Battle, BattleEvent, BattleWithdrawal
from .services import (
    _notify_chef,
    _release_battle_artifacts_on_finish,
    create_battle_event,
    get_or_create_battle_profile,
    penalise,
)

WITHDRAWAL_ALLOWANCE = 3


class WithdrawalNotAllowed(Exception):
    """The chef may not withdraw from this battle right now."""


def withdrawals_left(author) -> int:
    return get_or_create_battle_profile(author).withdrawals_remaining


def open_withdrawal_for(battle: Battle):
    return (
        BattleWithdrawal.objects.filter(battle=battle)
        .exclude(status=BattleWithdrawal.Status.CLOSED)
        .first()
    )


def can_withdraw(battle: Battle, author) -> bool:
    """A participant, a battle still live, no request already open, and an
    allowance left. The last of those is what darkens the button."""
    if not author or not battle.author_is_participant(author):
        return False
    if battle.status not in Battle.ACTIVE_STATUSES:
        return False
    if withdrawals_left(author) <= 0:
        return False
    return open_withdrawal_for(battle) is None


def request_withdrawal(*, battle: Battle, author, reason: str) -> BattleWithdrawal:
    """Step 1. The allowance is spent HERE, on the asking, not on the answer.

    Spend it on the outcome instead and a chef whose request is waved through
    pays nothing for a request he can repeat all day, and the fixed three stop
    meaning anything.
    """
    reason = (reason or "").strip()
    if not reason:
        raise WithdrawalNotAllowed("A reason is required.")
    if not can_withdraw(battle, author):
        raise WithdrawalNotAllowed("This battle cannot be withdrawn from.")

    other = battle.opponent_for(author)
    with transaction.atomic():
        profile = get_or_create_battle_profile(author)
        locked = type(profile).objects.select_for_update().get(pk=profile.pk)
        if locked.withdrawals_remaining <= 0:
            raise WithdrawalNotAllowed("No withdrawals left.")
        locked.withdrawals_remaining -= 1
        locked.save(update_fields=["withdrawals_remaining", "updated_at"])

        withdrawal = BattleWithdrawal.objects.create(
            battle=battle, requester=author, opponent=other, reason=reason,
        )
        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_FINISHED,
            battle=battle,
            actor=author,
            target=other,
            message=f"{author.name} asked to withdraw from Chef Battle '{battle.theme}'.",
            is_public=False,
            publish_to_news=False,
        )

    _notify_chef(
        author, other,
        subject=f"{author.name} asks to withdraw from your battle",
        body=(
            f"{author.name} has asked to withdraw from '{battle.theme}' and gave "
            f"this reason:\n\n{reason}\n\nYou decide what happens next: accept it "
            f"without a penalty, or ask for one. Either answer goes to a "
            f"moderator, who has the final word."
        ),
    )
    return withdrawal


def decide_withdrawal(*, withdrawal: BattleWithdrawal, author, with_penalty: bool,
                      opponent_reason: str = "") -> BattleWithdrawal:
    """Step 2. The other chef answers."""
    if withdrawal.opponent_id != getattr(author, "pk", None):
        raise WithdrawalNotAllowed("Only the other chef may answer this.")
    if withdrawal.status != BattleWithdrawal.Status.AWAITING_OPPONENT:
        raise WithdrawalNotAllowed("This request has already been answered.")

    opponent_reason = (opponent_reason or "").strip()
    if with_penalty and not opponent_reason:
        raise WithdrawalNotAllowed("Say why the penalty is deserved.")

    withdrawal.opponent_decision = (
        BattleWithdrawal.OpponentDecision.WITH_PENALTY if with_penalty
        else BattleWithdrawal.OpponentDecision.WITHOUT_PENALTY
    )
    withdrawal.opponent_reason = opponent_reason if with_penalty else ""
    withdrawal.opponent_decided_at = timezone.now()
    withdrawal.status = BattleWithdrawal.Status.AWAITING_MODERATOR
    withdrawal.save(update_fields=[
        "opponent_decision", "opponent_reason", "opponent_decided_at", "status",
    ])
    return withdrawal


def resolve_withdrawal(*, withdrawal: BattleWithdrawal, moderator, uphold_penalty: bool,
                       note: str = "") -> BattleWithdrawal:
    """Step 3. The moderator is the final judge, and ONLY he moves the numbers.

    The penalty is the Owner's figure: 15 rating and 3 reputation. Nothing else
    is taken - no loss, no broken streak - and the battle is CANCELLED rather
    than lost, because pulling out for a real reason is not a defeat. penalise()
    is the gate, so section 18 keeps the Owner's account whole here too.
    """
    if withdrawal.status == BattleWithdrawal.Status.CLOSED:
        raise WithdrawalNotAllowed("This request is already closed.")

    battle = withdrawal.battle
    with transaction.atomic():
        if uphold_penalty:
            profile = get_or_create_battle_profile(withdrawal.requester)
            fields = penalise(
                profile,
                rating=-BattleWithdrawal.PENALTY_RATING,
                reputation=-BattleWithdrawal.PENALTY_REPUTATION,
            )
            if fields:
                profile.save(update_fields=fields)

        withdrawal.penalty_applied = bool(uphold_penalty)
        withdrawal.moderator_note = (note or "").strip()
        withdrawal.reviewed_by = moderator
        withdrawal.reviewed_at = timezone.now()
        withdrawal.status = BattleWithdrawal.Status.CLOSED
        withdrawal.save(update_fields=[
            "penalty_applied", "moderator_note", "reviewed_by", "reviewed_at", "status",
        ])

        if battle.status in Battle.ACTIVE_STATUSES:
            _release_battle_artifacts_on_finish(battle)
            battle.status = Battle.Status.CANCELLED
            battle.waiting_until = None
            battle.result_reason = f"Withdrawn: {withdrawal.requester.name} pulled out."[:120]
            battle.save(update_fields=[
                "status", "waiting_until", "result_reason", "updated_at",
            ])

        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_FINISHED,
            battle=battle,
            actor=withdrawal.requester,
            target=withdrawal.opponent,
            message=(
                f"Chef Battle '{battle.theme}' was withdrawn by "
                f"{withdrawal.requester.name}."
            ),
            is_public=True,
            publish_to_news=True,
        )

    verdict = "with a penalty" if uphold_penalty else "without a penalty"
    for chef, other in ((withdrawal.requester, withdrawal.opponent),
                        (withdrawal.opponent, withdrawal.requester)):
        _notify_chef(
            other, chef,
            subject=f"The withdrawal from '{battle.theme}' has been settled",
            body=(
                f"A moderator has closed the withdrawal from '{battle.theme}' "
                f"{verdict}. The battle is cancelled."
            ),
        )
    return withdrawal
