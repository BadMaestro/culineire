"""Season lifecycle engine for Chef's Battle (TZ Phase 6).

Turns the Season / SeasonStanding models into a real, operable subsystem:
create -> activate -> close, snapshotting final standings from the live
ChefBattleProfile.seasonal_score and resetting it for the next season.

Only one season may be ACTIVE at a time. The live leaderboard reads
seasonal_score for the active season; SeasonStanding holds the frozen
history of ended seasons.
"""
from __future__ import annotations

from django.db import transaction

from .models import ChefBattleProfile, Season, SeasonStanding


def get_active_season() -> Season | None:
    """The single currently-active season, or None."""
    return (
        Season.objects.filter(status=Season.Status.ACTIVE)
        .order_by("-starts_at")
        .first()
    )


def get_latest_finished_season() -> Season | None:
    """Most recently ended season, for showing past champions."""
    return (
        Season.objects.filter(status=Season.Status.ENDED)
        .order_by("-ends_at")
        .first()
    )


def create_season(*, name: str, starts_at, ends_at, activate: bool = False) -> Season:
    if ends_at <= starts_at:
        raise ValueError("Season ends_at must be after starts_at.")
    if activate and get_active_season() is not None:
        raise ValueError("Another season is already active — close it before activating a new one.")
    return Season.objects.create(
        name=name,
        starts_at=starts_at,
        ends_at=ends_at,
        status=Season.Status.ACTIVE if activate else Season.Status.UPCOMING,
    )


def activate_season(season: Season) -> Season:
    if season.status == Season.Status.ACTIVE:
        return season
    if season.status == Season.Status.ENDED:
        raise ValueError("An ended season cannot be reactivated.")
    active = get_active_season()
    if active is not None and active.pk != season.pk:
        raise ValueError("Another season is already active — close it first.")
    season.status = Season.Status.ACTIVE
    season.save(update_fields=["status"])
    return season


def close_season(season: Season) -> dict:
    """Freeze final standings from the live seasonal_score, then reset scores.

    Idempotent per season: re-running would find no positive scores (already
    reset) and leave the existing standings untouched, so it never double-counts.
    """
    if season.status != Season.Status.ACTIVE:
        raise ValueError("Only an active season can be closed.")

    with transaction.atomic():
        profiles = list(
            ChefBattleProfile.objects.select_related("author")
            .filter(seasonal_score__gt=0)
            .order_by("-seasonal_score", "-wins", "author__name")
        )
        # Replace any prior snapshot for this season so a re-close is consistent.
        season.standings.all().delete()
        SeasonStanding.objects.bulk_create([
            SeasonStanding(
                season=season,
                chef=p.author,
                score=p.seasonal_score,
                rank_position=i + 1,
            )
            for i, p in enumerate(profiles)
        ])

        # Reset the live tally so the next season starts from zero.
        ChefBattleProfile.objects.filter(seasonal_score__gt=0).update(seasonal_score=0)

        season.status = Season.Status.ENDED
        season.save(update_fields=["status"])

    return {
        "season_id": season.pk,
        "standings_recorded": len(profiles),
        "champion": profiles[0].author if profiles else None,
    }
