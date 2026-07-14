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
from .season_signals import season_ended, season_ended_committed, season_started

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


def _issue_rewards(season):
    """Non-cash season rewards for the #1 faction on each axis: a Legendary
    artifact for each active champion + a SeasonReward audit record (which the
    Hall of Fame reads to list past champions). No tokens / no money path.
    """
    from django.db.models import Sum
    from recipes.models import RecipeAuthor
    from .models import Artifact, ChefArtifact, FactionSeasonStanding, SeasonReward
    from .services import _pick_artifact

    champions = (
        FactionSeasonStanding.objects
        .filter(season=season, rank_position=1, rewards_pending=True)
        .select_related("faction")
    )
    for standing in champions:
        member_ids = (
            FactionContribution.objects
            .filter(faction=standing.faction, season=season)
            .values_list("chef", flat=True).distinct()
        )
        for chef in RecipeAuthor.objects.filter(pk__in=member_ids):
            points = (
                FactionContribution.objects
                .filter(chef=chef, faction=standing.faction, season=season)
                .aggregate(t=Sum("points"))["t"] or 0
            )
            # Legendary artifact (if the chef doesn't already own every legendary).
            artifact = _pick_artifact(chef, {Artifact.Rarity.LEGENDARY: 1.0}, guaranteed=False)
            if artifact is not None:
                ChefArtifact.objects.create(
                    chef=chef, artifact=artifact, source=ChefArtifact.Source.ADMIN_GRANT,
                )
            SeasonReward.objects.get_or_create(
                chef=chef, faction=standing.faction, season=season,
                defaults={"points_snapshot": points, "placement": standing.rank_position},
            )
        standing.rewards_pending = False
        standing.save(update_fields=["rewards_pending"])

    # Sponsor prizes are external/manual; just record who sponsored the season.
    try:
        from sponsors.services import get_sponsor_of_month
        sponsor = get_sponsor_of_month()
        if sponsor:
            logger.info("Season %s champions presented by sponsor '%s'.", season.pk, sponsor)
    except Exception:
        pass


def on_season_ended_committed(sender, season, **kwargs):
    """Post-commit reward issuance (Legendary artifacts + Hall-of-Fame records).
    Runs after the season close is durably committed, so a failure here can't
    roll it back. Idempotent via the rewards_pending flag."""
    try:
        _issue_rewards(season)
    except Exception:
        logger.exception("Faction reward issuance failed for season pk=%s", season.pk)


def connect():
    season_started.connect(on_season_started, dispatch_uid="factions_on_season_started")
    season_ended.connect(on_season_ended, dispatch_uid="factions_on_season_ended")
    season_ended_committed.connect(on_season_ended_committed, dispatch_uid="factions_on_season_ended_committed")
