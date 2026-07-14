"""Arena Observer prize — front-of-house (GreenBear's lane).

Nomination page for the winning clan's champion + the observer's advisory
dispute-vote surface. Scoring/models/service live in observer_service.py and
clan_service.py (Bolt's lane); this module only drives the UI on that API.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from recipes.authoring import get_author_for_user
from recipes.models import RecipeAuthor

from .access import chef_battle_guard
from .clan_selectors import get_clan_roster
from .clan_service import get_season_winning_clan
from .models import (
    OBSERVER_SEATS_PER_SEASON,
    BattleReport,
    Season,
    SeasonArenaObserver,
)
from .observer_service import (
    can_nominate_observers,
    cast_observer_vote,
    get_active_arena_observers,
    get_observer_votes,
    is_active_arena_observer,
    nominate_arena_observers,
)
from .season_service import get_active_season


def _author(request):
    if not request.user.is_authenticated:
        return None
    return get_author_for_user(request.user)


def _eligible_won_season(author):
    """The most recent ENDED season where `author` may still nominate Observers."""
    for season in Season.objects.filter(status=Season.Status.ENDED).order_by("-starts_at")[:6]:
        if can_nominate_observers(author, season):
            return season
    return None


@chef_battle_guard
@login_required
def observer_nominate(request):
    """The winning clan's champion seats up to 2 Arena Observers for next season."""
    author = _author(request)
    if author is None:
        messages.error(request, "You need a recipe author profile.")
        return redirect("chef_battle:clan_home")

    won_season = _eligible_won_season(author)
    if won_season is None:
        return render(
            request,
            "chef_battle/observer_nominate.html",
            {"eligible": False},
        )

    clan = get_season_winning_clan(won_season)
    candidates = [m.chef for m in get_clan_roster(clan)]
    existing = list(
        SeasonArenaObserver.objects.filter(won_season=won_season).select_related("chef")
    )
    error = None

    if request.method == "POST" and not existing:
        a = RecipeAuthor.objects.filter(pk=request.POST.get("candidate_a")).first()
        b = RecipeAuthor.objects.filter(pk=request.POST.get("candidate_b")).first()
        if a is None or b is None:
            error = "Choose two clan members."
        else:
            try:
                nominate_arena_observers(author, a, b, won_season)
                messages.success(
                    request,
                    "Your two Arena Observers are seated for the coming season.",
                )
                return redirect("chef_battle:clan_detail", slug=clan.slug)
            except ValueError as exc:
                error = str(exc)

    return render(
        request,
        "chef_battle/observer_nominate.html",
        {
            "eligible": True,
            "won_season": won_season,
            "clan": clan,
            "candidates": candidates,
            "existing": existing,
            "seats": OBSERVER_SEATS_PER_SEASON,
            "error": error,
        },
    )


@chef_battle_guard
@login_required
def observer_disputes(request):
    """Active Observers' advisory surface: open disputes + their vote form.

    Votes are advisory — recorded and shown to the operator in the master
    console, but never binding (the operator/owner decides)."""
    author = _author(request)
    if author is None or not is_active_arena_observer(author):
        return render(request, "chef_battle/observer_disputes.html", {"is_observer": False})

    seat = (
        get_active_arena_observers()
        .filter(chef=author)
        .first()
    )
    open_reports = list(
        BattleReport.objects.filter(status=BattleReport.Status.SUBMITTED)
        .select_related("author", "battle")
        .order_by("-created_at")[:25]
    )
    my_votes = {v.battle_report_id: v for v in seat.dispute_votes.all()} if seat else {}
    for report in open_reports:
        report.my_vote = my_votes.get(report.id)

    return render(
        request,
        "chef_battle/observer_disputes.html",
        {
            "is_observer": True,
            "reports": open_reports,
            "recommendations": BattleReport.Recommendation.choices,
        },
    )


@chef_battle_guard
@login_required
@require_POST
def observer_vote(request, report_id):
    author = _author(request)
    report = get_object_or_404(BattleReport, pk=report_id)
    seat = get_active_arena_observers().filter(chef=author).first()
    if seat is None:
        messages.error(request, "Your Observer seat is not active this season.")
        return redirect("chef_battle:observer_disputes")
    try:
        cast_observer_vote(
            seat,
            report,
            request.POST.get("recommendation", ""),
            request.POST.get("note", "").strip(),
        )
        messages.success(request, "Your advisory recommendation was recorded.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("chef_battle:observer_disputes")
