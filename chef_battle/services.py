from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db import models
from django.db.models import Count, F, Sum
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from newsfeed.models import NewsFeedEntry

from .models import (
    APPRECIATION_GIFT_COST, Artifact, Battle, BattleChallenge, BattleCombatAction,
    BattleEntry, BattleEvent, BattleIngredient, BattleRound, ChefArtifact, ChefBattleProfile,
    IngredientLock, IngredientShot, AppreciationGift, LiveStreamSession,
    OperatorActionIdempotencyKey, ViewerBattleGift, TokenTransaction, TokenWallet,
)

logger = logging.getLogger(__name__)


def _notify_chef(sender_author, recipient_author, subject: str, body: str) -> None:
    """Send an in-site message and email notification. Silently skips if users are missing."""
    try:
        from messaging.models import Message
        from config.email_utils import build_absolute_url, sanitize_email_subject, send_template_mail
        sender = getattr(sender_author, "user", None)
        recipient = getattr(recipient_author, "user", None)
        if sender and recipient and sender != recipient:
            Message.objects.create(sender=sender, recipient=recipient, subject=subject, body=body)
            if recipient.email:
                send_template_mail(
                    subject=sanitize_email_subject(subject),
                    template="message_notification",
                    context={
                        "subject": subject,
                        "body": body,
                        "inbox_url": build_absolute_url(reverse("chef_battle:challenge_list")),
                    },
                    recipient_list=[recipient.email],
                    fail_silently=True,
                )
    except Exception:
        logger.exception("Failed to send battle notification")


RANK_THRESHOLDS = [
    (700, ChefBattleProfile.Rank.CULINARY_MASTER),
    (600, ChefBattleProfile.Rank.EXECUTIVE_CHEF),
    (500, ChefBattleProfile.Rank.HEAD_CHEF),
    (400, ChefBattleProfile.Rank.SOUS_CHEF),
    (300, ChefBattleProfile.Rank.CHEF_DE_PARTIE),
    (200, ChefBattleProfile.Rank.COMMIS_CHEF),
    (100, ChefBattleProfile.Rank.PREP_COOK),
    (0, ChefBattleProfile.Rank.KITCHEN_PORTER),
]


def get_or_create_battle_profile(author):
    from django.conf import settings as _settings
    profile, created = ChefBattleProfile.objects.get_or_create(author=author)
    if created and getattr(author, "slug", None) == getattr(_settings, "OWNER_SLUG", None):
        profile.rank = ChefBattleProfile.Rank.EXECUTIVE_CHEF
        profile.michelin_stars = 3
        profile.is_hero = True
        profile.rating = 9999
        profile.wins = 15
        profile.infinite_moves = True
        profile.save(update_fields=["rank", "michelin_stars", "is_hero", "rating", "wins", "infinite_moves", "updated_at"])
    return profile


def rank_for_rating(rating: int) -> str:
    for threshold, rank in RANK_THRESHOLDS:
        if rating >= threshold:
            return rank
    return ChefBattleProfile.Rank.KITCHEN_PORTER


def hash_request_value(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_battle_event(
    *,
    event_type,
    message,
    battle=None,
    challenge=None,
    actor=None,
    target=None,
    is_public=True,
    publish_to_news=False,
):
    event = BattleEvent.objects.create(
        battle=battle,
        challenge=challenge,
        event_type=event_type,
        actor=actor,
        target=target,
        message=message,
        is_public=is_public,
    )

    flag_on = getattr(settings, "CHEF_BATTLE_ENABLED", False)
    if publish_to_news and flag_on:
        event_key = f"chef_battle:{event.pk}"
        try:
            url = battle.get_absolute_url() if battle else reverse("chef_battle:challenge_list")
        except NoReverseMatch:
            url = ""
        try:
            from sponsors.services import get_sponsor_of_month
            sponsor = get_sponsor_of_month()
        except Exception:
            sponsor = ""
        NewsFeedEntry.objects.create(
            entry_type=NewsFeedEntry.EntryType.BATTLE_EVENT,
            title=message,
            message=f"Sponsored by: {sponsor}" if sponsor else "",
            url=url,
            is_auto=True,
            is_public=is_public,
            event_key=event_key,
            sub_type=event_type,
        )

    return event


def check_rank_matchup(challenger, opponent) -> str | None:
    """Allow battles between adjacent ranks; the site Hero is unrestricted."""
    c_profile = get_or_create_battle_profile(challenger)
    o_profile = get_or_create_battle_profile(opponent)
    if c_profile.is_hero or o_profile.is_hero:
        return None

    rank_order = {rank.value: index for index, rank in enumerate(ChefBattleProfile.Rank)}
    if abs(rank_order[c_profile.rank] - rank_order[o_profile.rank]) > 1:
        return (
            f"Rank mismatch: {challenger.name} is {c_profile.get_rank_display()}, "
            f"{opponent.name} is {o_profile.get_rank_display()}. "
            "Challenges are limited to the same or an adjacent rank."
        )
    return None


def accept_challenge(challenge: BattleChallenge) -> Battle:
    now = timezone.now()
    start_time = challenge.proposed_start_time or now
    status = Battle.Status.SCHEDULED if start_time > now else Battle.Status.MENU_LOCKED
    submission_deadline = start_time + timezone.timedelta(hours=48)
    voting_deadline = submission_deadline + timezone.timedelta(days=2)
    end_time = voting_deadline

    with transaction.atomic():
        challenge.status = BattleChallenge.Status.ACCEPTED
        challenge.accepted_at = now
        challenge.save(update_fields=["status", "accepted_at"])

        battle = Battle.objects.create(
            challenge=challenge,
            challenger=challenge.challenger,
            opponent=challenge.opponent,
            theme=challenge.theme,
            battle_type=challenge.battle_type,
            status=status,
            start_time=start_time,
            submission_deadline=submission_deadline,
            voting_deadline=voting_deadline,
            end_time=end_time,
        )

        create_battle_event(
            event_type=BattleEvent.EventType.CHALLENGE_ACCEPTED,
            challenge=challenge,
            battle=battle,
            actor=challenge.opponent,
            target=challenge.challenger,
            message=f"{challenge.opponent.name} accepted {challenge.challenger.name}'s Chef Battle: {challenge.theme}.",
            publish_to_news=True,
        )
        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_STARTED,
            battle=battle,
            actor=challenge.challenger,
            target=challenge.opponent,
            message=f"Chef Battle started: {challenge.challenger.name} vs {challenge.opponent.name} - {challenge.theme}.",
            publish_to_news=True,
        )

    try:
        battle_url = battle.get_absolute_url()
    except NoReverseMatch:
        battle_url = ""
    _notify_chef(
        challenge.opponent, challenge.challenger,
        subject=f"Your challenge was accepted: {challenge.theme}",
        body=(
            f"{challenge.opponent.name} accepted your Chef Battle challenge.\n\n"
            f"Theme: {challenge.theme}\n"
            f"Battle room: {settings.SITE_SCHEME}://{settings.SITE_DOMAIN}{battle_url}"
        ),
    )
    return battle


def refuse_challenge(challenge: BattleChallenge) -> None:
    with transaction.atomic():
        challenge.status = BattleChallenge.Status.REFUSED
        challenge.refused_at = timezone.now()
        challenge.save(update_fields=["status", "refused_at"])

        profile = get_or_create_battle_profile(challenge.opponent)
        profile.refused_battles += 1
        profile.reputation -= 5
        profile.save(update_fields=["refused_battles", "reputation", "updated_at"])

        # Live rules 2026-07-10: refusing costs 15 Battle Moves
        from .energy_service import spend_moves as _spend_moves, InsufficientEnergy
        from .models import BattleMoveTransaction
        try:
            _spend_moves(
                challenge.opponent,
                MOVES_REFUSE_PENALTY,
                BattleMoveTransaction.TxType.CHALLENGE_REFUSED,
            )
        except InsufficientEnergy:
            # Floor at zero: drain remaining moves, never go negative
            if profile.battle_moves > 0:
                profile.battle_moves = 0
                profile.save(update_fields=["battle_moves", "updated_at"])

        create_battle_event(
            event_type=BattleEvent.EventType.CHALLENGE_REFUSED,
            challenge=challenge,
            actor=challenge.opponent,
            target=challenge.challenger,
            message=f"{challenge.opponent.name} refused a Chef Battle challenge from {challenge.challenger.name}: {challenge.theme}.",
            publish_to_news=True,
        )

    _notify_chef(
        challenge.opponent, challenge.challenger,
        subject=f"Your Chef Battle challenge was refused: {challenge.theme}",
        body=(
            f"{challenge.opponent.name} has declined your Chef Battle challenge.\n\n"
            f"Theme: {challenge.theme}\n\n"
            f"Challenge another chef and keep fighting for your rank."
        ),
    )


def expire_stale_challenges() -> int:
    """Mark pending challenges past their deadline as EXPIRED. Returns count."""
    now = timezone.now()
    stale = BattleChallenge.objects.filter(
        status=BattleChallenge.Status.PENDING,
        expires_at__lte=now,
    )
    count = 0
    for challenge in stale:
        challenge.status = BattleChallenge.Status.EXPIRED
        challenge.save(update_fields=["status"])
        create_battle_event(
            event_type=BattleEvent.EventType.CHALLENGE_EXPIRED,
            challenge=challenge,
            actor=challenge.challenger,
            target=challenge.opponent,
            message=(
                f"Challenge expired: {challenge.opponent.name} did not respond "
                f"to {challenge.challenger.name}'s battle on '{challenge.theme}'."
            ),
            is_public=False,
        )
        count += 1
    return count


def handle_no_show_battles() -> int:
    """
    Process battles past submission_deadline where one or both chefs
    have not submitted an entry.

    - Both missing → CANCELLED, result_reason records double no-show.
    - One missing → the submitting chef wins by forfeit; loser takes a
      reputation hit, no rating change (forfeit does not affect Elo).
    """
    now = timezone.now()
    battles = Battle.objects.filter(
        status__in=[Battle.Status.MENU_LOCKED, Battle.Status.ACTIVE, Battle.Status.AWAITING_SUBMISSIONS],
        submission_deadline__lte=now,
    ).select_related("challenger", "opponent")

    count = 0
    for battle in battles:
        entries = list(battle.entries.values_list("author_id", flat=True))
        challenger_submitted = battle.challenger_id in entries
        opponent_submitted = battle.opponent_id in entries

        with transaction.atomic():
            if not challenger_submitted and not opponent_submitted:
                battle.status = Battle.Status.CANCELLED
                battle.result_reason = "Double no-show: neither chef submitted an entry."
                battle.save(update_fields=["status", "result_reason", "updated_at"])
                create_battle_event(
                    event_type=BattleEvent.EventType.BATTLE_FINISHED,
                    battle=battle,
                    message=(
                        f"Battle cancelled: neither {battle.challenger.name} nor "
                        f"{battle.opponent.name} submitted an entry for '{battle.theme}'."
                    ),
                    is_public=True,
                    publish_to_news=True,
                )

            elif not challenger_submitted:
                _award_forfeit_win(battle, winner=battle.opponent, loser=battle.challenger)

            elif not opponent_submitted:
                _award_forfeit_win(battle, winner=battle.challenger, loser=battle.opponent)

            else:
                # Both submitted but deadline passed without voting closing —
                # advance to voting so the normal result path can run.
                battle.entries.filter(is_revealed=False).update(is_revealed=True)
                battle.status = Battle.Status.VOTING
                battle.save(update_fields=["status", "updated_at"])

        count += 1
    return count


def _award_forfeit_win(battle: Battle, *, winner, loser) -> None:
    loser_profile = get_or_create_battle_profile(loser)
    loser_profile.losses += 1
    loser_profile.win_streak = 0
    loser_profile.reputation = max(-1000, loser_profile.reputation - 10)
    loser_profile.rank = rank_for_rating(loser_profile.rating)
    loser_profile.save(update_fields=["losses", "win_streak", "reputation", "rank", "updated_at"])

    winner_profile = get_or_create_battle_profile(winner)
    winner_profile.wins += 1
    winner_profile.win_streak += 1
    winner_profile.rank = rank_for_rating(winner_profile.rating)
    winner_profile.save(update_fields=["wins", "win_streak", "rank", "updated_at"])

    battle.winner = winner
    battle.loser = loser
    battle.status = Battle.Status.COMPLETED
    battle.result_reason = f"Forfeit: {loser.name} did not submit an entry."
    battle.save(update_fields=["winner", "loser", "status", "result_reason", "updated_at"])

    create_battle_event(
        event_type=BattleEvent.EventType.BATTLE_FINISHED,
        battle=battle,
        actor=winner,
        target=loser,
        message=(
            f"{winner.name} wins by forfeit in Chef Battle '{battle.theme}': "
            f"{loser.name} did not submit an entry."
        ),
        is_public=True,
        publish_to_news=True,
    )


def submit_battle_entry(*, battle: Battle, author, recipe=None, article=None, battle_statement: str = "") -> BattleEntry:
    """Create a BattleEntry, flagging it as late if the deadline has passed."""
    if not battle.author_is_participant(author):
        from django.core.exceptions import ValidationError
        raise ValidationError("Only battle participants can submit entries.")
    now = timezone.now()
    is_late = now > battle.submission_deadline
    entry = BattleEntry.objects.create(
        battle=battle,
        author=author,
        recipe=recipe,
        article=article,
        battle_statement=battle_statement,
        is_late=is_late,
    )
    return entry


def reveal_entries_if_ready(battle: Battle) -> None:
    entries = list(battle.entries.all())
    both_submitted = len(entries) == 2
    deadline_passed = timezone.now() >= battle.submission_deadline

    if battle.status == Battle.Status.MENU_LOCKED:
        # Both chefs submitted their recipes — combat can begin
        if both_submitted or deadline_passed:
            battle.entries.filter(is_revealed=False).update(is_revealed=True)
            battle.status = Battle.Status.ACTIVE
            battle.save(update_fields=["status", "updated_at"])
    elif battle.status == Battle.Status.ACTIVE:
        # Both chefs submitted combat actions — move to voting
        if both_submitted or deadline_passed:
            battle.entries.filter(is_revealed=False).update(is_revealed=True)
            battle.status = Battle.Status.VOTING
            battle.save(update_fields=["status", "updated_at"])


