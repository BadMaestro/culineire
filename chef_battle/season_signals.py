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
    rank_position. Receivers run in the SAME transaction as the close — so use
    this ONLY for light, must-be-atomic work (e.g. finalising
    FactionSeasonStanding from the frozen standings). Raising rolls back the
    entire close. Do NOT do heavy or fallible work here — use the post-commit
    signal below for that.

season_ended_committed(sender=Season, season=<Season instance>)
    Sent via transaction.on_commit AFTER close_season's transaction commits, so
    the season is durably closed before receivers run. Use this for heavy or
    fallible work — e.g. issuing SeasonReward via RewardRecord — because a
    failure here can NOT roll back the season close. Query the frozen snapshot
    yourself via season.standings.order_by("rank_position"). If the close
    transaction rolls back, this signal never fires.
"""
import django.dispatch

season_started = django.dispatch.Signal()
season_ended = django.dispatch.Signal()
season_ended_committed = django.dispatch.Signal()
