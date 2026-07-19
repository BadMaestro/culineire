"""Local-only settings for looking at the arena.

Two things make the arena impossible to inspect with a plain `runserver`:
the CHEF_BATTLE_ENABLED gate (404 for everyone) and the moderation gate on the
build board (moderator only). Logging in by hand is not an option for an agent,
so this module turns the flag on and signs every request in as the first
superuser.

THIS IS A BACKDOOR. It lives outside config/ and is never imported by the
production settings module — the only way to load it is to ask for it by name
(DJANGO_SETTINGS_MODULE=tools.dev_settings), which only tools/devserver_arena.py
does. It also refuses to load unless DEBUG is on, so pointing it at a real
environment fails loudly instead of silently opening the site.
"""

from config.settings import *  # noqa: F401,F403
from config.settings import MIDDLEWARE

if not DEBUG:  # noqa: F405
    raise RuntimeError(
        "tools.dev_settings signs every visitor in as a superuser. "
        "It must never run with DEBUG off."
    )

CHEF_BATTLE_ENABLED = True


class DevAutoLoginMiddleware:
    """Attach the first superuser to every request.

    Runs after AuthenticationMiddleware, so request.user already exists and is
    AnonymousUser; this replaces it. Nothing is written to the session, so no
    cookies are involved and the browser needs no login step.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.contrib.auth import get_user_model

        if not getattr(request.user, "is_authenticated", False):
            user = get_user_model().objects.filter(is_superuser=True).first()
            if user is not None:
                request.user = user
        return self.get_response(request)


MIDDLEWARE = list(MIDDLEWARE) + ["tools.dev_settings.DevAutoLoginMiddleware"]
