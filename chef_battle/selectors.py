from __future__ import annotations

from django.db import models
from django.db.models import Case, Count, IntegerField, QuerySet, When
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


def get_recent_completed_battles(limit: int = 10) -> QuerySet:
    return (
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(status=Battle.Status.COMPLETED)
        .order_by("-updated_at")[:limit]
    )


def get_top_profiles(limit: int = 10) -> QuerySet:
    return (
        ChefBattleProfile.objects.select_related("author")
        .filter(enrolled_at__isnull=False)
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
        .annotate(rank_order=_RANK_ORDER)
        .order_by("-rating", "-rank_order", "-wins", "author__name")[:limit]
    )


def get_hall_of_fame_battles(limit: int = 10) -> QuerySet:
    return (
        Battle.objects.select_related("challenger", "opponent", "winner", "loser")
        .filter(status=Battle.Status.COMPLETED, winner__isnull=False)
        .prefetch_related("entries__recipe", "votes")
        .order_by("updated_at")[:limit]
    )


def get_hall_of_fame_chefs(limit: int = 20) -> QuerySet:
    return (
        ChefBattleProfile.objects.select_related("author")
        .filter(wins__gt=0)
        .order_by("-wins", "-rating", "-crown_count", "author__name")[:limit]
    )


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
        BattleEntry, ContentReport, IngredientLock, IngredientShot,
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
                "locks_placed": b.ingredient_locks.count(),
                "shots_fired": b.ingredient_shots.count(),
                "max_locks": IngredientLock.MAX_LOCKS,
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
    """Biathlon lock/shot state for one INGREDIENT_PENALTY battle. Uses the
    same queries as get_biathlon_state but returns only JSON-safe fields."""
    from .models import IngredientLock, IngredientShot

    loser, winner = battle.loser, battle.winner
    loser_entry = (
        battle.entries.filter(author=loser).select_related("recipe").first()
        if loser else None
    )
    ingredients = []
    if loser_entry and loser_entry.recipe:
        ingredients = [
            line for line in loser_entry.recipe.ingredients.splitlines() if line.strip()
        ]
    locks = list(
        battle.ingredient_locks.filter(chef=loser).values_list("ingredient_index", flat=True)
    ) if loser else []
    shots = list(
        battle.ingredient_shots.filter(shooter=winner).values("target_index", "bounced")
    ) if winner else []
    return {
        "battle_id": battle.pk,
        "kind": "biathlon",
        "loser": loser.name if loser else None,
        "winner": winner.name if winner else None,
        "ingredient_count": len(ingredients),
        # Operator-only: lock indices are hidden from the winner publicly.
        "lock_indices": locks,
        "shots": shots,
        "locks_placed": len(locks),
        "shots_fired": len(shots),
        "max_locks": IngredientLock.MAX_LOCKS,
        "max_shots": IngredientShot.MAX_SHOTS,
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
        .order_by("-created_at")
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
def get_recent_battle_gifts(battle=None, limit: int = 6) -> list:
    """Recent viewer battle gifts to competing chefs, newest first, for the
    arena 'Recent Battle Gifts' panel. Empty list when none (empty-safe)."""
    from .models import ViewerBattleGift
    qs = ViewerBattleGift.objects.select_related("recipient", "artifact")
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


def get_crown_streak() -> int:
    """The current crown holder's win streak (0 if no active crown holder).
    Feeds the arena 'Crown Streak' metric."""
    from .models import ChefBattleProfile
    holder = (
        ChefBattleProfile.objects.filter(crown_until__gt=timezone.now())
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
# one visible rung: Challenge -> Combat -> Biathlon -> Cooking -> Mod Review ->
# Voting -> Crown. Keys/labels/steps are the front-end contract (Ember #159).
_ARENA_PHASE_RAIL = {
    "scheduled": ("challenge", "Challenge", 1),
    "menu_locked": ("challenge", "Challenge", 1),
    "active": ("combat", "Combat", 2),
    "ingredient_penalty": ("biathlon", "Biathlon", 3),
    "awaiting_submissions": ("cooking", "Cooking", 4),
    "revealed": ("cooking", "Cooking", 4),
    "cooking": ("cooking", "Cooking", 4),
    "presentation": ("mod_review", "Mod Review", 5),
    "disputed": ("mod_review", "Mod Review", 5),
    "voting": ("voting", "Voting", 6),
    "completed": ("crown", "Crown", 7),
}


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
