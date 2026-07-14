"""Anti-fraud pipeline for Chef Battles arena.

Each gate is a standalone function that returns (passed: bool, reason: str).
run_fraud_gates() runs all applicable gates and returns an aggregated result.

Design principles:
- Gates are independent and can be run selectively.
- No gate raises exceptions on normal inputs.
- All gates are logged but do not automatically suspend accounts.
- Suspension requires explicit staff action via admin or management command.
- ENABLE_AI_IMAGE_REVIEW_PROVIDER flag must be True before enabling AI gates.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Callable

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    gate: str
    passed: bool
    reason: str = ""


@dataclass
class FraudCheckResult:
    passed: bool
    gates: list[GateResult] = field(default_factory=list)
    failed_gates: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.passed:
            return "All fraud gates passed."
        return "Failed gates: " + ", ".join(self.failed_gates)


# ---------------------------------------------------------------------------
# Gate 1 — Account age
# ---------------------------------------------------------------------------

def gate_account_age(user, min_days: int = 1) -> GateResult:
    """Reject accounts created within the last N days."""
    if user is None:
        return GateResult("account_age", False, "No user supplied.")
    age = (timezone.now() - user.date_joined).days
    if age < min_days:
        return GateResult(
            "account_age", False,
            f"Account is {age}d old; minimum {min_days}d required."
        )
    return GateResult("account_age", True)


# ---------------------------------------------------------------------------
# Gate 2 — Vote rate limit (votes per IP per hour)
# ---------------------------------------------------------------------------

def gate_vote_rate_ip(ip_hash: str, battle_id: int, max_per_hour: int = 3) -> GateResult:
    """Reject if this IP hash already cast more than max_per_hour votes in this battle."""
    from .models import BattleVote
    cutoff = timezone.now() - timezone.timedelta(hours=1)
    count = BattleVote.objects.filter(
        battle_id=battle_id,
        ip_hash=ip_hash,
        created_at__gte=cutoff,
    ).count()
    if count >= max_per_hour:
        return GateResult(
            "vote_rate_ip", False,
            f"IP hash {ip_hash[:8]}… cast {count} votes in last hour (max {max_per_hour})."
        )
    return GateResult("vote_rate_ip", True)


# ---------------------------------------------------------------------------
# Gate 3 — Duplicate device fingerprint (same IP+UA voting in same battle)
# ---------------------------------------------------------------------------

def gate_duplicate_device(ip_hash: str, ua_hash: str, battle_id: int) -> GateResult:
    """Reject if this exact device fingerprint already voted in this battle."""
    from .models import BattleVote
    if not ip_hash or not ua_hash:
        return GateResult("duplicate_device", True, "Anonymous vote without full fingerprint — skipped.")
    exists = BattleVote.objects.filter(
        battle_id=battle_id,
        ip_hash=ip_hash,
        user_agent_hash=ua_hash,
        voter__isnull=True,
    ).exists()
    if exists:
        return GateResult("duplicate_device", False, "Device fingerprint already voted in this battle.")
    return GateResult("duplicate_device", True)


# ---------------------------------------------------------------------------
# Gate 4 — Self-vote
# ---------------------------------------------------------------------------

def gate_self_vote(voter_author, voted_for_author) -> GateResult:
    """Reject if the voter is voting for themselves."""
    if voter_author and voted_for_author and voter_author.pk == voted_for_author.pk:
        return GateResult("self_vote", False, "Chef cannot vote for themselves.")
    return GateResult("self_vote", True)


# ---------------------------------------------------------------------------
# Gate 5 — Participant vote
# ---------------------------------------------------------------------------

def gate_participant_vote(voter_author, battle) -> GateResult:
    """Reject if a battle participant tries to vote in their own battle."""
    if voter_author and battle and battle.author_is_participant(voter_author):
        return GateResult("participant_vote", False, "Battle participants cannot vote in their own battle.")
    return GateResult("participant_vote", True)


# ---------------------------------------------------------------------------
# Gate 6 — Suspended account
# ---------------------------------------------------------------------------

def gate_suspended_account(author) -> GateResult:
    """Reject if the chef's battle profile is suspended."""
    if author is None:
        return GateResult("suspended_account", True)
    profile = getattr(author, "battle_profile", None)
    if profile and profile.is_suspended:
        return GateResult(
            "suspended_account", False,
            f"Chef {author.slug} is suspended: {profile.suspension_reason or 'no reason given'}."
        )
    return GateResult("suspended_account", True)


