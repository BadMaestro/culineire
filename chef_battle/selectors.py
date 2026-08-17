from __future__ import annotations

from django.db import models
from django.db.models import Case, Count, IntegerField, Q, QuerySet, When
from django.utils import timezone

from .models import Battle, BattleChallenge, BattleEvent, BattleVote, ChefBattleProfile

_RANK_ORDER = Case(
    When(rank="culinary_master", then=8),
    When(rank="executive_chef", then=7),
    When(rank="head_chef", then=6),
    When(rank="sous_chef", then=5),
    When(rank="chef_de_partie", then=4),
    When(rank="commis_chef", then=3),
    When(rank="prep_cook", then=2),
    When(rank="kitchen_porter", then=1),
    default=0,
    output_field=IntegerField(),
)


def get_active_battles(limit: int = 12) -> QuerySet:
    return (
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(status__in=Battle.ACTIVE_STATUSES)
        .order_by("end_time")[:limit]
    )


def get_upcoming_battles(limit: int = 6) -> QuerySet:
    """Battles that have been arranged and have not started yet (card X01).

    The Owner, 2026-08-05: the arena exists so chefs, sponsors, spectators, VIPs
    and spirits can see each other AND to show the list of upcoming battles.
    Nothing answered the second half - there was no key in the payload and no
    selector behind it.

    UPCOMING IS A NARROWER SET THAN "NOT FINISHED", and the difference is why
    this is not get_active_battles() with a filter bolted on. ACTIVE_STATUSES
    deliberately includes SCHEDULED so a battle about to begin still draws on
    the floor; here SCHEDULED alone is not enough, because a scheduled battle
    whose start_time has passed is one the arena is already showing, not one it
    is announcing. The boundary is the clock, so it is applied here rather than
    left to the caller to remember.

    WAITING is excluded on purpose: that battle started, and is sitting out the
    grace period for its second chef. It is late, not forthcoming.

    SIX, because the board shows three pills to a row and at most two rows
    (Owner, 2026-08-05). A seventh would either add a row the composition has no
    height for or drop out silently, and a board that hides departures is worse
    than a short one.
    """
    return (
        Battle.objects.select_related("challenger", "opponent")
        .filter(status=Battle.Status.SCHEDULED, start_time__gt=timezone.now())
        .order_by("start_time")[:limit]
    )


def get_recent_completed_battles(limit: int = 10) -> QuerySet:
    return (
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(status=Battle.Status.COMPLETED)
        .order_by("-updated_at")[:limit]
    )


def _uncompeting_slugs() -> set[str]:
    """Slugs that must never appear in a COMPETITIVE aggregate.

    T22: the Owner is present on the Arena and may wear a clan, but he is
    outside the competition - his rank is hand-set (migrations 0020/0025), so a
    ladder keyed to WINS would carry an account that never earned its place.
    `is_immortal()` in services.py already stops the game taking anything FROM
    him; this stops it counting him.

    Deliberately separate from `_hidden_bot_slugs()` even though both end up as
    an `.exclude()`: bots are hidden by a switch that can be turned back on
    (ARENA_SHOW_EMULATION_BOTS), the Owner's exclusion is a permanent rule with
    no switch. One function per reason, so neither can be flipped by accident
    while trying to change the other.
    """
    from django.conf import settings as django_settings
    slug = getattr(django_settings, "OWNER_SLUG", None)
    return {slug} if slug else set()


def get_top_profiles(limit: int = 10) -> QuerySet:
    return (
        ChefBattleProfile.objects.select_related("author")
        .filter(enrolled_at__isnull=False)
        .exclude(author__slug__in=_uncompeting_slugs())
        .annotate(rank_order=_RANK_ORDER)
        .order_by("-rating", "-rank_order", "-wins", "author__name")[:limit]
    )


def get_public_events(limit: int = 12) -> QuerySet:
    return (
        BattleEvent.objects.select_related("battle", "actor", "target")
        .filter(is_public=True)
        .order_by("-created_at")[:limit]
    )


def get_expired_active_battles(limit: int = 20) -> QuerySet:
    now = timezone.now()
    return Battle.objects.filter(
        status__in=[Battle.Status.ACTIVE, Battle.Status.VOTING],
        end_time__lte=now,
    )[:limit]


def get_battle_vote_counts(battle: Battle) -> dict[int, int]:
    return {
        row["voted_for"]: row["total"]
        for row in battle.votes.values("voted_for").annotate(total=Count("id"))
    }


