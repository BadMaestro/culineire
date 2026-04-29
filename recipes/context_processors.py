from __future__ import annotations

from django.urls import NoReverseMatch, reverse

from .authoring import get_author_for_user


def _reverse_or_empty(viewname: str, *args) -> str:
    try:
        return reverse(viewname, args=args)
    except NoReverseMatch:
        return ""


def _find_author_for_user(user):
    return get_author_for_user(user)


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
    can_manage_content = user.is_staff

    actions = [
        {
            "label": "Create Recipe",
            "url": _reverse_or_empty("recipes:recipe_create") if author else "",
        },
        {
            "label": "Create Article",
            "url": _reverse_or_empty("articles:article_create") if author else "",
        },
        {
            "label": "Profile",
            "url": profile_url,
        },
        {
            "label": "Edit Profile",
            "url": _reverse_or_empty("recipes:author_edit") if author else "",
        },
        {
            "label": "Delete Profile",
            "url": _reverse_or_empty("admin:recipes_recipeauthor_delete", author.pk)
            if can_manage_content and author
            else "",
            "is_danger": True,
        },
    ]

    return {
        "header_author": author,
        "header_author_name": display_name,
        "header_author_actions": actions,
    }