# ---------------------------------------------------------------------------
# Gate 7 — Fraud-flagged account
# ---------------------------------------------------------------------------

def gate_fraud_flagged(author) -> GateResult:
    """Block actions from accounts with active fraud flags."""
    if author is None:
        return GateResult("fraud_flagged", True)
    profile = getattr(author, "battle_profile", None)
    if profile and profile.fraud_flag:
        return GateResult(
            "fraud_flagged", False,
            f"Chef {author.slug} has an active fraud flag."
        )
    return GateResult("fraud_flagged", True)


# ---------------------------------------------------------------------------
# Gate 8 — Token purchase velocity (too many purchases in 24h)
# ---------------------------------------------------------------------------

def gate_token_purchase_velocity(wallet, max_orders_per_day: int = 5) -> GateResult:
    """Reject if the wallet has too many completed orders in the last 24 hours."""
    from .models import TokenOrder
    cutoff = timezone.now() - timezone.timedelta(hours=24)
    count = TokenOrder.objects.filter(
        wallet=wallet,
        status=TokenOrder.Status.COMPLETED,
        created_at__gte=cutoff,
    ).count()
    if count >= max_orders_per_day:
        return GateResult(
            "token_purchase_velocity", False,
            f"Wallet made {count} purchases in last 24h (max {max_orders_per_day})."
        )
    return GateResult("token_purchase_velocity", True)


# ---------------------------------------------------------------------------
# Gate 9 — Gift velocity (too many gifts to same chef in 1h)
# ---------------------------------------------------------------------------

def gate_gift_velocity(sender_user, recipient_author, max_per_hour: int = 10) -> GateResult:
    """Reject if this sender has sent too many gifts to the same chef in the last hour."""
    from .models import AppreciationGift
    if sender_user is None:
        return GateResult("gift_velocity", True)
    cutoff = timezone.now() - timezone.timedelta(hours=1)
    count = AppreciationGift.objects.filter(
        sender=sender_user,
        recipient=recipient_author,
        sent_at__gte=cutoff,
    ).count()
    if count >= max_per_hour:
        return GateResult(
            "gift_velocity", False,
            f"Sender sent {count} gifts to this chef in last hour (max {max_per_hour})."
        )
    return GateResult("gift_velocity", True)


# ---------------------------------------------------------------------------
# Gate 10 — Challenge spam (too many challenges from same challenger in 24h)
# ---------------------------------------------------------------------------

def gate_challenge_spam(challenger, max_per_day: int = 3) -> GateResult:
    """Reject if challenger sent too many challenges in the last 24 hours."""
    from .models import BattleChallenge
    cutoff = timezone.now() - timezone.timedelta(hours=24)
    count = BattleChallenge.objects.filter(
        challenger=challenger,
        created_at__gte=cutoff,
    ).count()
    if count >= max_per_day:
        return GateResult(
            "challenge_spam", False,
            f"{challenger.slug} sent {count} challenges in last 24h (max {max_per_day})."
        )
    return GateResult("challenge_spam", True)


# ---------------------------------------------------------------------------
# Gate 11 — Repeat challenge cooldown (same pair)
# ---------------------------------------------------------------------------

