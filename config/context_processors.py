from django.conf import settings


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
