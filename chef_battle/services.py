from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from newsfeed.models import NewsFeedEntry

from .models import (
    APPRECIATION_GIFT_COST, Artifact, Battle, BattleChallenge, BattleCombatAction,
    BattleEntry, BattleEvent, BattleRound, ChefBattleProfile, IngredientLock,
    IngredientShot, AppreciationGift, ViewerBattleGift, TokenTransaction, TokenWallet,
)

logger = logging.getLogger(__name__)


def _notify_chef(sender_author, recipient_author, subject: str, body: str) -> None:
    """Send an in-site message and email notification. Silently skips if users are missing."""
    try:
        from messaging.models import Message
        from config.email_utils import build_absolute_url, sanitize_email_subject, send_template_mail
        sender = getattr(sender_author, "user", None)
        recipient = getattr(recipient_author, "user", None)
        if sender and recipient and sender != recipient:
            Message.objects.create(sender=sender, recipient=recipient, subject=subject, body=body)
            if recipient.email:
                send_template_mail(
                    subject=sanitize_email_subject(subject),
                    template="message_notification",
                    context={
                        "subject": subject,
                        "body": body,
                        "inbox_url": build_absolute_url(reverse("chef_battle:challenge_list")),
                    },
                    recipient_list=[recipient.email],
                    fail_silently=True,
                )
    except Exception:
        logger.exception("Failed to send battle notification")


RANK_THRESHOLDS = [
    (1800, ChefBattleProfile.Rank.CULINARY_MASTER),
    (1600, ChefBattleProfile.Rank.EXECUTIVE_CHEF),
    (1450, ChefBattleProfile.Rank.HEAD_CHEF),
    (1300, ChefBattleProfile.Rank.SOUS_CHEF),
    (1180, ChefBattleProfile.Rank.CHEF_DE_PARTIE),
    (1080, ChefBattleProfile.Rank.COMMIS_CHEF),
    (1000, ChefBattleProfile.Rank.PREP_COOK),
    (0, ChefBattleProfile.Rank.KITCHEN_PORTER),
]


def get_or_create_battle_profile(author):
    from django.conf import settings as _settings
    profile, created = ChefBattleProfile.objects.get_or_create(author=author)
    if created and getattr(author, "slug", None) == getattr(_settings, "OWNER_SLUG", None):
        profile.rank = ChefBattleProfile.Rank.HEAD_CHEF
        profile.michelin_stars = 3
        profile.is_hero = True
        profile.level = 5
        profile.rating = 9999
        profile.wins = 15
        profile.infinite_moves = True
        profile.save(update_fields=["rank", "michelin_stars", "is_hero", "level", "rating", "wins", "infinite_moves", "updated_at"])
    return profile


def rank_for_rating(rating: int) -> str:
    for threshold, rank in RANK_THRESHOLDS:
        if rating >= threshold:
            return rank
    return ChefBattleProfile.Rank.KITCHEN_PORTER


def hash_request_value(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_battle_event(
    *,
    event_type,
    message,
    battle=None,
    challenge=None,
    actor=None,
    target=None,
    is_public=True,
    publish_to_news=False,
):
    event = BattleEvent.objects.create(
        battle=battle,
        challenge=challenge,
        event_type=event_type,
        actor=actor,
        target=target,
        message=message,
        is_public=is_public,
    )

    flag_on = getattr(settings, "CHEF_BATTLE_ENABLED", False)
    if publish_to_news and flag_on:
        event_key = f"chef_battle:{event.pk}"
        try:
            url = battle.get_absolute_url() if battle else reverse("chef_battle:challenge_list")
        except NoReverseMatch:
            url = ""
        NewsFeedEntry.objects.create(
            entry_type=NewsFeedEntry.EntryType.SITE_UPDATE,
            title=message,
            url=url,
            is_auto=True,
            is_public=is_public,
            event_key=event_key,
        )

    return event


def check_level_matchup(challenger, opponent) -> str | None:
    """Return an error string if level gap is too large, else None."""
    c_profile = get_or_create_battle_profile(challenger)
    o_profile = get_or_create_battle_profile(opponent)
    # Hero counts as level 5 for matchup purposes
    c_level = 5 if c_profile.is_hero else c_profile.level
    o_level = 5 if o_profile.is_hero else o_profile.level
    if abs(c_level - o_level) > 1:
        return (
            f"Level mismatch: {challenger.name} is Level {c_level}, "
            f"{opponent.name} is Level {o_level}. "
            "Maximum allowed difference is 1 level."
        )
    return None


def accept_challenge(challenge: BattleChallenge) -> Battle:
    now = timezone.now()
    start_time = challenge.proposed_start_time or now
    status = Battle.Status.SCHEDULED if start_time > now else Battle.Status.MENU_LOCKED
    submission_deadline = start_time + timezone.timedelta(days=5)
    voting_deadline = submission_deadline + timezone.timedelta(days=2)
    end_time = voting_deadline

    with transaction.atomic():
        challenge.status = BattleChallenge.Status.ACCEPTED
        challenge.accepted_at = now
        challenge.save(update_fields=["status", "accepted_at"])

        battle = Battle.objects.create(
            challenge=challenge,
            challenger=challenge.challenger,
            opponent=challenge.opponent,
            theme=challenge.theme,
            battle_type=challenge.battle_type,
            status=status,
            start_time=start_time,
            submission_deadline=submission_deadline,
            voting_deadline=voting_deadline,
            end_time=end_time,
        )

        create_battle_event(
            event_type=BattleEvent.EventType.CHALLENGE_ACCEPTED,
            challenge=challenge,
            battle=battle,
            actor=challenge.opponent,
            target=challenge.challenger,
            message=f"{challenge.opponent.name} accepted {challenge.challenger.name}'s Chef Battle: {challenge.theme}.",
            publish_to_news=True,
        )
        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_STARTED,
            battle=battle,
            actor=challenge.challenger,
            target=challenge.opponent,
            message=f"Chef Battle started: {challenge.challenger.name} vs {challenge.opponent.name} - {challenge.theme}.",
            publish_to_news=True,
        )

    try:
        battle_url = battle.get_absolute_url()
    except NoReverseMatch:
        battle_url = ""
    _notify_chef(
        challenge.opponent, challenge.challenger,
        subject=f"Your challenge was accepted: {challenge.theme}",
        body=(
            f"{challenge.opponent.name} accepted your Chef Battle challenge.\n\n"
            f"Theme: {challenge.theme}\n"
            f"Battle room: {settings.SITE_SCHEME}://{settings.SITE_DOMAIN}{battle_url}"
        ),
    )
    return battle


