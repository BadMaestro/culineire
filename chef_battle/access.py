from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect


def is_battle_visible(request) -> bool:
    """
    Chef Battles is visible when:
    - CHEF_BATTLE_ENABLED is True (public launch), OR
    - the user is staff, superuser, or has bearseeker privileges
      (dark launch preview).

    Staff see the arena during dark launch, matching the panel-preview flag
    (``chef_battle_enabled``) they already get; the Arena Master Console stays
    behind ``has_arena_console_access`` (superuser only), so this does not open
    the console to staff.
    """
    if getattr(settings, "CHEF_BATTLE_ENABLED", False):
        return True
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    author = getattr(user, "recipe_author_profile", None)
    return bool(author and author.has_bearseeker_privileges)


def has_arena_console_access(request) -> bool:
    """
    Arena Master Console access (decision gate DG-01, P00_DECISIONS.yaml):
    - The owner (superuser + OWNER_SLUG) ALWAYS has access — the whole site
      is always visible to the owner, feature flags never hide it from them.
    - Other operators need superuser + RecipeAuthor.has_arena_console_access,
      AND the ARENA_MASTER_CONSOLE_ENABLED kill switch must be on.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return False
    author = getattr(user, "recipe_author_profile", None)
    if author is None:
        return False
    if author.slug == settings.OWNER_SLUG:
        return True
    return (
        getattr(settings, "ARENA_MASTER_CONSOLE_ENABLED", False)
        and author.has_arena_console_access
    )


def arena_console_guard(view_func):
    """
    View decorator for Arena Master Console views: Http404 for anyone who
    fails the DG-01 access check (same failure mode as the moderation tools).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not has_arena_console_access(request):
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper


def chef_battle_guard(view_func):
    """
    View decorator: raises Http404 for any user who cannot see Chef Battles.
    Suspended accounts are redirected with an error message on POST actions.
    Apply to every chef_battle view.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_battle_visible(request):
            raise Http404
        user = getattr(request, "user", None)
        if user and user.is_authenticated and request.method == "POST":
            try:
                profile = user.recipe_author_profile.battle_profile
                if profile.is_suspended:
                    messages.error(
                        request,
                        "Your arena account is currently suspended. "
                        "Please contact us if you believe this is an error.",
                    )
                    return redirect(request.path)
            except Exception:
                pass
        return view_func(request, *args, **kwargs)
    return wrapper
