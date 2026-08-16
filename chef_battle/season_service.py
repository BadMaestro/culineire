"""Season lifecycle engine for Chef's Battle (TZ Phase 6).

Turns the Season / SeasonStanding models into a real, operable subsystem:
create -> activate -> close, snapshotting final standings from the live
ChefBattleProfile.seasonal_score and resetting it for the next season.

Only one season may be ACTIVE at a time. The live leaderboard reads
seasonal_score for the active season; SeasonStanding holds the frozen
history of ended seasons.
"""
from __future__ import annotations

from django.db import IntegrityError, transaction

from .models import ChefBattleProfile, Season, SeasonStanding
from .season_signals import season_ended, season_ended_committed, season_started


def get_active_season() -> Season | None:
    """The single currently-active season, or None."""
    return (
        Season.objects.filter(status=Season.Status.ACTIVE)
        .order_by("-starts_at")
        .first()
    )



#: What a season pays when it says nothing of its own. These are the values the
#: service has always used; naming them here is what lets a season override them
#: as DATA instead of as a deploy (G11, tz_main.md section 17.12).
DEFAULT_REWARD_RULES = {
    "seasonal_win": 10,      # seasonal score for a win
    "seasonal_second": 5,    # ...and for second place or a draw
}

#: How the crown is decided when a season says nothing of its own. Free text on
#: purpose: it describes a rule to a human, it does not dispatch code. Anything
#: that dispatches code from a string in a database is a second state machine,
#: and TECHNICAL_STANDARDS section 1 forbids exactly that.
DEFAULT_CROWN_RULE = "24 hours to the winner of each battle."


def reward_rules(season=None) -> dict:
    """This season's reward numbers: the defaults, with its own overrides on top.

    G11, Owner 2026-08-11. Season.reward_rules_json existed in the ТЗ and not in
    the code, so the numbers lived in this module and changing them for one
    season meant a deploy. A season that says nothing behaves exactly as every
    season has so far - the defaults ARE the current behaviour, not a new set.

    A malformed or partial override never breaks a battle: unknown keys are
    ignored and missing ones fall back, because a bad row in a season should
    cost that season its override and nothing else.
    """
    rules = dict(DEFAULT_REWARD_RULES)
    if season is None:
        return rules
    override = getattr(season, "reward_rules_json", None)
    if isinstance(override, dict):
        for key in DEFAULT_REWARD_RULES:
            value = override.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                rules[key] = value
    return rules


def crown_rule(season=None) -> str:
    """The season's crown rule as text, or the standing one."""
    if season is not None and (season.crown_rule or "").strip():
        return season.crown_rule.strip()
    return DEFAULT_CROWN_RULE


def active_reward_rules() -> dict:
    """The rules in force right now. Safe to call from anywhere, including a
    path with no season at all - it answers with the defaults."""
    try:
        return reward_rules(get_active_season())
    except Exception:                      # pragma: no cover - defensive
        return dict(DEFAULT_REWARD_RULES)

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
    try:
        with transaction.atomic():
            return Season.objects.create(
                name=name,
                starts_at=starts_at,
                ends_at=ends_at,
                status=Season.Status.ACTIVE if activate else Season.Status.UPCOMING,
            )
    except IntegrityError:
        # F24 residual, 2026-08-11: the check above is an unlocked read: two
        # concurrent create_season(activate=True) calls for two DIFFERENT
        # seasons can both see nothing active and both reach this insert.
        # The DB's own only-one-active constraint is the actual guard; this
        # turns the loser's IntegrityError into the same message the
        # unlocked check above already gives the common case.
        raise ValueError("Another season is already active — close it before activating a new one.")