def calculate_battle_result(battle: Battle) -> Battle:
    if battle.status == Battle.Status.COMPLETED:
        return battle

    vote_counts = {
        item["voted_for"]: item["total"]
        for item in battle.votes.values("voted_for").annotate(total=Count("id"))
    }
    challenger_votes = vote_counts.get(battle.challenger_id, 0)
    opponent_votes = vote_counts.get(battle.opponent_id, 0)

    if challenger_votes == opponent_votes:
        ChefArtifact.objects.filter(
            locked_to_battle=battle,
            status=ChefArtifact.Status.AVAILABLE,
            source=ChefArtifact.Source.BATTLE_GIFT,
        ).update(status=ChefArtifact.Status.EXPIRED, expired_at=timezone.now())
        battle.result_reason = "Draw by public vote"
        battle.status = Battle.Status.COMPLETED
        battle.save(update_fields=["status", "result_reason", "updated_at"])
        return battle

    winner = battle.challenger if challenger_votes > opponent_votes else battle.opponent
    loser = battle.opponent if winner.pk == battle.challenger_id else battle.challenger

    with transaction.atomic():
        winner_profile = get_or_create_battle_profile(winner)
        loser_profile = get_or_create_battle_profile(loser)

        old_winner_rank = winner_profile.rank
        old_loser_rank = loser_profile.rank

        rating_delta = 25
        winner_profile.wins += 1
        winner_profile.win_streak += 1
        if winner_profile.win_streak > winner_profile.best_win_streak:
            winner_profile.best_win_streak = winner_profile.win_streak
        winner_profile.rating += rating_delta
        winner_profile.reputation += 15
        winner_profile.seasonal_score += 10
        winner_profile.crown_count += 1
        winner_profile.crown_until = timezone.now() + timezone.timedelta(hours=24)
        if not winner_profile.infinite_moves:
            winner_profile.rank = rank_for_rating(winner_profile.rating)
        winner_profile.save()

        loser_profile.losses += 1
        loser_profile.win_streak = 0
        loser_profile.rating = max(0, loser_profile.rating - 15)
        loser_profile.reputation = max(-1000, loser_profile.reputation - 3)
        if not loser_profile.infinite_moves:
            loser_profile.rank = rank_for_rating(loser_profile.rating)
        loser_profile.save()

        # Award moves with typed transaction records
        from .models import BattleMoveTransaction
        TxType = BattleMoveTransaction.TxType
        from .energy_service import ENERGY_CAP
        winner_profile.battle_moves = min(
            ENERGY_CAP,
            winner_profile.battle_moves + MOVES_BATTLE_WIN + MOVES_BATTLE_PARTICIPATION,
        )
        loser_profile.battle_moves = min(
            ENERGY_CAP,
            loser_profile.battle_moves + MOVES_BATTLE_PARTICIPATION,
        )
        winner_profile.save(update_fields=["battle_moves", "updated_at"])
        loser_profile.save(update_fields=["battle_moves", "updated_at"])
        BattleMoveTransaction.objects.bulk_create([
            BattleMoveTransaction(chef=winner, amount=MOVES_BATTLE_WIN, transaction_type=TxType.BATTLE_WON),
            BattleMoveTransaction(chef=winner, amount=MOVES_BATTLE_PARTICIPATION, transaction_type=TxType.BATTLE_PARTICIPATION),
            BattleMoveTransaction(chef=loser, amount=MOVES_BATTLE_PARTICIPATION, transaction_type=TxType.BATTLE_PARTICIPATION),
        ])

        # Battle-derived faction contribution (Phase 6): gated by same-faction=0
        # and the per-opponent seasonal cap. Isolated so a faction failure can't
        # break battle completion.
        try:
            from .faction_service import award_battle_faction_contribution
            award_battle_faction_contribution(
                winner, loser, MOVES_BATTLE_WIN + MOVES_BATTLE_PARTICIPATION, battle=battle
            )
            award_battle_faction_contribution(
                loser, winner, MOVES_BATTLE_PARTICIPATION, battle=battle
            )
        except Exception:
            logger.exception("Battle faction contribution failed for battle pk=%s", battle.pk)

        # Expire unused BATTLE_GIFT artifacts locked to this battle.
        ChefArtifact.objects.filter(
            locked_to_battle=battle,
            status=ChefArtifact.Status.AVAILABLE,
            source=ChefArtifact.Source.BATTLE_GIFT,
        ).update(status=ChefArtifact.Status.EXPIRED, expired_at=timezone.now())

        battle.winner = winner
        battle.loser = loser
        battle.status = Battle.Status.COMPLETED
        battle.crown_awarded = True
        battle.result_reason = f"Public vote: {challenger_votes}-{opponent_votes}"
        battle.save(update_fields=["winner", "loser", "status", "crown_awarded", "result_reason", "updated_at"])

        from .models import LedgerEvent
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.BATTLE_COMPLETED,
            actor=winner,
            target=loser,
            related_battle=battle,
            payload={
                "challenger_votes": challenger_votes,
                "opponent_votes": opponent_votes,
                "result_reason": battle.result_reason,
            },
        )

        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_COMPLETED,
            battle=battle,
            actor=winner,
            target=loser,
            message=f"{winner.name} defeated {loser.name} in Chef Battle: {battle.theme}.",
            publish_to_news=True,
        )
        create_battle_event(
            event_type=BattleEvent.EventType.CROWN_AWARDED,
            battle=battle,
            actor=winner,
            message=f"{winner.name} holds the Crown after winning: {battle.theme}.",
            publish_to_news=True,
        )
        if winner_profile.rank != old_winner_rank:
            create_battle_event(
                event_type=BattleEvent.EventType.RANK_PROMOTED,
                battle=battle,
                actor=winner,
                message=f"{winner.name} reached {winner_profile.get_rank_display()} rank.",
                publish_to_news=True,
            )
        if loser_profile.rank != old_loser_rank:
            create_battle_event(
                event_type=BattleEvent.EventType.RANK_PROMOTED,
                battle=battle,
                actor=loser,
                message=f"{loser.name} dropped to {loser_profile.get_rank_display()} rank.",
                publish_to_news=True,
            )

    try:
        battle_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}{battle.get_absolute_url()}"
    except (NoReverseMatch, AttributeError):
        battle_url = ""
    _notify_chef(
        loser, winner,
        subject=f"You won the Chef Battle: {battle.theme}",
        body=(
            f"Congratulations! You defeated {loser.name} in Chef Battle: {battle.theme}.\n\n"
            f"Result: {battle.result_reason}\n"
            f"You now hold the Crown for 24 hours.\n\n"
            f"Battle room: {battle_url}"
        ),
    )
    _notify_chef(
        winner, loser,
        subject=f"Chef Battle result: {battle.theme}",
        body=(
            f"{winner.name} defeated you in Chef Battle: {battle.theme}.\n\n"
            f"Result: {battle.result_reason}\n\n"
            f"Battle room: {battle_url}"
        ),
    )
    drop_battle_artifacts(battle)

    # Next Battle Unlock: after battle completes, check if any pending CBR/LSR
    # for both participants can now be queued for review.
    try:
        run_next_battle_unlock_for_chef(winner)
        run_next_battle_unlock_for_chef(loser)
    except Exception:
        logger.exception("Next Battle Unlock check failed for battle %s", battle.pk)

    return battle


# ── Phase 3: Battle moves economy ────────────────────────────────────────────

from .energy_service import (  # noqa: E402
    EARN_RECIPE_PUBLISHED as MOVES_RECIPE_APPROVED,
    EARN_ARTICLE_PUBLISHED as MOVES_ARTICLE_APPROVED,
    EARN_BATTLE_WON as MOVES_BATTLE_WIN,
    EARN_BATTLE_PARTICIPATION as MOVES_BATTLE_PARTICIPATION,
    ENERGY_CAP,
    award_moves as _energy_award_moves,
    spend_moves as _energy_spend_moves,
    InsufficientEnergy,
)

MOVES_MIN_TO_CHALLENGE = 10
MOVES_REFUSE_PENALTY = 15  # Live rules 2026-07-10: refusing costs 15 Battle Moves

# Legacy cap constants kept for backward compatibility with existing tests
MOVES_CONTENT_DAILY_CAP = ENERGY_CAP
MOVES_CONTENT_WEEKLY_CAP = ENERGY_CAP

ENROL_MOVES_MAX_TO_BATTLE = 60
ENROL_MOVES_PER_RECIPE = 5
ENROL_MOVES_PER_ARTICLE = 5
ENROL_MOVES_PER_PINCH = 1
ENROL_MOVES_PER_LIKE = 1


def calculate_enrol_moves(author) -> int:
    """Calculate total moves earned from prior activity before enrolling.

    Formula: 5 per approved recipe + 5 per approved article + 1 per approved pinch
             + 1 per unique like received on content.
    Returns raw total — no minimum. Cap applied at transfer time.
    """
    from recipes.models import Recipe
    from articles.models import Article
    from pinch.models import Pinch
    from collection.models import ContentReaction
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q

    recipe_count = Recipe.objects.filter(author=author, status=Recipe.Status.APPROVED).count()
    article_count = Article.objects.filter(author=author, status=Article.Status.APPROVED).count()
    pinch_count = Pinch.objects.filter(author=author, status=Pinch.Status.APPROVED).count()

    recipe_ct = ContentType.objects.get_for_model(Recipe)
    article_ct = ContentType.objects.get_for_model(Article)
    pinch_ct = ContentType.objects.get_for_model(Pinch)
    recipe_pks = list(Recipe.objects.filter(author=author).values_list("pk", flat=True))
    article_pks = list(Article.objects.filter(author=author).values_list("pk", flat=True))
    pinch_pks = list(Pinch.objects.filter(author=author).values_list("pk", flat=True))
    like_count = ContentReaction.objects.filter(
        reaction=ContentReaction.Reaction.LIKE,
    ).filter(
        Q(content_type=recipe_ct, object_id__in=recipe_pks) |
        Q(content_type=article_ct, object_id__in=article_pks) |
        Q(content_type=pinch_ct, object_id__in=pinch_pks),
    ).count()

    return (
        recipe_count * ENROL_MOVES_PER_RECIPE
        + article_count * ENROL_MOVES_PER_ARTICLE
        + pinch_count * ENROL_MOVES_PER_PINCH
        + like_count * ENROL_MOVES_PER_LIKE
    )


def award_enrol_bonus(author) -> int:
    """Credit enrolment moves based on prior activity.

    All earned moves go to chest_moves. Then up to ENROL_MOVES_MAX_TO_BATTLE
    are transferred to battle_moves (capped by ENERGY_CAP headroom).
    Remainder stays in the chest.
    Returns total moves calculated.
    """
    from .models import BattleMoveTransaction

    profile = get_or_create_battle_profile(author)
    if profile.infinite_moves:
        return 0

    total = calculate_enrol_moves(author)
    if total <= 0:
        return 0

    # All moves land in the chest first
    profile.refresh_from_db(fields=["chest_moves", "battle_moves"])
    profile.chest_moves += total
    profile.save(update_fields=["chest_moves"])

    # Transfer up to ENROL_MOVES_MAX_TO_BATTLE from chest to battle_moves
    headroom = max(0, ENERGY_CAP - profile.battle_moves)
    to_battle = min(profile.chest_moves, ENROL_MOVES_MAX_TO_BATTLE, headroom)
    if to_battle > 0:
        profile.refresh_from_db(fields=["chest_moves", "battle_moves"])
        profile.chest_moves -= to_battle
        profile.battle_moves = min(ENERGY_CAP, profile.battle_moves + to_battle)
        profile.save(update_fields=["chest_moves", "battle_moves"])
        BattleMoveTransaction.objects.create(
            chef=author,
            amount=to_battle,
            transaction_type=BattleMoveTransaction.TxType.ENROL_BONUS,
        )

    return total


def award_moves(author, amount: int, reason: str) -> None:
    """Backward-compatible wrapper used by existing signals.

    Delegates to energy_service.award_moves with a best-guess transaction_type.
    """
    from .models import BattleMoveTransaction
    TxType = BattleMoveTransaction.TxType
    _reason_map = {
        "Recipe approved": TxType.RECIPE_PUBLISHED,
        "Article approved": TxType.ARTICLE_PUBLISHED,
        "Battle win": TxType.BATTLE_WON,
        "Battle participation": TxType.BATTLE_PARTICIPATION,
    }
    tx_type = _reason_map.get(reason, TxType.ADMIN_ADJUSTMENT)
    try:
        _energy_award_moves(author, amount, tx_type)
    except Exception:
        logger.exception("Failed to award moves to author pk=%s", getattr(author, "pk", "?"))


# ── Phase 4: Combat mechanics ─────────────────────────────────────────────────

COMBAT_MOVES_MIN = 1
COMBAT_MOVES_MAX = 5
COMBAT_HITS_TO_WIN = 3  # not used for victory — just for display drama


def get_current_round(battle: Battle) -> int:
    """Return the next round number (1-based)."""
    last = battle.combat_rounds.order_by("-round_number").first()
    return (last.round_number + 1) if last else 1


def submit_combat_action(
    battle: Battle,
    chef,
    action_type: str,
    moves_invested: int,
    artifact_id: int | None = None,
    target_ingredient_id: int | None = None,
) -> BattleCombatAction:
    """
    Chef declares their combat action for the current round.
    Moves are NOT deducted yet — only on resolve.
    Raises ValueError on invalid input.
    """
    if battle.status not in (Battle.Status.ACTIVE, Battle.Status.AWAITING_SUBMISSIONS):
        raise ValueError("Combat actions are only allowed during an active battle.")

    if not battle.author_is_participant(chef):
        raise ValueError("You are not a participant in this battle.")

    if action_type not in (BattleCombatAction.ActionType.ATTACK, BattleCombatAction.ActionType.DEFEND):
        raise ValueError("Invalid action type.")

    moves_invested = max(COMBAT_MOVES_MIN, min(COMBAT_MOVES_MAX, moves_invested))

    profile = get_or_create_battle_profile(chef)
    # infinite_moves (hero rank, bots) bypasses the balance gate exactly like
    # the energy service does on spend — the two checks must stay consistent.
    if not profile.infinite_moves and profile.battle_moves < moves_invested:
        raise ValueError(f"Not enough battle moves. You have {profile.battle_moves}.")

    # Validate artifact ownership and availability before touching the DB.
    chef_artifact = None
    if artifact_id is not None:
        try:
            chef_artifact = ChefArtifact.objects.select_related("artifact").get(
                pk=artifact_id, chef=chef, status=ChefArtifact.Status.AVAILABLE,
            )
        except ChefArtifact.DoesNotExist:
            raise ValueError("Artifact not available or does not belong to you.")

    # Validate target ingredient: must belong to the opponent, not be locked, not already eliminated.
    target_ingredient = None
    if target_ingredient_id is not None and action_type == BattleCombatAction.ActionType.ATTACK:
        opponent = battle.opponent_for(chef)
        try:
            target_ingredient = BattleIngredient.objects.get(
                pk=target_ingredient_id,
                battle=battle,
                chef=opponent,
                is_key=False,
                is_eliminated=False,
            )
        except BattleIngredient.DoesNotExist:
            raise ValueError("Invalid target: ingredient not found, is locked, or already eliminated.")

    round_number = get_current_round(battle)

    action, created = BattleCombatAction.objects.get_or_create(
        battle=battle,
        chef=chef,
        round_number=round_number,
        defaults={
            "action_type": action_type,
            "moves_invested": moves_invested,
            "artifact_used": chef_artifact,
            "target_ingredient": target_ingredient,
        },
    )
    if not created:
        if action.is_locked:
            raise ValueError("Your action for this round is already locked.")
        action.action_type = action_type
        action.moves_invested = moves_invested
        action.artifact_used = chef_artifact
        action.target_ingredient = target_ingredient
        action.save(update_fields=["action_type", "moves_invested", "artifact_used", "target_ingredient", "updated_at"])

    # Auto-resolve if both chefs have submitted
    other_chef = battle.opponent_for(chef)
    if other_chef:
        other_action = BattleCombatAction.objects.filter(
            battle=battle, chef=other_chef, round_number=round_number
        ).first()
        if other_action:
            _resolve_round(battle, round_number)

    return action


