from __future__ import annotations

from django.db.models import Count, QuerySet
from django.utils import timezone

from .models import Battle, BattleChallenge, BattleEvent, BattleVote, ChefBattleProfile


def get_active_battles(limit: int = 12) -> QuerySet:
    return (
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(status__in=Battle.ACTIVE_STATUSES)
        .order_by("end_time")[:limit]
    )


def get_recent_completed_battles(limit: int = 10) -> QuerySet:
    return (
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(status=Battle.Status.COMPLETED)
        .order_by("-updated_at")[:limit]
    )


def get_top_profiles(limit: int = 10) -> QuerySet:
    return (
        ChefBattleProfile.objects.select_related("author")
        .filter(enrolled_at__isnull=False)
        .order_by("-rating", "-wins", "author__name")[:limit]
    )


def get_public_events(limit: int = 12) -> QuerySet:
    return (
        BattleEvent.objects.select_related("battle", "actor", "target")
        .filter(is_public=True)
        .order_by("-created_at")[:limit]
    )


def get_expired_active_battles(limit: int = 20) -> QuerySet:
    now = timezone.now()
    return Battle.objects.filter(
        status__in=[Battle.Status.ACTIVE, Battle.Status.VOTING],
        end_time__lte=now,
    )[:limit]


def get_battle_vote_counts(battle: Battle) -> dict[int, int]:
    return {
        row["voted_for"]: row["total"]
        for row in battle.votes.values("voted_for").annotate(total=Count("id"))
    }


def get_sent_challenges(author, limit: int = 20) -> QuerySet:
    return (
        BattleChallenge.objects.select_related("opponent")
        .filter(challenger=author)
        .order_by("-created_at")[:limit]
    )


def get_received_challenges(author, limit: int = 20) -> QuerySet:
    return (
        BattleChallenge.objects.select_related("challenger")
        .filter(opponent=author)
        .order_by("-created_at")[:limit]
    )


def get_rankings(limit: int = 100) -> QuerySet:
    return (
        ChefBattleProfile.objects.select_related("author")
        .filter(enrolled_at__isnull=False)
        .order_by("-rating", "-wins", "author__name")[:limit]
    )


def get_hall_of_fame_battles(limit: int = 10) -> QuerySet:
    return (
        Battle.objects.select_related("challenger", "opponent", "winner", "loser")
        .filter(status=Battle.Status.COMPLETED, winner__isnull=False)
        .prefetch_related("entries__recipe", "votes")
        .order_by("updated_at")[:limit]
    )


def get_hall_of_fame_chefs(limit: int = 20) -> QuerySet:
    return (
        ChefBattleProfile.objects.select_related("author")
        .filter(wins__gt=0)
        .order_by("-wins", "-rating", "-crown_count", "author__name")[:limit]
    )


def get_author_battle_summary(author):
    """Return battle_profile and recent_battles for the public author page."""
    from django.db.models import Q
    battle_profile = ChefBattleProfile.objects.filter(author=author).first()
    recent_battles = list(
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(Q(challenger=author) | Q(opponent=author))
        .order_by("-created_at")[:6]
    )
    return {"battle_profile": battle_profile, "recent_battles": recent_battles}
