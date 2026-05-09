from __future__ import annotations

from urllib.parse import urlencode

from django.db import DatabaseError
from django.urls import NoReverseMatch, reverse

from .authoring import get_author_for_user


def _unread_message_count(user):
    try:
        from messaging.models import Message
        return Message.objects.filter(recipient=user, is_read=False).count()
    except (DatabaseError, ImportError):
        return 0


def _pending_moderation_count():
    try:
        from recipes.models import Recipe
        from articles.models import Article
        pending_recipes = Recipe.objects.filter(status=Recipe.Status.PENDING).count()
        pending_articles = Article.objects.filter(status=Article.Status.PENDING).count()
        return pending_recipes + pending_articles
    except (DatabaseError, ImportError):
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

    if not user or not user.is_authenticated:
        return {}

    author = _find_author_for_user(user)
    display_name = (
        getattr(author, "name", "")
        or user.get_full_name()
        or user.get_username()
    )

    profile_url = author.get_absolute_url() if author else ""

    is_moderator = (
        user.is_staff
        or user.is_superuser
        or (author is not None and author.slug == "greenbear")
        or (author is not None and author.has_bearseeker_privileges)
    )

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
            "label": "Profile",
            "url": profile_url,
        },
        {
            "label": "Messages",
            "url": _reverse_or_empty("messaging:inbox"),
            "badge": unread_count if unread_count else None,
        },
    ]

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
    }