def _resolve_round(battle: Battle, round_number: int) -> BattleRound | None:
    """Resolve a round when both chefs have submitted actions. Deducts moves."""
    challenger_action = BattleCombatAction.objects.filter(
        battle=battle, chef=battle.challenger, round_number=round_number
    ).first()
    opponent_action = BattleCombatAction.objects.filter(
        battle=battle, chef=battle.opponent, round_number=round_number
    ).first()

    if not challenger_action or not opponent_action:
        return None

    # Determine attacker/defender for this round log
    # Both can attack simultaneously — resolve each direction
    # For simplicity: challenger attacks opponent, opponent defends (and vice versa)
    # Outcome based on net power comparison

    c_power = challenger_action.moves_invested
    o_power = opponent_action.moves_invested

    # Gap 2 fix: apply artifact effect if a chef activated one this round.
    # attack artifact -> bonus on ATTACK; defence/defense -> bonus on DEFEND;
    # boost -> bonus regardless of action type.
    def _artifact_bonus(action):
        ca = action.artifact_used
        if not ca or ca.status != "available":
            return 0
        et = (ca.artifact.effect_type or "").lower().replace("defence", "defense")
        ev = ca.artifact.effect_value or 0
        if et == "attack" and action.action_type == "attack":
            return ev
        if et == "defense" and action.action_type == "defend":
            return ev
        if et == "boost":
            return ev
        return 0

    c_bonus = _artifact_bonus(challenger_action)
    o_bonus = _artifact_bonus(opponent_action)

    # Consume activated artifacts inside the same resolution block
    for _action, _bonus in ((challenger_action, c_bonus), (opponent_action, o_bonus)):
        if _bonus and _action.artifact_used and _action.artifact_used.status == "available":
            ca = _action.artifact_used
            ca.status = "consumed"
            ca.consumed_at = timezone.now()
            ca.consumed_in_battle = battle
            ca.save(update_fields=["status", "consumed_at", "consumed_in_battle"])

    c_power += c_bonus
    o_power += o_bonus

    # Challenger attacks → opponent defends (and vice versa simultaneously)
    # We resolve as: whoever invested more in attack vs other's defence
    c_is_attacker = challenger_action.action_type == BattleCombatAction.ActionType.ATTACK
    o_is_attacker = opponent_action.action_type == BattleCombatAction.ActionType.ATTACK

    # Get previous round totals
    prev = battle.combat_rounds.filter(round_number=round_number - 1).first()
    prev_c_hits = prev.challenger_hits if prev else 0
    prev_o_hits = prev.opponent_hits if prev else 0

    c_hit_landed = False
    o_hit_landed = False

    if c_is_attacker and not o_is_attacker:
        # Challenger attacks, opponent defends
        if c_power > o_power * 1.5:
            outcome = BattleRound.Outcome.FULL_HIT
            c_hit_landed = True
        elif c_power > o_power:
            outcome = BattleRound.Outcome.PARTIAL_HIT
            c_hit_landed = True
        else:
            outcome = BattleRound.Outcome.BLOCKED
        attacker, defender = battle.challenger, battle.opponent
        attack_power, defence_power = c_power, o_power
    elif o_is_attacker and not c_is_attacker:
        # Opponent attacks, challenger defends
        if o_power > c_power * 1.5:
            outcome = BattleRound.Outcome.FULL_HIT
            o_hit_landed = True
        elif o_power > c_power:
            outcome = BattleRound.Outcome.PARTIAL_HIT
            o_hit_landed = True
        else:
            outcome = BattleRound.Outcome.BLOCKED
        attacker, defender = battle.opponent, battle.challenger
        attack_power, defence_power = o_power, c_power
    else:
        # Both attack or both defend — clash
        if c_power > o_power:
            outcome = BattleRound.Outcome.FULL_HIT
            c_hit_landed = True
            attacker, defender = battle.challenger, battle.opponent
        elif o_power > c_power:
            outcome = BattleRound.Outcome.FULL_HIT
            o_hit_landed = True
            attacker, defender = battle.opponent, battle.challenger
        else:
            outcome = BattleRound.Outcome.DRAW
            attacker, defender = battle.challenger, battle.opponent
        attack_power, defence_power = max(c_power, o_power), min(c_power, o_power)

    new_c_hits = prev_c_hits + (1 if c_hit_landed else 0)
    new_o_hits = prev_o_hits + (1 if o_hit_landed else 0)

    # Build log message
    outcome_labels = {
        BattleRound.Outcome.FULL_HIT: "lands a full hit",
        BattleRound.Outcome.PARTIAL_HIT: "lands a partial hit",
        BattleRound.Outcome.BLOCKED: "is blocked",
        BattleRound.Outcome.DRAW: "clash, draw",
    }
    log_msg = (
        f"{attacker.name} {outcome_labels.get(outcome, outcome)} "
        f"on {defender.name}. ({attack_power} vs {defence_power})"
    )

    with transaction.atomic():
        # Lock both actions
        BattleCombatAction.objects.filter(
            battle=battle, round_number=round_number
        ).update(is_locked=True)

        # Eliminate targeted ingredients on successful hits
        now = timezone.now()
        if c_hit_landed and challenger_action.target_ingredient_id:
            BattleIngredient.objects.filter(
                pk=challenger_action.target_ingredient_id,
                is_key=False, is_eliminated=False,
            ).update(is_eliminated=True, eliminated_at=now, eliminated_by=battle.challenger)
        if o_hit_landed and opponent_action.target_ingredient_id:
            BattleIngredient.objects.filter(
                pk=opponent_action.target_ingredient_id,
                is_key=False, is_eliminated=False,
            ).update(is_eliminated=True, eliminated_at=now, eliminated_by=battle.opponent)

        # Deduct moves via energy_service to create typed transaction records
        from .models import BattleMoveTransaction
        TxType = BattleMoveTransaction.TxType
        _energy_spend_moves(battle.challenger, challenger_action.moves_invested, TxType.COMBAT_ACTION_SPENT)
        _energy_spend_moves(battle.opponent, opponent_action.moves_invested, TxType.COMBAT_ACTION_SPENT)

        # Create round record
        round_obj = BattleRound.objects.create(
            battle=battle,
            round_number=round_number,
            attacker=attacker,
            defender=defender,
            attack_power=attack_power,
            defence_power=defence_power,
            outcome=outcome,
            challenger_hits=new_c_hits,
            opponent_hits=new_o_hits,
            log_message=log_msg,
        )

        # End combat phase when any chef reaches hits_to_win
        if new_c_hits >= COMBAT_HITS_TO_WIN or new_o_hits >= COMBAT_HITS_TO_WIN:
            battle.status = Battle.Status.AWAITING_SUBMISSIONS
            battle.save(update_fields=["status", "updated_at"])
            create_battle_event(
                battle=battle,
                event_type=BattleEvent.EventType.BATTLE_STARTED,
                message=(
                    f"Combat phase complete! "
                    f"{battle.challenger.name} {new_c_hits}:{new_o_hits} {battle.opponent.name}. "
                    f"Chefs now prepare their dishes."
                ),
            )

    return round_obj


def get_combat_state(battle: Battle) -> dict:
    """Return combat state dict for the battle room template."""
    rounds = list(battle.combat_rounds.order_by("round_number"))
    current_round = get_current_round(battle)
    last = rounds[-1] if rounds else None
    return {
        "rounds": rounds,
        "current_round": current_round,
        "challenger_hits": last.challenger_hits if last else 0,
        "opponent_hits": last.opponent_hits if last else 0,
        "hits_to_win": COMBAT_HITS_TO_WIN,
    }


# ── Pre-battle: Menu Declaration (Changing Room) ─────────────────────────────

def declare_menu(*, battle: Battle, chef, ingredients: list[dict]) -> list[BattleIngredient]:
    """Chef declares their ingredient list in the Changing Room.

    ingredients: list of dicts {'name': str, 'is_key': bool}.
    Validates count (5–7, equal to the opponent's declared count),
    exactly 2 is_key, unique names. Declaration is final — re-declaring raises.
    Transitions battle to ACTIVE when both chefs have declared.
    """
    if battle.status != Battle.Status.MENU_LOCKED:
        raise ValueError("Меню можно объявить только на стадии Changing Room (menu_locked).")
    if not battle.author_is_participant(chef):
        raise ValueError("Только участник боя может объявить меню.")
    if battle.battle_ingredients.filter(chef=chef).exists():
        raise ValueError("Меню уже объявлено и не может быть изменено.")

    count = len(ingredients)
    if count < BattleIngredient.MIN_COUNT or count > BattleIngredient.MAX_COUNT:
        raise ValueError(
            f"Список должен содержать от {BattleIngredient.MIN_COUNT} "
            f"до {BattleIngredient.MAX_COUNT} ингредиентов, получено {count}."
        )
    opponent_count = battle.battle_ingredients.filter(chef=battle.opponent_for(chef)).count()
    if opponent_count and count != opponent_count:
        raise ValueError(
            f"Соперник объявил {opponent_count} ингредиентов — ваш список должен содержать столько же."
        )
    key_count = sum(1 for i in ingredients if i.get("is_key"))
    if key_count != BattleIngredient.KEY_COUNT:
        raise ValueError(f"Необходимо отметить ровно {BattleIngredient.KEY_COUNT} ключевых ингредиента.")

    names = [i["name"].strip() for i in ingredients]
    if any(not n for n in names):
        raise ValueError("Название ингредиента не может быть пустым.")
    if len(set(n.lower() for n in names)) != len(names):
        raise ValueError("Ингредиенты не должны повторяться.")

    with transaction.atomic():
        created = []
        for pos, item in enumerate(ingredients):
            created.append(BattleIngredient.objects.create(
                battle=battle,
                chef=chef,
                name=item["name"].strip(),
                is_key=bool(item.get("is_key")),
                position=pos,
            ))

        # Transition to menu_locked when both chefs have declared
        both_declared = (
            battle.battle_ingredients.filter(chef=battle.challenger).exists()
            and battle.battle_ingredients.filter(chef=battle.opponent).exists()
        )
        if both_declared:
            battle.status = Battle.Status.ACTIVE
            battle.save(update_fields=["status"])
            create_battle_event(
                battle=battle,
                event_type=BattleEvent.EventType.BATTLE_STARTED,
                message="Оба шефа объявили меню. Бой начинается!",
                is_public=True,
            )

    return created


# ── Biathlon ─────────────────────────────────────────────────────────────────

def place_ingredient_lock(*, battle: Battle, chef, ingredient_index: int) -> IngredientLock:
    """Loser places a hidden lock on one of their ingredient lines."""
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        raise ValueError("Locks can only be placed during the ingredient penalty phase.")
    if battle.loser_id != chef.pk:
        raise ValueError("Only the loser can place ingredient locks.")
    existing = battle.ingredient_locks.filter(chef=chef).count()
    if existing >= IngredientLock.MAX_LOCKS:
        raise ValueError(f"You can only place {IngredientLock.MAX_LOCKS} locks.")
    loser_entry = battle.entries.filter(author=chef).select_related("recipe").first()
    if not loser_entry or not loser_entry.recipe:
        raise ValueError("No recipe found for this entry.")
    ingredients = [line for line in loser_entry.recipe.ingredients.splitlines() if line.strip()]
    if ingredient_index < 0 or ingredient_index >= len(ingredients):
        raise ValueError("Invalid ingredient index.")
    lock, created = IngredientLock.objects.get_or_create(
        battle=battle, chef=chef, ingredient_index=ingredient_index
    )
    if not created:
        raise ValueError("This ingredient is already locked.")
    return lock


def fire_ingredient_shot(*, battle: Battle, shooter, target_index: int) -> IngredientShot:
    """Winner fires one shot at a loser's ingredient line. Bounces off locks."""
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        raise ValueError("Shots can only be fired during the ingredient penalty phase.")
    if battle.winner_id != shooter.pk:
        raise ValueError("Only the winner can fire ingredient shots.")
    loser = battle.loser
    if not loser:
        raise ValueError("No loser found for this battle.")
    existing_shots = battle.ingredient_shots.filter(shooter=shooter).count()
    if existing_shots >= IngredientShot.MAX_SHOTS:
        raise ValueError(f"You can only fire {IngredientShot.MAX_SHOTS} shots.")
    loser_entry = battle.entries.filter(author=loser).select_related("recipe").first()
    if not loser_entry or not loser_entry.recipe:
        raise ValueError("No loser recipe found.")
    ingredients = [line for line in loser_entry.recipe.ingredients.splitlines() if line.strip()]
    if target_index < 0 or target_index >= len(ingredients):
        raise ValueError("Invalid ingredient index.")
    locked_indices = set(
        battle.ingredient_locks.filter(chef=loser).values_list("ingredient_index", flat=True)
    )
    bounced = target_index in locked_indices
    shot = IngredientShot.objects.create(
        battle=battle,
        shooter=shooter,
        target_index=target_index,
        bounced=bounced,
    )
    _post_biathlon_event(battle, shot, ingredients[target_index], bounced)
    return shot