def get_head_to_head(chef_a, chef_b, *, exclude_pk=None) -> dict:
    """T30/D1: how these two chefs have fared against each other before -
    the 'statistics' half of the antechamber the Hall Plan asks for, keyed
    to THIS matchup specifically rather than each chef's overall record
    (which the antechamber cards already show).

    Real data only, same discipline as get_crown_ladder: COMPLETED battles
    with a decided winner only - a battle still running, or one that ended
    in a no-reward cancellation/void with no winner, tells nothing about who
    has beaten whom. Symmetric in (chef_a, chef_b) - which side is the
    "challenger" of THIS battle does not change who is being compared.
    """
    qs = Battle.objects.filter(
        status=Battle.Status.COMPLETED,
        winner__isnull=False,
    ).filter(
        (Q(challenger=chef_a) & Q(opponent=chef_b))
        | (Q(challenger=chef_b) & Q(opponent=chef_a))
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    total = 0
    a_wins = 0
    b_wins = 0
    for winner_id in qs.values_list("winner_id", flat=True):
        total += 1
        if winner_id == chef_a.pk:
            a_wins += 1
        elif winner_id == chef_b.pk:
            b_wins += 1
    return {"total": total, "chef_a_wins": a_wins, "chef_b_wins": b_wins}


def get_sent_challenges(author, limit: int = 20) -> QuerySet:
    return (
        BattleChallenge.objects.select_related("opponent")
        .filter(challenger=author)
        .order_by("-created_at")[:limit]
    )


def get_received_challenges(author, limit: int = 20) -> QuerySet:
    return (
        BattleChallenge.objects.select_related("challenger")
        .filter(opponent=author)
        .order_by("-created_at")[:limit]
    )


def get_rankings(limit: int = 100) -> QuerySet:
    return (
        ChefBattleProfile.objects.select_related("author")
        .filter(enrolled_at__isnull=False)
        .exclude(author__slug__in=_uncompeting_slugs())
        .annotate(rank_order=_RANK_ORDER)
        .order_by("-rating", "-rank_order", "-wins", "author__name")[:limit]
    )


def get_hall_of_fame_battles(limit: int = 10):
    """The Founding Ten — the first battles ever completed on this site.

    hall_of_fame.md calls them "permanently marked", and until 2026-08-11 they
    were not: this ordered by ``updated_at``, which is ``auto_now``, so ANY
    later write to a completed battle — a moderation note, a dispute, a
    withdrawal resolution, an operator touch — moved it to the end of the
    ordering and silently evicted it from the founding ten, letting a newer
    battle take the seat. Found by the audit of 2026-08-10 (G4).

    The order now comes from the BATTLE_FINISHED event, whose ``created_at`` is
    ``auto_now_add`` and therefore cannot move. That is also the truthful
    ordering: it is when each battle actually finished, not when its row was
    last touched. A battle finished before the event log carried that type
    falls back to its own creation time, which is likewise immutable — never to
    ``updated_at``, which is the whole defect.
    """
    from .models import BattleEvent

    finished_at = {}
    for battle_id, created_at in (
        BattleEvent.objects
        .filter(event_type=BattleEvent.EventType.BATTLE_FINISHED, battle__isnull=False)
        .order_by("created_at")
        .values_list("battle_id", "created_at")
    ):
        finished_at.setdefault(battle_id, created_at)

    battles = list(
        Battle.objects.select_related("challenger", "opponent", "winner", "loser")
        .filter(status=Battle.Status.COMPLETED, winner__isnull=False)
        .prefetch_related("entries__recipe", "votes")
    )
    battles.sort(key=lambda b: (finished_at.get(b.pk) or b.created_at, b.pk))
    return battles[:limit]


def get_hall_of_fame_chefs(limit: int = 20):
    """The Board of Memory — the first chefs ever to step into the arena.

    hall_of_fame.md Rule 2: "The first 20 chefs who participate in any battle
    (as challenger or opponent) will have their names permanently inscribed."
    That is a PIONEER list and it is permanent. Until 2026-08-11 this returned
    the top twenty BY WINS, which is a leaderboard — a different set entirely,
    and one that changes every time somebody wins. Found by the audit of
    2026-08-10 (G7); the rankings page already exists for the leaderboard.

    Order of arrival is taken from each chef's earliest battle by ``created_at``
    (``auto_now_add``), so a chef's place on this board can never be taken from
    them by anything that happens afterwards.
    """
    seen = {}
    for challenger_id, opponent_id, created_at in (
        Battle.objects.order_by("created_at", "pk")
        .values_list("challenger_id", "opponent_id", "created_at")
    ):
        for author_id in (challenger_id, opponent_id):
            if author_id is not None and author_id not in seen:
                seen[author_id] = created_at
        if len(seen) >= limit:
            break

    if not seen:
        return []

    profiles = {
        p.author_id: p
        for p in ChefBattleProfile.objects.select_related("author")
        .filter(author_id__in=list(seen))
    }
    ordered = sorted(seen, key=lambda author_id: (seen[author_id], author_id))
    return [profiles[a] for a in ordered[:limit] if a in profiles]


def get_author_battle_summary(author):
    """Battle data for the merged author page arena section (chef_battle owns
    this so the recipes app never queries battle models directly):
    - battle_profile: the ChefBattleProfile (or None)
    - recent_battles: short list for compact summaries
    - battles: full recent history (20) for the arena section
    - gift_display: appreciation gifts aggregated by type
    """
    from django.db.models import Count, Q
    from .models import AppreciationGiftType, APPRECIATION_GIFT_EMOJI

    battle_profile = ChefBattleProfile.objects.filter(author=author).first()
    battles = list(
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(Q(challenger=author) | Q(opponent=author))
        .order_by("-created_at")[:20]
    )
    gift_display = [
        {
            "type": g["gift_type"],
            "label": AppreciationGiftType(g["gift_type"]).label,
            "count": g["total"],
            "emoji": APPRECIATION_GIFT_EMOJI.get(g["gift_type"], "\U0001F381"),
        }
        for g in author.appreciation_gifts.values("gift_type")
        .annotate(total=Count("id")).order_by("-total")
    ]
    return {
        "battle_profile": battle_profile,
        "recent_battles": battles[:6],
        "battles": battles,
        "gift_display": gift_display,
        "champion_badge": get_champion_badge(author),
    }


def get_champion_badge(author):
    """Season-champion medal for a chef's avatar, or None.

    Returns the most recent season the chef was crowned champion of (a
    SeasonReward with placement=1, written at season close). Drives the coin
    badge overlaid on the champion's avatar.
    """
    from .models import SeasonReward
    reward = (
        SeasonReward.objects.filter(chef=author, placement=1)
        .select_related("faction", "season")
        .order_by("-season__ends_at", "-created_at")
        .first()
    )
    if reward is None:
        return None
    return {
        "season_name": reward.season.name,
        "faction_name": reward.faction.name,
        "faction_kind": reward.faction.get_kind_display(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Arena Master Console read models (P02).
# Read-only. Every field maps to a documented real query — see
# docs/chef_battle/arena_master_console/P02_DATA_DICTIONARY.yaml.
# Fields whose source does not exist return explicit unavailable states,
# never fabricated numbers.
# ═════════════════════════════════════════════════════════════════════════════

ARENA_ONLINE_THRESHOLD_SECONDS = 180  # same as views._ARENA_ONLINE_THRESHOLD

# Console phase rail steps (reference design): status -> 1..7.
MASTER_PHASE_RAIL_STEP = {
    Battle.Status.SCHEDULED: 1,
    Battle.Status.MENU_LOCKED: 1,
    Battle.Status.ACTIVE: 2,
    Battle.Status.INGREDIENT_PENALTY: 3,
    Battle.Status.AWAITING_SUBMISSIONS: 4,
    Battle.Status.COOKING: 4,
    Battle.Status.REVEALED: 5,
    Battle.Status.PRESENTATION: 5,
    Battle.Status.VOTING: 6,
    Battle.Status.COMPLETED: 7,
}

# Canonical expected next status for display only. Real transitions are
# service-driven; this map never drives any write.
MASTER_NEXT_STATUS = {
    Battle.Status.SCHEDULED: Battle.Status.MENU_LOCKED,
    Battle.Status.MENU_LOCKED: Battle.Status.ACTIVE,
    Battle.Status.ACTIVE: Battle.Status.VOTING,
    Battle.Status.AWAITING_SUBMISSIONS: Battle.Status.REVEALED,
    Battle.Status.REVEALED: Battle.Status.VOTING,
    Battle.Status.COOKING: Battle.Status.PRESENTATION,
    Battle.Status.PRESENTATION: Battle.Status.VOTING,
    Battle.Status.VOTING: Battle.Status.COMPLETED,
    Battle.Status.INGREDIENT_PENALTY: Battle.Status.COMPLETED,
}


def _battle_deadline(battle, now):
    """The deadline currently counting down for this battle.
    voting -> voting_deadline; pre-voting -> submission_deadline; else end_time."""
    if battle.status == Battle.Status.VOTING:
        deadline = battle.voting_deadline or battle.end_time
    elif battle.status in (
        Battle.Status.SCHEDULED, Battle.Status.MENU_LOCKED, Battle.Status.ACTIVE,
        Battle.Status.AWAITING_SUBMISSIONS, Battle.Status.COOKING,
    ):
        deadline = battle.submission_deadline or battle.end_time
    else:
        deadline = battle.end_time
    if not deadline:
        return None, None
    seconds = int((deadline - now).total_seconds())
    return deadline.isoformat(), max(seconds, 0)


def _serialize_master_participant(author, profile, ready):
    return {
        "name": author.name,
        "slug": author.slug,
        "avatar_url": author.display_avatar_url,
        "rank": profile.rank if profile else None,
        "rank_label": profile.get_rank_display() if profile else None,
        "rating": profile.rating if profile else None,
        "wins": profile.wins if profile else None,
        "losses": profile.losses if profile else None,
        "win_streak": profile.win_streak if profile else None,
        "ready": ready,
    }


def get_master_state() -> dict:
    """Aggregated read-only state for the Arena Master Console (P02).

    One call assembles every console section. JSON-safe. No writes.
    Contract: docs/chef_battle/arena_master_console/P00_CONTRACTS.yaml.
    """
    from django.conf import settings as django_settings
    from django.db.models import Q, Sum
    from .models import (
        BattleEntry, BattleIngredient, ContentReport, IngredientShot,
        PayoutRequest, TokenTransaction, ViewerBattleGift,
    )

    now = timezone.now()
    online_cutoff = now - timezone.timedelta(seconds=ARENA_ONLINE_THRESHOLD_SECONDS)

    # ── arena section ────────────────────────────────────────────────
    profile_counts = ChefBattleProfile.objects.aggregate(
        enrolled=Count("id", filter=Q(enrolled_at__isnull=False)),
        online=Count("id", filter=Q(enrolled_at__isnull=False, is_suspended=False,
                                    last_seen_at__gte=online_cutoff)),
        suspended=Count("id", filter=Q(enrolled_at__isnull=False, is_suspended=True)),
    )
    crown = (
        ChefBattleProfile.objects.select_related("author")
        .filter(crown_until__gt=now)
        .exclude(author__slug__in=_uncompeting_slugs())  # T31
        .order_by("-crown_until")
        .first()
    )

    # ── battles section ──────────────────────────────────────────────
    # ACTIVE_STATUSES + ingredient_penalty (in-progress biathlon phase,
    # excluded from the public "in progress" set) + paused (Emergency Stop)
    # + revealed (P03 force target not in ACTIVE_STATUSES; would vanish from
    # the console if excluded).
    statuses = set(Battle.ACTIVE_STATUSES) | {
        Battle.Status.INGREDIENT_PENALTY,
        Battle.Status.PAUSED,
        Battle.Status.REVEALED,
    }
    battles = list(
        Battle.objects.select_related("challenger", "opponent")
        .filter(status__in=statuses)
        .order_by("end_time")
    )
    participant_ids = {b.challenger_id for b in battles} | {b.opponent_id for b in battles}
    profiles_by_author = {
        p.author_id: p
        for p in ChefBattleProfile.objects.filter(author_id__in=participant_ids)
    }

    battle_dicts = []
    for b in battles:
        deadline_iso, seconds_remaining = _battle_deadline(b, now)
        next_status = MASTER_NEXT_STATUS.get(b.status)
        battle_dicts.append({
            "id": b.pk,
            "status": b.status,
            "status_display": b.get_status_display(),
            "next_status": next_status,
            "next_status_display": Battle.Status(next_status).label if next_status else None,
            "phase_rail_step": MASTER_PHASE_RAIL_STEP.get(b.status),
            "theme": b.theme,
            "battle_type": b.battle_type,
            "is_paused": b.status == Battle.Status.PAUSED,
            "url": b.get_absolute_url(),
            "start_time": b.start_time.isoformat() if b.start_time else None,
            "submission_deadline": b.submission_deadline.isoformat() if b.submission_deadline else None,
            "voting_deadline": b.voting_deadline.isoformat() if b.voting_deadline else None,
            "end_time": b.end_time.isoformat() if b.end_time else None,
            "deadline": deadline_iso,
            "seconds_remaining": seconds_remaining,
            "combat_time_confirmed": b.combat_time_confirmed,
            "challenger": _serialize_master_participant(
                b.challenger, profiles_by_author.get(b.challenger_id), b.challenger_ready
            ),
            "opponent": _serialize_master_participant(
                b.opponent, profiles_by_author.get(b.opponent_id), b.opponent_ready
            ),
        })

    # ── combat section (JSON-safe summaries, same queries as combat UI) ──
    combat = []
    for b in battles:
        if b.status == Battle.Status.ACTIVE:
            rounds = list(
                b.combat_rounds.order_by("round_number")
                .values("round_number", "challenger_hits", "opponent_hits")
            )
            last = rounds[-1] if rounds else None
            combat.append({
                "battle_id": b.pk,
                "kind": "combat",
                "rounds_played": len(rounds),
                "challenger_hits": last["challenger_hits"] if last else 0,
                "opponent_hits": last["opponent_hits"] if last else 0,
            })
        elif b.status == Battle.Status.INGREDIENT_PENALTY:
            combat.append({
                "battle_id": b.pk,
                "kind": "biathlon",
                # T11: the two blocks are placed at declare_menu, before
                # Stage 1, so what this phase counts is shots - the blocks
                # are already there and are not an action the console waits on.
                "blocks_placed": b.battle_ingredients.filter(
                    chef_id=b.loser_id, is_key=True).count() if b.loser_id else 0,
                "shots_fired": b.ingredient_shots.count(),
                "max_blocks": BattleIngredient.KEY_COUNT,
                "max_shots": IngredientShot.MAX_SHOTS,
            })

    # ── moderation section ───────────────────────────────────────────
    moderation = {
        "cooking_queue": Battle.objects.filter(status__in=[
            Battle.Status.INGREDIENT_PENALTY, Battle.Status.COOKING,
        ]).count(),
        "content_reports_pending": ContentReport.objects.filter(
            status=ContentReport.Status.PENDING
        ).count(),
        "entries_flagged": BattleEntry.objects.filter(
            moderation_status__in=[
                BattleEntry.ModerationStatus.FLAGGED,
                BattleEntry.ModerationStatus.SUSPECTED_AI,
                BattleEntry.ModerationStatus.SUSPECTED_STOCK,
                BattleEntry.ModerationStatus.DUPLICATE,
            ]
        ).count(),
    }

    # ── voting section ───────────────────────────────────────────────
    voting = [
        _voting_analytics_for_battle(b, now) for b in battles
    ]

    # ── viewers section ──────────────────────────────────────────────
    # DG-04 resolved 2026-07-05 (design delegated to Claude by the owner):
    # BattleViewerPresence heartbeats ride the existing public 20 s polls;
    # a viewer is active if seen within 180 s. Device-hash pseudonymised,
    # no raw IP/UA stored, rows purged after an hour of inactivity.
    from django.db.models import Count as _PCount
    from .models import BattleViewerPresence

    presence_cutoff = now - timezone.timedelta(seconds=ARENA_ONLINE_THRESHOLD_SECONDS)
    presence_rows = {
        row["battle_id"]: row["n"]
        for row in BattleViewerPresence.objects.filter(last_seen_at__gte=presence_cutoff)
        .values("battle_id").annotate(n=_PCount("id"))
    }
    viewers = {
        "available": True,
        "definition": "distinct devices polling the page within 180s (battle room per battle; arena lobby separate)",
        "window_seconds": ARENA_ONLINE_THRESHOLD_SECONDS,
        "arena_lobby_viewers": presence_rows.get(None, 0),
        "battles": [
            {"battle_id": b.pk, "viewers": presence_rows.get(b.pk, 0)}
            for b in battles
        ],
        "arena_online_chefs": profile_counts["online"],
    }

    # ── economy section ──────────────────────────────────────────────
    day_ago = now - timezone.timedelta(hours=24)
    flows = TokenTransaction.objects.filter(created_at__gte=day_ago).aggregate(
        tokens_in=Sum("amount", filter=Q(amount__gt=0)),
        tokens_out=Sum("amount", filter=Q(amount__lt=0)),
    )
    battle_ids = [b.pk for b in battles]
    gift_totals = {
        row["battle_id"]: row
        for row in ViewerBattleGift.objects.filter(battle_id__in=battle_ids)
        .values("battle_id")
        .annotate(gifts=Count("id"), tokens=Sum("tokens_spent"))
    }
    economy = {
        "window_hours": 24,
        "tokens_in_24h": flows["tokens_in"] or 0,
        "tokens_out_24h": flows["tokens_out"] or 0,
        "battle_gifts": [
            {
                "battle_id": bid,
                "gift_count": gift_totals.get(bid, {}).get("gifts", 0),
                "tokens_spent": gift_totals.get(bid, {}).get("tokens", 0) or 0,
            }
            for bid in battle_ids
        ],
        "pending_payouts": PayoutRequest.objects.filter(
            status__in=[PayoutRequest.Status.PENDING, PayoutRequest.Status.UNDER_REVIEW]
        ).count(),
        "detail": get_master_economy_detail(),
    }

    # ── system section ───────────────────────────────────────────────
    system = {
        "server_time": now.isoformat(),
        "chef_battle_enabled": bool(getattr(django_settings, "CHEF_BATTLE_ENABLED", False)),
        "console_flag_enabled": bool(getattr(django_settings, "ARENA_MASTER_CONSOLE_ENABLED", False)),
        "active_battle_count": sum(1 for b in battles if b.status != Battle.Status.PAUSED),
        "paused_battle_count": sum(1 for b in battles if b.status == Battle.Status.PAUSED),
    }

    moderation["detail"] = get_master_moderation_detail()

    monitor = get_master_monitor(battles=battles)
    governance = get_master_governance_detail()

    return {
        "monitor": monitor,
        "governance": governance,
        "arena": {
            "enrolled_count": profile_counts["enrolled"],
            "online_count": profile_counts["online"],
            "suspended_count": profile_counts["suspended"],
            "crown_holder": {
                "name": crown.author.name,
                "slug": crown.author.slug,
                "avatar_url": crown.author.display_avatar_url,
                "crown_until": crown.crown_until.isoformat(),
            } if crown else None,
        },
        "battles": battle_dicts,
        "combat": combat,
        "moderation": moderation,
        "voting": voting,
        "viewers": viewers,
        "economy": economy,
        "system": system,
    }


# ═════════════════════════════════════════════════════════════════════════════
# P04 — Live Battle Monitor + Combat Engine read models.
# Read-only and side-effect free: pure ORM reads, no round resolution, no
# artifact consumption, no event creation. Visibility: this data is served
# ONLY through the operator console gate; public endpoints are untouched.
# See docs/chef_battle/arena_master_console/P04_VISIBILITY_MATRIX.yaml.
# ═════════════════════════════════════════════════════════════════════════════

def _monitor_combat_detail(battle):
    """Rounds, current-round declared actions and hit totals for one ACTIVE
    battle. Same rows the battle room uses; nothing is resolved or mutated."""
    from .models import BattleCombatAction, BattleRound

    rounds = list(
        battle.combat_rounds.order_by("round_number").values(
            "round_number", "outcome", "challenger_hits", "opponent_hits",
            "attacker_id", "defender_id", "log_message",
        )
    )
    current_round = (rounds[-1]["round_number"] + 1) if rounds else 1
    declared = list(
        BattleCombatAction.objects.filter(battle=battle, round_number=current_round)
        .select_related("chef")
    )

    def _per_chef_stats(chef_id):
        attacks = [r for r in rounds if r["attacker_id"] == chef_id]
        defences = [r for r in rounds if r["defender_id"] == chef_id]
        hits = sum(1 for r in attacks if r["outcome"] in (BattleRound.Outcome.FULL_HIT, BattleRound.Outcome.PARTIAL_HIT))
        return {
            "hits": hits,
            "misses": len(attacks) - hits,
            "defended": sum(1 for r in defences if r["outcome"] == BattleRound.Outcome.BLOCKED),
        }

    challenger_stats = _per_chef_stats(battle.challenger_id)
    opponent_stats = _per_chef_stats(battle.opponent_id)

    entries = {e.author_id: len(e.surviving_ingredients) for e in battle.entries.all()}
    challenger_stats["surviving_ingredients"] = entries.get(battle.challenger_id)
    opponent_stats["surviving_ingredients"] = entries.get(battle.opponent_id)

    # Strip attacker_id/defender_id from the public rounds list (internal FKs)
    rounds_out = [
        {k: v for k, v in r.items() if k not in ("attacker_id", "defender_id")}
        for r in rounds
    ]

    return {
        "battle_id": battle.pk,
        "kind": "combat",
        "current_round": current_round,
        "rounds": rounds_out,
        "challenger_hits": rounds[-1]["challenger_hits"] if rounds else 0,
        "opponent_hits": rounds[-1]["opponent_hits"] if rounds else 0,
        "challenger_stats": challenger_stats,
        "opponent_stats": opponent_stats,
        # Operator-only view of hidden declarations (documented decision):
        # console users are all superusers behind the DG-01 gate.
        "declared_actions": [
            {
                "chef": a.chef.slug,
                "action_type": a.action_type,
                "moves_invested": a.moves_invested,
                "is_locked": a.is_locked,
            }
            for a in declared
        ],
    }


def _monitor_biathlon_detail(battle):
    """Biathlon shot state for one INGREDIENT_PENALTY battle. Uses the same
    rows as get_biathlon_state but returns only JSON-safe fields.

    T11, 2026-08-15: reads the loser's DECLARED menu (BattleIngredient) rather
    than the raw text lines of his submitted recipe, and there is no
    loser-locking step left to count - both chefs blocked two ingredients at
    declare_menu, before Stage 1. `blocked_ids` stays operator-only: the
    winner learns which are blocked by bouncing off them, not from this.
    """
    from .models import BattleIngredient, IngredientShot

    loser, winner = battle.loser, battle.winner
    declared = list(
        battle.battle_ingredients.filter(chef=loser).order_by("position")
    ) if loser else []
    shots = list(
        battle.ingredient_shots.filter(shooter=winner).values("target_ingredient_id", "bounced")
    ) if winner else []
    return {
        "battle_id": battle.pk,
        "kind": "biathlon",
        "loser": loser.name if loser else None,
        "winner": winner.name if winner else None,
        "ingredient_count": len(declared),
        # Operator-only: which of the loser's ingredients are his two blocks.
        "blocked_ids": [i.pk for i in declared if i.is_key],
        "eliminated_ids": [i.pk for i in declared if i.is_eliminated],
        "shots": shots,
        "blocks_placed": sum(1 for i in declared if i.is_key),
        "max_blocks": BattleIngredient.KEY_COUNT,
        "shots_fired": len(shots),
        "max_shots": IngredientShot.MAX_SHOTS,
        "deadline": battle.ingredient_penalty_deadline.isoformat() if battle.ingredient_penalty_deadline else None,
    }


def get_master_monitor(battles=None) -> dict:
    """P04 monitor section for the console state payload.

    counts definitions (documented in P04_VISIBILITY_MATRIX.yaml):
    - battles_active: Battle.ACTIVE_STATUSES
    - battles_paused: PAUSED (Emergency Stop)
    - battles_unresolved: DISPUTED
    - challenges_pending / challenges_accepted: BattleChallenge.Status
    """
    from .models import ChefArtifact

    if battles is None:
        statuses = set(Battle.ACTIVE_STATUSES) | {
            Battle.Status.INGREDIENT_PENALTY, Battle.Status.PAUSED,
        }
        battles = list(
            Battle.objects.select_related("challenger", "opponent", "winner", "loser")
            .filter(status__in=statuses)
            .order_by("end_time")
        )

    counts = {
        "battles_active": sum(1 for b in battles if b.status in Battle.ACTIVE_STATUSES),
        "battles_paused": sum(1 for b in battles if b.status == Battle.Status.PAUSED),
        "battles_unresolved": Battle.objects.filter(status=Battle.Status.DISPUTED).count(),
        "challenges_pending": BattleChallenge.objects.filter(
            status=BattleChallenge.Status.PENDING).count(),
        "challenges_accepted": BattleChallenge.objects.filter(
            status=BattleChallenge.Status.ACCEPTED).count(),
    }

    battle_ids = [b.pk for b in battles]
    events = list(
        BattleEvent.objects.filter(battle_id__in=battle_ids)
        # -id after -created_at, and it is not decoration. auto_now_add can
        # stamp several rows inside the same clock tick, so three events written
        # in one loop tie and Postgres is free to return them in any order -
        # which is why ArenaMasterMonitorTests.test_event_log_append_only_ordering
        # failed under --parallel and passed alone, for weeks, on nobody's card.
        # The id is the append order, and an append-only log ordered by anything
        # else is not append-only.
        .order_by("-created_at", "-id")
        .values("id", "battle_id", "event_type", "message", "created_at", "is_public")[:20]
    )
    for e in events:
        e["created_at"] = e["created_at"].isoformat()

    detail = []
    for b in battles:
        if b.status == Battle.Status.ACTIVE:
            detail.append(_monitor_combat_detail(b))
        elif b.status == Battle.Status.INGREDIENT_PENALTY:
            detail.append(_monitor_biathlon_detail(b))

    artifacts_in_use = [
        {
            "chef": ca.chef.slug,
            "artifact": ca.artifact.name,
            "effect_type": ca.artifact.effect_type,
            "effect_value": ca.artifact.effect_value,
            "status": ca.status,
        }
        for ca in ChefArtifact.objects.filter(
            chef_id__in={b.challenger_id for b in battles} | {b.opponent_id for b in battles},
            status=ChefArtifact.Status.RESERVED,
        ).select_related("chef", "artifact")
    ] if battles else []

    return {
        "counts": counts,
        "events": events,
        "detail": detail,
        "artifacts_in_use": artifacts_in_use,
    }


# ═════════════════════════════════════════════════════════════════════════════
# P05 — Moderation & safety read models (operator-only via console gate).
# Private moderation notes never appear in public endpoints.
# ═════════════════════════════════════════════════════════════════════════════

def get_master_moderation_detail() -> dict:
    """Cooking queue, pending content reports, live-stream safety state, and
    chef safety checklist for the console moderation panel (P05). Pure reads."""
    from .models import (
        BattleEntry, ContentReport, LiveBattleAgreement, LiveStreamSession,
    )

    queue_battles = list(
        Battle.objects.filter(status__in=[
            Battle.Status.INGREDIENT_PENALTY, Battle.Status.COOKING,
        ])
        .select_related("challenger", "opponent")
        .prefetch_related("entries__author")
        .order_by("updated_at")[:10]
    )

    # Prefetch ChefBattleProfile safety fields for all participating authors.
    all_author_ids = set()
    for b in queue_battles:
        for e in b.entries.all():
            all_author_ids.add(e.author_id)
    profiles_map = {
        p.author_id: p
        for p in ChefBattleProfile.objects.filter(author_id__in=all_author_ids)
        .only("author_id", "age_verified", "is_suspended", "fraud_flag")
    } if all_author_ids else {}

    cooking_queue = []
    for b in queue_battles:
        cooking_queue.append({
            "battle_id": b.pk,
            "theme": b.theme,
            "url": b.get_absolute_url(),
            "entries": [
                {
                    "entry_id": e.pk,
                    "author": e.author.name,
                    "author_slug": e.author.slug,
                    "moderation_status": e.moderation_status,
                    "moderation_status_display": e.get_moderation_status_display(),
                    "has_cooked_photo": bool(e.cooked_photo),
                    "real_photo_confirmed": e.real_photo_confirmed,
                    "is_late": e.is_late,
                    "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
                    # P05 safety checklist
                    "age_verified": profiles_map[e.author_id].age_verified if e.author_id in profiles_map else None,
                    "is_suspended": profiles_map[e.author_id].is_suspended if e.author_id in profiles_map else None,
                    "fraud_flag": profiles_map[e.author_id].fraud_flag if e.author_id in profiles_map else None,
                }
                for e in b.entries.all()
            ],
        })

    reports = [
        {
            "report_id": r.pk,
            "content_kind": r.content_kind,
            "object_id": r.object_id,
            "reason": r.reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in ContentReport.objects.filter(status=ContentReport.Status.PENDING)
        .order_by("-created_at")[:10]
    ]

    sessions = list(
        LiveStreamSession.objects.filter(
            status__in=[LiveStreamSession.Status.SCHEDULED, LiveStreamSession.Status.LIVE]
        )
        .select_related("chef", "battle", "broadcast")
        .annotate(authoritative_report_count=Count("broadcast__reports", distinct=True))[:10]
    )
    agreement_chef_ids = set(
        LiveBattleAgreement.objects.filter(
            chef_id__in=[s.chef_id for s in sessions]
        ).values_list("chef_id", flat=True)
    ) if sessions else set()

    streams = []
    for s in sessions:
        broadcast = getattr(s, "broadcast", None)
        streams.append({
            "session_id": s.pk,
            "chef": s.chef.name,
            "chef_slug": s.chef.slug,
            "battle_id": s.battle_id,
            "status": s.status,
            "provider": s.provider or "none",
            "checklist_confirmed": s.checklist_confirmed,
            "agreement_signed": s.chef_id in agreement_chef_ids,
            "broadcast": {
                "moderation_status": broadcast.moderation_status,
                "safety_delay_enabled": broadcast.safety_delay_enabled,
                "report_count": s.authoritative_report_count,
                "stopped_by_staff": broadcast.stopped_by_staff,
            } if broadcast else None,
        })

    # P05: chefs needing safety attention (suspended or fraud-flagged).
    flagged_chefs = [
        {
            "chef_name": p.author.name,
            "chef_slug": p.author.slug,
            "is_suspended": p.is_suspended,
            "suspended_at": p.suspended_at.isoformat() if p.suspended_at else None,
            "suspension_reason": p.suspension_reason,
            "fraud_flag": p.fraud_flag,
            "fraud_flag_note": p.fraud_flag_note,
            "age_verified": p.age_verified,
        }
        for p in ChefBattleProfile.objects.select_related("author")
        .filter(enrolled_at__isnull=False)
        .filter(models.Q(is_suspended=True) | models.Q(fraud_flag=True))
        .order_by("-suspended_at", "author__name")[:20]
    ]

    return {
        "cooking_queue": cooking_queue,
        "content_reports": reports,
        "streams": streams,
        "flagged_chefs": flagged_chefs,
    }


# ═════════════════════════════════════════════════════════════════════════════
# P06 — Voting integrity & audience analytics (read-only, DG-05).
# No second vote engine: totals come from get_battle_vote_counts, evidence
# from VoteIntegrityEvent (rejected attempts, never in totals), the
# suspicious flag stays a manual moderator flag — no fabricated risk score.
# Metric definitions: docs/chef_battle/arena_master_console/P06_METRIC_DEFINITIONS.yaml
# ═════════════════════════════════════════════════════════════════════════════

VOTE_SERIES_WINDOW_HOURS = 24  # series window; hours bucketed in UTC


def _voting_analytics_for_battle(b, now):
    """Full voting panel entry for one battle. Pure reads, bounded queries."""
    from django.db.models import Count as _Count, Sum as _Sum
    from django.db.models.functions import TruncHour
    from .models import BattleChatMessage, VoteIntegrityEvent, ViewerBattleGift

    counts = get_battle_vote_counts(b)
    challenger_votes = counts.get(b.challenger_id, 0)
    opponent_votes = counts.get(b.opponent_id, 0)
    total = challenger_votes + opponent_votes

    # Percentages with explicit zero-vote handling (null, never fake 50/50).
    if total:
        challenger_pct = round(challenger_votes * 100 / total, 1)
        opponent_pct = round(100 - challenger_pct, 1)
    else:
        challenger_pct = opponent_pct = None

    # Votes per hour, last VOTE_SERIES_WINDOW_HOURS, bucketed in UTC.
    import datetime as _dt
    window_start = now - timezone.timedelta(hours=VOTE_SERIES_WINDOW_HOURS)
    series = [
        {"hour_utc": row["hour"].isoformat(), "votes": row["n"]}
        for row in (
            b.votes.filter(created_at__gte=window_start)
            # tzinfo forced to UTC so buckets match the documented timezone
            # (default TruncHour would bucket in the site TZ, Europe/Dublin).
            .annotate(hour=TruncHour("created_at", tzinfo=_dt.timezone.utc))
            .values("hour").annotate(n=_Count("id")).order_by("hour")
        )
    ]

    # DG-05 enforcement evidence: rejected attempts grouped by gate code.
    integrity_qs = VoteIntegrityEvent.objects.filter(battle=b)
    rejected_by_gate = {
        row["gate_code"]: row["n"]
        for row in integrity_qs.values("gate_code").annotate(n=_Count("id"))
    }
    rejected_24h = integrity_qs.filter(created_at__gte=window_start).count()

    # Suspicious queue: manual moderator flags only (no automatic score).
    suspicious = list(
        b.votes.filter(is_suspicious=True)
        .values("id", "voted_for__slug", "created_at")[:10]
    )
    for s in suspicious:
        s["created_at"] = s["created_at"].isoformat()

    # Completion readiness (display only; auto-completion owns the transition).
    deadline_passed = bool(
        b.status == Battle.Status.VOTING
        and (b.voting_deadline or b.end_time)
        and (b.voting_deadline or b.end_time) <= now
    )
    is_tie = challenger_votes == opponent_votes and challenger_votes > 0

    # Community pulse: visible chat volume + support tokens per chef.
    chat_total = BattleChatMessage.objects.filter(battle=b, is_hidden=False).count()
    chat_last_hour = BattleChatMessage.objects.filter(
        battle=b, is_hidden=False,
        created_at__gte=now - timezone.timedelta(hours=1),
    ).count()
    support = {
        row["recipient__slug"]: {
            "gifts": row["n"], "tokens": row["tokens"] or 0,
        }
        for row in ViewerBattleGift.objects.filter(battle=b)
        .values("recipient__slug").annotate(n=_Count("id"), tokens=_Sum("tokens_spent"))
    }

    return {
        "battle_id": b.pk,
        "challenger_votes": challenger_votes,
        "opponent_votes": opponent_votes,
        "total_votes": total,
        "challenger_pct": challenger_pct,
        "opponent_pct": opponent_pct,
        "votes_per_hour": series,
        "series_window_hours": VOTE_SERIES_WINDOW_HOURS,
        "series_timezone": "UTC",
        "enforcement": {
            "one_vote_per_account": "unique(battle, voter)",
            "one_vote_per_device": "unique(battle, ip_hash, user_agent_hash)",
            "rejected_attempts_total": sum(rejected_by_gate.values()),
            "rejected_attempts_24h": rejected_24h,
            "rejected_by_gate": rejected_by_gate,
        },
        "suspicious_votes": len(suspicious) if len(suspicious) < 10
                            else b.votes.filter(is_suspicious=True).count(),
        "suspicious_queue": suspicious,
        "is_tie": is_tie,
        "completion": {
            "deadline_passed": deadline_passed,
            "has_votes": total > 0,
            "ready": deadline_passed,
            "blocked_by_tie": deadline_passed and is_tie,
        },
        "pulse": {
            "chat_messages_total": chat_total,
            "chat_messages_last_hour": chat_last_hour,
            "support_by_chef": support,
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# P07 — Economy, gifts, tokens and artifacts (READ-ONLY).
# Payment-adjacent: no operator write exists in this phase; wallet balances,
# Stripe paid-status and webhooks are never touched. Tokens are closed-loop
# virtual items — never described as cash, earnings or withdrawable funds.
# Ledger definitions: docs/chef_battle/arena_master_console/P07_LEDGER_DEFINITIONS.yaml
# ═════════════════════════════════════════════════════════════════════════════

ECONOMY_WINDOW_HOURS = 24


def get_master_economy_detail() -> dict:
    """Console economy panel detail. Pure reads over indexed columns."""
    from django.db.models import Count as _Count, Q as _Q, Sum as _Sum
    from .models import (
        APPRECIATION_GIFT_COST, AppreciationGift, Artifact, ChefArtifact,
        TokenOrder, TokenTransaction,
    )

    now = timezone.now()
    window_start = now - timezone.timedelta(hours=ECONOMY_WINDOW_HOURS)

    # Token flow per transaction type inside the window (credits are
    # positive, debits negative — exactly as stored in the ledger).
    flows_by_type = {
        row["tx_type"]: {"count": row["n"], "tokens": row["total"] or 0}
        for row in TokenTransaction.objects.filter(created_at__gte=window_start)
        .values("tx_type").annotate(n=_Count("id"), total=_Sum("amount"))
    }

    # Appreciation gifts delivered per recipient chef in the window.
    gifts_by_chef = [
        {
            "chef": row["recipient__slug"],
            "gifts": row["n"],
            "tokens": row["tokens"] or 0,
        }
        for row in AppreciationGift.objects.filter(sent_at__gte=window_start)
        .values("recipient__slug").annotate(n=_Count("id"), tokens=_Sum("tokens_spent"))
        .order_by("-tokens")[:10]
    ]

    # Static appreciation catalogue (source of truth constant) + live 24h counts.
    delivered_by_type = {
        row["gift_type"]: row["n"]
        for row in AppreciationGift.objects.filter(sent_at__gte=window_start)
        .values("gift_type").annotate(n=_Count("id"))
    }
    gift_catalogue = [
        {"type": str(k), "cost_tokens": v, "delivered_24h": delivered_by_type.get(k, 0)}
        for k, v in APPRECIATION_GIFT_COST.items()
    ]

    # Artifact inventory by lifecycle status and catalogue rarity distribution.
    artifact_inventory = {
        row["status"]: row["n"]
        for row in ChefArtifact.objects.values("status").annotate(n=_Count("id"))
    }
    rarity_distribution = {
        row["rarity"]: row["n"]
        for row in Artifact.objects.filter(is_active=True)
        .values("rarity").annotate(n=_Count("id"))
    }

    # Order review: counts by status; ids only for states needing attention.
    orders_by_status = {
        row["status"]: row["n"]
        for row in TokenOrder.objects.values("status").annotate(n=_Count("id"))
    }
    attention_orders = list(
        TokenOrder.objects.filter(
            status__in=[TokenOrder.Status.DISPUTED, TokenOrder.Status.REFUNDED]
        ).order_by("-created_at").values_list("id", flat=True)[:10]
    )

    return {
        "window_hours": ECONOMY_WINDOW_HOURS,
        "flows_by_type": flows_by_type,
        "gift_catalogue": gift_catalogue,
        "gifts_by_chef_24h": gifts_by_chef,
        "artifact_inventory": artifact_inventory,
        "rarity_distribution": rarity_distribution,
        "orders_by_status": orders_by_status,
        "attention_order_ids": attention_orders,
    }


# ═════════════════════════════════════════════════════════════════════════════
# P08 — Rewards governance read models (DG-06: review tool for all console
# operators; financial authority stays with the owner). CBR/LSR are
# discretionary platform rewards — never funds, earnings or balances.
# ═════════════════════════════════════════════════════════════════════════════

def get_master_governance_detail() -> dict:
    """Panel 7 read models: reward status matrix, payout queue, battle
    reports, ledger hash-chain state. Pure reads."""
    from django.db.models import Count as _Count
    from .models import BattleReport, LedgerEvent, PayoutRequest, RewardRecord

    rewards_matrix = {}
    for row in RewardRecord.objects.values("reward_type", "status").annotate(n=_Count("id")):
        rewards_matrix.setdefault(row["reward_type"], {})[row["status"]] = row["n"]

    recent_rewards = [
        {
            "id": r.pk, "type": r.reward_type, "status": r.status,
            "tokens": r.tokens_granted, "recipient": r.recipient.slug,
            "reason": r.reason[:80],
        }
        for r in RewardRecord.objects.select_related("recipient")
        .order_by("-created_at")[:8]
    ]

    payouts = [
        {
            "id": p.pk, "chef": p.chef.slug, "status": p.status,
            "tokens": p.amount_reward_tokens,
            "gross_eur": str(p.gross_payout_eur),
            "requested_at": p.requested_at.isoformat(),
            "actionable": p.status in (
                PayoutRequest.Status.PENDING, PayoutRequest.Status.UNDER_REVIEW,
            ),
        }
        for p in PayoutRequest.objects.select_related("chef")
        .order_by("-requested_at")[:10]
    ]

    reports = [
        {
            "id": r.pk, "battle_id": r.battle_id, "author": r.author.slug,
            "recommendation": r.recommendation, "status": r.status,
            "flags": r.flags, "created_at": r.created_at.isoformat(),
        }
        for r in BattleReport.objects.select_related("author")
        .order_by("-created_at")[:8]
    ]

    ledger = _ledger_chain_status(LedgerEvent)

    return {
        "rewards_matrix": rewards_matrix,
        "recent_rewards": recent_rewards,
        "payouts": payouts,
        "reports": reports,
        "ledger": ledger,
    }


# verify_chain() scans the whole LedgerEvent table; at a 20 s poll cadence
# that cost is wasted (P09 hardening). The scan re-runs only when the table
# changed (count differs — one cheap COUNT per poll) or the 60 s TTL lapsed,
# so tampering that ADDS/REMOVES rows is caught immediately and in-place
# row edits within <=60 s. The authoritative check remains verify_chain().
_LEDGER_CHAIN_CACHE = {"at": None, "count": None, "value": None}
LEDGER_CHAIN_CACHE_SECONDS = 60


def _ledger_chain_status(LedgerEvent):
    now = timezone.now()
    current_count = LedgerEvent.objects.count()
    cached = _LEDGER_CHAIN_CACHE
    if (
        cached["at"] is not None
        and cached["count"] == current_count
        and (now - cached["at"]).total_seconds() < LEDGER_CHAIN_CACHE_SECONDS
    ):
        return cached["value"]
    chain_ok, first_broken = LedgerEvent.verify_chain()
    value = {
        "total_events": current_count,
        "chain_intact": chain_ok,
        "first_broken_pk": first_broken,
        "checked_at": now.isoformat(),
    }
    _LEDGER_CHAIN_CACHE.update(at=now, count=current_count, value=value)
    return value


# ── Live Arena data panels (arena rebuild) ──────────────────────────────────

def _hidden_bot_slugs() -> set[str]:
    """Emulation-bot slugs to exclude from a PUBLIC arena panel, or an empty
    set. T-AUDIT, 2026-08-15: this file's own crown/gift/blast panels had no
    equivalent of the ring query's exclusion (chef_battle/views.py) - a bot
    switched off the floor could still hold the crown streak, appear as top
    supporter or in Recent Battle Gifts, and fire the "starting soon" blast.
    Same source of truth as views.py's own copy (chef_battle/emulation.py's
    EMU_CHEFS); a second thin function, never a second list."""
    from django.conf import settings as django_settings
    from .emulation import EMU_CHEFS

    if bool(getattr(django_settings, "ARENA_SHOW_EMULATION_BOTS", False)):
        return set()
    return {slug for slug, _name in EMU_CHEFS}


def get_recent_battle_gifts(battle=None, limit: int = 6) -> list:
    """Recent viewer battle gifts to competing chefs, newest first, for the
    arena 'Recent Battle Gifts' panel. Empty list when none (empty-safe)."""
    from .models import ViewerBattleGift
    qs = (
        ViewerBattleGift.objects
        .select_related("recipient", "artifact")
        .exclude(recipient__slug__in=_hidden_bot_slugs())
    )
    if battle is not None:
        qs = qs.filter(battle=battle)
    return [
        {
            "recipient": g.recipient.name,
            "recipient_slug": g.recipient.slug,
            "item": getattr(g.artifact, "name", "Artifact") if g.artifact_id else "Gift",
            "tokens": g.tokens_spent,
            "sent_at": g.sent_at.isoformat(),
        }
        for g in qs.order_by("-sent_at")[:limit]
    ]


def get_top_supporter(battle=None) -> dict | None:
    """Highest token spender on the active battle's viewer gifts, or None.

    Feeds the lower-broadcast 'Top Supporter' ticker (M15). Real aggregate only —
    no synthetic names. Empty-safe when there is no battle or no gifts.
    """
    if battle is None:
        return None
    from django.db.models import Sum
    from .models import RecipeAuthor, ViewerBattleGift

    row = (
        ViewerBattleGift.objects.filter(battle=battle, sender_id__isnull=False)
        .values("sender_id")
        .annotate(tokens=Sum("tokens_spent"))
        .order_by("-tokens", "sender_id")
        .first()
    )
    if not row:
        return None
    author = RecipeAuthor.objects.filter(user_id=row["sender_id"]).first()
    if author is not None:
        return {
            "name": author.name,
            "slug": author.slug,
            "tokens": int(row["tokens"] or 0),
        }
    return {
        "name": "Supporter",
        "slug": "",
        "tokens": int(row["tokens"] or 0),
    }


def get_crown_streak() -> int:
    """The current crown holder's win streak (0 if no active crown holder).
    Feeds the arena 'Crown Streak' metric."""
    from .models import ChefBattleProfile
    holder = (
        ChefBattleProfile.objects.filter(crown_until__gt=timezone.now())
        .exclude(author__slug__in=_hidden_bot_slugs())
        .exclude(author__slug__in=_uncompeting_slugs())
        .order_by("-crown_until")
        .first()
    )
    return holder.win_streak if holder else 0


def get_crown_ladder(limit: int = 8) -> list:
    """Today's crown ladder: chefs ranked by crowns won today (desc). Real data
    only — no invented standings. Feeds the arena 'Today's Crown Ladder' panel."""
    from django.db.models import Count
    from .models import Battle
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        Battle.objects.filter(crown_awarded=True, winner__isnull=False, end_time__gte=start)
        .exclude(winner__slug__in=_uncompeting_slugs())
        .values("winner__name", "winner__slug")
        .annotate(crowns=Count("id"))
        .order_by("-crowns", "winner__name")[:limit]
    )
    return [{"name": r["winner__name"], "slug": r["winner__slug"], "crowns": r["crowns"]} for r in rows]


def get_arena_metrics(battle=None) -> dict:
    """Top-bar live metrics for the active battle (arena rebuild): active
    viewers (distinct heartbeats in 180s), total public votes, battle-gift
    count. All zero when no active battle (empty-safe)."""
    if battle is None:
        return {"active_viewers": 0, "public_votes": 0, "battle_gifts": 0}
    from .models import BattleViewerPresence, ViewerBattleGift
    cutoff = timezone.now() - timezone.timedelta(seconds=180)
    viewers = (
        BattleViewerPresence.objects.filter(battle=battle, last_seen_at__gte=cutoff)
        .values("viewer_hash").distinct().count()
    )
    votes = sum(get_battle_vote_counts(battle).values())
    gifts = ViewerBattleGift.objects.filter(battle=battle).count()
    return {"active_viewers": viewers, "public_votes": votes, "battle_gifts": gifts}


# 7-step public phase rail for the arena rebuild. Maps a live Battle.status to
# one visible rung: Challenge -> Combat -> Biathlon -> Cooking -> Review ->
# Voting -> Crown. Keys/labels/steps are the front-end contract (Ember #159;
# Build Plan 3R6 uses the public label "Review" for step 5).
_ARENA_PHASE_RAIL = {
    "scheduled": ("challenge", "Challenge", 1),
    # Still on the opening rung: the arena is waiting for the second chef.
    "waiting": ("challenge", "Challenge", 1),
    # Terminal without cooking, but the arc is over and a winner (or nobody)
    # is on the stage — the rail rests on its last rung.
    "walkover": ("crown", "Crown", 7),
    "void": ("crown", "Crown", 7),
    "menu_locked": ("challenge", "Challenge", 1),
    "active": ("combat", "Combat", 2),
    "ingredient_penalty": ("biathlon", "Biathlon", 3),
    "awaiting_submissions": ("cooking", "Cooking", 4),
    "revealed": ("cooking", "Cooking", 4),
    "cooking": ("cooking", "Cooking", 4),
    "presentation": ("mod_review", "Review", 5),
    "disputed": ("mod_review", "Review", 5),
    "voting": ("voting", "Voting", 6),
    "completed": ("crown", "Crown", 7),
}

# Canonical ordered rungs for Build Plan 3R6 stepper (SSR + poll).
_ARENA_PHASE_RAIL_STEPS = (
    {"key": "challenge", "label": "Challenge", "step": 1},
    {"key": "combat", "label": "Combat", "step": 2},
    {"key": "biathlon", "label": "Biathlon", "step": 3},
    {"key": "cooking", "label": "Cooking", "step": 4},
    {"key": "mod_review", "label": "Review", "step": 5},
    {"key": "voting", "label": "Voting", "step": 6},
    {"key": "crown", "label": "Crown", "step": 7},
)


def get_arena_phase_rail() -> list[dict]:
    """Ordered 7-step public phase rail for the confrontation-era stepper."""
    return [dict(step) for step in _ARENA_PHASE_RAIL_STEPS]


def get_arena_phase(battle=None) -> dict | None:
    """Public phase-rail rung for the active battle (arena rebuild). Returns
    {key, label, step} where step is 1..7 across the visible arc, or None when
    no active battle. PAUSED resolves to the phase it was paused from so the
    rail keeps its place during an emergency stop; unknown statuses fall back
    to the opening Challenge rung."""
    if battle is None:
        return None
    status = battle.status
    if status == "paused" and battle.paused_from_status:
        status = battle.paused_from_status
    key, label, step = _ARENA_PHASE_RAIL.get(status, ("challenge", "Challenge", 1))
    return {"key": key, "label": label, "step": step}


def get_arena_deadline(battle=None) -> dict | None:
    """Public-safe countdown for the active battle (arena rebuild). Reuses the
    existing per-phase deadline logic (_battle_deadline) and returns
    {deadline_iso, seconds_remaining} where seconds_remaining is clamped at 0,
    or None when there is no active battle or no deadline set. No invented
    timer: this only surfaces the deadline the battle already carries."""
    if battle is None:
        return None
    deadline_iso, seconds_remaining = _battle_deadline(battle, timezone.now())
    if deadline_iso is None:
        return None
    # Explain what this particular countdown means, from the same per-phase
    # source _battle_deadline draws on (Ember #176). Keeps the wording honest to
    # the real deadline field in play rather than a generic "Live deadline".
    if battle.status == Battle.Status.VOTING:
        kind, label = "voting", "Public voting closes"
    elif battle.status in (
        Battle.Status.SCHEDULED, Battle.Status.MENU_LOCKED, Battle.Status.ACTIVE,
        Battle.Status.AWAITING_SUBMISSIONS, Battle.Status.COOKING,
    ):
        kind, label = "submission", "Dish submission closes"
    else:
        kind, label = "battle", "Battle closes"
    return {
        "deadline_iso": deadline_iso,
        "seconds_remaining": seconds_remaining,
        "kind": kind,
        "label": label,
    }


#: How long before a battle's start time the sitewide blast starts inviting
#: visitors to take their seats (owner spec: a five-minute readiness window).
BLAST_LEAD = timezone.timedelta(minutes=5)


def get_starting_battle_blast() -> dict | None:
    """The battle whose start ritual is counting down right now, for the
    sitewide blast: enough to invite visitors to take a seat and to show the
    real remaining time. None when nothing is about to start.

    Rides the existing 45s sitewide blast poll — no new channel. The countdown
    is the battle's own start_time, so a client showing it can never invent a
    timer of its own."""
    from .models import Battle
    now = timezone.now()
    hidden_bots = _hidden_bot_slugs()
    battle = (
        Battle.objects
        .filter(status=Battle.Status.SCHEDULED,
                start_time__gt=now, start_time__lte=now + BLAST_LEAD)
        .exclude(challenger__slug__in=hidden_bots)
        .exclude(opponent__slug__in=hidden_bots)
        .select_related("challenger", "opponent")
        .order_by("start_time")
        .first()
    )
    if battle is None:
        return None
    return {
        "battle_id": battle.pk,
        "battle_url": battle.get_absolute_url(),
        "theme": battle.theme,
        "challenger": battle.challenger.name,
        "opponent": battle.opponent.name,
        "deadline_iso": battle.start_time.isoformat(),
        "seconds_remaining": max(int((battle.start_time - now).total_seconds()), 0),
    }


# Owner 2026-07-24 mockup redesign: chef octagon cell counts from centre out
# (stage=1 separate; these eight are Culinary Master → Kitchen Porter).
# Uneven-per-side is allowed — no longer forced multiples of 8.
RANK_RING_SEGMENTS = (9, 10, 15, 20, 25, 30, 35, 40)


def get_vip_sponsors() -> list[dict]:
    """The sponsors entitled to a seat in the arena's VIP ring (ring 11).

    The arena shares NO code and NO grid with the Sponsors puzzle (Owner,
    2026-07-30): the only relationship between them is the product one, that a
    sponsor sits in the VIP ring. So this reads sponsor RECORDS and returns
    nothing about where they sit on the puzzle — the arena seats them itself,
    in its own boxes, in the order given here.

    Only publicly active cells qualify, which is the same gate the sponsors
    page itself uses (`is_public_active` — ACTIVE or the legacy SOLD). A cell
    that is merely paid, reserved or pending approval has not been published
    and must not appear anywhere; nor must a cell with no sponsor name, which
    would seat a blank in a ring the Owner sells.

    Order is by cell_number so the seating is stable between polls: a sponsor
    who does not move must not appear to hop around the ring every 30 seconds.
    """
    from sponsors.models import SponsorCell

    rows = (
        SponsorCell.objects
        .filter(
            status__in=[SponsorCell.Status.ACTIVE, SponsorCell.Status.SOLD],
        )
        .exclude(sponsor_name="")
        .order_by("cell_number")
    )

    sponsors = []
    for cell in rows:
        sponsors.append({
            "cell_number": cell.cell_number,
            "name": cell.sponsor_name,
            "logo": cell.sponsor_logo.url if cell.sponsor_logo else "",
            "url": cell.sponsor_url,
            "tagline": cell.sponsor_tagline,
        })
    return sponsors


# Spectators sit around the octagon (NOT in chef cells).
#
# OWNER, 2026-08-17: THE GALLERY IS A CLOSED RING. "рисуем везде где есть
# свободное место вокруг октагона... представь, что ты пришел смотреть бокс,
# и встаешь туда где есть хорошее свободное место."
#
# This supersedes the letter of ARENA_BATTLE_PLAN §2a (Owner 2026-07-29),
# which put author seats in TWO ROWS TOP AND TWO ROWS BOTTOM and left the
# left and right flanks empty. The MEANING of §2a is kept exactly: the
# balconies still stand behind the author rows, they are simply behind them
# all the way round now instead of only above and below.
#
# It also supersedes the 2026-07-24 rule that spectators are an OVAL rather
# than rings on the octagon's own grid. His word today is that the gallery is
# built from the same cells as the rank rings - "механика и форма".
#
# Two rows, not more: he was asked and chose to keep the capacity and give
# the rows room to breathe rather than add rows.
SPECTATOR_OVAL_ROWS = {"ring": 2}

# Counts per row, inner first. Sum = 114, UNCHANGED from the two-bank layout
# (28+29 top, 28+29 bottom) - the same seats, spread around the whole octagon
# instead of packed into two arcs. The outer row holds two more than the inner
# one because it is longer.
#
# Frozen deliberately (M04): ring/cell ids stay stable when packing constants
# tighten, so a seated viewer is never walked to another chair by a spacing
# change.
SPECTATOR_OVAL_COUNTS = {
    "ring": (56, 58),
}

# Legacy name kept as alias for imports; capacity now comes from oval packing.
SPECTATOR_RING_SEGMENTS = ()  # empty — polar spectator rings removed

_FIRST_SPECTATOR_RING = 100  # synthetic oval ring ids start at 100+


def _oval_seat_list(floor_outer_radius=220.0, seat_pitch=None):
    """Plan-space oval seats mirroring ArenaGeometry.ovalSeats (JS).

    Stable ids: ring = 100 + side_index*10 + row, cell = 0..n-1.
    Counts come from SPECTATOR_OVAL_COUNTS (not derived from pitch) so denser
    packing can tighten pitch/gap without reshuffling seat identities.
    """
    import math

    pitch = seat_pitch if seat_pitch is not None else max(11.0, floor_outer_radius * 0.045)
    gap = floor_outer_radius * 0.055
    # OWNER, 2026-08-17: one closed ring per row, all the way round the
    # octagon. The two arcs (top -0.75pi..-0.25pi, bottom 0.25pi..0.75pi) that
    # left the flanks empty are gone.
    #
    # A ring is CIRCULAR, not elliptical: the seats are drawn as segments of an
    # octagonal ring by the same generator that draws the rank rings, and an
    # ellipse would put a seat's centre off its own cell. The old rx/ry
    # stretch (1.08 / 0.92) went with the oval and goes with it.
    #
    # Ring ids stay in the same 100+ space and cells stay 0..n-1, so the
    # ArenaSeat contract keeps its shape. Nobody is walked to another chair by
    # this: production carries zero occupied seats.
    rows = SPECTATOR_OVAL_ROWS["ring"]
    counts = SPECTATOR_OVAL_COUNTS["ring"]
    out = []
    for row in range(rows):
        radius = floor_outer_radius + gap + (row + 0.5) * pitch * 1.02
        count = counts[row]
        ring_id = _FIRST_SPECTATOR_RING + row
        for cell in range(count):
            # Half-step offset so a seat sits in the MIDDLE of its cell rather
            # than on the seam between two.
            angle = (cell + 0.5) / count * math.tau
            out.append({
                "side": "ring",
                "row": row,
                "cell": cell,
                "ring": ring_id,
                "x": radius * math.cos(angle),
                "y": radius * math.sin(angle),
            })
    return out


def spectator_capacity() -> int:
    """Total interactive spectator seats on the oval stands."""
    return len(_oval_seat_list())


# AR5 / ARENA_BATTLE_PLAN §2a: behind the two author rows stand the balconies,
# where unauthorised visitors appear as bodiless spirits. A balcony stand is
# NOT a seat and must never become one: it carries no ring/cell identity, it is
# absent from seat_map(), nothing is ever written to ArenaSeat for it, and no
# name, avatar or profile is attached to it. A spirit is a count made visible,
# never a person made up.
# Owner, 2026-08-17: behind the author ring, and therefore a ring too. The
# counts are the two banks' totals merged (24+24 and 22+22), so the balconies
# hold exactly as many spirits as before, spread all the way round.
BALCONY_ROWS = {"ring": 2}
BALCONY_COUNTS = {"ring": (48, 44)}


def _balcony_stand_list(floor_outer_radius=220.0, seat_pitch=None):
    """Plan-space balcony positions, continuing outward from the author rows.

    Deliberately the same pitch, gap and ellipse as ``_oval_seat_list`` so the
    balconies read as the next rows of the same hall rather than a second,
    unrelated grid. They start where the author rows end: row indices continue
    from SPECTATOR_OVAL_ROWS, so a balcony can never overlap a seat.

    No ``ring`` key is returned, and that omission is the contract — there is no
    stable id to hold, because nothing may hold one.
    """
    import math

    pitch = seat_pitch if seat_pitch is not None else max(11.0, floor_outer_radius * 0.045)
    gap = floor_outer_radius * 0.055
    seat_rows = SPECTATOR_OVAL_ROWS["ring"]
    counts = BALCONY_COUNTS["ring"]
    out = []
    for row in range(BALCONY_ROWS["ring"]):
        # Row indices continue past the author rows, so a balcony can never
        # land on a seat however the packing constants move.
        depth = seat_rows + row
        radius = floor_outer_radius + gap + (depth + 0.5) * pitch * 1.02
        count = counts[row]
        for cell in range(count):
            angle = (cell + 0.5) / count * math.tau
            out.append({
                "side": "ring",
                "row": row,
                "index": cell,
                "x": radius * math.cos(angle),
                "y": radius * math.sin(angle),
            })
    return out


def balcony_capacity() -> int:
    """How many spirits the balconies can show at once. Derived, never declared."""
    return len(_balcony_stand_list())


def unauthorised_arena_viewers(now=None) -> int:
    """Live count of unauthorised visitors present in the arena lobby.

    Reuses the existing DG-04 heartbeat rather than inventing a second presence
    system: BattleViewerPresence rows with battle=NULL are the lobby surface,
    ``is_authenticated`` is already recorded on every upsert, and the 180 s
    window is the same one that decides whether anyone else is shown as online.

    Expect ZERO on production today, and that is the honest answer rather than a
    fault: both lobby heartbeats sit behind the visibility gate, which 404s an
    anonymous visitor before the poll runs. The number becomes real on the day
    the Owner opens the Arena, and nothing here has to change for that.
    """
    from .models import BattleViewerPresence

    now = now or timezone.now()
    cutoff = now - timezone.timedelta(seconds=ARENA_ONLINE_THRESHOLD_SECONDS)
    return (
        BattleViewerPresence.objects
        .filter(battle__isnull=True, is_authenticated=False, last_seen_at__gte=cutoff)
        .values("viewer_hash").distinct().count()
    )


# AA1, 2026-08-15: get_arena_geometry() is built from the static constants
# below (RANK_RING_SEGMENTS, ChefBattleProfile.Rank.choices, the oval/balcony
# layout constants) with no DB dependency, so a plain manually-bumped string
# is the right version marker - not a hash. Hashing the ~21KB dict on every
# poll would defeat the point of not sending it every poll; hashing source
# text would false-invalidate on an unrelated comment edit. Bump this by hand
# whenever a constant get_arena_geometry() derives from actually changes
# shape - the poll only resends the geometry payload when this differs from
# what the client last saw.
ARENA_GEOMETRY_VERSION = "1"


def rank_ring_order() -> list[tuple[str, str]]:
    """Ranks in RING order: position 1 is Culinary Master, position 8 is
    Kitchen Porter.

    The one place that knows which way round the octagon is numbered. It is
    the INVERSE of `_RANK_ORDER` at the top of this file, which scores the
    other way for the leaderboard (8 = Master) - the two are easy to confuse
    and a caller that picks the wrong one silently gets a chef's aura upside
    down, so both now have a name and a stated direction.
    """
    from .models import ChefBattleProfile
    return list(reversed(ChefBattleProfile.Rank.choices))


def rank_to_ring_index(rank: str) -> int:
    """Ring number for a rank: 1 = Culinary Master ... 8 = Kitchen Porter.

    0 for an unknown rank rather than an exception: this feeds a CSS
    attribute, and a chef with a rank the octagon does not know about should
    lose their aura, not take the page down with them.

    Added 2026-08-16 for the clan aura, which needs this mapping outside the
    arena payload - a clan's aura is its highest-ranked member's aura, and
    that is computed on a clan page where no arena geometry is built.
    """
    for i, (value, _label) in enumerate(rank_ring_order(), start=1):
        if value == rank:
            return i
    return 0


def get_arena_geometry() -> dict:
    """Declarative arena structure for the procedural (SVG/Canvas) renderer.

    Owner 2026-07-24: chef octagon uses RANK_RING_SEGMENTS; spectators are an
    oval around the floor (spectator_oval), not polar rings on the same grid.
    """
    rings = [{"index": 0, "kind": "stage", "key": "stage", "label": "Centre Stage", "segments": 1}]
    for i, (value, label) in enumerate(rank_ring_order(), start=1):
        rings.append({
            "index": i,
            "kind": "rank",
            "key": value,
            "label": label,
            "segments": RANK_RING_SEGMENTS[i - 1],
        })
    oval = _oval_seat_list()
    balconies = _balcony_stand_list()
    # Compact ring descriptors for oval rows (for seat maps / tests).
    oval_rings = {}
    for seat in oval:
        rid = seat["ring"]
        if rid not in oval_rings:
            oval_rings[rid] = {
                "index": rid,
                "kind": "spectator",
                "key": f"oval_{seat['side']}_{seat['row']}",
                "label": "Spectators",
                "segments": 0,
                "side": seat["side"],
                "row": seat["row"] + 1,
                "rows_total": SPECTATOR_OVAL_ROWS[seat["side"]],
            }
        oval_rings[rid]["segments"] += 1
    floor_r = 220.0
    return {
        "sides": 8,
        "rings": rings + [oval_rings[k] for k in sorted(oval_rings)],
        "spectator_oval": {
            "rows_by_side": dict(SPECTATOR_OVAL_ROWS),
            "counts_by_side": {k: list(v) for k, v in SPECTATOR_OVAL_COUNTS.items()},
            "floor_outer_radius": floor_r,
            "capacity": len(oval),
            "seats": oval,
        },
        # AR5: the balconies are geometry only. No ring ids, no cells, no seat
        # map entry — the renderer is told WHERE a spirit may stand, and the
        # live payload separately says HOW MANY are actually there.
        "balconies": {
            "rows_by_side": dict(BALCONY_ROWS),
            "counts_by_side": {k: list(v) for k, v in BALCONY_COUNTS.items()},
            "capacity": len(balconies),
            "stands": balconies,
        },
    }


# A recipe entered in a battle is frozen for the battle's duration: the biathlon
# targets its ingredient lines by row index, and its approved status is what makes
# it visible to voters, so editing it mid-battle would drift those indices and
# could 404 the dish out from under the audience. "Over" is a small terminal set;
# every other status still holds the recipe, INCLUDING ingredient_penalty (the live
# biathlon phase) and paused (an emergency stop that can resume) — neither of which
# is in ACTIVE_STATUSES, which is why this does not reuse it.
_BATTLE_CONCLUDED_STATUSES = frozenset([
    Battle.Status.COMPLETED,
    Battle.Status.CANCELLED,
    Battle.Status.VOID,
    Battle.Status.WALKOVER,
])


def active_battle_locking_recipe(recipe):
    """Return a still-running battle this recipe is entered in, or ``None``.

    Used to stop a recipe being edited while it is competing.
    """
    if recipe is None or getattr(recipe, "pk", None) is None:
        return None
    return (
        Battle.objects.filter(entries__recipe=recipe)
        .exclude(status__in=_BATTLE_CONCLUDED_STATUSES)
        .distinct()
        .first()
    )
