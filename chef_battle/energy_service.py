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
from django.db.models import F
from django.db.models.functions import Least
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Earning rates ─────────────────────────────────────────────────────────────
EARN_RECIPE_PUBLISHED = 5
EARN_ARTICLE_PUBLISHED = 5
EARN_PINCH_PUBLISHED = 1
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
    """How many like_received moves this source_author has given to author in last 24 h."""
    from chef_battle.models import BattleMoveTransaction
    since = timezone.now() - timezone.timedelta(hours=LIKE_ANTI_FARM_WINDOW_HOURS)
    return BattleMoveTransaction.objects.filter(
        chef=author,
        transaction_type=BattleMoveTransaction.TxType.LIKE_RECEIVED,
        reference_object_id=source_author.pk,
        created_at__gte=since,
    ).count()


# Move-earning events that also feed Culinary Faction contribution (Phase 6).
# Content + likes now; battle_won/battle_participation are added together with
# the same-faction / per-opponent anti-abuse gates so battle points are never
# credited without their guards. Spends/penalties/admin/enrol are excluded.
_FACTION_EARN_TYPES = frozenset({
    "recipe_published", "article_published", "pinch_published", "like_received",
})

# Content whose publish reward is once-per-object (idempotent). Deliberately
# excludes like_received, which legitimately repeats under its own anti-farm gate.
_ONCE_PER_OBJECT_TYPES = frozenset({
    "recipe_published", "article_published", "pinch_published",
})


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

    # Publishing a piece of content rewards it ONCE. A recipe (or article/pinch)
    # can transition unapproved -> approved many times — a chef edits an approved
    # recipe, which flips it back to PENDING, a moderator re-approves, and the
    # publish signal fires again. Without this guard each re-approval re-awards
    # moves AND the uncapped faction/clan season contributions below, letting a
    # chef farm clan points by editing and re-approving the same recipe. The
    # reference's ContentType + pk are already recorded on every transaction, so
    # a prior award for this exact object is a simple existence check. Likes are
    # exempt: they carry their own per-source-per-day anti-farm gate and are
    # meant to repeat.
    if transaction_type in _ONCE_PER_OBJECT_TYPES and reference is not None:
        from django.contrib.contenttypes.models import ContentType
        if BattleMoveTransaction.objects.filter(
            chef=author,
            transaction_type=transaction_type,
            reference_content_type=ContentType.objects.get_for_model(reference),
            reference_object_id=reference.pk,
        ).exists():
            return 0

    # Anti-farming: max LIKE_ANTI_FARM_MAX_PER_SOURCE moves per unique liker per day
    if transaction_type == TxType.LIKE_RECEIVED and source_author is not None:
        if _anti_farm_like_count(author, source_author) >= LIKE_ANTI_FARM_MAX_PER_SOURCE:
            return 0

    # Faction contribution — season-cumulative and UNCAPPED. Fires here, past the
    # anti-farm gate, with the ORIGINAL amount and BEFORE the ENERGY_CAP early-
    # return below could suppress it. Isolated in a savepoint so a faction
    # failure never breaks the core moves economy.
    if transaction_type in _FACTION_EARN_TYPES:
        try:
            with transaction.atomic():
                from chef_battle.faction_service import award_faction_contribution
                award_faction_contribution(author, amount, source=reference)
        except Exception:
            logger.exception("Faction contribution failed for author pk=%s", author.pk)

    # Clan contribution — same earning events as factions, credited to the
    # author's current active clan for the active season (owner's rule: season
    # winner = clan with the highest combined member points). Same savepoint
    # isolation so a clan failure never breaks the moves economy.
    if transaction_type in _FACTION_EARN_TYPES:
        try:
            with transaction.atomic():
                from chef_battle.clan_service import award_clan_contribution
                from chef_battle.season_service import get_active_season
                award_clan_contribution(author, amount, get_active_season(), source=reference)
        except Exception:
            logger.exception("Clan contribution failed for author pk=%s", author.pk)

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

    # DB-side capped increment — read-modify-write loses updates when two
    # awards land at once (e.g. recipe publish + like in the same second).
    from chef_battle.models import ChefBattleProfile
    ChefBattleProfile.objects.filter(pk=profile.pk).update(
        battle_moves=Least(F("battle_moves") + amount, ENERGY_CAP),
        updated_at=timezone.now(),
    )

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

    from chef_battle.models import BattleMoveTransaction, ChefBattleProfile

    profile = _get_profile(author)

    if not profile.infinite_moves:
        # Conditional atomic UPDATE: balance check and deduction in one
        # statement, so concurrent spends cannot drive the balance negative.
        updated = ChefBattleProfile.objects.filter(
            pk=profile.pk, battle_moves__gte=amount
        ).update(
            battle_moves=F("battle_moves") - amount,
            updated_at=timezone.now(),
        )
        if not updated:
            profile.refresh_from_db(fields=["battle_moves"])
            raise InsufficientEnergy(
                f"Not enough battle moves. Have {profile.battle_moves}, need {amount}."
            )

    BattleMoveTransaction.objects.create(
        chef=author,
        amount=-amount,
        transaction_type=transaction_type,
    )