def gate_repeat_challenge_cooldown(challenger, opponent, cooldown_hours: int = 24) -> GateResult:
    """Reject if this exact pair had a recent challenge."""
    from django.db.models import Q
    from .models import BattleChallenge
    cutoff = timezone.now() - timezone.timedelta(hours=cooldown_hours)
    exists = BattleChallenge.objects.filter(
        Q(challenger=challenger, opponent=opponent) | Q(challenger=opponent, opponent=challenger),
        created_at__gte=cutoff,
    ).exists()
    if exists:
        return GateResult(
            "repeat_challenge_cooldown", False,
            f"Pair {challenger.slug} / {opponent.slug} already challenged within {cooldown_hours}h."
        )
    return GateResult("repeat_challenge_cooldown", True)


# ---------------------------------------------------------------------------
# Gate 12 — Post-battle cooldown (any completed battle, both participants)
# ---------------------------------------------------------------------------

def gate_post_battle_cooldown(challenger, cooldown_hours: int = 24) -> GateResult:
    """Reject if the challenger completed any battle within the last cooldown_hours.

    Live rules 2026-07-10: both chefs enter a 24h cooldown after a completed
    battle before they may issue or accept a new challenge.
    """
    from django.db.models import Q
    from .models import Battle
    cutoff = timezone.now() - timezone.timedelta(hours=cooldown_hours)
    recent = Battle.objects.filter(
        Q(challenger=challenger) | Q(opponent=challenger),
        status=Battle.Status.COMPLETED,
        updated_at__gte=cutoff,
    ).exists()
    if recent:
        return GateResult(
            "post_battle_cooldown", False,
            f"{challenger.slug} completed a battle within the last {cooldown_hours}h. "
            "Please wait before issuing a new challenge.",
        )
    return GateResult("post_battle_cooldown", True)


# ---------------------------------------------------------------------------
# Gate 13 — DSA report threshold (too many reports against one account)
# ---------------------------------------------------------------------------

def gate_dsa_report_threshold(author, max_reports: int = 5) -> GateResult:
    """Warn if author has accumulated too many DSA reports (does not block — logs only)."""
    if author is None:
        return GateResult("dsa_report_threshold", True)
    profile = getattr(author, "battle_profile", None)
    count = profile.dsa_reported_count if profile else 0
    if count >= max_reports:
        logger.warning(
            "DSA threshold gate: %s has %d reports (threshold %d). Manual review recommended.",
            author.slug, count, max_reports,
        )
        return GateResult(
            "dsa_report_threshold", False,
            f"{author.slug} has {count} DSA reports. Manual review recommended."
        )
    return GateResult("dsa_report_threshold", True)


# ---------------------------------------------------------------------------
# Gate 13 — Withdrawal consent required for token purchase
# ---------------------------------------------------------------------------

def gate_withdrawal_consent(withdrawal_waived: bool) -> GateResult:
    """Require explicit EU right-of-withdrawal waiver before token purchase."""
    if not withdrawal_waived:
        return GateResult(
            "withdrawal_consent", False,
            "Buyer has not waived the EU right of withdrawal. Purchase blocked."
        )
    return GateResult("withdrawal_consent", True)


# ---------------------------------------------------------------------------
# Gate 13b — Age verification (18+)
# ---------------------------------------------------------------------------

def gate_age_verified(author) -> GateResult:
    """Require the chef profile to have age_verified=True before paid actions."""
    if author is None:
        return GateResult("age_verified", False, "No chef profile found.")
    profile = getattr(author, "_battle_profile_cache", None)
    if profile is None:
        from .models import ChefBattleProfile
        profile = ChefBattleProfile.objects.filter(author=author).first()
    if profile is None or not profile.age_verified:
        return GateResult(
            "age_verified", False,
            "You must confirm that you are 18 or older before using paid Arena features."
        )
    return GateResult("age_verified", True)


# ---------------------------------------------------------------------------
# Gate 14 — AI image review (stub — only active if ENABLE_AI_IMAGE_REVIEW_PROVIDER)
# ---------------------------------------------------------------------------

