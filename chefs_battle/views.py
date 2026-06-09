from django.http import Http404
from django.shortcuts import render

from chefs_battle.services import build_roadmap_context


def _require_super_admin(user):
    if not (user.is_authenticated and user.is_superuser):
        raise Http404


def roadmap(request):
    _require_super_admin(request.user)
    return render(
        request,
        "chefs_battle/roadmap.html",
        {"roadmap": build_roadmap_context()},
    )