def refuse_challenge(challenge: BattleChallenge) -> None:
    with transaction.atomic():
        challenge.status = BattleChallenge.Status.REFUSED
        challenge.refused_at = timezone.now()
        challenge.save(update_fields=["status", "refused_at"])

        profile = get_or_create_battle_profile(challenge.opponent)
        profile.refused_battles += 1
        profile.reputation -= 5
        profile.save(update_fields=["refused_battles", "reputation", "updated_at"])

        create_battle_event(
            event_type=BattleEvent.EventType.CHALLENGE_REFUSED,
            challenge=challenge,
            actor=challenge.opponent,
            target=challenge.challenger,
            message=f"{challenge.opponent.name} refused a Chef Battle challenge from {challenge.challenger.name}: {challenge.theme}.",
            publish_to_news=True,
        )

    _notify_chef(
        challenge.opponent, challenge.challenger,
        subject=f"Your Chef Battle challenge was refused: {challenge.theme}",
        body=(
            f"{challenge.opponent.name} has declined your Chef Battle challenge.\n\n"
            f"Theme: {challenge.theme}\n\n"
            f"Challenge another chef and keep fighting for your rank."
        ),
    )


def expire_stale_challenges() -> int:
    """Mark pending challenges past their deadline as EXPIRED. Returns count."""
    now = timezone.now()
    stale = BattleChallenge.objects.filter(
        status=BattleChallenge.Status.PENDING,
        expires_at__lte=now,
    )
    count = 0
    for challenge in stale:
        challenge.status = BattleChallenge.Status.EXPIRED
        challenge.save(update_fields=["status"])
        create_battle_event(
            event_type=BattleEvent.EventType.CHALLENGE_EXPIRED,
            challenge=challenge,
            actor=challenge.challenger,
            target=challenge.opponent,
            message=(
                f"Challenge expired: {challenge.opponent.name} did not respond "
                f"to {challenge.challenger.name}'s battle on '{challenge.theme}'."
            ),
            is_public=False,
        )
        count += 1
    return count


def handle_no_show_battles() -> int:
    """
    Process battles past submission_deadline where one or both chefs
    have not submitted an entry.

    - Both missing → CANCELLED, result_reason records double no-show.
    - One missing → the submitting chef wins by forfeit; loser takes a
      reputation hit, no rating change (forfeit does not affect Elo).
    """
    now = timezone.now()
    battles = Battle.objects.filter(
        status__in=[Battle.Status.MENU_LOCKED, Battle.Status.ACTIVE, Battle.Status.AWAITING_SUBMISSIONS],
        submission_deadline__lte=now,
    ).select_related("challenger", "opponent")

    count = 0
    for battle in battles:
        entries = list(battle.entries.values_list("author_id", flat=True))
        challenger_submitted = battle.challenger_id in entries
        opponent_submitted = battle.opponent_id in entries

        with transaction.atomic():
            if not challenger_submitted and not opponent_submitted:
                battle.status = Battle.Status.CANCELLED
                battle.result_reason = "Double no-show: neither chef submitted an entry."
                battle.save(update_fields=["status", "result_reason", "updated_at"])
                create_battle_event(
                    event_type=BattleEvent.EventType.BATTLE_FINISHED,
                    battle=battle,
                    message=(
                        f"Battle cancelled: neither {battle.challenger.name} nor "
                        f"{battle.opponent.name} submitted an entry for '{battle.theme}'."
                    ),
                    is_public=True,
                    publish_to_news=True,
                )

            elif not challenger_submitted:
                _award_forfeit_win(battle, winner=battle.opponent, loser=battle.challenger)

            elif not opponent_submitted:
                _award_forfeit_win(battle, winner=battle.challenger, loser=battle.opponent)

            else:
                # Both submitted but deadline passed without voting closing —
                # advance to voting so the normal result path can run.
                battle.entries.filter(is_revealed=False).update(is_revealed=True)
                battle.status = Battle.Status.VOTING
                battle.save(update_fields=["status", "updated_at"])

        count += 1
    return count


def _award_forfeit_win(battle: Battle, *, winner, loser) -> None:
    loser_profile = get_or_create_battle_profile(loser)
    loser_profile.losses += 1
    loser_profile.win_streak = 0
    loser_profile.reputation = max(-1000, loser_profile.reputation - 10)
    loser_profile.rank = rank_for_rating(loser_profile.rating)
    loser_profile.save(update_fields=["losses", "win_streak", "reputation", "rank", "updated_at"])

    winner_profile = get_or_create_battle_profile(winner)
    winner_profile.wins += 1
    winner_profile.win_streak += 1
    winner_profile.rank = rank_for_rating(winner_profile.rating)
    winner_profile.recalculate_level()
    winner_profile.save(update_fields=["wins", "win_streak", "rank", "level", "is_hero", "updated_at"])

    battle.winner = winner
    battle.loser = loser
    battle.status = Battle.Status.COMPLETED
    battle.result_reason = f"Forfeit: {loser.name} did not submit an entry."
    battle.save(update_fields=["winner", "loser", "status", "result_reason", "updated_at"])

    create_battle_event(
        event_type=BattleEvent.EventType.BATTLE_FINISHED,
        battle=battle,
        actor=winner,
        target=loser,
        message=(
            f"{winner.name} wins by forfeit in Chef Battle '{battle.theme}': "
            f"{loser.name} did not submit an entry."
        ),
        is_public=True,
        publish_to_news=True,
    )


def submit_battle_entry(*, battle: Battle, author, recipe=None, article=None, battle_statement: str = "") -> BattleEntry:
    """Create a BattleEntry, flagging it as late if the deadline has passed."""
    now = timezone.now()
    is_late = now > battle.submission_deadline
    entry = BattleEntry.objects.create(
        battle=battle,
        author=author,
        recipe=recipe,
        article=article,
        battle_statement=battle_statement,
        is_late=is_late,
    )
    return entry


def reveal_entries_if_ready(battle: Battle) -> None:
    entries = list(battle.entries.all())
    both_submitted = len(entries) == 2
    deadline_passed = timezone.now() >= battle.submission_deadline

    if battle.status == Battle.Status.MENU_LOCKED:
        # Both chefs submitted their recipes — combat can begin
        if both_submitted or deadline_passed:
            battle.entries.filter(is_revealed=False).update(is_revealed=True)
            battle.status = Battle.Status.ACTIVE
            battle.save(update_fields=["status", "updated_at"])
    elif battle.status == Battle.Status.ACTIVE:
        # Both chefs submitted combat actions — move to voting
        if both_submitted or deadline_passed:
            battle.entries.filter(is_revealed=False).update(is_revealed=True)
            battle.status = Battle.Status.VOTING
            battle.save(update_fields=["status", "updated_at"])


