from django.conf import settings
from django.core.cache import cache


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


def chef_battle_widget(request):
    """Inject compact battle widget data into every template (cached 60 s)."""
    from chef_battle.access import is_battle_visible
    if not is_battle_visible(request):
        return {"battle_widget": None}
    CACHE_KEY = "chef_battle_widget_v1"
    data = cache.get(CACHE_KEY)
    if data is None:
        try:
            from chef_battle.models import Battle, ChefBattleProfile, BattleEvent
            active = list(
                Battle.objects.filter(status__in=Battle.ACTIVE_STATUSES)
                .select_related("challenger", "opponent")
                .order_by("-created_at")[:3]
            )
            leaders = list(
                ChefBattleProfile.objects.filter(is_suspended=False)
                .select_related("author")
                .order_by("-rating")[:5]
            )
            events = list(
                BattleEvent.objects.select_related("battle")
                .order_by("-created_at")[:5]
            )
            data = {"active": active, "leaders": leaders, "events": events}
        except Exception:
            data = {"active": [], "leaders": [], "events": []}
        cache.set(CACHE_KEY, data, 60)
    return {"battle_widget": data}


def site_url(request):
    """Inject SITE_URL into every template context for canonical / OG URLs."""
    site_domain = str(settings.SITE_DOMAIN).strip().rstrip("/")
    if site_domain.startswith(("http://", "https://")):
        base = site_domain
    else:
        base = f"{settings.SITE_SCHEME}://{site_domain}"
    return {"SITE_URL": base}
