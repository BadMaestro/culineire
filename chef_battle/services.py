from __future__ import annotations

import hashlib

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from newsfeed.models import NewsFeedEntry

from .models import Battle, BattleChallenge, BattleEvent, ChefBattleProfile


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
    end_time = start_time + timezone.timedelta(hours=24)

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
            submission_deadline=end_time,
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

        rating_delta = 25
        winner_profile.wins += 1
        winner_profile.win_streak += 1
        winner_profile.rating += rating_delta
        winner_profile.reputation += 15
        winner_profile.battle_moves += 3
        winner_profile.seasonal_score += 10
        winner_profile.crown_until = timezone.now() + timezone.timedelta(hours=24)
        winner_profile.rank = rank_for_rating(winner_profile.rating)
        winner_profile.save()

        loser_profile.losses += 1
        loser_profile.win_streak = 0
        loser_profile.rating = max(0, loser_profile.rating - 15)
        loser_profile.reputation = max(-1000, loser_profile.reputation - 3)
        loser_profile.rank = rank_for_rating(loser_profile.rating)
        loser_profile.save()

        battle.winner = winner
        battle.loser = loser
        battle.status = Battle.Status.COMPLETED
        battle.result_reason = f"Public vote: {challenger_votes}-{opponent_votes}"
        battle.save(update_fields=["winner", "loser", "status", "result_reason", "updated_at"])

        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_COMPLETED,
            battle=battle,
            actor=winner,
            target=loser,
            message=f"{winner.name} defeated {loser.name} in Chef Battle: {battle.theme}.",
            publish_to_news=True,
        )

    return battle