def calculate_battle_result(battle: Battle) -> Battle:
    if battle.status == Battle.Status.COMPLETED:
        return battle

    vote_counts = {
        item["voted_for"]: item["total"]
        for item in battle.votes.values("voted_for").annotate(total=Count("id"))
    }
    challenger_votes = vote_counts.get(battle.challenger_id, 0)
    opponent_votes = vote_counts.get(battle.opponent_id, 0)

    if challenger_votes == opponent_votes:
        battle.result_reason = "Draw by public vote"
        battle.status = Battle.Status.COMPLETED
        battle.save(update_fields=["status", "result_reason", "updated_at"])
        return battle

    winner = battle.challenger if challenger_votes > opponent_votes else battle.opponent
    loser = battle.opponent if winner.pk == battle.challenger_id else battle.challenger

    with transaction.atomic():
        winner_profile = get_or_create_battle_profile(winner)
        loser_profile = get_or_create_battle_profile(loser)

        old_winner_rank = winner_profile.rank
        old_loser_rank = loser_profile.rank

        rating_delta = 25
        winner_profile.wins += 1
        winner_profile.win_streak += 1
        if winner_profile.win_streak > winner_profile.best_win_streak:
            winner_profile.best_win_streak = winner_profile.win_streak
        winner_profile.rating += rating_delta
        winner_profile.reputation += 15
        winner_profile.battle_moves += MOVES_BATTLE_WIN + MOVES_BATTLE_PARTICIPATION
        winner_profile.seasonal_score += 10
        winner_profile.crown_count += 1
        winner_profile.crown_until = timezone.now() + timezone.timedelta(hours=24)
        winner_profile.rank = rank_for_rating(winner_profile.rating)
        level_changed = winner_profile.recalculate_level()
        winner_profile.save()

        loser_profile.losses += 1
        loser_profile.win_streak = 0
        loser_profile.rating = max(0, loser_profile.rating - 15)
        loser_profile.reputation = max(-1000, loser_profile.reputation - 3)
        loser_profile.battle_moves += MOVES_BATTLE_PARTICIPATION
        loser_profile.rank = rank_for_rating(loser_profile.rating)
        loser_profile.save()

        from .models import BattleMoveTransaction
        BattleMoveTransaction.objects.bulk_create([
            BattleMoveTransaction(chef=winner, amount=MOVES_BATTLE_WIN, reason="Battle win"),
            BattleMoveTransaction(chef=winner, amount=MOVES_BATTLE_PARTICIPATION, reason="Battle participation"),
            BattleMoveTransaction(chef=loser, amount=MOVES_BATTLE_PARTICIPATION, reason="Battle participation"),
        ])

        battle.winner = winner
        battle.loser = loser
        battle.status = Battle.Status.COMPLETED
        battle.crown_awarded = True
        battle.result_reason = f"Public vote: {challenger_votes}-{opponent_votes}"
        battle.save(update_fields=["winner", "loser", "status", "crown_awarded", "result_reason", "updated_at"])

        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_COMPLETED,
            battle=battle,
            actor=winner,
            target=loser,
            message=f"{winner.name} defeated {loser.name} in Chef Battle: {battle.theme}.",
            publish_to_news=True,
        )
        create_battle_event(
            event_type=BattleEvent.EventType.CROWN_AWARDED,
            battle=battle,
            actor=winner,
            message=f"{winner.name} holds the Crown after winning: {battle.theme}.",
            publish_to_news=True,
        )
        if level_changed:
            create_battle_event(
                event_type=BattleEvent.EventType.RANK_PROMOTED,
                battle=battle,
                actor=winner,
                message=f"{winner.name} reached {winner_profile.display_level}!",
                publish_to_news=True,
            )
        elif winner_profile.rank != old_winner_rank:
            create_battle_event(
                event_type=BattleEvent.EventType.RANK_PROMOTED,
                battle=battle,
                actor=winner,
                message=f"{winner.name} reached {winner_profile.get_rank_display()} rank.",
                publish_to_news=True,
            )
        if loser_profile.rank != old_loser_rank:
            create_battle_event(
                event_type=BattleEvent.EventType.RANK_PROMOTED,
                battle=battle,
                actor=loser,
                message=f"{loser.name} dropped to {loser_profile.get_rank_display()} rank.",
                publish_to_news=True,
            )

    try:
        battle_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}{battle.get_absolute_url()}"
    except (NoReverseMatch, AttributeError):
        battle_url = ""
    _notify_chef(
        loser, winner,
        subject=f"You won the Chef Battle: {battle.theme}",
        body=(
            f"Congratulations! You defeated {loser.name} in Chef Battle: {battle.theme}.\n\n"
            f"Result: {battle.result_reason}\n"
            f"You now hold the Crown for 24 hours.\n\n"
            f"Battle room: {battle_url}"
        ),
    )
    _notify_chef(
        winner, loser,
        subject=f"Chef Battle result: {battle.theme}",
        body=(
            f"{winner.name} defeated you in Chef Battle: {battle.theme}.\n\n"
            f"Result: {battle.result_reason}\n\n"
            f"Battle room: {battle_url}"
        ),
    )
    return battle


# ── Phase 3: Battle moves economy ────────────────────────────────────────────

MOVES_RECIPE_APPROVED = 2
MOVES_ARTICLE_APPROVED = 2
MOVES_BATTLE_WIN = 5
MOVES_BATTLE_PARTICIPATION = 1
MOVES_MIN_TO_CHALLENGE = 10

# Anti-farming caps: max moves earned from content approval per day/week
MOVES_CONTENT_DAILY_CAP = 15
MOVES_CONTENT_WEEKLY_CAP = 50
_CONTENT_REASONS = {"Recipe approved", "Article approved"}


def _content_moves_earned(author, period_start) -> int:
    """Sum of move amounts from content approval since period_start."""
    from .models import BattleMoveTransaction
    return (
        BattleMoveTransaction.objects.filter(
            chef=author,
            reason__in=_CONTENT_REASONS,
            created_at__gte=period_start,
        )
        .values_list("amount", flat=True)
        .__class__(
            BattleMoveTransaction.objects.filter(
                chef=author,
                reason__in=_CONTENT_REASONS,
                created_at__gte=period_start,
            )
        )
    )


def _content_moves_total(author, period_start) -> int:
    from django.db.models import Sum
    from .models import BattleMoveTransaction
    result = BattleMoveTransaction.objects.filter(
        chef=author,
        reason__in=_CONTENT_REASONS,
        created_at__gte=period_start,
    ).aggregate(total=Sum("amount"))["total"]
    return result or 0


