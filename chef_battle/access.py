from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.http import Http404


def is_battle_visible(request) -> bool:
    """
    Chef's Battle is visible when:
    - CHEF_BATTLE_ENABLED is True (public launch), OR
    - the user is staff or superuser (admin preview in any environment)
    """
    if getattr(settings, "CHEF_BATTLE_ENABLED", False):
        return True
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def chef_battle_guard(view_func):
    """
    View decorator: raises Http404 for any user who cannot see Chef's Battle.
    Apply to every chef_battle view.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_battle_visible(request):
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper
