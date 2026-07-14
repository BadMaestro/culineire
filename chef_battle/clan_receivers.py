"""Season-lifecycle receiver for Clans (Phase 6).

Freezes ClanSeasonStanding from the ClanContribution ledger when a season
closes, mirroring faction_receivers. Defensive: a clan bug must never roll back
Bolt's season close (it fires inside close_season's transaction).
"""
from __future__ import annotations

import logging

from .season_signals import season_ended

logger = logging.getLogger(__name__)


def _finalize_clan_standings(season):
    from .clan_service import get_clan_leaderboard, _clan_totals
    from .models import Clan, ClanSeasonStanding

    ranked = {r["clan"].pk: r for r in get_clan_leaderboard(season)}
    totals = _clan_totals(season)
    # One standing row per clan that earned anything this season.
    for clan in Clan.objects.filter(pk__in=list(totals.keys())):
        row = ranked.get(clan.pk)
        ClanSeasonStanding.objects.update_or_create(
            clan=clan, season=season,
            defaults={
                "total_points": totals[clan.pk]["total"],
                "active_member_count": totals[clan.pk]["active"],
                "rank_position": row["rank_position"] if row else None,
                "rewards_pending": row is not None and row["rank_position"] == 1,
            },
        )


def on_clan_season_ended(sender, season, **kwargs):
    try:
        _finalize_clan_standings(season)
    except Exception:
        logger.exception("Clan season_ended finalisation failed for season pk=%s", season.pk)


def connect():
    season_ended.connect(on_clan_season_ended, dispatch_uid="clans_on_season_ended")
