"""Clans & Alliances — front-of-house views (GreenBear's lane).

Read/UI + the membership flow. Scoring (ClanContribution, leaderboard, winning
clan, champion) is clan_service.py (Bolt's lane); membership writes go through
clan_selectors. This module never writes the points ledger.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from recipes.authoring import get_author_for_user

from .access import chef_battle_guard
from .clan_selectors import (
    CLAN_MAX_CATEGORIES,
    CLAN_MEMBER_CAP,
    approve_request,
    create_alliance,
    create_clan,
    deny_request,
    get_active_membership,
    get_alliance_clans,
    get_clan_alliance,
    get_clan_roster,
    get_clan_standing,
    get_clan_top_contributors,
    get_pending_membership,
    get_pending_requests,
    is_founder,
    join_alliance,
    leave_alliance,
    leave_clan,
    list_alliances,
    request_join,
)
from .clan_service import get_clan_leaderboard, get_season_winning_clan
from .faction_selectors import factions_by_kind
from .models import Clan, ClanMembership, Faction
from .season_service import get_active_season


def _season_label(season) -> str:
    if not season:
        return "No active season"
    return (
        f"{season.name} · {season.starts_at.day} {season.starts_at:%b} – "
        f"{season.ends_at.day} {season.ends_at:%b %Y}"
    )


def _author(request):
    if not request.user.is_authenticated:
        return None
    return get_author_for_user(request.user)


@chef_battle_guard
def clan_home(request):
    """Season clan leaderboard + a browse list, with the viewer's own status."""
    active = get_active_season()
    board = get_clan_leaderboard(active) if active else []
    winner = get_season_winning_clan(active) if active else None
    clans = (
        Clan.objects.filter(is_active=True, moderation_status=Clan.Moderation.APPROVED)
        .prefetch_related("categories")
        .order_by("name")
    )
    author = _author(request)
    my_membership = get_active_membership(author) if author else None

    from .observer_service import is_active_arena_observer
    from .observer_views import _eligible_won_season

    viewer_is_observer = bool(author) and is_active_arena_observer(author)
    viewer_can_nominate = bool(author) and _eligible_won_season(author) is not None

    return render(
        request,
        "chef_battle/clan_home.html",
        {
            "active_season": active,
            "season_label": _season_label(active),
            "board": board,
            "winner": winner,
            "clans": clans,
            "my_membership": my_membership,
            "member_cap": CLAN_MEMBER_CAP,
            "viewer_is_observer": viewer_is_observer,
            "viewer_can_nominate": viewer_can_nominate,
        },
    )


@chef_battle_guard
def clan_detail(request, slug):
    """One clan's page: crest, categories, roster, standing. Founder sees the
    join-request queue and alliance controls inline."""
    clan = get_object_or_404(
        Clan.objects.prefetch_related("categories"), slug=slug, is_active=True
    )
    active = get_active_season()
    author = _author(request)

    standing = get_clan_standing(clan, active)
    roster = get_clan_roster(clan)
    contributors = get_clan_top_contributors(clan, active)
    alliance_membership = get_clan_alliance(clan)

    viewer_founder = is_founder(author, clan) if author else False
    my_membership = get_active_membership(author) if author else None
    in_this_clan = my_membership is not None and my_membership.clan_id == clan.id
    pending_here = get_pending_membership(author, clan) if author else None
    can_join = (
        author is not None
        and clan.moderation_status == Clan.Moderation.APPROVED
        and my_membership is None
        and pending_here is None
        and len(roster) < CLAN_MEMBER_CAP
    )

    return render(
        request,
        "chef_battle/clan_detail.html",
        {
            "clan": clan,
            "active_season": active,
            "season_label": _season_label(active),
            "standing": standing,
            "roster": roster,
            "contributors": contributors,
            "member_cap": CLAN_MEMBER_CAP,
            "alliance_membership": alliance_membership,
            "viewer_founder": viewer_founder,
            "in_this_clan": in_this_clan,
            "pending_here": pending_here,
            "can_join": can_join,
            "pending_requests": get_pending_requests(clan) if viewer_founder else [],
            "all_alliances": list_alliances() if viewer_founder else [],
        },
    )


