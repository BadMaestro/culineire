"""Culinary Factions service — scoring math + live leaderboard (Phase 6).

The normalization formula lives here as the single source of truth so the UI
side (faction leaderboards, read-only) imports it instead of re-deriving it.

Design (cuisines_design.md E / 3.1):
  normalized_score = total_points / sqrt(active_member_count)
  - "active" (for the denominator)  = chefs with >= FACTION_ACTIVE_CONTRIBUTION_MIN
    contributions in the season (excludes never-contributed roster padding).
  - "ranked" (appears on the board) = factions with >= FACTION_RANK_MEMBER_FLOOR
    active members. These two thresholds are deliberately different numbers.

Live standings are computed on the fly here; FactionSeasonStanding rows are only
frozen at season_ended by the season receiver.
"""
from __future__ import annotations

import math

from django.db import transaction
from django.db.models import Count, Sum

from .models import (
    FACTION_ACTIVE_CONTRIBUTION_MIN,
    FACTION_RANK_MEMBER_FLOOR,
    Faction,
    FactionContribution,
    FactionMembership,
)


def award_faction_contribution(chef, points: int, *, source=None) -> int:
    """Credit `points` to the chef's active-season Cuisine AND Specialty factions.

    Writes one append-only FactionContribution row per axis the chef currently
    belongs to (so a chef in both a cuisine and a specialty gets two rows).
    No-op (returns 0) if points<=0, there is no active season, or the chef has
    no live membership. faction / faction_kind are denormalised at write time so
    the points stay with the faction the chef was in at the earning moment.

    Returns the number of contribution rows written.
    """
    if points <= 0:
        return 0
    from .season_service import get_active_season
    season = get_active_season()
    if season is None:
        return 0
    memberships = list(
        FactionMembership.objects.filter(
            chef=chef, season=season, left_at__isnull=True
        ).select_related("faction")
    )
    if not memberships:
        return 0

    content_type = object_id = None
    if source is not None:
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(source)
        object_id = source.pk

    with transaction.atomic():
        rows = [
            FactionContribution(
                chef=chef, faction=m.faction, faction_kind=m.faction_kind,
                season=season, source_content_type=content_type,
                source_object_id=object_id, points=points,
            )
            for m in memberships
        ]
        FactionContribution.objects.bulk_create(rows)
    return len(rows)


def normalized_score(total_points: int, active_member_count: int) -> float:
    """total / sqrt(active). Pure math — safe on any input.

    Size alone can't win (dividing by sqrt(N) damps a big roster); a new member
    only needs ~half the current per-capita average to be net-positive, so
    recruiting is always welcome but never decisive on its own.
    """
    if active_member_count <= 0 or total_points <= 0:
        return 0.0
    return total_points / math.sqrt(active_member_count)


def get_faction_leaderboard(season, kind: str) -> list[dict]:
    """Live, ranked standings for one axis (cuisine|specialty) in `season`.

    Returns dicts sorted by normalized_score desc, each with rank_position, for
    factions that clear the >= FACTION_RANK_MEMBER_FLOOR active-member floor.
    Read-only — never writes FactionSeasonStanding.
    """
    rows: list[dict] = []
    factions = Faction.objects.filter(kind=kind, is_active=True)
    for faction in factions:
        contribs = FactionContribution.objects.filter(faction=faction, season=season)
        total = contribs.aggregate(t=Sum("points"))["t"] or 0
        # Active = distinct chefs with >= MIN contributions this season.
        active = (
            contribs.values("chef")
            .annotate(n=Count("id"))
            .filter(n__gte=FACTION_ACTIVE_CONTRIBUTION_MIN)
            .count()
        )
        if active < FACTION_RANK_MEMBER_FLOOR:
            continue
        rows.append({
            "faction": faction,
            "total_points": total,
            "active_member_count": active,
            "normalized_score": normalized_score(total, active),
        })
    rows.sort(key=lambda r: r["normalized_score"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank_position"] = i
    return rows
