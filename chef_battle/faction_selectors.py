"""Culinary Factions — membership read/write for the UI (GreenBear's lane).

Selection is a UI action, not an earn event. Season-lock rule: a chef's first
pick for a kind is allowed at any time in the active season; switching within
an active season is locked (you may change only between seasons). The
FactionMembership unique constraint (chef, faction_kind, season) enforces one
Cuisine + one Specialty per season at the DB level.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError

from .models import Faction, FactionMembership


def factions_by_kind(kind: str):
    """Curated, active factions for one axis, alphabetical."""
    return Faction.objects.filter(kind=kind, is_active=True).order_by("name")


def get_membership(chef, kind: str, season):
    if not season:
        return None
    return (
        FactionMembership.objects.filter(chef=chef, faction_kind=kind, season=season)
        .select_related("faction")
        .first()
    )


def get_chef_factions(chef, season) -> dict:
    """{'cuisine': FactionMembership|None, 'specialty': FactionMembership|None}."""
    return {
        Faction.Kind.CUISINE.value: get_membership(chef, Faction.Kind.CUISINE.value, season),
        Faction.Kind.SPECIALTY.value: get_membership(chef, Faction.Kind.SPECIALTY.value, season),
    }


def set_faction_membership(chef, faction: Faction, season) -> FactionMembership:
    """Pick a faction for the active season.

    First pick (mid-season allowed) creates the membership; re-picking the same
    faction is a no-op; trying to switch to a different faction of the same kind
    within the active season is rejected (season-lock).
    """
    if season is None:
        raise ValidationError("There is no active season to join right now.")
    existing = FactionMembership.objects.filter(
        chef=chef, faction_kind=faction.kind, season=season
    ).first()
    if existing is not None:
        if existing.faction_id == faction.id:
            return existing
        raise ValidationError(
            f"Your {faction.get_kind_display()} is locked for this season — "
            f"you can change it next season."
        )
    return FactionMembership.objects.create(
        chef=chef, faction=faction, faction_kind=faction.kind, season=season
    )
