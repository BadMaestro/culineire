from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from .models import RecipeAuthor


def get_author_for_user(user):
    # Anonymous / missing users have no author; guard here so callers that
    # forget the is_authenticated check don't crash with a SimpleLazyObject
    # being fed to a pk lookup (surfaced via token_shop when the flag is on).
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return RecipeAuthor.objects.filter(user=user).first()


def user_can_manage_author(user, author) -> bool:
    if not user or not user.is_authenticated or not author:
        return False

    linked_author = get_author_for_user(user)
    return bool(linked_author and linked_author.pk == author.pk)


def author_skips_approval(author) -> bool:
    return bool(
        author
        and getattr(author, "slug", "") == getattr(settings, "OWNER_SLUG", "greenbear")
    )


class AuthorRequiredMixin(LoginRequiredMixin):
    author_required_message = (
        "Author Profile Required. Please Connect This Account To An Author Profile First."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.author = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        author = get_author_for_user(request.user)
        setattr(self, "author", author)

        if not author:
            messages.error(request, self.author_required_message)
            return redirect("home")

        return super().dispatch(request, *args, **kwargs)