def _post_biathlon_event(battle: Battle, shot: IngredientShot, ingredient_name: str, bounced: bool) -> None:
    if bounced:
        message = f"{battle.winner.name}'s shot at '{ingredient_name}' bounced off a lock."
    else:
        message = f"{battle.winner.name}'s shot hit '{ingredient_name}'."
    create_battle_event(battle=battle, event_type=BattleEvent.EventType.BATTLE_STARTED, message=message, actor=battle.winner, is_public=True)


def get_biathlon_state(battle: Battle) -> dict:
    """Return the full biathlon state for the template."""
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        return {}
    loser = battle.loser
    winner = battle.winner
    loser_entry = battle.entries.filter(author=loser).select_related("recipe").first() if loser else None
    ingredients = []
    if loser_entry and loser_entry.recipe:
        ingredients = [line for line in loser_entry.recipe.ingredients.splitlines() if line.strip()]
    locks = list(battle.ingredient_locks.filter(chef=loser).values_list("ingredient_index", flat=True))
    shots = list(battle.ingredient_shots.filter(shooter=winner).values("target_index", "bounced", "fired_at"))
    shot_indices = {s["target_index"] for s in shots}
    loser_locked_own = list(battle.ingredient_locks.filter(chef=loser).values_list("ingredient_index", flat=True))
    locks_placed = len(loser_locked_own)
    shots_fired = len(shots)
    loser_locks_done = locks_placed >= IngredientLock.MAX_LOCKS
    winner_shots_done = shots_fired >= IngredientShot.MAX_SHOTS
    return {
        "ingredients": ingredients,
        "locks": locks,
        "shots": shots,
        "shot_indices": shot_indices,
        "locks_placed": locks_placed,
        "shots_fired": shots_fired,
        "max_locks": IngredientLock.MAX_LOCKS,
        "max_shots": IngredientShot.MAX_SHOTS,
        "loser_locks_done": loser_locks_done,
        "winner_shots_done": winner_shots_done,
        "loser": loser,
        "winner": winner,
    }


# ── Cooking phase moderation ──────────────────────────────────────────────────

def get_surviving_ingredients(battle: Battle, chef) -> list:
    """Compute which of a chef's recipe ingredients survive the biathlon.

    For the loser: removes lines hit by non-bouncing shots.
    For the winner: returns the full ingredient list unchanged.
    Returns an empty list if no recipe entry is found.
    """
    entry = (
        battle.entries
        .filter(author=chef)
        .select_related("recipe")
        .first()
    )
    if not entry or not entry.recipe:
        return []
    all_ingredients = [
        line for line in entry.recipe.ingredients.splitlines() if line.strip()
    ]
    if battle.loser and chef.pk == battle.loser.pk:
        eliminated = set(
            battle.ingredient_shots
            .filter(bounced=False)
            .values_list("target_index", flat=True)
        )
        return [ing for i, ing in enumerate(all_ingredients) if i not in eliminated]
    return all_ingredients


def approve_cooking_phase(battle: Battle, moderator) -> Battle:
    """Moderator approves transition from INGREDIENT_PENALTY to COOKING."""
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        raise ValueError("Battle must be in ingredient_penalty status to approve cooking phase.")
    with transaction.atomic():
        # Persist surviving ingredients for each chef before status changes —
        # shots/locks are stable here; the list drives cooking-phase moderation.
        for chef in (battle.challenger, battle.opponent):
            surviving = get_surviving_ingredients(battle, chef)
            battle.entries.filter(author=chef).update(surviving_ingredients=surviving)

        battle.status = Battle.Status.COOKING
        battle.save(update_fields=["status", "updated_at"])
        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_STARTED,
            battle=battle,
            message="Cooking phase approved by moderator. Chefs may now submit their cooked dishes.",
            actor=None,
            is_public=True,
        )
    return battle


def get_battles_awaiting_cooking_approval() -> list:
    return list(
        Battle.objects.filter(status=Battle.Status.INGREDIENT_PENALTY)
        .select_related("challenger", "opponent", "winner", "loser")
        .prefetch_related("ingredient_shots", "ingredient_locks", "entries__recipe")
        .order_by("updated_at")
    )


# ── Token economy ──────────────────────────────────────────────────────────────

def get_or_create_wallet(chef) -> TokenWallet:
    wallet, _ = TokenWallet.objects.get_or_create(chef=chef)
    return wallet


def credit_tokens(chef, amount: int, tx_type: str, description: str = "", battle=None) -> TokenTransaction:
    """Add tokens to a chef's wallet. Returns the transaction."""
    if amount <= 0:
        raise ValueError("Credit amount must be positive.")
    with transaction.atomic():
        wallet = get_or_create_wallet(chef)
        # Atomic DB-side increment — a read-modify-write here loses updates
        # under concurrent credits (e.g. webhook retry + gift at once).
        TokenWallet.objects.filter(pk=wallet.pk).update(
            balance=F("balance") + amount,
            total_purchased=F("total_purchased") + amount,
            updated_at=timezone.now(),
        )
        wallet.refresh_from_db()
        return TokenTransaction.objects.create(
            wallet=wallet,
            tx_type=tx_type,
            amount=amount,
            balance_after=wallet.balance,
            description=description,
            related_battle=battle,
        )


def debit_tokens(chef, amount: int, tx_type: str, description: str = "", battle=None) -> TokenTransaction:
    """Deduct tokens from a chef's wallet. Raises ValueError if insufficient balance."""
    if amount <= 0:
        raise ValueError("Debit amount must be positive.")
    with transaction.atomic():
        wallet = get_or_create_wallet(chef)
        # Conditional atomic UPDATE: the balance check and the deduction happen
        # in one statement, so two concurrent debits cannot both pass a stale
        # balance check (double spend). Filter fails => insufficient funds.
        updated = TokenWallet.objects.filter(pk=wallet.pk, balance__gte=amount).update(
            balance=F("balance") - amount,
            total_spent=F("total_spent") + amount,
            updated_at=timezone.now(),
        )
        if not updated:
            wallet.refresh_from_db(fields=["balance"])
            raise ValueError(
                f"Insufficient tokens: need {amount}T, have {wallet.balance}T."
            )
        wallet.refresh_from_db()
        return TokenTransaction.objects.create(
            wallet=wallet,
            tx_type=tx_type,
            amount=-amount,
            balance_after=wallet.balance,
            description=description,
            related_battle=battle,
        )


# ── Cooking phase ─────────────────────────────────────────────────────────────

def submit_cooked_photo(*, battle: Battle, author, photo, real_photo_confirmed: bool = False) -> BattleEntry:
    """Chef uploads a cooked dish photo for moderation.

    Presentation opens only after both photos are explicitly approved by the
    arena owner; upload alone never publishes them.
    """
    import hashlib
    if battle.status != Battle.Status.COOKING:
        raise ValueError("Battle must be in COOKING status to submit a cooked photo.")
    entry = BattleEntry.objects.get(battle=battle, author=author)
    if entry.cooked_photo:
        raise ValueError("You have already submitted a cooked photo for this battle.")
    photo_hash = ""
    try:
        photo.seek(0)
        photo_hash = hashlib.sha256(photo.read()).hexdigest()
        photo.seek(0)
    except Exception:
        pass
    with transaction.atomic():
        entry.cooked_photo = photo
        entry.cooked_photo_submitted_at = timezone.now()
        entry.real_photo_confirmed = real_photo_confirmed
        entry.photo_hash = photo_hash
        entry.moderation_status = BattleEntry.ModerationStatus.PENDING
        entry.moderation_note = ""
        entry.reviewed_by = None
        entry.reviewed_at = None
        entry.save(update_fields=[
            "cooked_photo", "cooked_photo_submitted_at",
            "real_photo_confirmed", "photo_hash", "moderation_status",
            "moderation_note", "reviewed_by", "reviewed_at", "updated_at",
        ])
    return entry


# ── Viewer gifts ───────────────────────────────────────────────────────────────

def send_battle_artifact(*, sender_user, recipient, battle: Battle, artifact: Artifact) -> ViewerBattleGift:
    """Viewer delivers a battle artifact to a chef mid-battle.

    Total cost = artifact.token_cost * 2 (artifact price + delivery fee).
    The artifact is locked to this battle: it must be used here and cannot be
    carried to the chef's inventory. If unused when the battle ends it is expired.
    Multiple deliveries of the same artifact to the same chef are allowed.
    """
    if battle.status not in Battle.ACTIVE_STATUSES:
        raise ValueError("Cannot send battle gifts to a battle that is not active.")
    if not battle.author_is_participant(recipient):
        raise ValueError("Recipient must be a participant in this battle.")
    if not artifact.is_active:
        raise ValueError("This artifact is not available.")

    sender_author = getattr(sender_user, "recipe_author", None)
    if sender_author is None:
        from recipes.models import RecipeAuthor as RA
        sender_author = RA.objects.filter(user=sender_user).first()
    if sender_author is None:
        raise ValueError("Sender must have a chef profile to send gifts.")

    artifact_cost = artifact.token_cost
    delivery_fee = artifact_cost  # delivery fee equals the artifact price
    total_cost = artifact_cost + delivery_fee

    with transaction.atomic():
        debit_tokens(
            sender_author, total_cost,
            tx_type=TokenTransaction.TxType.GIFT_SENT,
            description=f"Battle gift: {artifact.name} to {recipient.name} (incl. delivery fee)",
            battle=battle,
        )
        gift = ViewerBattleGift.objects.create(
            battle=battle,
            recipient=recipient,
            sender=sender_user,
            artifact=artifact,
            tokens_spent=total_cost,
            delivery_fee=delivery_fee,
        )
        # Battle-locked artifact: locked_to_battle ensures it expires unused after the battle.
        ChefArtifact.objects.create(
            chef=recipient,
            artifact=artifact,
            source=ChefArtifact.Source.BATTLE_GIFT,
            status=ChefArtifact.Status.AVAILABLE,
            locked_to_battle=battle,
        )
    return gift


def send_appreciation_gift(*, sender_user, recipient, gift_type: str, message: str = "") -> AppreciationGift:
    """Viewer spends tokens to send an appreciation gift to a chef. All gifts are digital items only.

    Creates two LSR records:
    - Sender gets 10% of cost back immediately (issued to wallet).
    - Recipient chef gets a pending LSR equal to full gift cost (not credited until approved + Next Battle Unlock).
    """
    from .models import APPRECIATION_GIFT_REWARD_ELIGIBLE, APPRECIATION_GIFT_REWARD_BASIS
    cost = APPRECIATION_GIFT_COST.get(gift_type)
    if cost is None:
        raise ValueError(f"Unknown gift type: {gift_type}")

    sender_author = getattr(sender_user, "recipe_author", None)
    if sender_author is None:
        from recipes.models import RecipeAuthor as RA
        sender_author = RA.objects.filter(user=sender_user).first()
    if sender_author is None:
        raise ValueError("Sender must have a chef profile to send gifts.")

    with transaction.atomic():
        debit_tokens(
            sender_author, cost,
            tx_type=TokenTransaction.TxType.GIFT_SENT,
            description=f"Appreciation gift: {gift_type} → {recipient.name}",
        )
        gift = AppreciationGift.objects.create(
            recipient=recipient,
            sender=sender_user,
            gift_type=gift_type,
            tokens_spent=cost,
            message=message,
        )

        from .models import LedgerEvent, RewardRecord
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.GIFT_SENT,
            actor=sender_author,
            target=recipient,
            payload={"gift_type": gift_type, "tokens_spent": cost},
        )

        # LSR: sender earns 10% of the gift cost back as a Live Support Reward
        lsr_amount = max(1, cost // 10)
        reward = RewardRecord.objects.create(
            recipient=sender_author,
            reward_type=RewardRecord.RewardType.LSR,
            tokens_granted=lsr_amount,
            reason=f"LSR for sending {gift_type} to {recipient.name}",
            related_gift=gift,
        )
        credit_tokens(
            sender_author, lsr_amount,
            tx_type=TokenTransaction.TxType.ADMIN_GRANT,
            description=f"LSR reward for gift to {recipient.name}",
        )
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.LSR_GRANTED,
            actor=sender_author,
            payload={"tokens_granted": lsr_amount, "reward_id": reward.pk, "gift_type": gift_type},
        )

        # LSR for recipient chef: pending reward record (not credited until approved + Next Battle Unlock)
        if APPRECIATION_GIFT_REWARD_ELIGIBLE.get(gift_type, False):
            chef_lsr_amount = APPRECIATION_GIFT_REWARD_BASIS.get(gift_type, cost)
            chef_reward = RewardRecord.objects.create(
                recipient=recipient,
                reward_type=RewardRecord.RewardType.LSR,
                tokens_granted=chef_lsr_amount,
                reason=f"LSR: {sender_author.name} sent {gift_type}",
                related_gift=gift,
            )
            LedgerEvent.objects.create(
                event_type=LedgerEvent.EventType.LSR_GRANTED,
                actor=recipient,
                payload={
                    "source": "appreciation_gift",
                    "gift_type": gift_type,
                    "tokens_pending": chef_lsr_amount,
                    "reward_record_id": chef_reward.pk,
                    "from": sender_author.slug,
                },
            )

    return gift


# Rarity weights for artifact drops
_DROP_WEIGHTS_WINNER = {
    "common": 30,
    "uncommon": 27,
    "rare": 20,
    "epic": 15,
    "legendary": 8,
}

def _pick_artifact(chef, weights: dict, guaranteed: bool = False):
    """Pick a random artifact the chef doesn't already own, weighted by rarity.

    If guaranteed=True and weighted sampling fails (rarity pool exhausted),
    fall back to any unowned artifact so the winner always receives a drop.
    """
    import random
    rarities = list(weights.keys())
    rarity_weights = list(weights.values())
    owned_ids = set(
        ChefArtifact.objects.filter(chef=chef).values_list("artifact_id", flat=True)
    )
    for _ in range(10):
        rarity = random.choices(rarities, weights=rarity_weights, k=1)[0]
        candidates = list(
            Artifact.objects.filter(rarity=rarity, is_active=True).exclude(id__in=owned_ids)
        )
        if candidates:
            return random.choice(candidates)
    if guaranteed:
        # Fallback: pick any unowned active artifact
        fallback = list(Artifact.objects.filter(is_active=True).exclude(id__in=owned_ids))
        if fallback:
            return random.choice(fallback)
    return None


