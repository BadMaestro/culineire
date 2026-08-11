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
from .season_signals import season_ended, season_ended_committed, season_started


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
    with transaction.atomic():
        season.status = Season.Status.ACTIVE
        season.save(update_fields=["status"])
        # Integration hook: faction subsystem opens per-season standings.
        season_started.send(sender=Season, season=season)
    return season



def _season_record(season) -> dict:
    """Each chef's wins, losses and longest win streak INSIDE one season.

    G10, Owner 2026-08-11. tz_main.md section 17.13 asks a standing to carry the
    chef's record and the row held only a score and a position, so a season
    leaderboard could rank chefs and never say what any of them did.

    Counted from the season's own battles, deliberately NOT copied from the
    lifetime counters on the profile: those keep rising after the season ends,
    and a standing is a photograph of one season. A withdrawal, a void and a
    cancelled battle have no winner and count as neither - the rulebook is
    explicit that a withdrawal is not a defeat.

    WHICH BATTLES BELONG TO THE SEASON, and the ordering of the two rules
    matters: a battle stamped with this season's id belongs to it, full stop,
    even if the calendar was edited afterwards. Only an UNSTAMPED battle falls
    back to the date window, and that fallback exists solely for the battles
    fought before Battle.season was added on 2026-08-11 - without it, closing
    the first season after this release would record every chef as 0-0.
    """
    from django.db.models import Q
    from .models import Battle

    battles = (
        Battle.objects.filter(status=Battle.Status.COMPLETED, winner__isnull=False)
        .filter(
            Q(season=season)
            | Q(season__isnull=True,
                created_at__gte=season.starts_at, created_at__lt=season.ends_at)
        )
        .order_by("created_at", "pk")
        .values_list("challenger_id", "opponent_id", "winner_id")
    )

    record: dict[int, dict] = {}
    running: dict[int, int] = {}
    for challenger_id, opponent_id, winner_id in battles:
        for chef_id in (challenger_id, opponent_id):
            if chef_id is None:
                continue
            row = record.setdefault(chef_id, {"wins": 0, "losses": 0, "streak": 0})
            if chef_id == winner_id:
                row["wins"] += 1
                running[chef_id] = running.get(chef_id, 0) + 1
                row["streak"] = max(row["streak"], running[chef_id])
            else:
                row["losses"] += 1
                running[chef_id] = 0
    return record


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
        record = _season_record(season)

        # Replace any prior snapshot for this season so a re-close is consistent.
        season.standings.all().delete()
        SeasonStanding.objects.bulk_create([
            SeasonStanding(
                season=season,
                chef=p.author,
                score=p.seasonal_score,
                rank_position=i + 1,
                **record.get(p.author_id, {"wins": 0, "losses": 0, "streak": 0}),
            )
            for i, p in enumerate(profiles)
        ])

        # Reset the live tally so the next season starts from zero.
        ChefBattleProfile.objects.filter(seasonal_score__gt=0).update(seasonal_score=0)

        season.status = Season.Status.ENDED
        season.save(update_fields=["status"])

        # Integration hook (in-transaction): light, must-be-atomic work only —
        # e.g. finalising FactionSeasonStanding from the frozen standings. A
        # raising receiver rolls back the whole close. See season_signals.py.
        season_ended.send(
            sender=Season,
            season=season,
            standings=season.standings.order_by("rank_position"),
        )

        # Integration hook (post-commit): heavy / fallible work — e.g. issuing
        # SeasonReward via RewardRecord. Fires via on_commit AFTER this
        # transaction commits, so a reward-issuance failure can never roll back
        # the season close. Discarded if the transaction rolls back.
        transaction.on_commit(
            lambda: season_ended_committed.send(sender=Season, season=season)
        )

    return {
        "season_id": season.pk,
        "standings_recorded": len(profiles),
        "champion": profiles[0].author if profiles else None,
    }
