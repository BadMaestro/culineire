from __future__ import annotations

import logging

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


def _sponsor_attention_count():
    try:
        from sponsors.attention import get_sponsor_moderation_attention_count
        return get_sponsor_moderation_attention_count()
    except Exception:
        return 0


def _pending_moderation_count():
    try:
        from django.conf import settings as _settings
        from recipes.models import Recipe
        from articles.models import Article
        from pinch.models import Pinch
        owner = getattr(_settings, "OWNER_SLUG", "greenbear")
        pending_recipes = Recipe.objects.filter(status=Recipe.Status.PENDING, is_deleted=False).exclude(author__slug=owner).count()
        pending_articles = Article.objects.filter(status=Article.Status.PENDING, is_deleted=False).exclude(author__slug=owner).count()
        pending_bites = Pinch.objects.filter(status=Pinch.Status.PENDING).exclude(author__slug=owner).count()
        return pending_recipes + pending_articles + pending_bites
    except ImportError:
        return 0
    except DatabaseError:
        logger.debug("Could not fetch pending moderation count", exc_info=True)
        return 0


def _author_workspace_attention_count(author):
    if not author:
        return 0
    try:
        from recipes.models import Recipe
        return Recipe.objects.filter(
            author=author,
            is_deleted=False,
            status__in=[
                Recipe.Status.DRAFT,
                Recipe.Status.PENDING,
                Recipe.Status.NEEDS_CHANGES,
                Recipe.Status.REJECTED,
            ],
        ).count()
    except ImportError:
        return 0
    except DatabaseError:
        logger.debug("Could not fetch author workspace attention count", exc_info=True)
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
    flag_on = getattr(settings, "CHEF_BATTLE_ENABLED", False)
    _author = getattr(user, "recipe_author_profile", None) if user and user.is_authenticated else None
    chef_battle_enabled = flag_on or bool(
        user and user.is_authenticated and (
            user.is_staff or user.is_superuser
            or (_author and _author.has_bearseeker_privileges)
        )
    )

    try:
        from pinch.visibility import can_view_pinch_public_area
        can_view_pinch = can_view_pinch_public_area(user)
    except Exception:
        can_view_pinch = False

    if not user or not user.is_authenticated:
        return {
            "can_view_pinch_public_area": can_view_pinch,
            "chef_battle_enabled": chef_battle_enabled,
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

    # Messages first
    actions.append({
        "label": "Messages",
        "url": _reverse_or_empty("messaging:inbox"),
        "badge": unread_count if unread_count else None,
    })

    if author:
        workspace_attention_count = _author_workspace_attention_count(author)
        actions.append({
            "label": "My Content Studio",
            "url": _reverse_or_empty("recipes:author_dashboard"),
            "badge": workspace_attention_count if workspace_attention_count else None,
        })
        try:
            _enrolled = bool(author.battle_profile.enrolled_at)
        except Exception:
            _enrolled = False
        if not _enrolled:
            actions.append({
                "label": "Become a Chef",
                "url": _reverse_or_empty("chef_battle:chef_enroll"),
            })

    if flag_on or (user and user.is_authenticated and (user.is_staff or user.is_superuser)):
        actions.append({
            "label": "Chef Battles",
            "url": _reverse_or_empty("chef_battle:home"),
        })

    if is_moderator:
        pending_count = _pending_moderation_count()
        actions.insert(0, {
            "label": "Moderation Panel",
            "url": _reverse_or_empty("recipes:moderation_panel"),
            "badge": pending_count if pending_count else None,
        })
        sponsor_attention_count = _sponsor_attention_count()
        actions.insert(1, {
            "label": "Sponsor Applications",
            "url": _reverse_or_empty("sponsors:moderation_applications"),
            "badge": sponsor_attention_count if sponsor_attention_count else None,
        })

    return {
        "header_author": author,
        "header_author_name": display_name,
        "header_author_actions": actions,
        "can_view_pinch_public_area": can_view_pinch,
        "chef_battle_enabled": chef_battle_enabled,
        "chef_battle_flag_on": flag_on,
    }