def gate_ai_image_review(image_field) -> GateResult:
    """AI-powered image content check. Only runs if ENABLE_AI_IMAGE_REVIEW_PROVIDER=True."""
    if not getattr(settings, "ENABLE_AI_IMAGE_REVIEW_PROVIDER", False):
        return GateResult("ai_image_review", True, "AI image review disabled (feature flag off).")
    # Real implementation goes here when provider is configured.
    logger.info("AI image review gate invoked but no provider implemented yet.")
    return GateResult("ai_image_review", True, "AI image review: no provider configured.")


# ---------------------------------------------------------------------------
# Gate 15 — Live video session safety (stub)
# ---------------------------------------------------------------------------

def gate_live_video_safety(session_id: str | None) -> GateResult:
    """Live video round safety gate. Only runs if ENABLE_LIVE_VIDEO=True."""
    if not getattr(settings, "ENABLE_LIVE_VIDEO", False):
        return GateResult("live_video_safety", True, "Live video disabled (feature flag off).")
    if not session_id:
        return GateResult("live_video_safety", False, "No live video session ID provided.")
    # Real implementation goes here when video provider is configured.
    return GateResult("live_video_safety", True)


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_fraud_gates(gates: list[tuple[Callable, tuple, dict]]) -> FraudCheckResult:
    """Run a list of (gate_fn, args, kwargs) tuples.

    Example:
        result = run_fraud_gates([
            (gate_account_age, (request.user,), {}),
            (gate_self_vote, (voter_author, voted_for_author), {}),
        ])
        if not result.passed:
            raise PermissionDenied(result.summary)
    """
    gate_results = []
    failed = []
    for gate_fn, args, kwargs in gates:
        try:
            r = gate_fn(*args, **kwargs)
        except Exception as exc:
            logger.exception("Fraud gate %s raised an exception", gate_fn.__name__)
            r = GateResult(gate_fn.__name__, False, f"Gate error: {exc}")
        gate_results.append(r)
        if not r.passed:
            failed.append(r.gate)
            logger.warning("Fraud gate FAILED: %s — %s", r.gate, r.reason)

    return FraudCheckResult(passed=not failed, gates=gate_results, failed_gates=failed)


# ---------------------------------------------------------------------------
# Faction gates (Phase 6) — battle-derived contribution guards
# ---------------------------------------------------------------------------

def gate_same_faction_battle(chef, opponent, faction_kind: str, season) -> GateResult:
    """Block faction points when both chefs share a faction on this axis.

    Same-faction battles awarding points would let a faction farm itself
    (collusion), so they earn zero on that axis.
    """
    from .models import FactionMembership
    c = (FactionMembership.objects
         .filter(chef=chef, faction_kind=faction_kind, season=season, left_at__isnull=True)
         .values_list("faction_id", flat=True).first())
    o = (FactionMembership.objects
         .filter(chef=opponent, faction_kind=faction_kind, season=season, left_at__isnull=True)
         .values_list("faction_id", flat=True).first())
    if c is not None and c == o:
        return GateResult("same_faction_battle", False, "Same-faction battle awards no faction points.")
    return GateResult("same_faction_battle", True)


def gate_faction_battle_cap(chef, opponent, season, battle, cap: int = 3) -> GateResult:
    """Block faction points once this pair has produced `cap` completed battles
    in the season — throttles win-trading against one opponent."""
    from django.db.models import Q
    from .models import Battle
    prior = (
        Battle.objects.filter(
            status=Battle.Status.COMPLETED,
            start_time__gte=season.starts_at,
            start_time__lte=season.ends_at,
        )
        .filter(Q(challenger=chef, opponent=opponent) | Q(challenger=opponent, opponent=chef))
        .exclude(pk=battle.pk)
        .count()
    )
    if prior >= cap:
        return GateResult("faction_battle_cap", False, f"Per-opponent faction cap ({cap}) reached this season.")
    return GateResult("faction_battle_cap", True)
