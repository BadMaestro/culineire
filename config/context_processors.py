from django.conf import settings
from django.core.cache import cache
from django.urls import reverse


def _cache_get(key):
    """Read the cache without ever being able to break the page.

    These context processors run on EVERY rendered page, so an exception raised
    here returns 500 for the whole site. That is not hypothetical: on 2026-07-22
    a single .djcache file left owned by root (a diagnostic run as the wrong
    user) stopped the deploy worker from writing, and pages started failing.

    Missing the cache costs one extra query. Raising costs the site.
    """
    try:
        return cache.get(key)
    except Exception:  # noqa: BLE001 - a broken cache is not a broken page
        return None


def _cache_set(key, value, seconds):
    try:
        cache.set(key, value, seconds)
    except Exception:  # noqa: BLE001
        pass



def hero_chef_promotions(request):
    """Build cached promotional messages for the animated hero chef.

    F65, 2026-08-11: the Chef Battle promo item used to be baked into this
    SHARED, sitewide cache entry (one key, no viewer dimension), checked
    against the global CHEF_BATTLE_ENABLED flag only at the moment the
    cache happened to be repopulated. is_battle_visible() also depends on
    the REQUESTING viewer (staff/superusers see it even with the flag off),
    which can never be safely baked into a cache with no per-viewer key -
    and turning the flag off did not clear the cache, so anyone could see
    the promo text and the Arena link for up to this entry's TTL after
    dark-launch was supposed to hide it again. The Chef Battle item is
    computed fresh per request, outside the cached block, and only the
    remaining battle-agnostic promotions are cached.
    """
    cache_key = "hero_chef_promotions_v1"
    promotions = _cache_get(cache_key)
    if promotions is None:
        try:
            from articles.models import Article
            from recipes.models import Recipe
            from sponsors.models import SponsorCell

            promotions = []
            latest_article = (
                Article.objects.filter(status=Article.Status.APPROVED, is_deleted=False)
                .order_by("-published", "-pk")
                .values("slug")
                .first()
            )
            if latest_article:
                promotions.append({
                    "text": "Have you read our latest article yet?",
                    "url": reverse("articles:article_detail", args=[latest_article["slug"]]),
                })

            latest_recipe = (
                Recipe.objects.filter(status=Recipe.Status.APPROVED, is_deleted=False)
                .order_by("-created_at", "-pk")
                .values("slug")
                .first()
            )
            if latest_recipe:
                promotions.append({
                    "text": "Have you seen our latest recipe yet?",
                    "url": reverse("recipes:recipe_detail", kwargs={"slug": latest_recipe["slug"]}),
                })

            sponsor = (
                SponsorCell.objects.filter(
                    ring=0,
                    status__in=[SponsorCell.Status.ACTIVE, SponsorCell.Status.SOLD],
                )
                .values("sponsor_name", "sponsor_url")
                .first()
            )
            if sponsor and sponsor["sponsor_name"]:
                promotions.append({
                    "text": (
                        f"Our sponsor this month is {sponsor['sponsor_name']}, "
                        "A huge thank you for their support!"
                    ),
                    "url": sponsor["sponsor_url"] or reverse("sponsors:puzzle"),
                })

            promotions.append({
                "text": "I don’t accept tips! Want to thank me?",
                "url": "https://buymeacoffee.com/bearcave",
            })
            _cache_set(cache_key, promotions, 300)
        except Exception:
            promotions = [{
                "text": "I don’t accept tips! Want to thank me?",
                "url": "https://buymeacoffee.com/bearcave",
            }]

    promotions = list(promotions)
    try:
        from chef_battle.access import is_battle_visible
        if is_battle_visible(request):
            promotions.insert(min(2, len(promotions)), {
                "text": "Do you know who’s competing in Chef Battles right now?",
                "url": reverse("chef_battle:arena"),
            })
    except Exception:  # noqa: BLE001 - a broken gate is not a broken page
        pass

    return {"hero_chef_promotions": promotions}


