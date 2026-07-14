"""Live-arena snapshot contract (Phase 1 transport envelope).

Single source of truth for what the broadcast arena renders. Server-authoritative
+ envelope (server_timestamp, sequence) so the frontend can interpolate the timer,
reject stale updates and resync on reconnect with a full snapshot. Field keys
match the frontend fixture exactly (agreed with GreenBear).
"""
from __future__ import annotations

from django.utils import timezone

STATIC_COUNTRY = "Ireland"           # owner decision: country is static for now
VIEWER_ONLINE_SECONDS = 120
CHAT_TAIL = 12


def _viewer_count(battle) -> int:
    from .models import BattleViewerPresence
    cutoff = timezone.now() - timezone.timedelta(seconds=VIEWER_ONLINE_SECONDS)
    return (
        BattleViewerPresence.objects.filter(battle=battle, last_seen_at__gte=cutoff)
        .values("viewer_hash").distinct().count()
    )


def _chat_count(battle) -> int:
    from .models import BattleChatMessage
    return BattleChatMessage.objects.filter(battle=battle, is_hidden=False).count()


def _supporter_count(battle, chef) -> int:
    # Only battle-scoped gifts count as this battle's supporters.
    from .models import ViewerBattleGift
    return ViewerBattleGift.objects.filter(battle=battle, recipient=chef).count()


def _chef_side(battle, author, side, reactions):
    from .models import ChefBattleProfile, ClanMembership, LiveStreamSession
    profile = ChefBattleProfile.objects.filter(author=author).first()
    membership = (
        ClanMembership.objects.filter(
            chef=author, status=ClanMembership.Status.ACTIVE, left_at__isnull=True
        ).select_related("clan").first()
    )
    stream = LiveStreamSession.objects.filter(battle=battle, chef=author).order_by("-id").first()
    playback = getattr(stream, "provider_playback_url", "") or ""
    rank_label = profile.get_rank_display() if profile else ""
    return {
        "num": "CHEF #1" if side == "left" else "CHEF #2",
        "name": author.name,
        "rank": rank_label,
        "clan": membership.clan.name if membership else "",
        "country": STATIC_COUNTRY,
        "avatar_url": getattr(author, "display_avatar_url", "") or "",
        "playback_url": playback,
        "stream_state": "active" if playback else "waiting",
        "viewers": _viewer_count(battle),
        "likes": reactions.get(side, 0),          # real reaction count
        "comments": _chat_count(battle),
        "supporters": _supporter_count(battle, author),
        "role": rank_label,
    }


def build_arena_snapshot(battle, *, sequence: int = 0) -> dict:
    """Full server-authoritative snapshot for one battle. Reconnect = re-fetch this."""
    from .models import BattleChatMessage
    from .reaction_service import side_counts
    from .selectors import _battle_deadline

    now = timezone.now()
    _deadline, remaining = _battle_deadline(battle, now)
    reactions = side_counts(battle)

    tail = list(
        BattleChatMessage.objects.filter(battle=battle, is_hidden=False)
        .order_by("-created_at")[:CHAT_TAIL]
    )
    tail.reverse()
    chat = [(m.display_name or "Guest", m.body) for m in tail]

    return {
        "server_timestamp": now.isoformat(),
        "sequence": sequence,
        "battle": {
            "id": battle.pk,
            "public_id": battle.pk,
            "title": "Chef's Battle",
            "theme": battle.theme,
            "state": battle.status,
            "remaining_seconds": remaining or 0,
            "is_chat_enabled": True,
            "is_support_enabled": True,
        },
        "left": _chef_side(battle, battle.challenger, "left", reactions),
        "right": _chef_side(battle, battle.opponent, "right", reactions),
        "chat": chat,
    }


def get_current_arena_battle():
    """The battle the live arena should feature: a live/active one first, else the
    most recent. None when no battles exist (preview falls back to fixtures)."""
    from .models import Battle
    live = (
        Battle.objects.filter(status__in=Battle.ACTIVE_STATUSES)
        .select_related("challenger", "opponent")
        .order_by("-start_time")
        .first()
    )
    if live:
        return live
    return (
        Battle.objects.select_related("challenger", "opponent")
        .order_by("-start_time")
        .first()
    )