def drop_battle_artifacts(battle: Battle) -> list:
    """Award random artifact drops to participants after a completed battle.

    Winner always receives a drop (guaranteed=True).
    Loser has a 50% chance of a consolation drop.
    """
    import random
    drops = []
    winner = battle.winner
    loser = battle.loser

    participants = []
    if winner:
        participants.append((winner, _DROP_WEIGHTS_WINNER, True))
    if loser and random.random() < 0.50:
        participants.append((loser, _DROP_WEIGHTS_WINNER, False))

    for chef, weights, guaranteed in participants:
        artifact = _pick_artifact(chef, weights, guaranteed=guaranteed)
        if artifact is None:
            continue
        ca = ChefArtifact.objects.create(
            chef=chef,
            artifact=artifact,
            source=ChefArtifact.Source.DROP,
        )
        drops.append(ca)
        create_battle_event(
            event_type=BattleEvent.EventType.ARTIFACT_DROPPED,
            battle=battle,
            actor=chef,
            message=f"{chef.name} received a {artifact.get_rarity_display()} artifact drop: {artifact.name}.",
            publish_to_news=False,
        )
    return drops


# ── RewardRecord lifecycle ──────────────────────────────────────────────────

def issue_reward(reward_id: int, reviewed_by=None) -> "RewardRecord":
    """Approve a PENDING/QUEUED RewardRecord and credit tokens to the recipient's wallet.
    Raises ValueError if the record is not in an issuable state."""
    from .models import RewardRecord, TokenWallet, TokenTransaction, LedgerEvent
    from django.utils import timezone

    with transaction.atomic():
        record = RewardRecord.objects.select_for_update().get(pk=reward_id)
        if record.status not in (RewardRecord.Status.PENDING, RewardRecord.Status.QUEUED, RewardRecord.Status.APPROVED):
            raise ValueError(f"RewardRecord {reward_id} is in status '{record.status}' and cannot be issued.")

        wallet, _ = TokenWallet.objects.get_or_create(chef=record.recipient)
        new_balance = wallet.balance + record.tokens_granted
        wallet.balance = new_balance
        wallet.save(update_fields=["balance", "updated_at"])

        TokenTransaction.objects.create(
            wallet=wallet,
            tx_type=TokenTransaction.TxType.ADMIN_GRANT,
            amount=record.tokens_granted,
            balance_after=new_balance,
            description=f"{record.get_reward_type_display()}: {record.reason}",
        )

        record.status = RewardRecord.Status.ISSUED
        record.issued_at = timezone.now()
        if reviewed_by is not None:
            record.reviewed_by = reviewed_by
        record.save(update_fields=["status", "issued_at", "reviewed_by", "updated_at"])

        event_type = (
            LedgerEvent.EventType.CBR_GRANTED
            if record.reward_type == RewardRecord.RewardType.CBR
            else LedgerEvent.EventType.LSR_GRANTED
        )
        LedgerEvent.objects.create(
            event_type=event_type,
            actor=record.recipient,
            payload={
                "reward_record_id": record.pk,
                "tokens_granted": record.tokens_granted,
                "reason": record.reason,
            },
        )

    return record


def expire_rewards() -> int:
    """Mark all ISSUED RewardRecords past their expires_at as EXPIRED. Returns count."""
    from .models import RewardRecord
    from django.utils import timezone

    now = timezone.now()
    qs = RewardRecord.objects.filter(
        status=RewardRecord.Status.ISSUED,
        expires_at__isnull=False,
        expires_at__lt=now,
    )
    count = qs.update(status=RewardRecord.Status.EXPIRED)
    return count


def reverse_reward(reward_id: int, note: str = "", reversed_by=None) -> "RewardRecord":
    """Reverse an ISSUED reward: deduct tokens from wallet and mark as REVERSED."""
    from .models import RewardRecord, TokenWallet, TokenTransaction
    from django.utils import timezone

    with transaction.atomic():
        record = RewardRecord.objects.select_for_update().get(pk=reward_id)
        if record.status != RewardRecord.Status.ISSUED:
            raise ValueError(f"Only ISSUED rewards can be reversed; this one is '{record.status}'.")

        wallet = TokenWallet.objects.select_for_update().filter(chef=record.recipient).first()
        if wallet:
            deduct = min(record.tokens_granted, wallet.balance)
            if deduct > 0:
                new_balance = wallet.balance - deduct
                wallet.balance = new_balance
                wallet.save(update_fields=["balance", "updated_at"])
                TokenTransaction.objects.create(
                    wallet=wallet,
                    tx_type=TokenTransaction.TxType.ADMIN_DEDUCT,
                    amount=-deduct,
                    balance_after=new_balance,
                    description=f"Reward reversal: {record.reason}",
                )

        record.status = RewardRecord.Status.REVERSED
        record.reversed_at = timezone.now()
        record.status_note = note
        if reversed_by is not None:
            record.reviewed_by = reversed_by
        record.save(update_fields=["status", "reversed_at", "status_note", "reviewed_by", "updated_at"])

    return record


# ── Next Battle Unlock ──────────────────────────────────────────────────────

def _is_eligible_battle(battle, chef) -> bool:
    """Return True if this battle qualifies as an unlock battle for the chef's CBR/LSR.

    Eligible = completed, both entries submitted, chef's entry cooking-photo approved
    by a moderator, voting done, not cancelled/disputed/fraud-flagged.
    """
    from .models import Battle, BattleEntry

    if battle.status != Battle.Status.COMPLETED:
        return False
    if battle.status in (Battle.Status.CANCELLED, Battle.Status.DISPUTED):
        return False

    # Chef must have been a participant
    if chef not in (battle.challenger, battle.opponent):
        return False

    # Both entries must exist
    entries = list(battle.entries.select_related("author").all())
    if len(entries) < 2:
        return False

    # Chef's own entry must have moderation_status=APPROVED (cooking photo confirmed)
    chef_entry = next((e for e in entries if e.author_id == chef.pk), None)
    if chef_entry is None:
        return False
    if chef_entry.moderation_status != BattleEntry.ModerationStatus.APPROVED:
        return False

    # No fraud / suspension on chef profile at this point
    from .models import ChefBattleProfile
    profile = ChefBattleProfile.objects.filter(author=chef).first()
    if profile and (profile.is_suspended or profile.fraud_flag):
        return False

    return True


def check_next_battle_unlock(chef, reward_record) -> bool:
    """Check whether a chef has completed an eligible battle AFTER the reward record was created.

    Returns True if the unlock condition is met and the reward_record is now QUEUED for review.
    """
    from .models import Battle, RewardRecord
    from django.db.models import Q

    if reward_record.status not in (RewardRecord.Status.PENDING,):
        return reward_record.status in (
            RewardRecord.Status.QUEUED,
            RewardRecord.Status.APPROVED,
            RewardRecord.Status.ISSUED,
        )

    completed_after = Battle.objects.filter(
        Q(challenger=chef) | Q(opponent=chef),
        status=Battle.Status.COMPLETED,
        end_time__gt=reward_record.created_at,
    ).order_by("end_time")

    for battle in completed_after:
        if _is_eligible_battle(battle, chef):
            with transaction.atomic():
                rr = RewardRecord.objects.select_for_update().get(pk=reward_record.pk)
                if rr.status == RewardRecord.Status.PENDING:
                    rr.status = RewardRecord.Status.QUEUED
                    rr.status_note = f"Unlocked by battle #{battle.pk}"
                    rr.save(update_fields=["status", "status_note", "updated_at"])
            return True

    return False


def run_next_battle_unlock_for_chef(chef) -> int:
    """Check all PENDING reward records for a chef and queue any that are now unlocked.

    Returns the count of records moved to QUEUED status.
    Called after calculate_battle_result() to unlock rewards from previous battles.
    """
    from .models import RewardRecord
    pending = RewardRecord.objects.filter(
        recipient=chef, status=RewardRecord.Status.PENDING
    ).order_by("created_at")
    count = 0
    for record in pending:
        if check_next_battle_unlock(chef, record):
            count += 1
    return count


def handle_token_order_chargeback(token_order_id: int, chargeback: bool = False) -> dict:
    """Lock a token order and reverse related rewards when a refund or chargeback occurs.

    - Marks the TokenOrder as refunded (or disputed if chargeback=True).
    - Reverses any PENDING/QUEUED reward records linked to gifts funded by this order.
    - Flags all related AppreciationGift records.
    - Suspends the chef's payout eligibility flag.
    - Creates an immutable ledger entry for the compliance record.
    - Never silently deletes any records.

    Returns a summary dict with counts of affected records.
    """
    from .models import (
        AppreciationGift, LedgerEvent, RewardRecord, TokenOrder, TokenWallet, TokenTransaction,
    )

    with transaction.atomic():
        try:
            order = TokenOrder.objects.select_for_update().select_related("wallet__chef").get(pk=token_order_id)
        except TokenOrder.DoesNotExist:
            logger.error("handle_token_order_chargeback: TokenOrder %s not found", token_order_id)
            return {"error": "TokenOrder not found"}

        buyer_author = getattr(order.wallet, "chef", None)

        new_status = TokenOrder.Status.DISPUTED if chargeback else TokenOrder.Status.REFUNDED
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        # Deduct tokens from buyer's wallet if they were credited
        deducted_tokens = 0
        if buyer_author and order.tokens and order.tokens > 0:
            wallet = TokenWallet.objects.filter(chef=buyer_author).select_for_update().first()
            if wallet:
                actual_deduct = min(wallet.balance, order.tokens)
                if actual_deduct > 0:
                    wallet.balance -= actual_deduct
                    wallet.save(update_fields=["balance"])
                    TokenTransaction.objects.create(
                        wallet=wallet,
                        tx_type=TokenTransaction.TxType.REFUND,
                        amount=-actual_deduct,
                        balance_after=wallet.balance,
                        description=f"{'Chargeback' if chargeback else 'Refund'} — order #{order.pk}",
                    )
                    deducted_tokens = actual_deduct

        # Reverse PENDING/QUEUED rewards linked to gifts sent after this order's purchase
        reversed_rewards = 0
        buyer_user = getattr(buyer_author, "user", None) if buyer_author else None
        if buyer_user:
            reversible_statuses = [RewardRecord.Status.PENDING, RewardRecord.Status.QUEUED]
            gifts = AppreciationGift.objects.filter(
                sender=buyer_user,
                sent_at__gte=order.created_at,
            ).values_list("pk", flat=True)

            rewards_qs = RewardRecord.objects.select_for_update().filter(
                related_gift__in=gifts,
                status__in=reversible_statuses,
            )
            for rr in rewards_qs:
                rr.status = RewardRecord.Status.REVERSED
                rr.status_note = f"Reversed: {'chargeback' if chargeback else 'refund'} on order #{order.pk}"
                rr.save(update_fields=["status", "status_note", "updated_at"])
                reversed_rewards += 1

        # Flag related gifts for compliance review
        flagged_gifts = 0
        if buyer_user:
            flagged_gifts = AppreciationGift.objects.filter(
                sender=buyer_user,
                sent_at__gte=order.created_at,
                is_flagged=False,
            ).update(is_flagged=True)

        # Flag the buyer's profile for compliance review
        if buyer_author:
            profile = ChefBattleProfile.objects.filter(author=buyer_author).first()
            if profile and not profile.payout_blocked:
                profile.payout_blocked = True
                profile.save(update_fields=["payout_blocked"])

        action = "chargeback" if chargeback else "refund"
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.CHARGEBACK_LOCK,
            actor=buyer_author,
            payload={
                "action": action,
                "token_order_id": token_order_id,
                "new_status": new_status,
                "deducted_tokens": deducted_tokens,
                "reversed_rewards": reversed_rewards,
                "flagged_gifts": flagged_gifts,
            },
        )
        logger.info(
            "handle_token_order_chargeback: order=%s action=%s deducted=%s reversed=%s flagged=%s",
            token_order_id, action, deducted_tokens, reversed_rewards, flagged_gifts,
        )
        return {
            "order_id": token_order_id,
            "new_status": new_status,
            "deducted_tokens": deducted_tokens,
            "reversed_rewards": reversed_rewards,
            "flagged_gifts": flagged_gifts,
        }


def check_payout_eligibility(chef) -> dict:
    """Return a dict of {eligible: bool, reasons: list[str]} for payout request validation.

    Checks (all must pass):
    1. Chef profile exists and age_verified=True
    2. reward_agreement_accepted=True
    3. stripe_connect_onboarded=True
    4. not is_suspended and not fraud_flag and not payout_blocked
    5. Minimum 2000 APPROVED reward tokens (across all RewardRecord)
    6. No open PayoutRequest (PENDING or UNDER_REVIEW)
    """
    from .models import ChefBattleProfile, PayoutRequest, RewardRecord

    reasons = []

    profile = ChefBattleProfile.objects.filter(author=chef).first()
    if profile is None:
        return {"eligible": False, "reasons": ["No Chef Battle profile found."]}

    if not profile.age_verified:
        reasons.append("You must confirm you are 18 or older.")
    if not profile.reward_agreement_accepted:
        reasons.append("You must accept the Chef Reward Agreement before requesting a payout.")
    if not profile.stripe_connect_onboarded:
        reasons.append("Stripe Connect onboarding is not complete.")
    if profile.is_suspended:
        reasons.append("Your account is currently suspended.")
    if profile.fraud_flag:
        reasons.append("Your account has an active fraud flag under review.")
    if profile.payout_blocked:
        reasons.append("Your payout eligibility is blocked pending compliance review.")

    approved_tokens = RewardRecord.objects.filter(
        recipient=chef, status=RewardRecord.Status.APPROVED
    ).aggregate(total=Sum("tokens_granted"))["total"] or 0
    MIN_TOKENS = 2000
    if approved_tokens < MIN_TOKENS:
        reasons.append(
            f"Minimum {MIN_TOKENS} approved reward tokens required. You have {approved_tokens}."
        )

    open_request = PayoutRequest.objects.filter(
        chef=chef, status__in=[PayoutRequest.Status.PENDING, PayoutRequest.Status.UNDER_REVIEW]
    ).exists()
    if open_request:
        reasons.append("You already have a payout request under review.")

    return {"eligible": len(reasons) == 0, "reasons": reasons, "approved_tokens": approved_tokens}


