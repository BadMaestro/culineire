from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from newsfeed.models import NewsFeedEntry

from .models import Battle, BattleChallenge, BattleEntry, BattleEvent, ChefBattleProfile

logger = logging.getLogger(__name__)


def _notify_chef(sender_author, recipient_author, subject: str, body: str) -> None:
    """Send an in-site message notification. Silently skips if users are missing."""
    try:
        from messaging.models import Message
        sender = getattr(sender_author, "user", None)
        recipient = getattr(recipient_author, "user", None)
        if sender and recipient and sender != recipient:
            Message.objects.create(sender=sender, recipient=recipient, subject=subject, body=body)
    except Exception:
        logger.exception("Failed to send battle notification")


RANK_THRESHOLDS = [
    (1800, ChefBattleProfile.Rank.CULINARY_MASTER),
    (1600, ChefBattleProfile.Rank.EXECUTIVE_CHEF),
    (1450, ChefBattleProfile.Rank.HEAD_CHEF),
    (1300, ChefBattleProfile.Rank.SOUS_CHEF),
    (1180, ChefBattleProfile.Rank.CHEF_DE_PARTIE),
    (1080, ChefBattleProfile.Rank.COMMIS_CHEF),
    (1000, ChefBattleProfile.Rank.PREP_COOK),
    (0, ChefBattleProfile.Rank.KITCHEN_PORTER),
]


def get_or_create_battle_profile(author):
    profile, _ = ChefBattleProfile.objects.get_or_create(author=author)
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
        NewsFeedEntry.objects.create(
            entry_type=NewsFeedEntry.EntryType.SITE_UPDATE,
            title=message,
            url=url,
            is_auto=True,
            is_public=is_public,
            event_key=event_key,
        )

    return event


def accept_challenge(challenge: BattleChallenge) -> Battle:
    now = timezone.now()
    start_time = challenge.proposed_start_time or now
    status = Battle.Status.SCHEDULED if start_time > now else Battle.Status.ACTIVE
    submission_deadline = start_time + timezone.timedelta(days=5)
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
        status__in=[Battle.Status.ACTIVE, Battle.Status.AWAITING_SUBMISSIONS],
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
    if len(entries) == 2 or timezone.now() >= battle.submission_deadline:
        battle.entries.filter(is_revealed=False).update(is_revealed=True)
        if battle.status == Battle.Status.ACTIVE:
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
        winner_profile.battle_moves += MOVES_BATTLE_WIN + MOVES_BATTLE_PARTICIPATION
        winner_profile.seasonal_score += 10
        winner_profile.crown_count += 1
        winner_profile.crown_until = timezone.now() + timezone.timedelta(hours=24)
        winner_profile.rank = rank_for_rating(winner_profile.rating)
        winner_profile.save()

        loser_profile.losses += 1
        loser_profile.win_streak = 0
        loser_profile.rating = max(0, loser_profile.rating - 15)
        loser_profile.reputation = max(-1000, loser_profile.reputation - 3)
        loser_profile.battle_moves += MOVES_BATTLE_PARTICIPATION
        loser_profile.rank = rank_for_rating(loser_profile.rating)
        loser_profile.save()

        from .models import BattleMoveTransaction
        BattleMoveTransaction.objects.bulk_create([
            BattleMoveTransaction(chef=winner, amount=MOVES_BATTLE_WIN, reason="Battle win"),
            BattleMoveTransaction(chef=winner, amount=MOVES_BATTLE_PARTICIPATION, reason="Battle participation"),
            BattleMoveTransaction(chef=loser, amount=MOVES_BATTLE_PARTICIPATION, reason="Battle participation"),
        ])

        battle.winner = winner
        battle.loser = loser
        battle.status = Battle.Status.COMPLETED
        battle.crown_awarded = True
        battle.result_reason = f"Public vote: {challenger_votes}-{opponent_votes}"
        battle.save(update_fields=["winner", "loser", "status", "crown_awarded", "result_reason", "updated_at"])

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
    return battle


# ── Phase 3: Battle moves economy ────────────────────────────────────────────

MOVES_RECIPE_APPROVED = 3
MOVES_ARTICLE_APPROVED = 2
MOVES_BATTLE_WIN = 5
MOVES_BATTLE_PARTICIPATION = 1

# Anti-farming caps: max moves earned from content approval per day/week
MOVES_CONTENT_DAILY_CAP = 15
MOVES_CONTENT_WEEKLY_CAP = 50
_CONTENT_REASONS = {"Recipe approved", "Article approved"}


def _content_moves_earned(author, period_start) -> int:
    """Sum of move amounts from content approval since period_start."""
    from .models import BattleMoveTransaction
    return (
        BattleMoveTransaction.objects.filter(
            chef=author,
            reason__in=_CONTENT_REASONS,
            created_at__gte=period_start,
        )
        .values_list("amount", flat=True)
        .__class__(
            BattleMoveTransaction.objects.filter(
                chef=author,
                reason__in=_CONTENT_REASONS,
                created_at__gte=period_start,
            )
        )
    )


def _content_moves_total(author, period_start) -> int:
    from django.db.models import Sum
    from .models import BattleMoveTransaction
    result = BattleMoveTransaction.objects.filter(
        chef=author,
        reason__in=_CONTENT_REASONS,
        created_at__gte=period_start,
    ).aggregate(total=Sum("amount"))["total"]
    return result or 0


def award_moves(author, amount: int, reason: str) -> None:
    """Credit battle moves to a chef and update their profile.

    Content-approval reasons are capped (daily + weekly anti-farming).
    Silently no-ops on any error.
    """
    if amount == 0:
        return
    try:
        from .models import BattleMoveTransaction
        now = timezone.now()

        if reason in _CONTENT_REASONS:
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timezone.timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_earned = _content_moves_total(author, day_start)
            weekly_earned = _content_moves_total(author, week_start)
            daily_remaining = max(0, MOVES_CONTENT_DAILY_CAP - daily_earned)
            weekly_remaining = max(0, MOVES_CONTENT_WEEKLY_CAP - weekly_earned)
            amount = min(amount, daily_remaining, weekly_remaining)
            if amount <= 0:
                return

        profile = get_or_create_battle_profile(author)
        profile.battle_moves = max(0, profile.battle_moves + amount)
        profile.save(update_fields=["battle_moves", "updated_at"])
        BattleMoveTransaction.objects.create(chef=author, amount=amount, reason=reason)
    except Exception:
        logger.exception("Failed to award moves to author pk=%s", getattr(author, "pk", "?"))
