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


def _anti_farm_like_count(author, source_author=None, source_user=None) -> int:
    """How many like_received moves this liker has given to author in last 24 h.

    Counted twice over, because the key changed. Rows written before the liker's
    User became the key store the liker's RecipeAuthor pk with a NULL content
    type; newer rows store the User pk under the User content type. Both are
    counted so the daily allowance is not silently reset by the switch, and the
    two are matched on different columns so an author pk can never be mistaken
    for a user pk that happens to share its number.
    """
    from chef_battle.models import BattleMoveTransaction
    since = timezone.now() - timezone.timedelta(hours=LIKE_ANTI_FARM_WINDOW_HOURS)
    base = BattleMoveTransaction.objects.filter(
        chef=author,
        transaction_type=BattleMoveTransaction.TxType.LIKE_RECEIVED,
        created_at__gte=since,
    )
    total = 0
    if source_user is not None:
        from django.contrib.contenttypes.models import ContentType
        total += base.filter(
            reference_content_type=ContentType.objects.get_for_model(source_user),
            reference_object_id=source_user.pk,
        ).count()
    if source_author is not None:
        total += base.filter(
            reference_content_type__isnull=True,
            reference_object_id=source_author.pk,
        ).count()
    return total


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
    source_user=None,
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
        source_author: for LIKE_RECEIVED — the liker's RecipeAuthor, if they
            have one. Legacy anti-farm key, kept so existing rows keep counting.
        source_user: for LIKE_RECEIVED — the liker's User. This is the real
            anti-farm key: every liker has a User, while only some have an
            author profile, and keying on the profile let anyone without one
            past the gate entirely.
        reference: any Django model instance; its ContentType + pk are stored
    """
    if amount <= 0:
        return 0

    from chef_battle.models import BattleMoveTransaction, ChefBattleProfile
    TxType = BattleMoveTransaction.TxType

    # F39, 2026-08-11: lock this chef's profile row first, before the
    # once-per-object dedup check and the anti-farm count below. Neither used
    # to have anything serialising two concurrent award_moves calls for the
    # SAME chef - a re-approval signal firing twice, or two likes landing in
    # the same instant, could both read "not yet awarded" / "under the cap"
    # before either committed, doubling moves, the uncapped faction/clan
    # contributions and reputation, or letting more than
    # LIKE_ANTI_FARM_MAX_PER_SOURCE through in a day. Locking the profile row
    # serialises the whole function per chef: a second call blocks here
    # until the first commits, then sees what the first actually wrote.
    profile = _get_profile(author)
    ChefBattleProfile.objects.select_for_update().get(pk=profile.pk)

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

    # Anti-farming: max LIKE_ANTI_FARM_MAX_PER_SOURCE moves per unique liker per day.
    # A like whose source cannot be identified at all is not paid: it cannot be
    # rate-limited, and like_received also feeds the uncapped faction and clan
    # season totals, so an unlimited unidentified award is a clan-farming hole
    # rather than a small overpayment.
    if transaction_type == TxType.LIKE_RECEIVED:
        if source_user is None and source_author is None:
            return 0
        if _anti_farm_like_count(
            author, source_author=source_author, source_user=source_user
        ) >= LIKE_ANTI_FARM_MAX_PER_SOURCE:
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

    # Culinary Reputation — G6, the Owner's order of 2026-08-11. Fires in the
    # same place and for the same reasons as the faction and clan blocks above:
    # past the anti-farm and once-per-object gates, so a farmed like pays no
    # reputation either, and BEFORE the ENERGY_CAP early-return below, because a
    # chef whose move balance is full has still earned the status. Same savepoint
    # isolation, so a reputation failure never breaks the moves economy.
    #
    # This is the line the ТЗ asked for in tz_main.md section 9 and that nothing
    # implemented: until now reputation moved only on battle outcomes, so the two
    # ladders the specification separates on purpose were both PvP-driven.
    try:
        with transaction.atomic():
            from chef_battle.services import award_content_reputation
            award_content_reputation(author, transaction_type)
    except Exception:
        logger.exception("Reputation award failed for author pk=%s", author.pk)

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
    if transaction_type == TxType.LIKE_RECEIVED and source_user is not None:
        # Store the liker's User as a typed reference so the anti-farm count can
        # match on it without colliding with the legacy untyped author-pk rows.
        from django.contrib.contenttypes.models import ContentType
        content_type_obj = ContentType.objects.get_for_model(source_user)
        reference_object_id = source_user.pk
    elif reference is not None:
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

    # G9, Owner 2026-08-11: the ledger records the balance it produced, the
    # same way TokenTransaction always has. Read back AFTER the DB-side update
    # rather than computed in Python, because the increment above is capped and
    # may have landed alongside a concurrent one - an arithmetic guess would
    # record a balance the row never held, which is worse than no column at all.
    balance_after = ChefBattleProfile.objects.filter(pk=profile.pk).values_list(
        "battle_moves", flat=True).first()

    BattleMoveTransaction.objects.create(
        chef=author,
        amount=amount,
        balance_after=balance_after,
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

    # G9: same reason as the award path - read the balance the database
    # actually holds, never the one Python expected.
    balance_after = ChefBattleProfile.objects.filter(pk=profile.pk).values_list(
        "battle_moves", flat=True).first()

    BattleMoveTransaction.objects.create(
        chef=author,
        amount=-amount,
        balance_after=balance_after,
        transaction_type=transaction_type,
    )
