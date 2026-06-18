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
    - the user is staff, superuser, or has bearseeker privileges (admin preview)
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
