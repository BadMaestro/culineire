"""Arena Observer prize — nomination, active-role checks, advisory dispute votes.

The winning clan's champion (top contributor) may seat up to 2 clan members as
Arena Observers for the FOLLOWING season. The role is derived from won_season +
season ordering (no stored expiry to drift): active only while the current
active season is the immediate successor of won_season.

Canonical rules: docs/chef_battle/clans_alliances_rules.md sec 3.
"""
from __future__ import annotations

from django.db import transaction

from .clan_service import get_season_clan_champion, get_season_winning_clan
from .models import (
    OBSERVER_SEATS_PER_SEASON,
    ClanMembership,
    ObserverDisputeVote,
    Season,
    SeasonArenaObserver,
)
from .season_service import get_active_season


def _successor_season(won_season):
    """The season immediately after won_season (by start), or None."""
    return (
        Season.objects.filter(starts_at__gt=won_season.starts_at)
        .order_by("starts_at")
        .first()
    )


def _predecessor_season(season):
    """The season immediately before `season` (by start), or None."""
    return (
        Season.objects.filter(starts_at__lt=season.starts_at)
        .order_by("-starts_at")
        .first()
    )


def is_active_arena_observer(author, season=None) -> bool:
    """True if `author` holds an active Observer seat for the given (or current
    active) season — i.e. that season is the immediate successor of a season
    they were nominated for. ACCESS GATE for the dispute-vote UI."""
    season = season or get_active_season()
    if season is None:
        return False
    prev = _predecessor_season(season)
    if prev is None:
        return False
    return SeasonArenaObserver.objects.filter(chef=author, won_season=prev).exists()


def get_active_arena_observers(season=None):
    """QuerySet of Observers whose seat is active for the given/current season."""
    season = season or get_active_season()
    if season is None:
        return SeasonArenaObserver.objects.none()
    prev = _predecessor_season(season)
    if prev is None:
        return SeasonArenaObserver.objects.none()
    return (
        SeasonArenaObserver.objects.filter(won_season=prev)
        .select_related("chef", "clan", "won_season", "nominated_by")
    )


def can_nominate_observers(author, won_season) -> bool:
    """True if `author` is the champion of won_season's winning clan and the
    nomination window is still open (successor season not yet ended, seats free)."""
    if won_season is None or won_season.status != Season.Status.ENDED:
        return False
    winner = get_season_winning_clan(won_season)
    if winner is None:
        return False
    champion = get_season_clan_champion(won_season, winner)
    if champion is None or champion.pk != author.pk:
        return False
    successor = _successor_season(won_season)
    if successor is not None and successor.status == Season.Status.ENDED:
        return False  # window has closed
    taken = SeasonArenaObserver.objects.filter(won_season=won_season).count()
    return taken < OBSERVER_SEATS_PER_SEASON


def nominate_arena_observers(champion, candidate_a, candidate_b, won_season):
    """Seat two Arena Observers chosen by the winning clan's champion.

    Validates eligibility, that the two are distinct active members of the
    winning clan, and the open window. Idempotent per (chef, won_season)."""
    if not can_nominate_observers(champion, won_season):
        raise ValueError("Not eligible to nominate Arena Observers for this season.")
    if candidate_a.pk == candidate_b.pk:
        raise ValueError("Nominate two different chefs.")

    winner = get_season_winning_clan(won_season)
    member_ids = set(
        ClanMembership.objects.filter(
            clan=winner, status=ClanMembership.Status.ACTIVE, left_at__isnull=True
        ).values_list("chef_id", flat=True)
    )
    for candidate in (candidate_a, candidate_b):
        if candidate.pk not in member_ids:
            raise ValueError("Candidates must be active members of the winning clan.")

    created = []
    with transaction.atomic():
        for candidate in (candidate_a, candidate_b):
            obj, _ = SeasonArenaObserver.objects.get_or_create(
                chef=candidate, won_season=won_season,
                defaults={"nominated_by": champion, "clan": winner},
            )
            created.append(obj)
    return created


def cast_observer_vote(observer, battle_report, recommendation, note: str = ""):
    """Record an Observer's ADVISORY vote on a dispute (BattleReport). Requires
    the observer's seat to be active for the current season. One vote per report,
    updatable. Non-binding — the operator/owner decides."""
    if not is_active_arena_observer(observer.chef):
        raise ValueError("Observer seat is not active for the current season.")
    vote, _ = ObserverDisputeVote.objects.update_or_create(
        observer=observer, battle_report=battle_report,
        defaults={"recommendation": recommendation, "note": note},
    )
    return vote


def get_observer_votes(battle_report):
    """All Observer votes on a report, oldest first (for operator display)."""
    return list(
        ObserverDisputeVote.objects.filter(battle_report=battle_report)
        .select_related("observer", "observer__chef")
        .order_by("created_at")
    )
