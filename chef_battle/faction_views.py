"""Culinary Factions — front-of-house views (GreenBear's lane).

Read/UI only. The earn-path, season receivers, normalisation math and
anti-abuse gates live in faction_service.py / energy_service.py / fraud.py
(Bolt's lane). This module never writes FactionContribution or
FactionSeasonStanding — it only reads via faction_service helpers.
"""
from __future__ import annotations

from django.shortcuts import render

from .access import chef_battle_guard
from .faction_service import get_faction_leaderboard
from .models import Faction
from .season_service import get_active_season

RANK_MEMBER_FLOOR = 5  # display copy only; the real gate lives in faction_service


def _season_label(season) -> str:
    if not season:
        return "No active season"
    return (
        f"{season.name} · {season.starts_at.day} {season.starts_at:%b} – "
        f"{season.ends_at.day} {season.ends_at:%b %Y}"
    )


@chef_battle_guard
def faction_leaderboards(request):
    """Live Cuisine and Specialty rankings for the active season."""
    active = get_active_season()
    cuisine_board = (
        get_faction_leaderboard(active, Faction.Kind.CUISINE.value) if active else []
    )
    specialty_board = (
        get_faction_leaderboard(active, Faction.Kind.SPECIALTY.value) if active else []
    )
    return render(
        request,
        "chef_battle/faction_leaderboard.html",
        {
            "active_season": active,
            "season_label": _season_label(active),
            "cuisine_board": cuisine_board,
            "specialty_board": specialty_board,
            "rank_floor": RANK_MEMBER_FLOOR,
        },
    )