def award_moves(author, amount: int, reason: str) -> None:
    """Credit battle moves to a chef and update their profile.

    Content-approval reasons are capped (daily + weekly anti-farming).
    Silently no-ops on any error.
    """
    if amount == 0:
        return
    try:
        from .models import BattleMoveTransaction
        now = timezone.now()

        if reason in _CONTENT_REASONS:
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timezone.timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_earned = _content_moves_total(author, day_start)
            weekly_earned = _content_moves_total(author, week_start)
            daily_remaining = max(0, MOVES_CONTENT_DAILY_CAP - daily_earned)
            weekly_remaining = max(0, MOVES_CONTENT_WEEKLY_CAP - weekly_earned)
            amount = min(amount, daily_remaining, weekly_remaining)
            if amount <= 0:
                return

        profile = get_or_create_battle_profile(author)
        profile.battle_moves = max(0, profile.battle_moves + amount)
        profile.save(update_fields=["battle_moves", "updated_at"])
        BattleMoveTransaction.objects.create(chef=author, amount=amount, reason=reason)
    except Exception:
        logger.exception("Failed to award moves to author pk=%s", getattr(author, "pk", "?"))


# ── Phase 4: Combat mechanics ─────────────────────────────────────────────────

COMBAT_MOVES_MIN = 1
COMBAT_MOVES_MAX = 10
COMBAT_HITS_TO_WIN = 3  # not used for victory — just for display drama


def get_current_round(battle: Battle) -> int:
    """Return the next round number (1-based)."""
    last = battle.combat_rounds.order_by("-round_number").first()
    return (last.round_number + 1) if last else 1


def submit_combat_action(
    battle: Battle,
    chef,
    action_type: str,
    moves_invested: int,
) -> BattleCombatAction:
    """
    Chef declares their combat action for the current round.
    Moves are NOT deducted yet — only on resolve.
    Raises ValueError on invalid input.
    """
    if battle.status not in (Battle.Status.ACTIVE, Battle.Status.AWAITING_SUBMISSIONS):
        raise ValueError("Combat actions are only allowed during an active battle.")

    if not battle.author_is_participant(chef):
        raise ValueError("You are not a participant in this battle.")

    if action_type not in (BattleCombatAction.ActionType.ATTACK, BattleCombatAction.ActionType.DEFEND):
        raise ValueError("Invalid action type.")

    moves_invested = max(COMBAT_MOVES_MIN, min(COMBAT_MOVES_MAX, moves_invested))

    profile = get_or_create_battle_profile(chef)
    if profile.battle_moves < moves_invested:
        raise ValueError(f"Not enough battle moves. You have {profile.battle_moves}.")

    round_number = get_current_round(battle)

    action, created = BattleCombatAction.objects.get_or_create(
        battle=battle,
        chef=chef,
        round_number=round_number,
        defaults={"action_type": action_type, "moves_invested": moves_invested},
    )
    if not created:
        if action.is_locked:
            raise ValueError("Your action for this round is already locked.")
        action.action_type = action_type
        action.moves_invested = moves_invested
        action.save(update_fields=["action_type", "moves_invested", "updated_at"])

    # Auto-resolve if both chefs have submitted
    other_chef = battle.opponent_for(chef)
    if other_chef:
        other_action = BattleCombatAction.objects.filter(
            battle=battle, chef=other_chef, round_number=round_number
        ).first()
        if other_action:
            _resolve_round(battle, round_number)

    return action


