"""Season lifecycle signals — Phase 6 integration contract.

Emitted by chef_battle.season_service so other subsystems (e.g. GreenBear's
Factions) can react to season transitions without importing season_service
internals. Connect receivers to these in your own app's ready().

season_started(sender=Season, season=<Season instance>)
    Sent when a season becomes ACTIVE (inside activate_season, in-transaction).
    Receivers may open per-season standings for the new season.

season_ended(sender=Season, season=<Season instance>, standings=<QuerySet[SeasonStanding]>)
    Sent when a season is CLOSED (inside close_season's transaction, AFTER the
    ranked SeasonStanding snapshot is written and live seasonal_score is reset).
    `standings` is the frozen, ranked snapshot for this season, ordered by
    rank_position. Receivers run in the SAME transaction as the close — keep
    them fast; raising propagates and rolls back the entire close, so faction
    finalisation and SeasonReward issuance commit atomically with the season end
    or not at all.
"""
import django.dispatch

season_started = django.dispatch.Signal()
season_ended = django.dispatch.Signal()
