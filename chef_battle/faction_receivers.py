"""Season-lifecycle receivers for Culinary Factions (Phase 6).

Hang off Bolt's own season_signals. season_started / season_ended fire INSIDE
close_season's / activate_season's transaction, so those receivers are wrapped
defensively — a faction bug must never roll back the season transition itself.
Reward issuance is deferred to the post-commit signal (added separately).
"""
from __future__ import annotations

import logging

from django.db.models import Count, Sum

from .models import (
    FACTION_ACTIVE_CONTRIBUTION_MIN,
    Faction,
    FactionContribution,
    FactionMembership,
    FactionSeasonStanding,
)
from .season_signals import season_ended, season_started

logger = logging.getLogger(__name__)


def _open_and_carryover(season):
    # Open an (empty) standing row per active faction for the new season.
    for faction in Faction.objects.filter(is_active=True):
        FactionSeasonStanding.objects.get_or_create(faction=faction, season=season)

    # Carry each chef's live pick over from the most recent finished season, so
    # they keep their faction by default (less churn) unless they re-pick.
    from .season_service import get_latest_finished_season
    prior = get_latest_finished_season()
    if prior is None or prior.pk == season.pk:
        return
    prior_memberships = (
        FactionMembership.objects.filter(season=prior, left_at__isnull=True)
        .select_related("faction", "chef")
    )
    for m in prior_memberships:
        profile = getattr(m.chef, "battle_profile", None)
        if profile is not None and getattr(profile, "is_suspended", False):
            continue
        FactionMembership.objects.get_or_create(
            chef=m.chef, faction_kind=m.faction_kind, season=season,
            defaults={"faction": m.faction},
        )


def _finalize_standings(season):
    from .faction_service import get_faction_leaderboard, normalized_score
    for kind in (Faction.Kind.CUISINE, Faction.Kind.SPECIALTY):
        ranked = {r["faction"].pk: r["rank_position"] for r in get_faction_leaderboard(season, kind)}
        for faction in Faction.objects.filter(kind=kind, is_active=True):
            contribs = FactionContribution.objects.filter(faction=faction, season=season)
            total = contribs.aggregate(t=Sum("points"))["t"] or 0
            active = (
                contribs.values("chef").annotate(n=Count("id"))
                .filter(n__gte=FACTION_ACTIVE_CONTRIBUTION_MIN).count()
            )
            rank = ranked.get(faction.pk)
            FactionSeasonStanding.objects.update_or_create(
                faction=faction, season=season,
                defaults={
                    "total_points": total,
                    "active_member_count": active,
                    "normalized_score": normalized_score(total, active),
                    "rank_position": rank,
                    "rewards_pending": rank is not None,
                },
            )


def on_season_started(sender, season, **kwargs):
    """Open standings + carry membership over. Defensive: never rolls back the
    season activation (which fires this inside its transaction)."""
    try:
        _open_and_carryover(season)
    except Exception:
        logger.exception("Faction season_started handling failed for season pk=%s", season.pk)


def on_season_ended(sender, season, **kwargs):
    """Freeze FactionSeasonStanding (total/active/normalized/rank) from the
    ledger; mark ranked factions rewards_pending. Defensive: a failure here must
    not roll back Bolt's season close (reward issuance lives on the post-commit
    signal)."""
    try:
        _finalize_standings(season)
    except Exception:
        logger.exception("Faction season_ended finalisation failed for season pk=%s", season.pk)


def connect():
    season_started.connect(on_season_started, dispatch_uid="factions_on_season_started")
    season_ended.connect(on_season_ended, dispatch_uid="factions_on_season_ended")
