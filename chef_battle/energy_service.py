"""
Phase 3: Battle-moves energy economy.

Rules (per specification):
- balance mutations go through append-only BattleMoveTransaction records only
- absolute balance ceiling: ENERGY_CAP moves
- like_received anti-farming: max LIKE_ANTI_FARM_MAX likes from same source per 24 h
- spend raises InsufficientEnergy when balance would go below zero
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Earning rates ─────────────────────────────────────────────────────────────
EARN_RECIPE_PUBLISHED = 5
EARN_ARTICLE_PUBLISHED = 3
EARN_LIKE_RECEIVED = 1
EARN_BATTLE_WON = 10
EARN_BATTLE_PARTICIPATION = 1

# ── Caps ─────────────────────────────────────────────────────────────────────
ENERGY_CAP = 100
LIKE_ANTI_FARM_WINDOW_HOURS = 24
LIKE_ANTI_FARM_MAX_PER_SOURCE = 3


class InsufficientEnergy(Exception):
    pass


def _get_profile(author):
    from chef_battle.services import get_or_create_battle_profile
    return get_or_create_battle_profile(author)


def _anti_farm_like_count(author, source_author) -> int:
    """How many like_received events from source_author to author in last 24 h."""
    from chef_battle.models import BattleMoveTransaction
    since = timezone.now() - timezone.timedelta(hours=LIKE_ANTI_FARM_WINDOW_HOURS)
    return BattleMoveTransaction.objects.filter(
        chef=author,
        transaction_type=BattleMoveTransaction.TxType.LIKE_RECEIVED,
        reference_object_id=source_author.pk,
        created_at__gte=since,
    ).count()


@transaction.atomic
def award_moves(
    author,
    amount: int,
    transaction_type: str,
    *,
    source_author=None,
    reference=None,
) -> int:
    """
    Credit `amount` battle moves to `author`.

    Returns actual moves awarded (may be less than `amount` due to cap or
    anti-farming; 0 if nothing was awarded).

    Args:
        author: RecipeAuthor instance
        amount: positive integer
        transaction_type: BattleMoveTransaction.TxType value
        source_author: for LIKE_RECEIVED — the author who liked (anti-farm key)
        reference: any Django model instance; its ContentType + pk are stored
    """
    if amount <= 0:
        return 0

    from chef_battle.models import BattleMoveTransaction
    TxType = BattleMoveTransaction.TxType

    # Anti-farming gate for likes
    if transaction_type == TxType.LIKE_RECEIVED and source_author is not None:
        if _anti_farm_like_count(author, source_author) >= LIKE_ANTI_FARM_MAX_PER_SOURCE:
            return 0

    profile = _get_profile(author)
    if profile.infinite_moves:
        # Infinite-balance profiles (greenbear etc.) skip the cap
        pass
    else:
        headroom = max(0, ENERGY_CAP - profile.battle_moves)
        amount = min(amount, headroom)
        if amount <= 0:
            logger.debug(
                "Energy cap reached for author pk=%s; skipping award",
                author.pk,
            )
            return 0

    # Resolve generic FK reference
    content_type_obj = None
    reference_object_id = None
    if reference is not None:
        from django.contrib.contenttypes.models import ContentType
        content_type_obj = ContentType.objects.get_for_model(reference)
        reference_object_id = reference.pk
    elif source_author is not None and transaction_type == TxType.LIKE_RECEIVED:
        reference_object_id = source_author.pk

    profile.battle_moves = min(ENERGY_CAP, profile.battle_moves + amount)
    profile.save(update_fields=["battle_moves", "updated_at"])

    BattleMoveTransaction.objects.create(
        chef=author,
        amount=amount,
        transaction_type=transaction_type,
        reference_content_type=content_type_obj,
        reference_object_id=reference_object_id,
    )

    return amount


@transaction.atomic
def spend_moves(author, amount: int, transaction_type: str) -> None:
    """
    Deduct `amount` battle moves from `author`.
    Raises InsufficientEnergy if balance would go below zero.
    """
    if amount <= 0:
        return

    from chef_battle.models import BattleMoveTransaction

    profile = _get_profile(author)

    if not profile.infinite_moves and profile.battle_moves < amount:
        raise InsufficientEnergy(
            f"Not enough battle moves. Have {profile.battle_moves}, need {amount}."
        )

    if not profile.infinite_moves:
        profile.battle_moves -= amount
        profile.save(update_fields=["battle_moves", "updated_at"])

    BattleMoveTransaction.objects.create(
        chef=author,
        amount=-amount,
        transaction_type=transaction_type,
    )
