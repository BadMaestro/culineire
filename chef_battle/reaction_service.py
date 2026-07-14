"""Live-arena 'heart' reactions. Append-only rows; the per-side count is a
COUNT over rows. Anti-farm (rate limit) lives here, not in the schema."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import BattleReaction

REACTION_WINDOW_SECONDS = 60
REACTION_MAX_PER_WINDOW = 60  # per source (author or session) per battle, rolling window


def side_counts(battle) -> dict:
    counts = {"left": 0, "right": 0}
    for row in BattleReaction.objects.filter(battle=battle).values("side").annotate(n=Count("id")):
        counts[row["side"]] = row["n"]
    return counts


def record_battle_reaction(battle, side: str, *, author=None, session_key: str = "") -> int:
    """Record one heart for `side`; returns the new count for that side.
    Raises ValueError on a bad side, PermissionError when rate-limited."""
    if side not in (BattleReaction.Side.LEFT, BattleReaction.Side.RIGHT):
        raise ValueError("invalid side")
    if author is None and not session_key:
        raise PermissionError("no source")

    since = timezone.now() - timedelta(seconds=REACTION_WINDOW_SECONDS)
    source = Q(author=author) if author is not None else Q(session_key=session_key)
    recent = BattleReaction.objects.filter(source, battle=battle, created_at__gte=since).count()
    if recent >= REACTION_MAX_PER_WINDOW:
        raise PermissionError("rate limited")

    BattleReaction.objects.create(
        battle=battle, side=side, author=author, session_key=session_key or ""
    )
    return side_counts(battle)[side]
