from __future__ import annotations

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
    """Return battle_profile and recent_battles for the public author page."""
    from django.db.models import Q
    battle_profile = ChefBattleProfile.objects.filter(author=author).first()
    recent_battles = list(
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(Q(challenger=author) | Q(opponent=author))
        .order_by("-created_at")[:6]
    )
    return {"battle_profile": battle_profile, "recent_battles": recent_battles}


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
    # excluded from the public "in progress" set) + paused (Emergency Stop).
    statuses = set(Battle.ACTIVE_STATUSES) | {
        Battle.Status.INGREDIENT_PENALTY,
        Battle.Status.PAUSED,
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
        "cooking_queue": Battle.objects.filter(status=Battle.Status.INGREDIENT_PENALTY).count(),
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
    voting = []
    for b in battles:
        counts = get_battle_vote_counts(b)
        challenger_votes = counts.get(b.challenger_id, 0)
        opponent_votes = counts.get(b.opponent_id, 0)
        voting.append({
            "battle_id": b.pk,
            "challenger_votes": challenger_votes,
            "opponent_votes": opponent_votes,
            "total_votes": challenger_votes + opponent_votes,
            "suspicious_votes": b.votes.filter(is_suspicious=True).count(),
            # DG-05: tie = exactly equal non-zero counts
            "is_tie": challenger_votes == opponent_votes and challenger_votes > 0,
        })

    # ── viewers section ──────────────────────────────────────────────
    # DG-04 assumed a per-page presence system; P02 discovery found none
    # exists (presence.PresenceEvent is an owner/admin login event log).
    # Per the non-fabrication rule this stays explicitly unavailable. The
    # only real presence signal today is the arena heartbeat below.
    viewers = {
        "available": False,
        "reason": "No per-page presence source exists; see P02_DATA_DICTIONARY.yaml.",
        "arena_online_chefs": profile_counts["online"],
        "window_seconds": ARENA_ONLINE_THRESHOLD_SECONDS,
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

    return {
        "monitor": monitor,
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
    from .models import BattleCombatAction

    rounds = list(
        battle.combat_rounds.order_by("round_number").values(
            "round_number", "outcome", "challenger_hits", "opponent_hits", "log_message",
        )
    )
    current_round = (rounds[-1]["round_number"] + 1) if rounds else 1
    declared = list(
        BattleCombatAction.objects.filter(battle=battle, round_number=current_round)
        .select_related("chef")
    )
    return {
        "battle_id": battle.pk,
        "kind": "combat",
        "current_round": current_round,
        "rounds": rounds,
        "challenger_hits": rounds[-1]["challenger_hits"] if rounds else 0,
        "opponent_hits": rounds[-1]["opponent_hits"] if rounds else 0,
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
    """Cooking queue, pending content reports, and live-stream safety state
    for the console moderation panel. Pure reads."""
    from .models import (
        BattleEntry, ContentReport, LiveBattleAgreement, LiveStreamSession,
    )

    queue_battles = list(
        Battle.objects.filter(status=Battle.Status.INGREDIENT_PENALTY)
        .select_related("challenger", "opponent")
        .prefetch_related("entries__author")
        .order_by("updated_at")[:10]
    )
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

    return {
        "cooking_queue": cooking_queue,
        "content_reports": reports,
        "streams": streams,
    }