def create_payout_request(chef, request_http=None) -> "PayoutRequest":
    """Create a PayoutRequest for a chef after eligibility checks pass.

    Locks all APPROVED reward records to ISSUED status immediately so they
    cannot be double-spent. Rate snapshot is frozen at creation time.
    Raises ValueError if not eligible.
    """
    from decimal import Decimal
    from .models import ChefBattleProfile, ChefRewardAgreement, DAC7Record, LedgerEvent, PayoutRequest, RewardRecord

    eligibility = check_payout_eligibility(chef)
    if not eligibility["eligible"]:
        raise ValueError(" ".join(eligibility["reasons"]))

    profile = ChefBattleProfile.objects.get(author=chef)
    dac7 = DAC7Record.objects.filter(chef=chef).first()
    agreement = ChefRewardAgreement.objects.filter(chef=chef).order_by("-accepted_at").first()

    rate = Decimal(PayoutRequest.PAYOUT_RATE_EUR_PER_TOKEN)

    with transaction.atomic():
        approved_records = RewardRecord.objects.select_for_update().filter(
            recipient=chef, status=RewardRecord.Status.APPROVED
        )
        total_tokens = sum(r.tokens_granted for r in approved_records)
        if total_tokens < 2000:
            raise ValueError("Not enough approved tokens.")

        gross_eur = (Decimal(total_tokens) * rate).quantize(Decimal("0.01"))

        payout = PayoutRequest.objects.create(
            chef=chef,
            dac7_record=dac7,
            reward_agreement=agreement,
            amount_reward_tokens=total_tokens,
            payout_rate_snapshot=rate,
            gross_payout_eur=gross_eur,
            stripe_connect_account_id=dac7.stripe_connect_account_id if dac7 else "",
        )

        # Move approved records to ISSUED (locked for this payout)
        for record in approved_records:
            record.status = RewardRecord.Status.ISSUED
            record.status_note = f"Locked for PayoutRequest #{payout.pk}"
            record.save(update_fields=["status", "status_note", "updated_at"])

        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ADMIN_NOTE,
            actor=chef,
            payload={
                "action": "payout_request_created",
                "payout_request_id": payout.pk,
                "total_tokens": total_tokens,
                "gross_eur": str(gross_eur),
                "rate": str(rate),
            },
        )

    logger.info("Payout request #%s created for %s: %sT / €%s", payout.pk, chef, total_tokens, gross_eur)
    return payout


def approve_payout_request(payout_request_id: int, reviewed_by_user) -> "PayoutRequest":
    """Admin: approve a PayoutRequest and trigger Stripe Connect transfer.

    Sets status to APPROVED (then PAID after transfer). Moves ISSUED reward records to ACKNOWLEDGED.
    """
    from .models import LedgerEvent, PayoutRequest, RewardRecord

    with transaction.atomic():
        try:
            payout = PayoutRequest.objects.select_for_update().get(pk=payout_request_id)
        except PayoutRequest.DoesNotExist:
            raise ValueError(f"PayoutRequest #{payout_request_id} not found.")

        if payout.status not in (PayoutRequest.Status.PENDING, PayoutRequest.Status.UNDER_REVIEW):
            raise ValueError(f"PayoutRequest #{payout_request_id} is in status '{payout.status}' and cannot be approved.")

        payout.status = PayoutRequest.Status.APPROVED
        payout.reviewed_by = reviewed_by_user
        payout.reviewed_at = timezone.now()
        payout.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ADMIN_NOTE,
            actor=payout.chef,
            payload={
                "action": "payout_approved",
                "payout_request_id": payout.pk,
                "approved_by": reviewed_by_user.username,
                "gross_eur": str(payout.gross_payout_eur),
            },
        )

    # Attempt Stripe Connect transfer outside the atomic block
    try:
        _execute_stripe_connect_transfer(payout)
    except Exception:
        logger.exception("Stripe Connect transfer failed for PayoutRequest #%s", payout_request_id)
        # Leave as APPROVED — admin can retry

    return payout


def reject_payout_request(payout_request_id: int, reviewed_by_user, reason: str) -> "PayoutRequest":
    """Admin: reject a PayoutRequest. Moves ISSUED reward records back to APPROVED."""
    from .models import LedgerEvent, PayoutRequest, RewardRecord

    with transaction.atomic():
        try:
            payout = PayoutRequest.objects.select_for_update().get(pk=payout_request_id)
        except PayoutRequest.DoesNotExist:
            raise ValueError(f"PayoutRequest #{payout_request_id} not found.")

        if payout.status not in (PayoutRequest.Status.PENDING, PayoutRequest.Status.UNDER_REVIEW, PayoutRequest.Status.APPROVED):
            raise ValueError(f"PayoutRequest #{payout_request_id} cannot be rejected from status '{payout.status}'.")

        payout.status = PayoutRequest.Status.REJECTED
        payout.reviewed_by = reviewed_by_user
        payout.reviewed_at = timezone.now()
        payout.rejection_reason = reason
        payout.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])

        # Return ISSUED records to APPROVED so chef can re-request
        RewardRecord.objects.filter(
            recipient=payout.chef,
            status=RewardRecord.Status.ISSUED,
            status_note__contains=f"PayoutRequest #{payout.pk}",
        ).update(status=RewardRecord.Status.APPROVED, status_note="Returned: payout rejected")

        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ADMIN_NOTE,
            actor=payout.chef,
            payload={
                "action": "payout_rejected",
                "payout_request_id": payout.pk,
                "rejected_by": reviewed_by_user.username,
                "reason": reason,
            },
        )

    return payout


def _execute_stripe_connect_transfer(payout: "PayoutRequest") -> None:
    """Attempt a Stripe Connect transfer for an approved payout. Updates status to PAID on success."""
    from decimal import Decimal
    from .models import LedgerEvent, PayoutRequest

    if not payout.stripe_connect_account_id:
        logger.error("No Stripe Connect account ID on PayoutRequest #%s", payout.pk)
        return

    try:
        import stripe
        stripe.api_key = __import__("django.conf", fromlist=["settings"]).settings.STRIPE_SECRET_KEY
        transfer = stripe.Transfer.create(
            amount=int(payout.gross_payout_eur * 100),
            currency=payout.currency or "eur",
            destination=payout.stripe_connect_account_id,
            metadata={"payout_request_id": str(payout.pk), "chef": str(payout.chef_id)},
        )
        transfer_id = transfer.get("id", "")
        with transaction.atomic():
            pr = PayoutRequest.objects.select_for_update().get(pk=payout.pk)
            pr.status = PayoutRequest.Status.PAID
            pr.stripe_transfer_id = transfer_id
            pr.paid_at = timezone.now()
            pr.save(update_fields=["status", "stripe_transfer_id", "paid_at", "updated_at"])
            LedgerEvent.objects.create(
                event_type=LedgerEvent.EventType.ADMIN_NOTE,
                actor=payout.chef,
                payload={
                    "action": "payout_paid",
                    "payout_request_id": payout.pk,
                    "stripe_transfer_id": transfer_id,
                    "gross_eur": str(payout.gross_payout_eur),
                },
            )
        logger.info("PayoutRequest #%s paid: transfer %s", payout.pk, transfer_id)
    except ImportError:
        logger.error("stripe package not installed — cannot execute transfer for PayoutRequest #%s", payout.pk)
    except Exception:
        logger.exception("Stripe transfer failed for PayoutRequest #%s", payout.pk)
        raise


def get_chef_payout_statement(chef) -> dict:
    """Return a summary dict for a chef's reward/payout ledger page.

    Used in the chef profile payout statement view.
    """
    from .models import PayoutRequest, RewardRecord

    reward_summary = {}
    for status in RewardRecord.Status:
        reward_summary[status.value] = RewardRecord.objects.filter(
            recipient=chef, status=status
        ).aggregate(total=Sum("tokens_granted"), count=Count("pk"))

    payout_history = PayoutRequest.objects.filter(chef=chef).order_by("-requested_at")[:20]

    eligibility = check_payout_eligibility(chef)

    return {
        "reward_summary": reward_summary,
        "payout_history": payout_history,
        "eligibility": eligibility,
    }


def submit_content_report(
    reporter,
    content_kind: str,
    object_id: int,
    reason: str,
) -> "ContentReport":
    """Create a DSA/platform content report.

    reporter: the User (not RecipeAuthor) submitting the report.
    content_kind: one of ContentReport.ContentKind values.
    object_id: PK of the reported object.
    reason: free-text reason (shown to moderators).
    Returns the created ContentReport.
    """
    from .models import ContentReport, LedgerEvent

    report = ContentReport.objects.create(
        reporter=reporter,
        content_kind=content_kind,
        object_id=object_id,
        reason=reason,
        status=ContentReport.Status.PENDING,
    )

    reporter_author = getattr(reporter, "recipe_author", None)
    LedgerEvent.objects.create(
        event_type=LedgerEvent.EventType.CONTENT_REPORT,
        actor=reporter_author,
        payload={
            "report_id": report.pk,
            "content_kind": content_kind,
            "object_id": object_id,
        },
    )
    return report


# ── Reward Agreement ─────────────────────────────────────────────────────────

REWARD_AGREEMENT_TEXT_v1 = """CHEF BATTLE REWARD AGREEMENT

By accepting this agreement you confirm that you have read and understood the following terms.

1. NATURE OF REWARDS
CulinEire Chef Battle Rewards (CBR) and Live Support Rewards (LSR) are discretionary platform rewards granted at the sole discretion of CulinEire. They are not money, not user funds, not e-money, and confer no legal right to payment.

2. CONVERSION AND PAYOUT
Approved reward tokens may be converted to real-money payouts at a rate of €0.025 per token, subject to a minimum threshold of 2,000 approved reward tokens. The payout rate may change for future reward grants; the rate is locked at request time.

3. ELIGIBILITY CONDITIONS
Payout requests are subject to: (a) age verification (18+); (b) completion of Stripe Connect onboarding; (c) no active fraud flags, suspensions, or compliance holds; and (d) acceptance of this agreement.

4. REVERSAL AND FORFEITURE
The platform reserves the right to reverse, void, or expire rewards at any time for breach of Chef Battles rules, fraudulent activity, chargebacks, or material policy violations.

5. TAX AND REPORTING (DAC7)
Payouts are subject to EU Directive 2021/514 (DAC7 / MRDP) reporting obligations. By accepting, you consent to the collection of your identity and income data and its annual reporting to Irish Revenue where applicable thresholds are met. Data is retained for 10 years.

6. GOVERNING LAW
This agreement is governed by the laws of Ireland. Disputes are subject to the exclusive jurisdiction of the Irish courts.

CulinEire is a trading name of Bearcave Limited, registered in Ireland."""


def accept_reward_agreement(chef, ip_address: str = "", user_agent: str = "") -> "ChefRewardAgreement":
    """Record a chef's acceptance of the Chef Reward Agreement and set the profile flag."""
    from .models import ChefBattleProfile, ChefRewardAgreement

    agreement = ChefRewardAgreement.objects.create(
        chef=chef,
        agreement_version="1.0",
        consent_text_snapshot=REWARD_AGREEMENT_TEXT_v1,
        ip_address=ip_address or None,
        user_agent=user_agent[:512] if user_agent else "",
    )
    ChefBattleProfile.objects.filter(author=chef).update(reward_agreement_accepted=True)
    logger.info("Chef %s accepted Reward Agreement v1.0", chef)
    return agreement


# ── Forbidden claims detection (PDF v6 §30) ──────────────────────────────────

_FORBIDDEN_PHRASES = [
    "safe for all allerg",
    "free from all allerg",
    "suitable for all allerg",
    "cures diabetes",
    "cures cancer",
    "prevents disease",
    "eliminates disease",
    "clinically proven",
    "medically proven",
    "doctor recommended",
    "guaranteed weight loss",
    "burn fat fast",
    "detox your body",
    "cleanse your body",
    "boost your immune system",
    "no risk",
    "100% safe",
    "completely safe for",
]


def check_forbidden_claims(text: str) -> list[str]:
    """Return list of forbidden phrases found in text (case-insensitive). Empty list = clean."""
    lower = (text or "").lower()
    return [phrase for phrase in _FORBIDDEN_PHRASES if phrase in lower]


# ═════════════════════════════════════════════════════════════════════════════
# Arena Master Console operator orchestration (P03).
# DG-02: ONLY the owner (OWNER_SLUG) may force phase transitions.
# Every action: transactional, idempotency-guarded via expected_status,
# audited as a BattleEvent OPERATOR_ACTION with a correlation id.
# Contract: docs/chef_battle/arena_master_console/P03_TRANSITION_MATRIX.yaml.
# ═════════════════════════════════════════════════════════════════════════════

class OperatorActionError(ValueError):
    """Raised when an operator action is rejected (invalid state, stale
    expected_status, unauthorized actor). Message is safe to show in the UI."""


def _require_owner(operator_author):
    if not operator_author or operator_author.slug != settings.OWNER_SLUG:
        raise OperatorActionError("Only the arena owner may perform this action.")


def _operator_event(*, battle, operator_author, action, before, after, reason, correlation_id, extra=None):
    payload = {
        "action": action,
        "before_status": before,
        "after_status": after,
        "reason": reason,
        "correlation_id": correlation_id,
        "outcome": "applied",
    }
    if extra:
        payload.update(extra)
    event = create_battle_event(
        event_type=BattleEvent.EventType.OPERATOR_ACTION,
        battle=battle,
        actor=operator_author,
        message=f"Operator action '{action}': {before} -> {after}. Reason: {reason or 'not given'}.",
        is_public=False,
    )
    event.payload_json = payload
    event.save(update_fields=["payload_json"])
    return event


def record_rejected_operator_action(
    *, action, operator_author, error, correlation_id="", battle_id=None, extra=None,
):
    """Private audit trail for a console write attempt that did NOT apply:
    permission denial (403), invalid/malformed input (400), not-found (404),
    or a service-level rejection (stale expected_status, missing reason,
    invalid transition — 409). Mirrors ``_operator_event``'s shape but with
    ``outcome: "rejected"`` so an investigation can reconstruct every
    attempted high-risk action, not only the ones that succeeded. Never
    raises: a battle lookup failure here must not mask the original error.
    """
    battle = None
    if battle_id:
        try:
            battle = Battle.objects.filter(pk=battle_id).first()
        except (TypeError, ValueError):
            battle = None
    payload = {
        "action": action,
        "correlation_id": correlation_id,
        "outcome": "rejected",
        "error": str(error)[:300],
    }
    if extra:
        payload.update(extra)
    event = create_battle_event(
        event_type=BattleEvent.EventType.OPERATOR_ACTION,
        battle=battle,
        actor=operator_author,
        message=f"Operator action '{action}' REJECTED: {error}"[:500],
        is_public=False,
    )
    event.payload_json = payload
    event.save(update_fields=["payload_json"])
    return event