def _resolve_round(battle: Battle, round_number: int) -> BattleRound | None:
    """Resolve a round when both chefs have submitted actions. Deducts moves."""
    challenger_action = BattleCombatAction.objects.filter(
        battle=battle, chef=battle.challenger, round_number=round_number
    ).first()
    opponent_action = BattleCombatAction.objects.filter(
        battle=battle, chef=battle.opponent, round_number=round_number
    ).first()

    if not challenger_action or not opponent_action:
        return None

    # Determine attacker/defender for this round log
    # Both can attack simultaneously — resolve each direction
    # For simplicity: challenger attacks opponent, opponent defends (and vice versa)
    # Outcome based on net power comparison

    c_power = challenger_action.moves_invested
    o_power = opponent_action.moves_invested

    # Challenger attacks → opponent defends (and vice versa simultaneously)
    # We resolve as: whoever invested more in attack vs other's defence
    c_is_attacker = challenger_action.action_type == BattleCombatAction.ActionType.ATTACK
    o_is_attacker = opponent_action.action_type == BattleCombatAction.ActionType.ATTACK

    # Get previous round totals
    prev = battle.combat_rounds.filter(round_number=round_number - 1).first()
    prev_c_hits = prev.challenger_hits if prev else 0
    prev_o_hits = prev.opponent_hits if prev else 0

    c_hit_landed = False
    o_hit_landed = False

    if c_is_attacker and not o_is_attacker:
        # Challenger attacks, opponent defends
        if c_power > o_power * 1.5:
            outcome = BattleRound.Outcome.FULL_HIT
            c_hit_landed = True
        elif c_power > o_power:
            outcome = BattleRound.Outcome.PARTIAL_HIT
            c_hit_landed = True
        else:
            outcome = BattleRound.Outcome.BLOCKED
        attacker, defender = battle.challenger, battle.opponent
        attack_power, defence_power = c_power, o_power
    elif o_is_attacker and not c_is_attacker:
        # Opponent attacks, challenger defends
        if o_power > c_power * 1.5:
            outcome = BattleRound.Outcome.FULL_HIT
            o_hit_landed = True
        elif o_power > c_power:
            outcome = BattleRound.Outcome.PARTIAL_HIT
            o_hit_landed = True
        else:
            outcome = BattleRound.Outcome.BLOCKED
        attacker, defender = battle.opponent, battle.challenger
        attack_power, defence_power = o_power, c_power
    else:
        # Both attack or both defend — clash
        if c_power > o_power:
            outcome = BattleRound.Outcome.FULL_HIT
            c_hit_landed = True
            attacker, defender = battle.challenger, battle.opponent
        elif o_power > c_power:
            outcome = BattleRound.Outcome.FULL_HIT
            o_hit_landed = True
            attacker, defender = battle.opponent, battle.challenger
        else:
            outcome = BattleRound.Outcome.DRAW
            attacker, defender = battle.challenger, battle.opponent
        attack_power, defence_power = max(c_power, o_power), min(c_power, o_power)

    new_c_hits = prev_c_hits + (1 if c_hit_landed else 0)
    new_o_hits = prev_o_hits + (1 if o_hit_landed else 0)

    # Build log message
    outcome_labels = {
        BattleRound.Outcome.FULL_HIT: "lands a full hit",
        BattleRound.Outcome.PARTIAL_HIT: "lands a partial hit",
        BattleRound.Outcome.BLOCKED: "is blocked",
        BattleRound.Outcome.DRAW: "clash, draw",
    }
    log_msg = (
        f"{attacker.name} {outcome_labels.get(outcome, outcome)} "
        f"on {defender.name}. ({attack_power} vs {defence_power})"
    )

    with transaction.atomic():
        # Lock both actions
        BattleCombatAction.objects.filter(
            battle=battle, round_number=round_number
        ).update(is_locked=True)

        # Deduct moves
        c_profile = get_or_create_battle_profile(battle.challenger)
        o_profile = get_or_create_battle_profile(battle.opponent)
        c_profile.battle_moves = max(0, c_profile.battle_moves - challenger_action.moves_invested)
        o_profile.battle_moves = max(0, o_profile.battle_moves - opponent_action.moves_invested)
        c_profile.save(update_fields=["battle_moves"])
        o_profile.save(update_fields=["battle_moves"])

        # Create round record
        round_obj = BattleRound.objects.create(
            battle=battle,
            round_number=round_number,
            attacker=attacker,
            defender=defender,
            attack_power=attack_power,
            defence_power=defence_power,
            outcome=outcome,
            challenger_hits=new_c_hits,
            opponent_hits=new_o_hits,
            log_message=log_msg,
        )

        # End combat phase when any chef reaches hits_to_win
        if new_c_hits >= COMBAT_HITS_TO_WIN or new_o_hits >= COMBAT_HITS_TO_WIN:
            battle.status = Battle.Status.AWAITING_SUBMISSIONS
            battle.save(update_fields=["status", "updated_at"])
            create_battle_event(
                battle=battle,
                event_type=BattleEvent.EventType.BATTLE_STARTED,
                message=(
                    f"Combat phase complete! "
                    f"{battle.challenger.name} {new_c_hits}:{new_o_hits} {battle.opponent.name}. "
                    f"Chefs now prepare their dishes."
                ),
            )

    return round_obj


def get_combat_state(battle: Battle) -> dict:
    """Return combat state dict for the battle room template."""
    rounds = list(battle.combat_rounds.order_by("round_number"))
    current_round = get_current_round(battle)
    last = rounds[-1] if rounds else None
    return {
        "rounds": rounds,
        "current_round": current_round,
        "challenger_hits": last.challenger_hits if last else 0,
        "opponent_hits": last.opponent_hits if last else 0,
        "hits_to_win": COMBAT_HITS_TO_WIN,
    }


# ── Biathlon ─────────────────────────────────────────────────────────────────

def place_ingredient_lock(*, battle: Battle, chef, ingredient_index: int) -> IngredientLock:
    """Loser places a hidden lock on one of their ingredient lines."""
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        raise ValueError("Locks can only be placed during the ingredient penalty phase.")
    if battle.loser_id != chef.pk:
        raise ValueError("Only the loser can place ingredient locks.")
    existing = battle.ingredient_locks.filter(chef=chef).count()
    if existing >= IngredientLock.MAX_LOCKS:
        raise ValueError(f"You can only place {IngredientLock.MAX_LOCKS} locks.")
    loser_entry = battle.entries.filter(author=chef).select_related("recipe").first()
    if not loser_entry or not loser_entry.recipe:
        raise ValueError("No recipe found for this entry.")
    ingredients = [line for line in loser_entry.recipe.ingredients.splitlines() if line.strip()]
    if ingredient_index < 0 or ingredient_index >= len(ingredients):
        raise ValueError("Invalid ingredient index.")
    lock, created = IngredientLock.objects.get_or_create(
        battle=battle, chef=chef, ingredient_index=ingredient_index
    )
    if not created:
        raise ValueError("This ingredient is already locked.")
    return lock