def activate_season(season: Season) -> Season:
    if season.status == Season.Status.ACTIVE:
        return season
    if season.status == Season.Status.ENDED:
        raise ValueError("An ended season cannot be reactivated.")
    try:
        with transaction.atomic():
            # F24, 2026-08-11: this row was never locked, so two overlapping
            # roll_seasons runs (the command documents no mutex, same as every
            # other cron sweep in this app) could both pass the status checks on
            # the SAME season before either committed and both fire
            # season_started. Lock the row and re-check under it.
            locked = Season.objects.select_for_update().get(pk=season.pk)
            if locked.status == Season.Status.ACTIVE:
                season.status = locked.status
                return season
            if locked.status == Season.Status.ENDED:
                raise ValueError("An ended season cannot be reactivated.")
            # F24 residual, 2026-08-11: this read is of a DIFFERENT row and is
            # itself unlocked - two DIFFERENT seasons activated at once each
            # lock their own row and never collide here, so both could see
            # nothing active and both pass. Caught below by the DB's own
            # only-one-active constraint, the actual guard for this case.
            active = get_active_season()
            if active is not None and active.pk != locked.pk:
                raise ValueError("Another season is already active — close it first.")
            locked.status = Season.Status.ACTIVE
            locked.save(update_fields=["status"])
            # Integration hook: faction subsystem opens per-season standings.
            season_started.send(sender=Season, season=locked)
            season.status = locked.status
    except IntegrityError:
        raise ValueError("Another season is already active — close it first.")
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
        # F24, 2026-08-11: neither this row nor the "is it still active"
        # check was locked, so two overlapping roll_seasons runs on the SAME
        # season could both pass the top-of-function check before either
        # committed - both would snapshot standings, both would reset
        # seasonal_score, and both would fire season_ended/
        # season_ended_committed a second time, which issue real
        # SeasonReward/RewardRecord rows and are not documented as safe to
        # replay. Lock the row and re-check under it, same pattern as
        # activate_season above.
        locked = Season.objects.select_for_update().get(pk=season.pk)
        if locked.status != Season.Status.ACTIVE:
            # A concurrent close already won this race and committed - the
            # function is documented idempotent per season, so hand back the
            # snapshot that call already froze rather than raise or redo it.
            season.status = locked.status
            existing = list(season.standings.order_by("rank_position"))
            return {
                "season_id": season.pk,
                "standings_recorded": len(existing),
                "champion": existing[0].chef if existing else None,
            }

        # T22: the Owner is outside the competition, so he cannot take a
        # season standing either - a season is the most permanent competitive
        # record this game keeps.
        from .selectors import _uncompeting_slugs
        profiles = list(
            ChefBattleProfile.objects.select_related("author")
            .filter(seasonal_score__gt=0)
            .exclude(author__slug__in=_uncompeting_slugs())
            .order_by("-seasonal_score", "-wins", "author__name")
        )
        record = _season_record(locked)

        # Replace any prior snapshot for this season so a re-close is consistent.
        locked.standings.all().delete()
        SeasonStanding.objects.bulk_create([
            SeasonStanding(
                season=locked,
                chef=p.author,
                score=p.seasonal_score,
                rank_position=i + 1,
                **record.get(p.author_id, {"wins": 0, "losses": 0, "streak": 0}),
            )
            for i, p in enumerate(profiles)
        ])

        # Reset the live tally so the next season starts from zero.
        ChefBattleProfile.objects.filter(seasonal_score__gt=0).update(seasonal_score=0)

        locked.status = Season.Status.ENDED
        locked.save(update_fields=["status"])
        season.status = locked.status

        # Integration hook (in-transaction): light, must-be-atomic work only —
        # e.g. finalising FactionSeasonStanding from the frozen standings. A
        # raising receiver rolls back the whole close. See season_signals.py.
        season_ended.send(
            sender=Season,
            season=locked,
            standings=locked.standings.order_by("rank_position"),
        )

        # Integration hook (post-commit): heavy / fallible work — e.g. issuing
        # SeasonReward via RewardRecord. Fires via on_commit AFTER this
        # transaction commits, so a reward-issuance failure can never roll back
        # the season close. Discarded if the transaction rolls back.
        transaction.on_commit(
            lambda: season_ended_committed.send(sender=Season, season=locked)
        )

    return {
        "season_id": season.pk,
        "standings_recorded": len(profiles),
        "champion": profiles[0].author if profiles else None,
    }