def _locked_battle(battle_id, expected_status):
    """Fetch the battle under row lock and verify the operator saw the
    current state (stale-click / double-click / concurrent-operator guard)."""
    battle = Battle.objects.select_for_update().select_related(
        "challenger", "opponent"
    ).get(pk=battle_id)
    if expected_status and battle.status != expected_status:
        raise OperatorActionError(
            f"Stale state: battle is now '{battle.status}', not '{expected_status}'. "
            "Refresh and retry."
        )
    return battle


def _notify_participants(battle, subject, body, operator_author):
    """Notify both chefs via the existing in-site + email channel."""
    for author in (battle.challenger, battle.opponent):
        _notify_chef(operator_author, author, subject, body)


# Transitions where an existing domain service owns the invariant.
# The operator force path MUST call the service, never assign directly.
_SERVICE_OWNED_TRANSITIONS = {
    (Battle.Status.INGREDIENT_PENALTY, Battle.Status.COOKING): "approve_cooking_phase",
    (Battle.Status.VOTING, Battle.Status.COMPLETED): "calculate_battle_result",
    (Battle.Status.ACTIVE, Battle.Status.COMPLETED): "calculate_battle_result",
}

# Force-transition targets the console may request at all.
OPERATOR_ALLOWED_TARGETS = {
    Battle.Status.SCHEDULED, Battle.Status.MENU_LOCKED, Battle.Status.ACTIVE,
    Battle.Status.AWAITING_SUBMISSIONS, Battle.Status.REVEALED,
    Battle.Status.COOKING, Battle.Status.PRESENTATION, Battle.Status.VOTING,
    Battle.Status.COMPLETED, Battle.Status.INGREDIENT_PENALTY,
}


def operator_force_status(
    *, battle_id, operator_author, target_status, expected_status,
    reason="", correlation_id="",
):
    """GreenBear-only forced phase transition (DG-02).

    Uses the owning domain service when one exists for the transition;
    direct assignment only for states no service covers, inside the same
    transaction, always audited."""
    _require_owner(operator_author)
    if target_status not in OPERATOR_ALLOWED_TARGETS:
        raise OperatorActionError(f"'{target_status}' is not a valid force target.")

    with transaction.atomic():
        battle = _locked_battle(battle_id, expected_status)
        before = battle.status
        if before == target_status:
            raise OperatorActionError(f"Battle is already '{target_status}'.")
        if before == Battle.Status.PAUSED:
            raise OperatorActionError("Battle is paused. Use Resume or Cancel first.")

        service_name = _SERVICE_OWNED_TRANSITIONS.get((before, target_status))
        if service_name == "approve_cooking_phase":
            approve_cooking_phase(battle, operator_author)
        elif service_name == "calculate_battle_result":
            calculate_battle_result(battle)
            battle.refresh_from_db()
            if battle.status != Battle.Status.COMPLETED:
                raise OperatorActionError(
                    f"Result service left battle in '{battle.status}'; not forcing further."
                )
        else:
            battle.status = target_status
            battle.save(update_fields=["status", "updated_at"])

        _operator_event(
            battle=battle, operator_author=operator_author,
            action="force_status", before=before, after=battle.status,
            reason=reason, correlation_id=correlation_id,
            extra={"service_used": service_name or "direct"},
        )
    return battle


def operator_emergency_stop(*, battle_id, operator_author, reason, correlation_id=""):
    """Emergency Stop per DG-03: PAUSED status, timers freeze (frontend reads
    is_paused), live streams terminated, audit event, chefs notified."""
    _require_owner(operator_author)
    if not (reason or "").strip():
        raise OperatorActionError("Emergency Stop requires a reason.")

    with transaction.atomic():
        battle = _locked_battle(battle_id, expected_status=None)
        before = battle.status
        if before == Battle.Status.PAUSED:
            raise OperatorActionError("Battle is already paused.")
        if before in (Battle.Status.COMPLETED, Battle.Status.CANCELLED):
            raise OperatorActionError(f"Cannot pause a {before} battle.")

        now = timezone.now()
        battle.paused_from_status = before
        battle.paused_at = now
        battle.paused_reason = reason
        battle.status = Battle.Status.PAUSED
        battle.save(update_fields=[
            "status", "paused_at", "paused_reason", "paused_from_status", "updated_at",
        ])

        terminated = list(
            battle.live_streams.filter(
                status__in=[LiveStreamSession.Status.SCHEDULED, LiveStreamSession.Status.LIVE]
            )
        )
        for stream in terminated:
            stream.status = LiveStreamSession.Status.TERMINATED
            stream.ended_at = now
            stream.terminated_reason = f"Emergency Stop: {reason}"[:300]
            stream.terminated_by = operator_author.user
            stream.save(update_fields=[
                "status", "ended_at", "terminated_reason", "terminated_by", "updated_at",
            ])

        _operator_event(
            battle=battle, operator_author=operator_author,
            action="emergency_stop", before=before, after=Battle.Status.PAUSED,
            reason=reason, correlation_id=correlation_id,
            extra={"streams_terminated": len(terminated)},
        )
        _notify_participants(
            battle,
            subject=f"Battle #{battle.pk} paused (Emergency Stop)",
            body=(
                f"Your battle '{battle.theme}' has been paused by the arena operator. "
                f"Reason: {reason}. All timers are frozen; you will be notified when "
                "the battle resumes or is cancelled."
            ),
            operator_author=operator_author,
        )
    return battle


def operator_resume(*, battle_id, operator_author, correlation_id=""):
    """Resume a PAUSED battle to the status it was paused from (DG-03)."""
    _require_owner(operator_author)
    with transaction.atomic():
        battle = _locked_battle(battle_id, expected_status=Battle.Status.PAUSED)
        restore_to = battle.paused_from_status
        if not restore_to:
            raise OperatorActionError("No pre-pause status recorded; cannot resume.")
        resumed_at = timezone.now()
        pause_duration = max(
            timezone.timedelta(0),
            resumed_at - battle.paused_at if battle.paused_at else timezone.timedelta(0),
        )
        shifted_deadlines = []
        for field_name in ("submission_deadline", "voting_deadline", "end_time"):
            deadline = getattr(battle, field_name)
            if deadline is not None:
                setattr(battle, field_name, deadline + pause_duration)
                shifted_deadlines.append(field_name)
        battle.status = restore_to
        battle.paused_at = None
        battle.paused_reason = ""
        battle.paused_from_status = ""
        battle.save(update_fields=[
            "status", "paused_at", "paused_reason", "paused_from_status", "updated_at",
            *shifted_deadlines,
        ])
        _operator_event(
            battle=battle, operator_author=operator_author,
            action="resume", before=Battle.Status.PAUSED, after=restore_to,
            reason="", correlation_id=correlation_id,
            extra={
                "pause_duration_seconds": max(0, int(pause_duration.total_seconds())),
                "shifted_deadlines": shifted_deadlines,
            },
        )
        _notify_participants(
            battle,
            subject=f"Battle #{battle.pk} resumed",
            body=f"Your battle '{battle.theme}' has resumed in phase '{restore_to}'.",
            operator_author=operator_author,
        )
    return battle


def operator_cancel(*, battle_id, operator_author, reason, correlation_id=""):
    """Cancel a battle (owner-only). Follows the handle_no_show_battles
    cancellation pattern: CANCELLED + result_reason + audit event."""
    _require_owner(operator_author)
    if not (reason or "").strip():
        raise OperatorActionError("Cancellation requires a reason.")
    with transaction.atomic():
        battle = _locked_battle(battle_id, expected_status=None)
        before = battle.status
        if before in (Battle.Status.COMPLETED, Battle.Status.CANCELLED):
            raise OperatorActionError(f"Cannot cancel a {before} battle.")
        battle.status = Battle.Status.CANCELLED
        battle.result_reason = f"Cancelled by arena operator: {reason}"[:120]
        if before == Battle.Status.PAUSED:
            battle.paused_at = None
            battle.paused_from_status = ""
            battle.paused_reason = ""
        battle.save(update_fields=[
            "status", "result_reason", "paused_at", "paused_from_status",
            "paused_reason", "updated_at",
        ])
        _operator_event(
            battle=battle, operator_author=operator_author,
            action="cancel", before=before, after=Battle.Status.CANCELLED,
            reason=reason, correlation_id=correlation_id,
        )
        _notify_participants(
            battle,
            subject=f"Battle #{battle.pk} cancelled",
            body=f"Your battle '{battle.theme}' was cancelled by the arena operator. Reason: {reason}.",
            operator_author=operator_author,
        )
    return battle


def operator_delete_test_battle(*, battle_id, operator_author, correlation_id=""):
    """Permanently remove unscored test data from the dark-launch console.

    This is unavailable once Chef Battles is public. A scored result changes
    chef profiles and move ledgers, so only battles without a winner or crown
    can be erased safely. The linked challenge is removed as well, keeping the
    test console and challenge inboxes clean.
    """
    _require_owner(operator_author)
    if getattr(settings, "CHEF_BATTLE_ENABLED", False):
        raise OperatorActionError(
            "Test battle deletion is only available while Chef Battles is in test mode."
        )

    with transaction.atomic():
        battle = _locked_battle(battle_id, expected_status=None)
        if battle.winner_id or battle.loser_id or battle.crown_awarded:
            raise OperatorActionError(
                "This battle has a scored result and cannot be deleted safely."
            )

        deleted = {
            "id": battle.pk,
            "theme": battle.theme,
            "status": battle.status,
            "challenge_id": battle.challenge_id,
        }
        if battle.challenge_id:
            BattleChallenge.objects.select_for_update().filter(
                pk=battle.challenge_id
            ).delete()
        battle.delete()

    logger.warning(
        "Owner %s deleted unscored test battle #%s (correlation=%s).",
        operator_author.slug,
        deleted["id"],
        correlation_id,
    )
    return deleted


def operator_broadcast(*, operator_author, message, battle_id=None, correlation_id=""):
    """Owner-only public announcement into the battle event feed.

    Unlike force_status/emergency_stop/resume/cancel, a broadcast has no
    target state a repeat click would already satisfy — it is not naturally
    idempotent. A supplied correlation_id is therefore enforced as a genuine
    replay guard: the unique-constrained insert into
    OperatorActionIdempotencyKey happens inside the same transaction as event
    creation, so a duplicate/replayed request (or a real race between two
    simultaneous requests with the same key) raises IntegrityError and rolls
    back before a second public announcement is ever created.
    """
    _require_owner(operator_author)
    if not (message or "").strip():
        raise OperatorActionError("Broadcast message cannot be empty.")
    with transaction.atomic():
        if correlation_id:
            try:
                OperatorActionIdempotencyKey.objects.create(
                    correlation_id=correlation_id, action="broadcast",
                )
            except IntegrityError:
                raise OperatorActionError(
                    "This broadcast was already sent (duplicate request)."
                )
        battle = Battle.objects.get(pk=battle_id) if battle_id else None
        event = create_battle_event(
            event_type=BattleEvent.EventType.OPERATOR_ACTION,
            battle=battle,
            actor=operator_author,
            message=message.strip()[:500],
            is_public=True,
        )
        event.payload_json = {
            "action": "broadcast", "correlation_id": correlation_id, "outcome": "applied",
        }
        event.save(update_fields=["payload_json"])
    return event


# ═════════════════════════════════════════════════════════════════════════════
# P05 — Moderation & safety operator actions (owner-only per DG-01 access
# model: non-owner console operators are read-only). Reasons are mandatory
# for every adverse action; everything is audited as OPERATOR_ACTION.
# ═════════════════════════════════════════════════════════════════════════════

# Entry statuses the console may set. Adverse ones require a reason.
_ENTRY_ADVERSE = {
    BattleEntry.ModerationStatus.FLAGGED,
    BattleEntry.ModerationStatus.REJECTED,
    BattleEntry.ModerationStatus.NEEDS_CHANGES,
}
_ENTRY_ALLOWED = _ENTRY_ADVERSE | {BattleEntry.ModerationStatus.APPROVED}


def operator_moderate_entry(*, entry_id, operator_author, new_status, reason="",
                            correlation_id=""):
    """Owner-only battle-entry moderation from the console. Reuses the
    existing BattleEntry moderation fields (status/note/reviewed_by/at)."""
    _require_owner(operator_author)
    if new_status not in _ENTRY_ALLOWED:
        raise OperatorActionError(f"'{new_status}' is not a console-settable entry status.")
    if new_status in _ENTRY_ADVERSE and not (reason or "").strip():
        raise OperatorActionError("Adverse moderation actions require a reason.")

    with transaction.atomic():
        try:
            entry_ref = BattleEntry.objects.only("battle_id").get(pk=entry_id)
            battle = Battle.objects.select_for_update().get(pk=entry_ref.battle_id)
            entry = (BattleEntry.objects.select_for_update()
                     .select_related("author").get(pk=entry_id))
        except BattleEntry.DoesNotExist:
            raise OperatorActionError("Entry not found.")
        before = entry.moderation_status
        if before == new_status:
            raise OperatorActionError(f"Entry is already '{new_status}'.")
        if new_status == BattleEntry.ModerationStatus.APPROVED:
            if not entry.cooked_photo or not entry.real_photo_confirmed:
                raise OperatorActionError(
                    "Cannot approve an entry without a cooked photo and real-photo confirmation."
                )
        entry.moderation_status = new_status
        if reason:
            entry.moderation_note = reason
        entry.reviewed_by = operator_author.user
        entry.reviewed_at = timezone.now()
        entry.save(update_fields=[
            "moderation_status", "moderation_note", "reviewed_by", "reviewed_at", "updated_at",
        ])
        if new_status == BattleEntry.ModerationStatus.APPROVED:
            eligible_entries = (
                BattleEntry.objects.filter(
                    battle=battle,
                    author_id__in=[battle.challenger_id, battle.opponent_id],
                    moderation_status=BattleEntry.ModerationStatus.APPROVED,
                    real_photo_confirmed=True,
                    cooked_photo__isnull=False,
                )
                .exclude(cooked_photo="")
                .count()
            )
            if battle.status == Battle.Status.COOKING and eligible_entries == 2:
                battle.status = Battle.Status.PRESENTATION
                battle.save(update_fields=["status", "updated_at"])
                create_battle_event(
                    event_type=BattleEvent.EventType.BATTLE_STARTED,
                    battle=battle,
                    message=("Both cooked dish photos were approved. "
                             "Presentation phase begins."),
                    is_public=True,
                )
        _operator_event(
            battle=battle, operator_author=operator_author,
            action="moderate_entry", before=before, after=new_status,
            reason=reason, correlation_id=correlation_id,
            extra={"entry_id": entry.pk, "entry_author": entry.author.slug},
        )
        if new_status in _ENTRY_ADVERSE:
            _notify_chef(
                operator_author, entry.author,
                subject=f"Your battle entry needs attention (battle #{entry.battle_id})",
                body=(
                    f"Your entry for '{entry.battle.theme}' was marked "
                    f"'{entry.get_moderation_status_display()}' by the arena operator. "
                    f"Reason: {reason}."
                ),
            )
    return entry


