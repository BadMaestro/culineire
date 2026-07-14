"""Clans & Alliances — membership read/write for the UI (GreenBear's lane).

The scoring side (ClanContribution ledger, leaderboard, winning clan, champion)
lives in clan_service.py (Bolt's lane). This module owns the *membership* flow:
founding a clan, the request -> approve join flow, leaving, and the Season-1
alliance foundation. It never writes ClanContribution or ClanSeasonStanding.

Owner-delegated rules (design doc docs/chef_battle/clans_design.md):
- soft member cap of CLAN_MEMBER_CAP;
- join is request -> founder approves;
- points already earned stay with the clan when a member leaves (event-sourced
  ledger, so nothing to move here — leaving only stops future accrual).
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    Alliance,
    AllianceMembership,
    Clan,
    ClanContribution,
    ClanMembership,
)

CLAN_MEMBER_CAP = 12          # soft cap on active members (founder included)
CLAN_MIN_CATEGORIES = 1
CLAN_MAX_CATEGORIES = 3       # owner rule: up to 3, and never every category


# ---------------------------------------------------------------- reads --------

def get_active_membership(chef):
    """The chef's single active clan membership (or None)."""
    if chef is None:
        return None
    return (
        ClanMembership.objects.filter(
            chef=chef, status=ClanMembership.Status.ACTIVE, left_at__isnull=True
        )
        .select_related("clan")
        .first()
    )


def get_pending_membership(chef, clan):
    """A chef's outstanding join request to a specific clan (or None)."""
    if chef is None or clan is None:
        return None
    return ClanMembership.objects.filter(
        chef=chef, clan=clan, status=ClanMembership.Status.PENDING, left_at__isnull=True
    ).first()


def active_member_count(clan) -> int:
    return ClanMembership.objects.filter(
        clan=clan, status=ClanMembership.Status.ACTIVE, left_at__isnull=True
    ).count()


def get_clan_roster(clan) -> list:
    """Active members, founder first, then by join time."""
    return list(
        ClanMembership.objects.filter(
            clan=clan, status=ClanMembership.Status.ACTIVE, left_at__isnull=True
        )
        .select_related("chef")
        .order_by("-role", "joined_at")  # 'member' < 'founder' desc puts founder first
    )


def get_pending_requests(clan) -> list:
    """Outstanding join requests for the founder to review."""
    return list(
        ClanMembership.objects.filter(
            clan=clan, status=ClanMembership.Status.PENDING, left_at__isnull=True
        )
        .select_related("chef")
        .order_by("joined_at")
    )


def is_founder(chef, clan) -> bool:
    return chef is not None and clan is not None and clan.founder_id == chef.id


def get_clan_standing(clan, season) -> dict:
    """One clan's live standing for a season (works below the rank floor too)."""
    from .clan_service import get_clan_leaderboard

    if season is None:
        return {"total_points": 0, "active_member_count": 0, "rank_position": None}
    total = (
        ClanContribution.objects.filter(clan=clan, season=season).aggregate(
            t=Sum("points")
        )["t"]
        or 0
    )
    rank = None
    for row in get_clan_leaderboard(season):
        if row["clan"].id == clan.id:
            rank = row["rank_position"]
            break
    return {
        "total_points": total,
        "active_member_count": active_member_count(clan),
        "rank_position": rank,
    }


def get_clan_top_contributors(clan, season, limit: int = 15) -> list:
    """Members who contributed most to this clan this season, points desc."""
    if season is None:
        return []
    return list(
        ClanContribution.objects.filter(clan=clan, season=season)
        .values("chef", "chef__name", "chef__slug")
        .annotate(points=Sum("points"))
        .order_by("-points")[:limit]
    )


# --------------------------------------------------------------- writes --------

def _unique_slug(name: str) -> str:
    base = slugify(name)[:70] or "clan"
    slug = base
    n = 2
    while Clan.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


@transaction.atomic
def create_clan(founder, name: str, crest_icon: str, category_ids: list) -> Clan:
    """Found a clan (moderation: pending) and seat the founder as its first
    active member. Enforces the one-active-clan-per-chef rule and the 1..3
    (never all) category rule."""
    from .models import Faction

    name = (name or "").strip()
    if not name:
        raise ValidationError("Your clan needs a name.")
    if get_active_membership(founder) is not None:
        raise ValidationError("You are already in a clan. Leave it before founding a new one.")

    ids = [int(i) for i in category_ids if str(i).isdigit()]
    categories = list(Faction.objects.filter(pk__in=ids, is_active=True))
    if len(categories) < CLAN_MIN_CATEGORIES:
        raise ValidationError("Choose at least one category for your clan.")
    if len(categories) > CLAN_MAX_CATEGORIES:
        raise ValidationError(f"A clan may hold at most {CLAN_MAX_CATEGORIES} categories.")
    total_available = Faction.objects.filter(is_active=True).count()
    if len(categories) >= total_available:
        raise ValidationError("A clan cannot select every available category.")

    clan = Clan.objects.create(
        founder=founder,
        name=name,
        slug=_unique_slug(name),
        crest_icon=(crest_icon or "").strip()[:8],
        moderation_status=Clan.Moderation.PENDING,
        is_active=True,
    )
    clan.categories.set(categories)
    ClanMembership.objects.create(
        clan=clan,
        chef=founder,
        role=ClanMembership.Role.FOUNDER,
        status=ClanMembership.Status.ACTIVE,
    )
    return clan


