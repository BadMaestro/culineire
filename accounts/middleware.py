from django.contrib.auth import logout
from django.http import HttpResponseForbidden
from django.utils import timezone


class OwnerTimedBlockMiddleware:
    """End existing sessions while an Owner timed block is active."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            author = getattr(user, "recipe_author_profile", None)
            if author is not None:
                from chef_battle.models import OwnerAccountRestriction
                if OwnerAccountRestriction.objects.filter(
                    author=author,
                    blocked_until__gt=timezone.now(),
                ).exists():
                    logout(request)
                    return HttpResponseForbidden("This account is temporarily blocked.")
        return self.get_response(request)