def operator_review_report(*, report_id, operator_author, new_status, note="",
                           correlation_id=""):
    """Owner-only content-report review. Reuses ContentReport review fields."""
    from .models import ContentReport

    _require_owner(operator_author)
    allowed = {
        ContentReport.Status.REVIEWED,
        ContentReport.Status.ACTIONED,
        ContentReport.Status.DISMISSED,
    }
    if new_status not in allowed:
        raise OperatorActionError(f"'{new_status}' is not a valid report resolution.")
    if not (note or "").strip():
        raise OperatorActionError("Report review requires a note.")

    with transaction.atomic():
        try:
            report = ContentReport.objects.select_for_update().get(pk=report_id)
        except ContentReport.DoesNotExist:
            raise OperatorActionError("Report not found.")
        before = report.status
        if before == new_status:
            raise OperatorActionError(f"Report is already '{new_status}'.")
        report.status = new_status
        report.moderator_note = note
        report.reviewed_by = operator_author.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "moderator_note", "reviewed_by", "reviewed_at"])
        _operator_event(
            battle=None, operator_author=operator_author,
            action="review_report", before=before, after=new_status,
            reason=note, correlation_id=correlation_id,
            extra={"report_id": report.pk, "content_kind": report.content_kind,
                   "object_id": report.object_id},
        )
    return report


def operator_end_stream(*, session_id, operator_author, reason, correlation_id=""):
    """Owner-only stream shutdown. Updates platform records only: session ->
    TERMINATED, broadcast marked stopped_by_staff. NO provider API call is
    made or claimed — no provider integration is configured
    (ENABLE_LIVE_VIDEO is off); the response states this honestly."""
    _require_owner(operator_author)
    if not (reason or "").strip():
        raise OperatorActionError("Ending a stream requires a reason.")

    with transaction.atomic():
        try:
            session = (LiveStreamSession.objects.select_for_update(of=("self",))
                       .select_related("chef", "battle").get(pk=session_id))
        except LiveStreamSession.DoesNotExist:
            raise OperatorActionError("Stream session not found.")
        before = session.status
        if before in (LiveStreamSession.Status.ENDED, LiveStreamSession.Status.TERMINATED):
            raise OperatorActionError(f"Stream is already '{before}'.")
        now = timezone.now()
        session.status = LiveStreamSession.Status.TERMINATED
        session.ended_at = now
        session.terminated_reason = reason[:300]
        session.terminated_by = operator_author.user
        session.save(update_fields=[
            "status", "ended_at", "terminated_reason", "terminated_by", "updated_at",
        ])
        broadcast = getattr(session, "broadcast", None)
        if broadcast is not None:
            broadcast.stopped_by_staff = True
            broadcast.stop_reason = reason[:300]
            broadcast.reviewed_by = operator_author.user
            broadcast.reviewed_at = now
            broadcast.save(update_fields=[
                "stopped_by_staff", "stop_reason", "reviewed_by", "reviewed_at", "updated_at",
            ])
        _operator_event(
            battle=session.battle, operator_author=operator_author,
            action="end_stream", before=before,
            after=LiveStreamSession.Status.TERMINATED,
            reason=reason, correlation_id=correlation_id,
            extra={
                "session_id": session.pk,
                "chef": session.chef.slug,
                "provider": session.provider or "none",
                "provider_side_terminated": False,
            },
        )
        _notify_chef(
            operator_author, session.chef,
            subject=f"Your live stream was ended by the arena operator",
            body=f"Your stream (session #{session.pk}) was ended. Reason: {reason}.",
        )
    return session


# ═════════════════════════════════════════════════════════════════════════════
# P05 — Moderation and safety console actions (DG-03 / DG-05).
# Suspension, fraud-flag, and their reversals are owner-only writes that
# reuse the existing ChefBattleProfile fields and LedgerEvent audit trail.
# Every adverse action requires a non-empty reason/note and produces a
# private BattleEvent OPERATOR_ACTION audit entry (battle=None).
# ═════════════════════════════════════════════════════════════════════════════


def _get_profile_by_slug(chef_slug: str):
    """Resolve a RecipeAuthor slug to its ChefBattleProfile or raise OperatorActionError."""
    from recipes.models import RecipeAuthor
    try:
        author = RecipeAuthor.objects.select_related("battle_profile").get(slug=chef_slug)
    except RecipeAuthor.DoesNotExist:
        raise OperatorActionError(f"Chef '{chef_slug}' not found.")
    profile = getattr(author, "battle_profile", None)
    if profile is None:
        raise OperatorActionError(f"Chef '{chef_slug}' has no battle profile.")
    return author, profile


def operator_suspend_chef(*, chef_slug, operator_author, reason, correlation_id=""):
    """Owner-only: suspend a chef (sets is_suspended=True). Requires a reason.
    Creates a LedgerEvent(ACCOUNT_SUSPENDED) audit entry consistent with the
    Django admin suspend_profiles action."""
    from .models import LedgerEvent
    _require_owner(operator_author)
    if not (reason or "").strip():
        raise OperatorActionError("Suspending a chef requires a reason.")
    with transaction.atomic():
        author, profile = _get_profile_by_slug(chef_slug)
        if profile.is_suspended:
            raise OperatorActionError(f"Chef '{chef_slug}' is already suspended.")
        now = timezone.now()
        profile.is_suspended = True
        profile.suspended_at = now
        profile.suspension_reason = reason[:200]
        profile.save(update_fields=["is_suspended", "suspended_at", "suspension_reason"])
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ACCOUNT_SUSPENDED,
            actor=author,
            payload={"suspended_by": operator_author.slug, "reason": reason[:300]},
        )
        _operator_event(
            battle=None, operator_author=operator_author,
            action="suspend_chef", before="active", after="suspended",
            reason=reason, correlation_id=correlation_id,
            extra={"chef_slug": chef_slug},
        )
        _notify_chef(
            operator_author, author,
            subject="Your chef account has been suspended",
            body=(
                f"Your Chef's Battle account has been suspended by the arena operator. "
                f"Reason: {reason}. Please contact support if you believe this is an error."
            ),
        )
    return profile


def operator_unsuspend_chef(*, chef_slug, operator_author, correlation_id=""):
    """Owner-only: lift a chef suspension (sets is_suspended=False)."""
    _require_owner(operator_author)
    with transaction.atomic():
        author, profile = _get_profile_by_slug(chef_slug)
        if not profile.is_suspended:
            raise OperatorActionError(f"Chef '{chef_slug}' is not suspended.")
        profile.is_suspended = False
        profile.suspended_at = None
        profile.suspension_reason = ""
        profile.save(update_fields=["is_suspended", "suspended_at", "suspension_reason"])
        _operator_event(
            battle=None, operator_author=operator_author,
            action="unsuspend_chef", before="suspended", after="active",
            reason="", correlation_id=correlation_id,
            extra={"chef_slug": chef_slug},
        )
        _notify_chef(
            operator_author, author,
            subject="Your chef account suspension has been lifted",
            body="Your Chef's Battle account suspension has been lifted by the arena operator.",
        )
    return profile


def operator_set_fraud_flag(*, chef_slug, operator_author, note, correlation_id=""):
    """Owner-only: set fraud_flag=True on a chef profile. Requires a note."""
    from .models import LedgerEvent
    _require_owner(operator_author)
    if not (note or "").strip():
        raise OperatorActionError("Setting the fraud flag requires a note.")
    with transaction.atomic():
        author, profile = _get_profile_by_slug(chef_slug)
        if profile.fraud_flag:
            raise OperatorActionError(f"Chef '{chef_slug}' is already fraud-flagged.")
        profile.fraud_flag = True
        profile.fraud_flag_note = note[:200]
        profile.save(update_fields=["fraud_flag", "fraud_flag_note"])
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.FRAUD_FLAG,
            actor=author,
            payload={"flagged_by": operator_author.slug, "note": note[:300]},
        )
        _operator_event(
            battle=None, operator_author=operator_author,
            action="set_fraud_flag", before="unflagged", after="fraud_flagged",
            reason=note, correlation_id=correlation_id,
            extra={"chef_slug": chef_slug},
        )
    return profile


def operator_clear_fraud_flag(*, chef_slug, operator_author, correlation_id=""):
    """Owner-only: clear fraud_flag on a chef profile."""
    _require_owner(operator_author)
    with transaction.atomic():
        author, profile = _get_profile_by_slug(chef_slug)
        if not profile.fraud_flag:
            raise OperatorActionError(f"Chef '{chef_slug}' has no fraud flag set.")
        profile.fraud_flag = False
        profile.fraud_flag_note = ""
        profile.save(update_fields=["fraud_flag", "fraud_flag_note"])
        _operator_event(
            battle=None, operator_author=operator_author,
            action="clear_fraud_flag", before="fraud_flagged", after="unflagged",
            reason="", correlation_id=correlation_id,
            extra={"chef_slug": chef_slug},
        )
    return profile


# ═════════════════════════════════════════════════════════════════════════════
# P08 — Rewards governance (DG-06).
# Battle reports: the ONE write available to every console operator.
# Payout approve/reject: owner-only wrappers over the existing owning
# services (approve_payout_request / reject_payout_request) + console audit.
# ═════════════════════════════════════════════════════════════════════════════

def operator_submit_battle_report(*, battle_id, operator_author, summary,
                                  recommendation, flags=None, correlation_id=""):
    """Any console operator may submit a structured post-battle report to the
    owner (DG-06 workflow). Not owner-gated by design."""
    from .models import BattleReport

    if not operator_author:
        raise OperatorActionError("Operator profile required.")
    if not (summary or "").strip():
        raise OperatorActionError("Report summary is required.")
    if recommendation not in BattleReport.Recommendation.values:
        raise OperatorActionError(f"'{recommendation}' is not a valid recommendation.")

    with transaction.atomic():
        try:
            battle = Battle.objects.get(pk=battle_id)
        except Battle.DoesNotExist:
            raise OperatorActionError("Battle not found.")
        report = BattleReport.objects.create(
            battle=battle,
            author=operator_author,
            summary=summary.strip(),
            flags=[str(fl)[:80] for fl in (flags or [])][:10],
            recommendation=recommendation,
        )
        _operator_event(
            battle=battle, operator_author=operator_author,
            action="submit_battle_report", before=battle.status, after=battle.status,
            reason=f"recommendation: {recommendation}", correlation_id=correlation_id,
            extra={"report_id": report.pk, "flags": report.flags},
        )
    # Notify the owner outside the transaction (email path is fail-silent).
    from django.conf import settings as django_settings
    from recipes.models import RecipeAuthor as _RA
    owner = _RA.objects.filter(slug=django_settings.OWNER_SLUG).first()
    if owner and owner.pk != operator_author.pk:
        _notify_chef(
            operator_author, owner,
            subject=f"Battle report submitted for battle #{battle.pk}",
            body=(
                f"{operator_author.name} submitted a report on '{battle.theme}'. "
                f"Recommendation: {report.get_recommendation_display()}. "
                f"Summary: {report.summary[:500]}"
            ),
        )
    return report


def operator_review_payout(*, payout_id, operator_author, decision, reason="",
                           correlation_id=""):
    """Owner-only payout decision. Delegates to the owning services
    (approve_payout_request / reject_payout_request) — never touches status,
    reward records, ledger or Stripe directly."""
    _require_owner(operator_author)
    if decision == "approve":
        try:
            payout = approve_payout_request(payout_id, operator_author.user)
        except ValueError as exc:
            raise OperatorActionError(str(exc))
    elif decision == "reject":
        if not (reason or "").strip():
            raise OperatorActionError("Rejecting a payout requires a reason.")
        try:
            payout = reject_payout_request(payout_id, operator_author.user, reason)
        except ValueError as exc:
            raise OperatorActionError(str(exc))
    else:
        raise OperatorActionError(f"'{decision}' is not a valid payout decision.")

    _operator_event(
        battle=None, operator_author=operator_author,
        action=f"payout_{decision}", before="pending/under_review", after=payout.status,
        reason=reason, correlation_id=correlation_id,
        extra={"payout_id": payout.pk, "chef": payout.chef.slug,
               "tokens": payout.amount_reward_tokens},
    )
    return payout


# ═════════════════════════════════════════════════════════════════════════════
# Viewer presence heartbeat (DG-04, owner-delegated design 2026-07-05).
# Piggybacks on the existing public 20 s polls — no new endpoints, no
# WebSockets. Device key = sha256(IP)+sha256(UA) digest (same
# pseudonymisation as vote dedup); battle=None means the arena lobby.
# Active viewer definition: seen within VIEWER_PRESENCE_WINDOW_SECONDS.
# ═════════════════════════════════════════════════════════════════════════════

VIEWER_PRESENCE_WINDOW_SECONDS = 180
VIEWER_PRESENCE_PURGE_AFTER_SECONDS = 3600


def record_viewer_presence(request, battle=None) -> None:
    """Upsert a presence heartbeat. MUST never break the public poll that
    calls it — every failure is swallowed and logged."""
    from .models import BattleViewerPresence

    from monitoring.tracker import get_client_ip

    try:
        ip = get_client_ip(request) or ""
        ua = request.META.get("HTTP_USER_AGENT", "")
        if not ip and not ua:
            return
        viewer_hash = hash_request_value(f"{ip}|{ua}")
        now = timezone.now()
        BattleViewerPresence.objects.update_or_create(
            battle=battle,
            viewer_hash=viewer_hash,
            defaults={
                "last_seen_at": now,
                "is_authenticated": bool(getattr(request.user, "is_authenticated", False)),
            },
        )
        # Opportunistic retention: drop rows idle for over an hour on the
        # same surface (indexed delete; keeps the table tiny by design).
        BattleViewerPresence.objects.filter(
            battle=battle,
            last_seen_at__lt=now - timezone.timedelta(
                seconds=VIEWER_PRESENCE_PURGE_AFTER_SECONDS),
        ).delete()
    except Exception:
        logger.exception("viewer presence heartbeat failed")