def fire_ingredient_shot(*, battle: Battle, shooter, target_index: int) -> IngredientShot:
    """Winner fires one shot at a loser's ingredient line. Bounces off locks."""
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        raise ValueError("Shots can only be fired during the ingredient penalty phase.")
    if battle.winner_id != shooter.pk:
        raise ValueError("Only the winner can fire ingredient shots.")
    loser = battle.loser
    if not loser:
        raise ValueError("No loser found for this battle.")
    existing_shots = battle.ingredient_shots.filter(shooter=shooter).count()
    if existing_shots >= IngredientShot.MAX_SHOTS:
        raise ValueError(f"You can only fire {IngredientShot.MAX_SHOTS} shots.")
    loser_entry = battle.entries.filter(author=loser).select_related("recipe").first()
    if not loser_entry or not loser_entry.recipe:
        raise ValueError("No loser recipe found.")
    ingredients = [line for line in loser_entry.recipe.ingredients.splitlines() if line.strip()]
    if target_index < 0 or target_index >= len(ingredients):
        raise ValueError("Invalid ingredient index.")
    locked_indices = set(
        battle.ingredient_locks.filter(chef=loser).values_list("ingredient_index", flat=True)
    )
    bounced = target_index in locked_indices
    shot = IngredientShot.objects.create(
        battle=battle,
        shooter=shooter,
        target_index=target_index,
        bounced=bounced,
    )
    _post_biathlon_event(battle, shot, ingredients[target_index], bounced)
    return shot


def _post_biathlon_event(battle: Battle, shot: IngredientShot, ingredient_name: str, bounced: bool) -> None:
    if bounced:
        message = f"{battle.winner.name}'s shot at '{ingredient_name}' bounced off a lock."
    else:
        message = f"{battle.winner.name}'s shot hit '{ingredient_name}'."
    _create_battle_event(battle=battle, message=message, actor=battle.winner, is_public=True)


def get_biathlon_state(battle: Battle) -> dict:
    """Return the full biathlon state for the template."""
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        return {}
    loser = battle.loser
    winner = battle.winner
    loser_entry = battle.entries.filter(author=loser).select_related("recipe").first() if loser else None
    ingredients = []
    if loser_entry and loser_entry.recipe:
        ingredients = [line for line in loser_entry.recipe.ingredients.splitlines() if line.strip()]
    locks = list(battle.ingredient_locks.filter(chef=loser).values_list("ingredient_index", flat=True))
    shots = list(battle.ingredient_shots.filter(shooter=winner).values("target_index", "bounced", "fired_at"))
    shot_indices = {s["target_index"] for s in shots}
    loser_locked_own = list(battle.ingredient_locks.filter(chef=loser).values_list("ingredient_index", flat=True))
    locks_placed = len(loser_locked_own)
    shots_fired = len(shots)
    loser_locks_done = locks_placed >= IngredientLock.MAX_LOCKS
    winner_shots_done = shots_fired >= IngredientShot.MAX_SHOTS
    return {
        "ingredients": ingredients,
        "locks": locks,
        "shots": shots,
        "shot_indices": shot_indices,
        "locks_placed": locks_placed,
        "shots_fired": shots_fired,
        "max_locks": IngredientLock.MAX_LOCKS,
        "max_shots": IngredientShot.MAX_SHOTS,
        "loser_locks_done": loser_locks_done,
        "winner_shots_done": winner_shots_done,
        "loser": loser,
        "winner": winner,
    }


# ── Cooking phase moderation ──────────────────────────────────────────────────

def approve_cooking_phase(battle: Battle, moderator) -> Battle:
    """Moderator approves transition from INGREDIENT_PENALTY to COOKING."""
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        raise ValueError("Battle must be in ingredient_penalty status to approve cooking phase.")
    with transaction.atomic():
        battle.status = Battle.Status.COOKING
        battle.save(update_fields=["status", "updated_at"])
        _create_battle_event(
            battle=battle,
            message=f"Cooking phase approved by moderator. Chefs may now submit their cooked dishes.",
            actor=None,
            is_public=True,
        )
    return battle


def get_battles_awaiting_cooking_approval() -> list:
    return list(
        Battle.objects.filter(status=Battle.Status.INGREDIENT_PENALTY)
        .select_related("challenger", "opponent", "winner", "loser")
        .prefetch_related("ingredient_shots", "ingredient_locks", "entries__recipe")
        .order_by("updated_at")
    )


# ── Token economy ──────────────────────────────────────────────────────────────

def get_or_create_wallet(chef) -> TokenWallet:
    wallet, _ = TokenWallet.objects.get_or_create(chef=chef)
    return wallet


