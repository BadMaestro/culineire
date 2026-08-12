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
        # F51, 2026-08-11: can_withdraw's battle.status check above ran
        # unlocked, before this transaction opened; only the chef's own
        # allowance profile was locked inside it. A battle that finished
        # naturally in the gap could still get a withdrawal request created
        # against it - the request itself, not just its later resolution.
        # resolve_withdrawal (F29) already refuses to CANCEL a battle that
        # turns out to have finished, so this could not corrupt the battle
        # outcome, but it still wastes the chef's allowance and opens a
        # withdrawal against a battle that no longer needs one.
        locked_battle = Battle.objects.select_for_update().get(pk=battle.pk)
        if locked_battle.status not in Battle.ACTIVE_STATUSES:
            raise WithdrawalNotAllowed("This battle cannot be withdrawn from.")

        profile = get_or_create_battle_profile(author)
        locked = type(profile).objects.select_for_update().get(pk=profile.pk)
        if locked.withdrawals_remaining <= 0:
            raise WithdrawalNotAllowed("No withdrawals left.")
        locked.withdrawals_remaining -= 1
        locked.save(update_fields=["withdrawals_remaining", "updated_at"])

        withdrawal = BattleWithdrawal.objects.create(
            battle=locked_battle, requester=author, opponent=other, reason=reason,
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

    with transaction.atomic():
        # F46, 2026-08-11: the AWAITING_OPPONENT check above ran unlocked,
        # with no transaction at all around the write below. A moderator can
        # only resolve a withdrawal once it reaches AWAITING_MODERATOR
        # (resolve_withdrawal, locked since F36) - but if a moderator somehow
        # closed this withdrawal (CLOSED) while this call was still working
        # from a stale copy, this write would blindly reopen it back to
        # AWAITING_MODERATOR, handing resolve_withdrawal a second legitimate-
        # looking pass at a request it already settled.
        locked = BattleWithdrawal.objects.select_for_update().get(pk=withdrawal.pk)
        if locked.status != BattleWithdrawal.Status.AWAITING_OPPONENT:
            raise WithdrawalNotAllowed("This request has already been answered.")

        locked.opponent_decision = (
            BattleWithdrawal.OpponentDecision.WITH_PENALTY if with_penalty
            else BattleWithdrawal.OpponentDecision.WITHOUT_PENALTY
        )
        locked.opponent_reason = opponent_reason if with_penalty else ""
        locked.opponent_decided_at = timezone.now()
        locked.status = BattleWithdrawal.Status.AWAITING_MODERATOR
        locked.save(update_fields=[
            "opponent_decision", "opponent_reason", "opponent_decided_at", "status",
        ])
        withdrawal.opponent_decision = locked.opponent_decision
        withdrawal.opponent_reason = locked.opponent_reason
        withdrawal.opponent_decided_at = locked.opponent_decided_at
        withdrawal.status = locked.status
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
        # F36, 2026-08-11: the CLOSED check above reads whatever object the
        # caller's request loaded, unlocked - two concurrent resolve calls for
        # the SAME withdrawal (a double-click, or two moderator tabs) both
        # pass it before either commits, and both would apply the penalty:
        # -30 rating / -6 reputation instead of the Owner's -15/-3 figure.
        # Lock the withdrawal row and re-check under the lock, the same
        # discipline F29 already applied to the battle it cancels.
        locked_withdrawal = BattleWithdrawal.objects.select_for_update().get(pk=withdrawal.pk)
        if locked_withdrawal.status == BattleWithdrawal.Status.CLOSED:
            raise WithdrawalNotAllowed("This request is already closed.")

        # F29, 2026-08-11: withdrawal.battle is whatever the caller's request
        # loaded, which can be stale by the time a moderator's decision lands -
        # calculate_battle_result or the stall sweep can complete or void the
        # same battle in between. Re-read it under a lock here and gate the
        # CANCELLED rewrite on THAT status, so a battle that already finished
        # naturally is never dragged back to CANCELLED and double-penalised.
        locked_battle = Battle.objects.select_for_update().get(pk=locked_withdrawal.battle_id)

        if uphold_penalty:
            profile = get_or_create_battle_profile(locked_withdrawal.requester)
            fields = penalise(
                profile,
                battle=locked_battle,
                rating=-BattleWithdrawal.PENALTY_RATING,
                reputation=-BattleWithdrawal.PENALTY_REPUTATION,
            )
            if fields:
                profile.save(update_fields=fields)

        locked_withdrawal.penalty_applied = bool(uphold_penalty)
        locked_withdrawal.moderator_note = (note or "").strip()
        locked_withdrawal.reviewed_by = moderator
        locked_withdrawal.reviewed_at = timezone.now()
        locked_withdrawal.status = BattleWithdrawal.Status.CLOSED
        locked_withdrawal.save(update_fields=[
            "penalty_applied", "moderator_note", "reviewed_by", "reviewed_at", "status",
        ])

        if locked_battle.status in Battle.ACTIVE_STATUSES:
            _release_battle_artifacts_on_finish(locked_battle)
            locked_battle.status = Battle.Status.CANCELLED
            locked_battle.waiting_until = None
            locked_battle.result_reason = (
                f"Withdrawn: {locked_withdrawal.requester.name} pulled out."[:120]
            )
            locked_battle.save(update_fields=[
                "status", "waiting_until", "result_reason", "updated_at",
            ])
        battle.status = locked_battle.status
        battle.waiting_until = locked_battle.waiting_until
        battle.result_reason = locked_battle.result_reason
        withdrawal.status = locked_withdrawal.status
        withdrawal.penalty_applied = locked_withdrawal.penalty_applied
        withdrawal.moderator_note = locked_withdrawal.moderator_note
        withdrawal.reviewed_by = locked_withdrawal.reviewed_by
        withdrawal.reviewed_at = locked_withdrawal.reviewed_at

        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_FINISHED,
            battle=locked_battle,
            actor=locked_withdrawal.requester,
            target=locked_withdrawal.opponent,
            message=(
                f"Chef Battle '{battle.theme}' was withdrawn by "
                f"{locked_withdrawal.requester.name}."
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
