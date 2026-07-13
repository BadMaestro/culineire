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

from django.db.models import Count, Sum

from .models import (
    FACTION_ACTIVE_CONTRIBUTION_MIN,
    FACTION_RANK_MEMBER_FLOOR,
    Faction,
    FactionContribution,
)


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
