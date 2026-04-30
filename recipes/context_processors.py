from __future__ import annotations

from urllib.parse import urlencode

from django.urls import NoReverseMatch, reverse

from .authoring import get_author_for_user


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

    actions = [
        {
            "label": "My Recipes",
            "url": _with_query(_reverse_or_empty("recipes:recipe_list"), author=author.slug)
            if author
            else "",
            "secondary_label": "+ New",
            "secondary_url": _reverse_or_empty("recipes:recipe_create") if author else "",
        },
        {
            "label": "My Articles",
            "url": _with_query(_reverse_or_empty("articles:article_list"), author=author.slug)
            if author
            else "",
            "secondary_label": "+ New",
            "secondary_url": _reverse_or_empty("articles:article_create") if author else "",
        },
        {
            "label": "Profile",
            "url": profile_url,
        },
    ]

    return {
        "header_author": author,
        "header_author_name": display_name,
        "header_author_actions": actions,
    }
