from __future__ import annotations

import logging

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
        from django.conf import settings as _settings
        from recipes.models import Recipe
        from articles.models import Article
        from amuse_bouche.models import AmuseBouche
        owner = getattr(_settings, "OWNER_SLUG", "greenbear")
        pending_recipes = Recipe.objects.filter(status=Recipe.Status.PENDING, is_deleted=False).count()
        pending_articles = Article.objects.filter(status=Article.Status.PENDING, is_deleted=False).count()
        pending_bites = AmuseBouche.objects.filter(status=AmuseBouche.Status.PENDING).exclude(author__slug=owner).count()
        return pending_recipes + pending_articles + pending_bites
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


def header_author(request):
    user = getattr(request, "user", None)

    try:
        from amuse_bouche.visibility import can_view_amuse_bouche_public_area
        can_view_amuse_bouche = can_view_amuse_bouche_public_area(user)
    except Exception:
        can_view_amuse_bouche = False

    if not user or not user.is_authenticated:
        return {
            "can_view_amuse_bouche_public_area": can_view_amuse_bouche,
        }

    author = _find_author_for_user(user)
    display_name = (
        getattr(author, "name", "")
        or user.get_full_name()
        or user.get_username()
    )

    is_moderator = _is_moderator(user)
    unread_count = _unread_message_count(user)

    actions = []

    if author:
        actions.append({
            "label": "My Content Studio",
            "url": _reverse_or_empty("recipes:author_dashboard"),
        })

    actions.append({
        "label": "Messages",
        "url": _reverse_or_empty("messaging:inbox"),
        "badge": unread_count if unread_count else None,
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
        "can_view_amuse_bouche_public_area": can_view_amuse_bouche,
    }
