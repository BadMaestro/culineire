from django.conf import settings


def hero_battle_panel(request):
    """Inject battle panel data into every template context (cached 60s)."""
    flag_on = getattr(settings, "CHEF_BATTLE_ENABLED", False)
    user = request.user
    _author = getattr(user, "recipe_author_profile", None) if user and user.is_authenticated else None
    chef_battle_enabled = flag_on or bool(
        user and user.is_authenticated and (
            user.is_staff or user.is_superuser
            or (_author and _author.has_bearseeker_privileges)
        )
    )
    if not chef_battle_enabled:
        return {}
    from django.core.cache import cache
    cache_key = "hero_battle_panel_data"
    data = cache.get(cache_key)
    if data is None:
        try:
            from django.utils import timezone
            from chef_battle.models import Battle, BattleEvent, ChefBattleProfile
            battle_events = list(
                BattleEvent.objects.select_related("battle", "actor", "target")
                .filter(is_public=True, event_type__in=[
                    BattleEvent.EventType.CHALLENGE_ACCEPTED,
                    BattleEvent.EventType.BATTLE_STARTED,
                    BattleEvent.EventType.BATTLE_FINISHED,
                    BattleEvent.EventType.CROWN_AWARDED,
                    BattleEvent.EventType.RANK_PROMOTED,
                ])
                .order_by("-created_at")[:5]
            )
            active_battles = list(
                Battle.objects.select_related("challenger", "opponent", "winner")
                .filter(status__in=[Battle.Status.ACTIVE, Battle.Status.VOTING, Battle.Status.SCHEDULED])
                .order_by("end_time")[:4]
            )
            battle_crown_holder = (
                ChefBattleProfile.objects.select_related("user__recipe_author_profile")
                .filter(crown_until__gt=timezone.now())
                .order_by("-crown_until")
                .first()
            )
            data = {
                "active_battles": active_battles,
                "battle_crown_holder": battle_crown_holder,
                "battle_events": battle_events,
            }
            cache.set(cache_key, data, 60)
        except Exception:
            data = {"active_battles": [], "battle_crown_holder": None, "battle_events": []}
    return data


def active_battle_pip(request):
    """Inject the current user's active battle (if any) for the floating pip."""
    if not request.user.is_authenticated:
        return {"active_battle_pip": None}
    try:
        from recipes.models import RecipeAuthor
        from chef_battle.models import Battle
        from django.db.models import Q
        author = RecipeAuthor.objects.filter(user=request.user).first()
        if not author:
            return {"active_battle_pip": None}
        battle = Battle.objects.filter(
            Q(challenger=author) | Q(opponent=author),
            status=Battle.Status.ACTIVE,
        ).order_by("-created_at").first()
        return {"active_battle_pip": battle}
    except Exception:
        return {"active_battle_pip": None}


def site_url(request):
    """Inject SITE_URL into every template context for canonical / OG URLs."""
    site_domain = str(settings.SITE_DOMAIN).strip().rstrip("/")
    if site_domain.startswith(("http://", "https://")):
        base = site_domain
    else:
        base = f"{settings.SITE_SCHEME}://{site_domain}"
    return {"SITE_URL": base}
