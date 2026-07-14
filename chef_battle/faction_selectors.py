"""Culinary Factions — membership read/write for the UI (GreenBear's lane).

Selection is a UI action, not an earn event. Season-lock rule: a chef's first
pick for a kind is allowed at any time in the active season; switching within
an active season is locked (you may change only between seasons). The
FactionMembership unique constraint (chef, faction_kind, season) enforces one
Cuisine + one Specialty per season at the DB level.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Faction, FactionMembership

# A chef may freely change (or keep the carried-over) faction during this window
# at the start of a season; after it, the pick locks until the next season.
# The window doubles as the early-join reward-eligibility window (design sec 8),
# and is safe from bandwagoning because standings are still empty this early.
FACTION_REPICK_WINDOW_DAYS = 7


def in_repick_window(season) -> bool:
    """True while a season is early enough that faction picks can still change."""
    if season is None or season.starts_at is None:
        return False
    return timezone.now() <= season.starts_at + timedelta(days=FACTION_REPICK_WINDOW_DAYS)


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

    - First pick (allowed any time in the season) creates the membership.
    - Re-picking the same faction is a no-op.
    - Changing to a different faction of the same kind is allowed only during the
      re-pick window at the start of the season; after it, the pick is locked
      until the next season. Points already earned stay with the faction they
      were earned for (event-sourced), so a mid-window switch only redirects
      future contributions.
    """
    if season is None:
        raise ValidationError("There is no active season to join right now.")
    existing = FactionMembership.objects.filter(
        chef=chef, faction_kind=faction.kind, season=season
    ).first()
    if existing is None:
        return FactionMembership.objects.create(
            chef=chef, faction=faction, faction_kind=faction.kind, season=season
        )
    if existing.faction_id == faction.id:
        return existing
    if in_repick_window(season):
        existing.faction = faction
        existing.save(update_fields=["faction"])
        return existing
    raise ValidationError(
        f"Your {faction.get_kind_display()} is locked for this season — "
        f"you can change it next season."
    )
