from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from .models import RecipeAuthor


def get_author_for_user(user):
    return RecipeAuthor.objects.filter(user=user).first()


class AuthorRequiredMixin(LoginRequiredMixin):
    author_required_message = (
        "Author Profile Required. Please Connect This Account To An Author Profile First."
    )

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        self.author = get_author_for_user(request.user)

        if not self.author:
            messages.error(request, self.author_required_message)
            return redirect("home")

        return super().dispatch(request, *args, **kwargs)
