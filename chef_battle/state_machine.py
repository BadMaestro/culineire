"""Authoritative Battle.status transition contract.

The database trigger installed by migration 0094 applies the same contract to
every writer, including admin actions, commands and stale ORM instances.
"""

from django.db import transaction

from .models import Battle


TERMINAL_OUTCOMES = {
    Battle.Status.COMPLETED, Battle.Status.CANCELLED,
    Battle.Status.DISPUTED, Battle.Status.PAUSED,
    Battle.Status.WALKOVER, Battle.Status.VOID,
}

ALLOWED_BATTLE_TRANSITIONS = {
    Battle.Status.SCHEDULED: {
        Battle.Status.WAITING, Battle.Status.MENU_LOCKED,
        Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.WAITING: {
        Battle.Status.MENU_LOCKED, Battle.Status.WALKOVER, Battle.Status.VOID,
        Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.MENU_LOCKED: {
        Battle.Status.ACTIVE, Battle.Status.VOTING,
        Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.ACTIVE: {
        Battle.Status.INGREDIENT_PENALTY, Battle.Status.VOTING,
        Battle.Status.COMPLETED,
        Battle.Status.WALKOVER, Battle.Status.VOID,
        Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.AWAITING_SUBMISSIONS: {
        Battle.Status.REVEALED, Battle.Status.VOTING,
        Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.REVEALED: {
        Battle.Status.COOKING, Battle.Status.PRESENTATION, Battle.Status.VOTING,
        Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.INGREDIENT_PENALTY: {
        Battle.Status.COOKING, Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.COOKING: {
        Battle.Status.PRESENTATION, Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.PRESENTATION: {
        Battle.Status.VOTING, Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.VOTING: {
        Battle.Status.COMPLETED, Battle.Status.DISPUTED,
        Battle.Status.CANCELLED, Battle.Status.PAUSED,
    },
    Battle.Status.DISPUTED: {Battle.Status.VOTING, Battle.Status.CANCELLED},
    Battle.Status.PAUSED: {
        Battle.Status.SCHEDULED, Battle.Status.WAITING,
        Battle.Status.MENU_LOCKED, Battle.Status.ACTIVE,
        Battle.Status.AWAITING_SUBMISSIONS, Battle.Status.REVEALED,
        Battle.Status.INGREDIENT_PENALTY, Battle.Status.COOKING,
        Battle.Status.PRESENTATION, Battle.Status.VOTING,
        Battle.Status.CANCELLED,
    },
    Battle.Status.COMPLETED: set(),
    Battle.Status.CANCELLED: set(),
    Battle.Status.WALKOVER: set(),
    Battle.Status.VOID: set(),
}

# Every live phase may be ended by an audited operator/no-show/withdrawal
# policy. What must never happen is the reverse: a terminal row becoming live.
for _live_status in (
    Battle.Status.SCHEDULED, Battle.Status.WAITING, Battle.Status.MENU_LOCKED,
    Battle.Status.ACTIVE, Battle.Status.AWAITING_SUBMISSIONS,
    Battle.Status.REVEALED, Battle.Status.INGREDIENT_PENALTY,
    Battle.Status.COOKING, Battle.Status.PRESENTATION, Battle.Status.VOTING,
):
    ALLOWED_BATTLE_TRANSITIONS[_live_status].update(TERMINAL_OUTCOMES)


def transition_battle_status(battle_id, target_status, *, updates=None):
    """Lock, validate and perform one state transition.

    Callers with phase-specific side effects should keep those effects in the
    surrounding atomic block. The database independently enforces the matrix,
    so a direct or stale ORM save cannot bypass this contract.
    """
    updates = dict(updates or {})
    with transaction.atomic():
        battle = Battle.objects.select_for_update().get(pk=battle_id)
        if target_status != battle.status and target_status not in ALLOWED_BATTLE_TRANSITIONS.get(battle.status, set()):
            raise ValueError(
                f"Illegal Battle.status transition: {battle.status} -> {target_status}."
            )
        for field, value in updates.items():
            if field == "status":
                raise ValueError("Pass the target state as target_status, not in updates.")
            setattr(battle, field, value)
        battle.status = target_status
        battle.save(update_fields=["status", *updates.keys(), "updated_at"])
        return battle