@chef_battle_guard
@login_required
def clan_create(request):
    """Found a clan: name, crest, and up to 3 categories (cuisines + specialties)."""
    author = _author(request)
    if author is None:
        messages.error(request, "You need a recipe author profile to found a clan.")
        return redirect("chef_battle:clan_home")

    existing = get_active_membership(author)
    if existing is not None:
        messages.info(request, "You are already in a clan.")
        return redirect("chef_battle:clan_detail", slug=existing.clan.slug)

    error = None
    if request.method == "POST":
        try:
            clan = create_clan(
                author,
                request.POST.get("name", ""),
                request.POST.get("crest_icon", ""),
                request.POST.getlist("categories"),
            )
            messages.success(
                request,
                "Your clan is founded and awaiting moderation approval before it "
                "appears on the leaderboard.",
            )
            return redirect("chef_battle:clan_detail", slug=clan.slug)
        except ValidationError as exc:
            error = getattr(exc, "message", None) or "; ".join(exc.messages)

    return render(
        request,
        "chef_battle/clan_create.html",
        {
            "cuisines": factions_by_kind(Faction.Kind.CUISINE.value),
            "specialties": factions_by_kind(Faction.Kind.SPECIALTY.value),
            "max_categories": CLAN_MAX_CATEGORIES,
            "error": error,
            "submitted_name": request.POST.get("name", ""),
            "submitted_crest": request.POST.get("crest_icon", ""),
            "submitted_categories": [int(i) for i in request.POST.getlist("categories") if i.isdigit()],
        },
    )


@chef_battle_guard
@login_required
@require_POST
def clan_join(request, slug):
    clan = get_object_or_404(Clan, slug=slug, is_active=True)
    author = _author(request)
    try:
        request_join(author, clan)
        messages.success(request, "Request sent — the founder will review it.")
    except ValidationError as exc:
        messages.error(request, getattr(exc, "message", None) or "; ".join(exc.messages))
    return redirect("chef_battle:clan_detail", slug=slug)


@chef_battle_guard
@login_required
@require_POST
def clan_leave(request):
    author = _author(request)
    try:
        leave_clan(author)
        messages.success(request, "You have left your clan.")
    except ValidationError as exc:
        messages.error(request, getattr(exc, "message", None) or "; ".join(exc.messages))
    return redirect("chef_battle:clan_home")


@chef_battle_guard
@login_required
@require_POST
def clan_request_action(request, membership_id):
    """Founder approves or denies a pending join request."""
    author = _author(request)
    membership = get_object_or_404(
        ClanMembership, pk=membership_id, status=ClanMembership.Status.PENDING
    )
    slug = membership.clan.slug
    action = request.POST.get("action")
    try:
        if action == "approve":
            approve_request(author, membership)
            messages.success(request, "Member approved.")
        elif action == "deny":
            deny_request(author, membership)
            messages.success(request, "Request declined.")
    except ValidationError as exc:
        messages.error(request, getattr(exc, "message", None) or "; ".join(exc.messages))
    return redirect("chef_battle:clan_detail", slug=slug)


@chef_battle_guard
@login_required
@require_POST
def alliance_action(request, slug):
    """Founder-only alliance foundation controls (create / join / leave)."""
    clan = get_object_or_404(Clan, slug=slug, is_active=True)
    author = _author(request)
    action = request.POST.get("action")
    try:
        if action == "create":
            create_alliance(author, clan, request.POST.get("alliance_name", ""))
            messages.success(request, "Alliance created and your clan enrolled.")
        elif action == "join":
            from .models import Alliance

            alliance = get_object_or_404(Alliance, pk=request.POST.get("alliance_id"))
            join_alliance(author, clan, alliance)
            messages.success(request, "Your clan joined the alliance.")
        elif action == "leave":
            leave_alliance(author, clan)
            messages.success(request, "Your clan left the alliance.")
    except ValidationError as exc:
        messages.error(request, getattr(exc, "message", None) or "; ".join(exc.messages))
    return redirect("chef_battle:clan_detail", slug=slug)
