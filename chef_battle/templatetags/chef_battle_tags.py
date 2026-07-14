from django import template

register = template.Library()


@register.filter
def opponent_for(battle, author):
    return battle.opponent_for(author)


@register.inclusion_tag("chef_battle/_faction_line.html")
def chef_faction_line(author):
    """Render a chef's current-season Cuisine · Specialty lore line.

    Self-contained: queries factions directly so the recipes app / shared
    battle-context builder need not know about factions.
    """
    from chef_battle.faction_selectors import get_chef_factions
    from chef_battle.models import Faction
    from chef_battle.season_service import get_active_season

    season = get_active_season()
    factions = get_chef_factions(author, season) if (author and season) else {}
    return {
        "cuisine": factions.get(Faction.Kind.CUISINE.value),
        "specialty": factions.get(Faction.Kind.SPECIALTY.value),
    }


@register.inclusion_tag("chef_battle/_arena_observer_badge.html")
def arena_observer_badge(author):
    """Show an 'Arena Observer' badge if the chef holds an active seat this season.

    Self-contained: the recipes app profile need not know about the observer
    prize; the tag asks observer_service directly.
    """
    from chef_battle.observer_service import is_active_arena_observer

    active = bool(author) and is_active_arena_observer(author)
    return {"is_observer": active}