def credit_tokens(chef, amount: int, tx_type: str, description: str = "", battle=None) -> TokenTransaction:
    """Add tokens to a chef's wallet. Returns the transaction."""
    if amount <= 0:
        raise ValueError("Credit amount must be positive.")
    with transaction.atomic():
        wallet = get_or_create_wallet(chef)
        wallet.balance += amount
        wallet.total_purchased += amount
        wallet.save(update_fields=["balance", "total_purchased", "updated_at"])
        return TokenTransaction.objects.create(
            wallet=wallet,
            tx_type=tx_type,
            amount=amount,
            balance_after=wallet.balance,
            description=description,
            related_battle=battle,
        )


def debit_tokens(chef, amount: int, tx_type: str, description: str = "", battle=None) -> TokenTransaction:
    """Deduct tokens from a chef's wallet. Raises ValueError if insufficient balance."""
    if amount <= 0:
        raise ValueError("Debit amount must be positive.")
    with transaction.atomic():
        wallet = get_or_create_wallet(chef)
        if wallet.balance < amount:
            raise ValueError(
                f"Insufficient tokens: need {amount}T, have {wallet.balance}T."
            )
        wallet.balance -= amount
        wallet.total_spent += amount
        wallet.save(update_fields=["balance", "total_spent", "updated_at"])
        return TokenTransaction.objects.create(
            wallet=wallet,
            tx_type=tx_type,
            amount=-amount,
            balance_after=wallet.balance,
            description=description,
            related_battle=battle,
        )


# ── Cooking phase ─────────────────────────────────────────────────────────────

def submit_cooked_photo(*, battle: Battle, author, photo) -> BattleEntry:
    """Chef uploads their cooked dish photo. Advances to PRESENTATION when both submitted."""
    if battle.status != Battle.Status.COOKING:
        raise ValueError("Battle must be in COOKING status to submit a cooked photo.")
    entry = BattleEntry.objects.get(battle=battle, author=author)
    if entry.cooked_photo:
        raise ValueError("You have already submitted a cooked photo for this battle.")
    with transaction.atomic():
        entry.cooked_photo = photo
        entry.cooked_photo_submitted_at = timezone.now()
        entry.save(update_fields=["cooked_photo", "cooked_photo_submitted_at", "updated_at"])
        both_submitted = not BattleEntry.objects.filter(
            battle=battle, cooked_photo__isnull=True
        ).exclude(cooked_photo="").exists()
        if both_submitted:
            battle.status = Battle.Status.PRESENTATION
            battle.save(update_fields=["status", "updated_at"])
            create_battle_event(
                event_type=BattleEvent.EventType.BATTLE_STARTED,
                battle=battle,
                message="Both chefs have submitted their cooked dish photos. Presentation phase begins.",
                is_public=True,
            )
    return entry


# ── Viewer gifts ───────────────────────────────────────────────────────────────

def send_battle_artifact(*, sender_user, recipient, battle: Battle, artifact: Artifact) -> ViewerBattleGift:
    """Viewer spends tokens to send a battle artifact to a chef in an active battle."""
    if battle.status not in Battle.ACTIVE_STATUSES:
        raise ValueError("Cannot send battle gifts to a battle that is not active.")
    if not battle.author_is_participant(recipient):
        raise ValueError("Recipient must be a participant in this battle.")
    if not artifact.is_active:
        raise ValueError("This artifact is not available.")

    sender_author = getattr(sender_user, "recipe_author", None)
    if sender_author is None:
        from recipes.models import RecipeAuthor as RA
        sender_author = RA.objects.filter(user=sender_user).first()
    if sender_author is None:
        raise ValueError("Sender must have a chef profile to send gifts.")

    cost = artifact.token_cost
    with transaction.atomic():
        debit_tokens(
            sender_author, cost,
            tx_type=TokenTransaction.TxType.GIFT_SENT,
            description=f"Battle gift: {artifact.name} → {recipient.name}",
            battle=battle,
        )
        gift = ViewerBattleGift.objects.create(
            battle=battle,
            recipient=recipient,
            sender=sender_user,
            artifact=artifact,
            tokens_spent=cost,
        )
    return gift


def send_appreciation_gift(*, sender_user, recipient, gift_type: str, message: str = "") -> AppreciationGift:
    """Viewer spends tokens to send an appreciation gift to a chef (permanent on profile)."""
    cost = APPRECIATION_GIFT_COST.get(gift_type)
    if cost is None:
        raise ValueError(f"Unknown gift type: {gift_type}")

    sender_author = getattr(sender_user, "recipe_author", None)
    if sender_author is None:
        from recipes.models import RecipeAuthor as RA
        sender_author = RA.objects.filter(user=sender_user).first()
    if sender_author is None:
        raise ValueError("Sender must have a chef profile to send gifts.")

    with transaction.atomic():
        debit_tokens(
            sender_author, cost,
            tx_type=TokenTransaction.TxType.GIFT_SENT,
            description=f"Appreciation gift: {gift_type} → {recipient.name}",
        )
        gift = AppreciationGift.objects.create(
            recipient=recipient,
            sender=sender_user,
            gift_type=gift_type,
            tokens_spent=cost,
            message=message,
        )
    return gift
