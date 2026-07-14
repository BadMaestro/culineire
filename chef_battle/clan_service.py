"""Clan scoring & selectors (Phase 6).

Mirrors faction_service, but the season winner is decided by the RAW SUM of a
clan's members' seasonal points (owner's rule: "the clan whose members scored
the highest total"), not by a size-normalised score. Points live in the
append-only ClanContribution ledger, denormalised onto the clan at write time,
so they stay with the clan when a member leaves.

Canonical rules: docs/chef_battle/clans_alliances_rules.md (sections 1, 3).
"""
from __future__ import annotations

from django.db.models import Count, Sum

from .models import (
    CLAN_ACTIVE_CONTRIBUTION_MIN,
    CLAN_RANK_MEMBER_FLOOR,
    Clan,
    ClanContribution,
    ClanMembership,
)


def award_clan_contribution(chef, points: int, season, *, source=None) -> int:
    """Write a ClanContribution for `chef`'s current active clan, if any.

    Returns the points written (0 if the chef is in no active clan, or points<=0).
    The clan is denormalised so the ledger row survives a later membership change.
    """
    if points <= 0 or season is None:
        return 0
    membership = (
        ClanMembership.objects
        .filter(chef=chef, status=ClanMembership.Status.ACTIVE, left_at__isnull=True)
        .select_related("clan")
        .first()
    )
    if membership is None or not membership.clan.is_active:
        return 0

    kwargs = {"chef": chef, "clan": membership.clan, "season": season, "points": points}
    if source is not None:
        from django.contrib.contenttypes.models import ContentType
        kwargs["source_content_type"] = ContentType.objects.get_for_model(source.__class__)
        kwargs["source_object_id"] = source.pk
    ClanContribution.objects.create(**kwargs)
    return points


def _clan_totals(season):
    """(clan_pk -> {total, active}) for every clan with any contribution this season."""
    totals: dict[int, dict] = {}
    contribs = ClanContribution.objects.filter(season=season)
    for row in contribs.values("clan").annotate(total=Sum("points")):
        totals.setdefault(row["clan"], {})["total"] = row["total"] or 0
    # Active = distinct chefs with >= MIN contributions this season, per clan.
    active_rows = (
        contribs.values("clan", "chef")
        .annotate(n=Count("id"))
        .filter(n__gte=CLAN_ACTIVE_CONTRIBUTION_MIN)
    )
    counts: dict[int, int] = {}
    for r in active_rows:
        counts[r["clan"]] = counts.get(r["clan"], 0) + 1
    for pk, c in counts.items():
        totals.setdefault(pk, {"total": 0})["active"] = c
    for v in totals.values():
        v.setdefault("total", 0)
        v.setdefault("active", 0)
    return totals


def get_clan_leaderboard(season) -> list[dict]:
    """Live, ranked clan standings for `season`, sorted by total_points desc.

    Only clans that are active, approved, and clear the CLAN_RANK_MEMBER_FLOOR
    active-member floor appear. Read-only — never writes ClanSeasonStanding.
    """
    if season is None:
        return []
    totals = _clan_totals(season)
    eligible_pks = [pk for pk, v in totals.items() if v["active"] >= CLAN_RANK_MEMBER_FLOOR]
    clans = {
        c.pk: c
        for c in Clan.objects.filter(
            pk__in=eligible_pks, is_active=True, moderation_status=Clan.Moderation.APPROVED
        )
    }
    rows = [
        {
            "clan": clans[pk],
            "total_points": totals[pk]["total"],
            "active_member_count": totals[pk]["active"],
        }
        for pk in clans
    ]
    rows.sort(key=lambda r: (r["total_points"], r["active_member_count"]), reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank_position"] = i
    return rows


def get_season_winning_clan(season):
    """The single winning clan of `season` (rank 1 on the live board), or None."""
    board = get_clan_leaderboard(season)
    return board[0]["clan"] if board else None


def get_season_clan_champion(season, clan):
    """The clan's top individual contributor this season (the chef who may
    nominate Arena Observers), or None if the clan earned nothing."""
    if season is None or clan is None:
        return None
    top = (
        ClanContribution.objects
        .filter(season=season, clan=clan)
        .values("chef")
        .annotate(total=Sum("points"))
        .order_by("-total", "chef")
        .first()
    )
    if top is None or not top["total"]:
        return None
    from recipes.models import RecipeAuthor
    return RecipeAuthor.objects.filter(pk=top["chef"]).first()