def request_join(chef, clan) -> ClanMembership:
    """Ask to join a clan (creates a pending membership for the founder to approve)."""
    if not clan.is_active or clan.moderation_status != Clan.Moderation.APPROVED:
        raise ValidationError("This clan is not open to new members right now.")
    if get_active_membership(chef) is not None:
        raise ValidationError("You are already in a clan. Leave it before joining another.")
    if get_pending_membership(chef, clan) is not None:
        raise ValidationError("You already have a pending request to this clan.")
    if active_member_count(clan) >= CLAN_MEMBER_CAP:
        raise ValidationError("This clan is full.")
    return ClanMembership.objects.create(
        clan=clan, chef=chef, role=ClanMembership.Role.MEMBER,
        status=ClanMembership.Status.PENDING,
    )


@transaction.atomic
def approve_request(founder, membership: ClanMembership) -> ClanMembership:
    """Founder approves a pending request -> active membership."""
    clan = membership.clan
    if not is_founder(founder, clan):
        raise ValidationError("Only the clan founder can approve members.")
    if membership.status != ClanMembership.Status.PENDING:
        raise ValidationError("That request is no longer pending.")
    if get_active_membership(membership.chef) is not None:
        # The applicant joined another clan while this request sat in the queue.
        raise ValidationError("This chef has since joined another clan.")
    if active_member_count(clan) >= CLAN_MEMBER_CAP:
        raise ValidationError("Your clan is full.")
    try:
        membership.status = ClanMembership.Status.ACTIVE
        membership.save(update_fields=["status"])
    except IntegrityError:
        raise ValidationError("This chef is already active in a clan.")
    return membership


def deny_request(founder, membership: ClanMembership) -> None:
    """Founder rejects a pending request."""
    if not is_founder(founder, membership.clan):
        raise ValidationError("Only the clan founder can decline members.")
    if membership.status != ClanMembership.Status.PENDING:
        raise ValidationError("That request is no longer pending.")
    membership.delete()


def leave_clan(chef) -> None:
    """Leave your current clan. The founder cannot leave (they would have to
    disband the clan — not offered in this MVP). Points already earned stay
    with the clan."""
    membership = get_active_membership(chef)
    if membership is None:
        raise ValidationError("You are not in a clan.")
    if membership.role == ClanMembership.Role.FOUNDER:
        raise ValidationError(
            "As the founder you cannot leave your own clan in this version."
        )
    membership.left_at = timezone.now()
    membership.save(update_fields=["left_at"])


# ------------------------------------------------------ alliances (S1) ---------

def get_clan_alliance(clan):
    """The clan's active alliance membership (or None)."""
    if clan is None:
        return None
    return (
        AllianceMembership.objects.filter(clan=clan, left_at__isnull=True)
        .select_related("alliance")
        .first()
    )


def get_alliance_clans(alliance) -> list:
    return list(
        AllianceMembership.objects.filter(alliance=alliance, left_at__isnull=True)
        .select_related("clan")
        .order_by("joined_at")
    )


def list_alliances() -> list:
    return list(
        Alliance.objects.filter(is_active=True)
        .annotate(
            clan_count=Count(
                "memberships",
                filter=Q(memberships__left_at__isnull=True),
            )
        )
        .order_by("name")
    )


@transaction.atomic
def create_alliance(founder, clan, name: str) -> Alliance:
    """Found an alliance and enrol the founder's clan as its first member.
    Only a clan founder may create an alliance on behalf of their clan (S1
    foundation — a minimal hook; full mechanics expand in a later season)."""
    if not is_founder(founder, clan):
        raise ValidationError("Only a clan founder can create an alliance for their clan.")
    if get_clan_alliance(clan) is not None:
        raise ValidationError("Your clan is already in an alliance.")
    name = (name or "").strip()
    if not name:
        raise ValidationError("Your alliance needs a name.")
    base = slugify(name)[:70] or "alliance"
    slug, n = base, 2
    while Alliance.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    alliance = Alliance.objects.create(name=name, slug=slug, is_active=True)
    AllianceMembership.objects.create(alliance=alliance, clan=clan)
    return alliance


def join_alliance(founder, clan, alliance) -> AllianceMembership:
    if not is_founder(founder, clan):
        raise ValidationError("Only a clan founder can enrol their clan in an alliance.")
    if not alliance.is_active:
        raise ValidationError("That alliance is not active.")
    if get_clan_alliance(clan) is not None:
        raise ValidationError("Your clan is already in an alliance.")
    return AllianceMembership.objects.create(alliance=alliance, clan=clan)


def leave_alliance(founder, clan) -> None:
    if not is_founder(founder, clan):
        raise ValidationError("Only a clan founder can withdraw their clan from an alliance.")
    membership = get_clan_alliance(clan)
    if membership is None:
        raise ValidationError("Your clan is not in an alliance.")
    membership.left_at = timezone.now()
    membership.save(update_fields=["left_at"])
