from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import DatabaseError
from django.urls import NoReverseMatch, reverse

from accounts.views import is_moderator as _is_moderator
from .authoring import get_author_for_user

logger = logging.getLogger(__name__)


def _unread_message_count(user):
    try:
        from messaging.models import Message
        return Message.objects.filter(recipient=user, is_read=False).count()
    except ImportError:
        return 0
    except DatabaseError:
        logger.debug("Could not fetch unread message count for user %s", getattr(user, "pk", "?"), exc_info=True)
        return 0


def _pending_moderation_count():
    try:
        from recipes.models import Recipe
        from articles.models import Article
        pending_recipes = Recipe.objects.filter(status=Recipe.Status.PENDING, is_deleted=False).count()
        pending_articles = Article.objects.filter(status=Article.Status.PENDING, is_deleted=False).count()
        return pending_recipes + pending_articles
    except ImportError:
        return 0
    except DatabaseError:
        logger.debug("Could not fetch pending moderation count", exc_info=True)
        return 0


def _reverse_or_empty(viewname: str, *args) -> str:
    try:
        return reverse(viewname, args=args)
    except NoReverseMatch:
        return ""


def _find_author_for_user(user):
    return get_author_for_user(user)


def _with_query(url: str, **params) -> str:
    if not url:
        return ""
    query = urlencode({key: value for key, value in params.items() if value})
    return f"{url}?{query}" if query else url


def header_author(request):
    user = getattr(request, "user", None)
    flag_on = getattr(settings, "CHEF_BATTLE_ENABLED", False)
    chef_battle_enabled = flag_on or bool(
        user and user.is_authenticated and (user.is_staff or user.is_superuser)
    )

    if not user or not user.is_authenticated:
        return {"chef_battle_enabled": chef_battle_enabled}

    author = _find_author_for_user(user)
    display_name = (
        getattr(author, "name", "")
        or user.get_full_name()
        or user.get_username()
    )

    profile_url = author.get_absolute_url() if author else ""

    is_moderator = _is_moderator(user)

    unread_count = _unread_message_count(user)

    actions = [
        {
            "label": "My Recipes",
            "url": _with_query(_reverse_or_empty("recipes:recipe_list"), author=author.slug)
            if author
            else "",
            "secondary_label": "(+ New)",
            "secondary_url": _reverse_or_empty("recipes:recipe_create") if author else "",
        },
        {
            "label": "My Articles",
            "url": _with_query(_reverse_or_empty("articles:article_list"), author=author.slug)
            if author
            else "",
            "secondary_label": "(+ New)",
            "secondary_url": _reverse_or_empty("articles:article_create") if author else "",
        },
        {
            "label": "My Collection",
            "url": _reverse_or_empty("collection:my_collection"),
        },
        {
            "label": "Profile",
            "url": profile_url,
        },
        {
            "label": "Messages",
            "url": _reverse_or_empty("messaging:inbox"),
            "badge": unread_count if unread_count else None,
        },
    ]

    if flag_on or (user and user.is_authenticated and (user.is_staff or user.is_superuser)):
        actions.insert(3, {
            "label": "Chef Battle",
            "url": _reverse_or_empty("chef_battle:challenge_list"),
        })

    if is_moderator:
        pending_count = _pending_moderation_count()
        actions.insert(0, {
            "label": "Moderation Panel",
            "url": _reverse_or_empty("recipes:moderation_panel"),
            "badge": pending_count if pending_count else None,
        })

    return {
        "header_author": author,
        "header_author_name": display_name,
        "header_author_actions": actions,
        "chef_battle_enabled": chef_battle_enabled,
        "chef_battle_flag_on": flag_on,
    }