def hero_battle_panel(request):
    """Inject battle panel data into every template context (cached 60s)."""
    flag_on = getattr(settings, "CHEF_BATTLE_ENABLED", False)
    # One source of truth for who may see Chef Battles (AGENTS.md 7). This test
    # was written out by hand in four places - here, battle_widget_context,
    # recipes.header_author and chef_battle.access - so widening one left the
    # other three disagreeing with it. Owner, 2026-08-04: only a
    # "(Bear)seeker Super User" sees this application.
    from chef_battle.access import is_battle_visible
    if not is_battle_visible(request):
        return {}
    from django.core.cache import cache
    cache_key = "hero_battle_panel_data"
    data = _cache_get(cache_key)
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
                ChefBattleProfile.objects.select_related("author")
                .filter(crown_until__gt=timezone.now())
                .order_by("-crown_until")
                .first()
            )
            data = {
                "active_battles": active_battles,
                "battle_crown_holder": battle_crown_holder,
                "battle_events": battle_events,
            }
            _cache_set(cache_key, data, 60)
        except Exception:
            data = {"active_battles": [], "battle_crown_holder": None, "battle_events": []}
    return data


def active_battle_pip(request):
    """Inject the current user's active battle (if any) for the floating pip.

    Gated on the same audience as the rest of the app. The pip renders three
    Chef Battles URLs into the page and is the ONE sitewide battle surface whose
    template block sits outside `{% if chef_battle_enabled %}`, so without this
    check an Author who is a battle participant would carry battle_detail,
    battle_state_poll and battle_combat_action links on every page - all of
    which now 404 for them. A participant is not a viewer: enrollment is a
    participation state and has never been a visibility grant.
    """
    if not request.user.is_authenticated:
        return {"active_battle_pip": None}
    from chef_battle.access import is_battle_visible
    if not is_battle_visible(request):
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


def battle_widget_context(request):
    """Inject battle_widget data for the sitewide Chef Battles sidebar widget."""
    # Same single source as the page itself. When this widget was wider than the
    # page, the entrance it advertised led to a 404 - and the fix chosen then was
    # to widen the PAGE rather than narrow the widget, which is how a moderator
    # ended up inside a staff-only application. test_gate_parity holds them
    # together now.
    from chef_battle.access import is_battle_visible
    if not is_battle_visible(request):
        return {}
    cache_key = "battle_widget_v1"
    data = _cache_get(cache_key)
    if data is None:
        try:
            from chef_battle.models import Battle, BattleEvent, ChefBattleProfile
            from django.utils import timezone
            active = list(
                Battle.objects.select_related("challenger", "opponent")
                .filter(status__in=[Battle.Status.ACTIVE, Battle.Status.VOTING, Battle.Status.SCHEDULED])
                .order_by("end_time")[:4]
            )
            leaders = list(
                ChefBattleProfile.objects.select_related("author")
                .order_by("-rating")[:5]
            )
            for profile in leaders:
                profile.has_crown = bool(
                    getattr(profile, "crown_until", None)
                    and profile.crown_until > timezone.now()
                )
            events = list(
                BattleEvent.objects.select_related("battle")
                .filter(is_public=True)
                .order_by("-created_at")[:5]
            )
            data = {"active": active, "leaders": leaders, "events": events}
            _cache_set(cache_key, data, 60)
        except Exception:
            data = {"active": [], "leaders": [], "events": []}
    from chef_battle.access import has_arena_console_access
    return {
        "battle_widget": data,
        "can_access_arena_console": has_arena_console_access(request),
    }


def battle_visibility(request):
    """Expose the *view's* Chef Battle gate to templates.

    Any control that links into a guarded battle view — the "Issue a Challenge"
    button, arena links — must gate on THIS value, computed from the very
    function the views enforce (``is_battle_visible``), so a visible button
    always leads somewhere rather than to a 404.  Re-implementing the same
    condition inline in a template would be free to drift from the view; calling
    the view's own predicate cannot.
    """
    from chef_battle.access import is_battle_visible
    return {"battle_visible": is_battle_visible(request)}


def site_url(request):
    """Inject SITE_URL into every template context for canonical / OG URLs."""
    site_domain = str(settings.SITE_DOMAIN).strip().rstrip("/")
    if site_domain.startswith(("http://", "https://")):
        base = site_domain
    else:
        base = f"{settings.SITE_SCHEME}://{site_domain}"
    return {"SITE_URL": base}
