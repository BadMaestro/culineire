"""Culinary Factions — front-of-house views (GreenBear's lane).

Read/UI only. The earn-path, season receivers, normalisation math and
anti-abuse gates live in faction_service.py / energy_service.py / fraud.py
(Bolt's lane). This module never writes FactionContribution or
FactionSeasonStanding — membership writes go through faction_selectors.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from recipes.authoring import get_author_for_user

from .access import chef_battle_guard
from .faction_selectors import (
    factions_by_kind,
    get_chef_factions,
    in_repick_window,
    set_faction_membership,
)
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


@chef_battle_guard
@login_required
def faction_choose(request):
    """Pick a Cuisine and a Specialty for the active season.

    First pick is allowed any time in the active season; an already-chosen kind
    is locked until next season (enforced in faction_selectors.set_faction_membership).
    """
    author = get_author_for_user(request.user)
    if author is None:
        messages.error(request, "You need a recipe author profile to represent a faction.")
        return redirect("chef_battle:home")

    active = get_active_season()
    current = get_chef_factions(author, active) if active else {}
    error = None

    if request.method == "POST" and active:
        picks = {
            Faction.Kind.CUISINE.value: request.POST.get("cuisine"),
            Faction.Kind.SPECIALTY.value: request.POST.get("specialty"),
        }
        try:
            changed = False
            for kind, fid in picks.items():
                if not fid:
                    continue
                faction = Faction.objects.filter(pk=fid, kind=kind, is_active=True).first()
                if faction is None:
                    continue
                before = current.get(kind)
                set_faction_membership(author, faction, active)
                if before is None or before.faction_id != faction.id:
                    changed = True
            if changed:
                messages.success(request, "Your faction is set for this season.")
            return redirect("chef_battle:faction_leaderboards")
        except ValidationError as exc:
            error = getattr(exc, "message", None) or str(exc)
            current = get_chef_factions(author, active)

    return render(
        request,
        "chef_battle/faction_choose.html",
        {
            "active_season": active,
            "season_label": _season_label(active),
            "cuisines": factions_by_kind(Faction.Kind.CUISINE.value),
            "specialties": factions_by_kind(Faction.Kind.SPECIALTY.value),
            "current_cuisine": current.get(Faction.Kind.CUISINE.value),
            "current_specialty": current.get(Faction.Kind.SPECIALTY.value),
            "in_window": in_repick_window(active) if active else False,
            "error": error,
        },
    )
