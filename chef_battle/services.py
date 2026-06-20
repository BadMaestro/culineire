from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.db import transaction
from django.db import models
from django.db.models import Count, Sum
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from newsfeed.models import NewsFeedEntry

from .models import (
    APPRECIATION_GIFT_COST, Artifact, Battle, BattleChallenge, BattleCombatAction,
    BattleEntry, BattleEvent, BattleRound, ChefArtifact, ChefBattleProfile, IngredientLock,
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
        profile.rank = ChefBattleProfile.Rank.EXECUTIVE_CHEF
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
        try:
            from sponsors.services import get_sponsor_of_month
            sponsor = get_sponsor_of_month()
        except Exception:
            sponsor = ""
        NewsFeedEntry.objects.create(
            entry_type=NewsFeedEntry.EntryType.BATTLE_EVENT,
            title=message,
            message=f"Sponsored by: {sponsor}" if sponsor else "",
            url=url,
            is_auto=True,
            is_public=is_public,
            event_key=event_key,
            sub_type=event_type,
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
    winner_profile.recalculate_prestige_title()
    winner_profile.save(update_fields=["wins", "win_streak", "rank", "level", "is_hero", "prestige_title", "updated_at"])

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
    if not battle.author_is_participant(author):
        from django.core.exceptions import ValidationError
        raise ValidationError("Only battle participants can submit entries.")
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
        winner_profile.seasonal_score += 10
        winner_profile.crown_count += 1
        winner_profile.crown_until = timezone.now() + timezone.timedelta(hours=24)
        if not winner_profile.infinite_moves:
            winner_profile.rank = rank_for_rating(winner_profile.rating)
        level_changed = winner_profile.recalculate_level()
        winner_profile.recalculate_prestige_title()
        winner_profile.save()

        loser_profile.losses += 1
        loser_profile.win_streak = 0
        loser_profile.rating = max(0, loser_profile.rating - 15)
        loser_profile.reputation = max(-1000, loser_profile.reputation - 3)
        if not loser_profile.infinite_moves:
            loser_profile.rank = rank_for_rating(loser_profile.rating)
        loser_profile.save()

        # Award moves with typed transaction records
        from .models import BattleMoveTransaction
        TxType = BattleMoveTransaction.TxType
        from .energy_service import ENERGY_CAP
        winner_profile.battle_moves = min(
            ENERGY_CAP,
            winner_profile.battle_moves + MOVES_BATTLE_WIN + MOVES_BATTLE_PARTICIPATION,
        )
        loser_profile.battle_moves = min(
            ENERGY_CAP,
            loser_profile.battle_moves + MOVES_BATTLE_PARTICIPATION,
        )
        winner_profile.save(update_fields=["battle_moves", "updated_at"])
        loser_profile.save(update_fields=["battle_moves", "updated_at"])
        BattleMoveTransaction.objects.bulk_create([
            BattleMoveTransaction(chef=winner, amount=MOVES_BATTLE_WIN, transaction_type=TxType.BATTLE_WON),
            BattleMoveTransaction(chef=winner, amount=MOVES_BATTLE_PARTICIPATION, transaction_type=TxType.BATTLE_PARTICIPATION),
            BattleMoveTransaction(chef=loser, amount=MOVES_BATTLE_PARTICIPATION, transaction_type=TxType.BATTLE_PARTICIPATION),
        ])

        battle.winner = winner
        battle.loser = loser
        battle.status = Battle.Status.COMPLETED
        battle.crown_awarded = True
        battle.result_reason = f"Public vote: {challenger_votes}-{opponent_votes}"
        battle.save(update_fields=["winner", "loser", "status", "crown_awarded", "result_reason", "updated_at"])

        from .models import LedgerEvent
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.BATTLE_COMPLETED,
            actor=winner,
            target=loser,
            related_battle=battle,
            payload={
                "challenger_votes": challenger_votes,
                "opponent_votes": opponent_votes,
                "result_reason": battle.result_reason,
            },
        )

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
    drop_battle_artifacts(battle)

    # Next Battle Unlock: after battle completes, check if any pending CBR/LSR
    # for both participants can now be queued for review.
    try:
        run_next_battle_unlock_for_chef(winner)
        run_next_battle_unlock_for_chef(loser)
    except Exception:
        logger.exception("Next Battle Unlock check failed for battle %s", battle.pk)

    return battle


# ── Phase 3: Battle moves economy ────────────────────────────────────────────

from .energy_service import (  # noqa: E402
    EARN_RECIPE_PUBLISHED as MOVES_RECIPE_APPROVED,
    EARN_ARTICLE_PUBLISHED as MOVES_ARTICLE_APPROVED,
    EARN_BATTLE_WON as MOVES_BATTLE_WIN,
    EARN_BATTLE_PARTICIPATION as MOVES_BATTLE_PARTICIPATION,
    ENERGY_CAP,
    award_moves as _energy_award_moves,
    spend_moves as _energy_spend_moves,
    InsufficientEnergy,
)

MOVES_MIN_TO_CHALLENGE = 10

# Legacy cap constants kept for backward compatibility with existing tests
MOVES_CONTENT_DAILY_CAP = ENERGY_CAP
MOVES_CONTENT_WEEKLY_CAP = ENERGY_CAP


def award_moves(author, amount: int, reason: str) -> None:
    """Backward-compatible wrapper used by existing signals.

    Delegates to energy_service.award_moves with a best-guess transaction_type.
    """
    from .models import BattleMoveTransaction
    TxType = BattleMoveTransaction.TxType
    _reason_map = {
        "Recipe approved": TxType.RECIPE_PUBLISHED,
        "Article approved": TxType.ARTICLE_PUBLISHED,
        "Battle win": TxType.BATTLE_WON,
        "Battle participation": TxType.BATTLE_PARTICIPATION,
    }
    tx_type = _reason_map.get(reason, TxType.ADMIN_ADJUSTMENT)
    try:
        _energy_award_moves(author, amount, tx_type)
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

        # Deduct moves via energy_service to create typed transaction records
        from .models import BattleMoveTransaction
        TxType = BattleMoveTransaction.TxType
        _energy_spend_moves(battle.challenger, challenger_action.moves_invested, TxType.COMBAT_ACTION_SPENT)
        _energy_spend_moves(battle.opponent, opponent_action.moves_invested, TxType.COMBAT_ACTION_SPENT)

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
    create_battle_event(battle=battle, event_type=BattleEvent.EventType.BATTLE_STARTED, message=message, actor=battle.winner, is_public=True)


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
        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_STARTED,
            battle=battle,
            message="Cooking phase approved by moderator. Chefs may now submit their cooked dishes.",
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

def submit_cooked_photo(*, battle: Battle, author, photo, real_photo_confirmed: bool = False) -> BattleEntry:
    """Chef uploads their cooked dish photo. Advances to PRESENTATION when both submitted."""
    import hashlib
    if battle.status != Battle.Status.COOKING:
        raise ValueError("Battle must be in COOKING status to submit a cooked photo.")
    entry = BattleEntry.objects.get(battle=battle, author=author)
    if entry.cooked_photo:
        raise ValueError("You have already submitted a cooked photo for this battle.")
    photo_hash = ""
    try:
        photo.seek(0)
        photo_hash = hashlib.sha256(photo.read()).hexdigest()
        photo.seek(0)
    except Exception:
        pass
    with transaction.atomic():
        entry.cooked_photo = photo
        entry.cooked_photo_submitted_at = timezone.now()
        entry.real_photo_confirmed = real_photo_confirmed
        entry.photo_hash = photo_hash
        entry.save(update_fields=[
            "cooked_photo", "cooked_photo_submitted_at",
            "real_photo_confirmed", "photo_hash", "updated_at",
        ])
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
    """Viewer spends tokens to send an appreciation gift to a chef. All gifts are digital items only.

    Creates two LSR records:
    - Sender gets 10% of cost back immediately (issued to wallet).
    - Recipient chef gets a pending LSR equal to full gift cost (not credited until approved + Next Battle Unlock).
    """
    from .models import APPRECIATION_GIFT_REWARD_ELIGIBLE, APPRECIATION_GIFT_REWARD_BASIS
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

        from .models import LedgerEvent, RewardRecord
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.GIFT_SENT,
            actor=sender_author,
            target=recipient,
            payload={"gift_type": gift_type, "tokens_spent": cost},
        )

        # LSR: sender earns 10% of the gift cost back as a Live Support Reward
        lsr_amount = max(1, cost // 10)
        reward = RewardRecord.objects.create(
            recipient=sender_author,
            reward_type=RewardRecord.RewardType.LSR,
            tokens_granted=lsr_amount,
            reason=f"LSR for sending {gift_type} to {recipient.name}",
            related_gift=gift,
        )
        credit_tokens(
            sender_author, lsr_amount,
            tx_type=TokenTransaction.TxType.ADMIN_GRANT,
            description=f"LSR reward for gift to {recipient.name}",
        )
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.LSR_GRANTED,
            actor=sender_author,
            payload={"tokens_granted": lsr_amount, "reward_id": reward.pk, "gift_type": gift_type},
        )

        # LSR for recipient chef: pending reward record (not credited until approved + Next Battle Unlock)
        if APPRECIATION_GIFT_REWARD_ELIGIBLE.get(gift_type, False):
            chef_lsr_amount = APPRECIATION_GIFT_REWARD_BASIS.get(gift_type, cost)
            chef_reward = RewardRecord.objects.create(
                recipient=recipient,
                reward_type=RewardRecord.RewardType.LSR,
                tokens_granted=chef_lsr_amount,
                reason=f"LSR: {sender_author.name} sent {gift_type}",
                related_gift=gift,
            )
            LedgerEvent.objects.create(
                event_type=LedgerEvent.EventType.LSR_GRANTED,
                actor=recipient,
                payload={
                    "source": "appreciation_gift",
                    "gift_type": gift_type,
                    "tokens_pending": chef_lsr_amount,
                    "reward_record_id": chef_reward.pk,
                    "from": sender_author.slug,
                },
            )

    return gift


# Rarity weights for artifact drops
_DROP_WEIGHTS_WINNER = {
    "common": 30,
    "uncommon": 27,
    "rare": 20,
    "epic": 15,
    "legendary": 8,
}

def _pick_artifact(chef, weights: dict, guaranteed: bool = False):
    """Pick a random artifact the chef doesn't already own, weighted by rarity.

    If guaranteed=True and weighted sampling fails (rarity pool exhausted),
    fall back to any unowned artifact so the winner always receives a drop.
    """
    import random
    rarities = list(weights.keys())
    rarity_weights = list(weights.values())
    owned_ids = set(
        ChefArtifact.objects.filter(chef=chef).values_list("artifact_id", flat=True)
    )
    for _ in range(10):
        rarity = random.choices(rarities, weights=rarity_weights, k=1)[0]
        candidates = list(
            Artifact.objects.filter(rarity=rarity, is_active=True).exclude(id__in=owned_ids)
        )
        if candidates:
            return random.choice(candidates)
    if guaranteed:
        # Fallback: pick any unowned active artifact
        fallback = list(Artifact.objects.filter(is_active=True).exclude(id__in=owned_ids))
        if fallback:
            return random.choice(fallback)
    return None


def drop_battle_artifacts(battle: Battle) -> list:
    """Award random artifact drops to participants after a completed battle.

    Winner always receives a drop (guaranteed=True).
    Loser has a 50% chance of a consolation drop.
    """
    import random
    drops = []
    winner = battle.winner
    loser = battle.loser

    participants = []
    if winner:
        participants.append((winner, _DROP_WEIGHTS_WINNER, True))
    if loser and random.random() < 0.50:
        participants.append((loser, _DROP_WEIGHTS_WINNER, False))

    for chef, weights, guaranteed in participants:
        artifact = _pick_artifact(chef, weights, guaranteed=guaranteed)
        if artifact is None:
            continue
        ca = ChefArtifact.objects.create(
            chef=chef,
            artifact=artifact,
            source=ChefArtifact.Source.DROP,
        )
        drops.append(ca)
        create_battle_event(
            event_type=BattleEvent.EventType.ARTIFACT_DROPPED,
            battle=battle,
            actor=chef,
            message=f"{chef.name} received a {artifact.get_rarity_display()} artifact drop: {artifact.name}.",
            publish_to_news=False,
        )
    return drops


# ── RewardRecord lifecycle ──────────────────────────────────────────────────

def issue_reward(reward_id: int, reviewed_by=None) -> "RewardRecord":
    """Approve a PENDING/QUEUED RewardRecord and credit tokens to the recipient's wallet.
    Raises ValueError if the record is not in an issuable state."""
    from .models import RewardRecord, TokenWallet, TokenTransaction, LedgerEvent
    from django.utils import timezone

    with transaction.atomic():
        record = RewardRecord.objects.select_for_update().get(pk=reward_id)
        if record.status not in (RewardRecord.Status.PENDING, RewardRecord.Status.QUEUED, RewardRecord.Status.APPROVED):
            raise ValueError(f"RewardRecord {reward_id} is in status '{record.status}' and cannot be issued.")

        wallet, _ = TokenWallet.objects.get_or_create(chef=record.recipient)
        new_balance = wallet.balance + record.tokens_granted
        wallet.balance = new_balance
        wallet.save(update_fields=["balance", "updated_at"])

        TokenTransaction.objects.create(
            wallet=wallet,
            tx_type=TokenTransaction.TxType.ADMIN_GRANT,
            amount=record.tokens_granted,
            balance_after=new_balance,
            description=f"{record.get_reward_type_display()}: {record.reason}",
        )

        record.status = RewardRecord.Status.ISSUED
        record.issued_at = timezone.now()
        if reviewed_by is not None:
            record.reviewed_by = reviewed_by
        record.save(update_fields=["status", "issued_at", "reviewed_by", "updated_at"])

        event_type = (
            LedgerEvent.EventType.CBR_GRANTED
            if record.reward_type == RewardRecord.RewardType.CBR
            else LedgerEvent.EventType.LSR_GRANTED
        )
        LedgerEvent.objects.create(
            event_type=event_type,
            actor=record.recipient,
            payload={
                "reward_record_id": record.pk,
                "tokens_granted": record.tokens_granted,
                "reason": record.reason,
            },
        )

    return record


def expire_rewards() -> int:
    """Mark all ISSUED RewardRecords past their expires_at as EXPIRED. Returns count."""
    from .models import RewardRecord
    from django.utils import timezone

    now = timezone.now()
    qs = RewardRecord.objects.filter(
        status=RewardRecord.Status.ISSUED,
        expires_at__isnull=False,
        expires_at__lt=now,
    )
    count = qs.update(status=RewardRecord.Status.EXPIRED)
    return count


def reverse_reward(reward_id: int, note: str = "", reversed_by=None) -> "RewardRecord":
    """Reverse an ISSUED reward: deduct tokens from wallet and mark as REVERSED."""
    from .models import RewardRecord, TokenWallet, TokenTransaction
    from django.utils import timezone

    with transaction.atomic():
        record = RewardRecord.objects.select_for_update().get(pk=reward_id)
        if record.status != RewardRecord.Status.ISSUED:
            raise ValueError(f"Only ISSUED rewards can be reversed; this one is '{record.status}'.")

        wallet = TokenWallet.objects.select_for_update().filter(chef=record.recipient).first()
        if wallet:
            deduct = min(record.tokens_granted, wallet.balance)
            if deduct > 0:
                new_balance = wallet.balance - deduct
                wallet.balance = new_balance
                wallet.save(update_fields=["balance", "updated_at"])
                TokenTransaction.objects.create(
                    wallet=wallet,
                    tx_type=TokenTransaction.TxType.ADMIN_DEDUCT,
                    amount=-deduct,
                    balance_after=new_balance,
                    description=f"Reward reversal: {record.reason}",
                )

        record.status = RewardRecord.Status.REVERSED
        record.reversed_at = timezone.now()
        record.status_note = note
        if reversed_by is not None:
            record.reviewed_by = reversed_by
        record.save(update_fields=["status", "reversed_at", "status_note", "reviewed_by", "updated_at"])

    return record


# ── Next Battle Unlock ──────────────────────────────────────────────────────

def _is_eligible_battle(battle, chef) -> bool:
    """Return True if this battle qualifies as an unlock battle for the chef's CBR/LSR.

    Eligible = completed, both entries submitted, chef's entry cooking-photo approved
    by a moderator, voting done, not cancelled/disputed/fraud-flagged.
    """
    from .models import Battle, BattleEntry

    if battle.status != Battle.Status.COMPLETED:
        return False
    if battle.status in (Battle.Status.CANCELLED, Battle.Status.DISPUTED):
        return False

    # Chef must have been a participant
    if chef not in (battle.challenger, battle.opponent):
        return False

    # Both entries must exist
    entries = list(battle.entries.select_related("author").all())
    if len(entries) < 2:
        return False

    # Chef's own entry must have moderation_status=APPROVED (cooking photo confirmed)
    chef_entry = next((e for e in entries if e.author_id == chef.pk), None)
    if chef_entry is None:
        return False
    if chef_entry.moderation_status != BattleEntry.ModerationStatus.APPROVED:
        return False

    # No fraud / suspension on chef profile at this point
    from .models import ChefBattleProfile
    profile = ChefBattleProfile.objects.filter(author=chef).first()
    if profile and (profile.is_suspended or profile.fraud_flag):
        return False

    return True


def check_next_battle_unlock(chef, reward_record) -> bool:
    """Check whether a chef has completed an eligible battle AFTER the reward record was created.

    Returns True if the unlock condition is met and the reward_record is now QUEUED for review.
    """
    from .models import Battle, RewardRecord
    from django.db.models import Q

    if reward_record.status not in (RewardRecord.Status.PENDING,):
        return reward_record.status in (
            RewardRecord.Status.QUEUED,
            RewardRecord.Status.APPROVED,
            RewardRecord.Status.ISSUED,
        )

    completed_after = Battle.objects.filter(
        Q(challenger=chef) | Q(opponent=chef),
        status=Battle.Status.COMPLETED,
        end_time__gt=reward_record.created_at,
    ).order_by("end_time")

    for battle in completed_after:
        if _is_eligible_battle(battle, chef):
            with transaction.atomic():
                rr = RewardRecord.objects.select_for_update().get(pk=reward_record.pk)
                if rr.status == RewardRecord.Status.PENDING:
                    rr.status = RewardRecord.Status.QUEUED
                    rr.status_note = f"Unlocked by battle #{battle.pk}"
                    rr.save(update_fields=["status", "status_note", "updated_at"])
            return True

    return False


def run_next_battle_unlock_for_chef(chef) -> int:
    """Check all PENDING reward records for a chef and queue any that are now unlocked.

    Returns the count of records moved to QUEUED status.
    Called after calculate_battle_result() to unlock rewards from previous battles.
    """
    from .models import RewardRecord
    pending = RewardRecord.objects.filter(
        recipient=chef, status=RewardRecord.Status.PENDING
    ).order_by("created_at")
    count = 0
    for record in pending:
        if check_next_battle_unlock(chef, record):
            count += 1
    return count


def handle_token_order_chargeback(token_order_id: int, chargeback: bool = False) -> dict:
    """Lock a token order and reverse related rewards when a refund or chargeback occurs.

    - Marks the TokenOrder as refunded (or disputed if chargeback=True).
    - Reverses any PENDING/QUEUED reward records linked to gifts funded by this order.
    - Flags all related AppreciationGift records.
    - Suspends the chef's payout eligibility flag.
    - Creates an immutable ledger entry for the compliance record.
    - Never silently deletes any records.

    Returns a summary dict with counts of affected records.
    """
    from .models import (
        AppreciationGift, LedgerEvent, RewardRecord, TokenOrder, TokenWallet, TokenTransaction,
    )

    with transaction.atomic():
        try:
            order = TokenOrder.objects.select_for_update().select_related("wallet__owner").get(pk=token_order_id)
        except TokenOrder.DoesNotExist:
            logger.error("handle_token_order_chargeback: TokenOrder %s not found", token_order_id)
            return {"error": "TokenOrder not found"}

        buyer_author = getattr(order.wallet, "owner", None)

        new_status = TokenOrder.Status.DISPUTED if chargeback else TokenOrder.Status.REFUNDED
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        # Deduct tokens from buyer's wallet if they were credited
        deducted_tokens = 0
        if buyer_author and order.tokens and order.tokens > 0:
            wallet = TokenWallet.objects.filter(owner=buyer_author).select_for_update().first()
            if wallet:
                actual_deduct = min(wallet.balance, order.tokens)
                if actual_deduct > 0:
                    wallet.balance -= actual_deduct
                    wallet.save(update_fields=["balance"])
                    TokenTransaction.objects.create(
                        wallet=wallet,
                        amount=-actual_deduct,
                        reason=f"{'Chargeback' if chargeback else 'Refund'} — order #{order.pk}",
                    )
                    deducted_tokens = actual_deduct

        # Reverse PENDING/QUEUED rewards linked to gifts sent after this order's purchase
        reversed_rewards = 0
        buyer_user = getattr(buyer_author, "user", None) if buyer_author else None
        if buyer_user:
            reversible_statuses = [RewardRecord.Status.PENDING, RewardRecord.Status.QUEUED]
            gifts = AppreciationGift.objects.filter(
                sender=buyer_user,
                sent_at__gte=order.created_at,
            ).values_list("pk", flat=True)

            rewards_qs = RewardRecord.objects.select_for_update().filter(
                related_gift__in=gifts,
                status__in=reversible_statuses,
            )
            for rr in rewards_qs:
                rr.status = RewardRecord.Status.REVERSED
                rr.status_note = f"Reversed: {'chargeback' if chargeback else 'refund'} on order #{order.pk}"
                rr.save(update_fields=["status", "status_note", "updated_at"])
                reversed_rewards += 1

        # Flag related gifts for compliance review
        flagged_gifts = 0
        if buyer_user:
            flagged_gifts = AppreciationGift.objects.filter(
                sender=buyer_user,
                sent_at__gte=order.created_at,
                is_flagged=False,
            ).update(is_flagged=True)

        # Flag the buyer's profile for compliance review
        if buyer_author:
            profile = ChefBattleProfile.objects.filter(author=buyer_author).first()
            if profile and not profile.payout_blocked:
                profile.payout_blocked = True
                profile.save(update_fields=["payout_blocked"])

        action = "chargeback" if chargeback else "refund"
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.CHARGEBACK_LOCK,
            actor=buyer_author,
            payload={
                "action": action,
                "token_order_id": token_order_id,
                "new_status": new_status,
                "deducted_tokens": deducted_tokens,
                "reversed_rewards": reversed_rewards,
                "flagged_gifts": flagged_gifts,
            },
        )
        logger.info(
            "handle_token_order_chargeback: order=%s action=%s deducted=%s reversed=%s flagged=%s",
            token_order_id, action, deducted_tokens, reversed_rewards, flagged_gifts,
        )
        return {
            "order_id": token_order_id,
            "new_status": new_status,
            "deducted_tokens": deducted_tokens,
            "reversed_rewards": reversed_rewards,
            "flagged_gifts": flagged_gifts,
        }


def check_payout_eligibility(chef) -> dict:
    """Return a dict of {eligible: bool, reasons: list[str]} for payout request validation.

    Checks (all must pass):
    1. Chef profile exists and age_verified=True
    2. reward_agreement_accepted=True
    3. stripe_connect_onboarded=True
    4. not is_suspended and not fraud_flag and not payout_blocked
    5. Minimum 2000 APPROVED reward tokens (across all RewardRecord)
    6. No open PayoutRequest (PENDING or UNDER_REVIEW)
    """
    from .models import ChefBattleProfile, PayoutRequest, RewardRecord

    reasons = []

    profile = ChefBattleProfile.objects.filter(author=chef).first()
    if profile is None:
        return {"eligible": False, "reasons": ["No Chef Battle profile found."]}

    if not profile.age_verified:
        reasons.append("You must confirm you are 18 or older.")
    if not profile.reward_agreement_accepted:
        reasons.append("You must accept the Chef Reward Agreement before requesting a payout.")
    if not profile.stripe_connect_onboarded:
        reasons.append("Stripe Connect onboarding is not complete.")
    if profile.is_suspended:
        reasons.append("Your account is currently suspended.")
    if profile.fraud_flag:
        reasons.append("Your account has an active fraud flag under review.")
    if profile.payout_blocked:
        reasons.append("Your payout eligibility is blocked pending compliance review.")

    approved_tokens = RewardRecord.objects.filter(
        recipient=chef, status=RewardRecord.Status.APPROVED
    ).aggregate(total=Sum("tokens_granted"))["total"] or 0
    MIN_TOKENS = 2000
    if approved_tokens < MIN_TOKENS:
        reasons.append(
            f"Minimum {MIN_TOKENS} approved reward tokens required. You have {approved_tokens}."
        )

    open_request = PayoutRequest.objects.filter(
        chef=chef, status__in=[PayoutRequest.Status.PENDING, PayoutRequest.Status.UNDER_REVIEW]
    ).exists()
    if open_request:
        reasons.append("You already have a payout request under review.")

    return {"eligible": len(reasons) == 0, "reasons": reasons, "approved_tokens": approved_tokens}


def create_payout_request(chef, request_http=None) -> "PayoutRequest":
    """Create a PayoutRequest for a chef after eligibility checks pass.

    Locks all APPROVED reward records to ISSUED status immediately so they
    cannot be double-spent. Rate snapshot is frozen at creation time.
    Raises ValueError if not eligible.
    """
    from decimal import Decimal
    from .models import ChefBattleProfile, ChefRewardAgreement, DAC7Record, LedgerEvent, PayoutRequest, RewardRecord

    eligibility = check_payout_eligibility(chef)
    if not eligibility["eligible"]:
        raise ValueError(" ".join(eligibility["reasons"]))

    profile = ChefBattleProfile.objects.get(author=chef)
    dac7 = DAC7Record.objects.filter(chef=chef).first()
    agreement = ChefRewardAgreement.objects.filter(chef=chef).order_by("-accepted_at").first()

    rate = Decimal(PayoutRequest.PAYOUT_RATE_EUR_PER_TOKEN)

    with transaction.atomic():
        approved_records = RewardRecord.objects.select_for_update().filter(
            recipient=chef, status=RewardRecord.Status.APPROVED
        )
        total_tokens = sum(r.tokens_granted for r in approved_records)
        if total_tokens < 2000:
            raise ValueError("Not enough approved tokens.")

        gross_eur = (Decimal(total_tokens) * rate).quantize(Decimal("0.01"))

        payout = PayoutRequest.objects.create(
            chef=chef,
            dac7_record=dac7,
            reward_agreement=agreement,
            amount_reward_tokens=total_tokens,
            payout_rate_snapshot=rate,
            gross_payout_eur=gross_eur,
            stripe_connect_account_id=dac7.stripe_connect_account_id if dac7 else "",
        )

        # Move approved records to ISSUED (locked for this payout)
        for record in approved_records:
            record.status = RewardRecord.Status.ISSUED
            record.status_note = f"Locked for PayoutRequest #{payout.pk}"
            record.save(update_fields=["status", "status_note", "updated_at"])

        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ADMIN_NOTE,
            actor=chef,
            payload={
                "action": "payout_request_created",
                "payout_request_id": payout.pk,
                "total_tokens": total_tokens,
                "gross_eur": str(gross_eur),
                "rate": str(rate),
            },
        )

    logger.info("Payout request #%s created for %s: %sT / €%s", payout.pk, chef, total_tokens, gross_eur)
    return payout


def approve_payout_request(payout_request_id: int, reviewed_by_user) -> "PayoutRequest":
    """Admin: approve a PayoutRequest and trigger Stripe Connect transfer.

    Sets status to APPROVED (then PAID after transfer). Moves ISSUED reward records to ACKNOWLEDGED.
    """
    from .models import LedgerEvent, PayoutRequest, RewardRecord

    with transaction.atomic():
        try:
            payout = PayoutRequest.objects.select_for_update().get(pk=payout_request_id)
        except PayoutRequest.DoesNotExist:
            raise ValueError(f"PayoutRequest #{payout_request_id} not found.")

        if payout.status not in (PayoutRequest.Status.PENDING, PayoutRequest.Status.UNDER_REVIEW):
            raise ValueError(f"PayoutRequest #{payout_request_id} is in status '{payout.status}' and cannot be approved.")

        payout.status = PayoutRequest.Status.APPROVED
        payout.reviewed_by = reviewed_by_user
        payout.reviewed_at = timezone.now()
        payout.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ADMIN_NOTE,
            actor=payout.chef,
            payload={
                "action": "payout_approved",
                "payout_request_id": payout.pk,
                "approved_by": reviewed_by_user.username,
                "gross_eur": str(payout.gross_payout_eur),
            },
        )

    # Attempt Stripe Connect transfer outside the atomic block
    try:
        _execute_stripe_connect_transfer(payout)
    except Exception:
        logger.exception("Stripe Connect transfer failed for PayoutRequest #%s", payout_request_id)
        # Leave as APPROVED — admin can retry

    return payout


def reject_payout_request(payout_request_id: int, reviewed_by_user, reason: str) -> "PayoutRequest":
    """Admin: reject a PayoutRequest. Moves ISSUED reward records back to APPROVED."""
    from .models import LedgerEvent, PayoutRequest, RewardRecord

    with transaction.atomic():
        try:
            payout = PayoutRequest.objects.select_for_update().get(pk=payout_request_id)
        except PayoutRequest.DoesNotExist:
            raise ValueError(f"PayoutRequest #{payout_request_id} not found.")

        if payout.status not in (PayoutRequest.Status.PENDING, PayoutRequest.Status.UNDER_REVIEW, PayoutRequest.Status.APPROVED):
            raise ValueError(f"PayoutRequest #{payout_request_id} cannot be rejected from status '{payout.status}'.")

        payout.status = PayoutRequest.Status.REJECTED
        payout.reviewed_by = reviewed_by_user
        payout.reviewed_at = timezone.now()
        payout.rejection_reason = reason
        payout.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])

        # Return ISSUED records to APPROVED so chef can re-request
        RewardRecord.objects.filter(
            recipient=payout.chef,
            status=RewardRecord.Status.ISSUED,
            status_note__contains=f"PayoutRequest #{payout.pk}",
        ).update(status=RewardRecord.Status.APPROVED, status_note="Returned: payout rejected")

        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ADMIN_NOTE,
            actor=payout.chef,
            payload={
                "action": "payout_rejected",
                "payout_request_id": payout.pk,
                "rejected_by": reviewed_by_user.username,
                "reason": reason,
            },
        )

    return payout


def _execute_stripe_connect_transfer(payout: "PayoutRequest") -> None:
    """Attempt a Stripe Connect transfer for an approved payout. Updates status to PAID on success."""
    from decimal import Decimal
    from .models import LedgerEvent, PayoutRequest

    if not payout.stripe_connect_account_id:
        logger.error("No Stripe Connect account ID on PayoutRequest #%s", payout.pk)
        return

    try:
        import stripe
        stripe.api_key = __import__("django.conf", fromlist=["settings"]).settings.STRIPE_SECRET_KEY
        transfer = stripe.Transfer.create(
            amount=int(payout.gross_payout_eur * 100),
            currency=payout.currency or "eur",
            destination=payout.stripe_connect_account_id,
            metadata={"payout_request_id": str(payout.pk), "chef": str(payout.chef_id)},
        )
        transfer_id = transfer.get("id", "")
        with transaction.atomic():
            pr = PayoutRequest.objects.select_for_update().get(pk=payout.pk)
            pr.status = PayoutRequest.Status.PAID
            pr.stripe_transfer_id = transfer_id
            pr.paid_at = timezone.now()
            pr.save(update_fields=["status", "stripe_transfer_id", "paid_at", "updated_at"])
            LedgerEvent.objects.create(
                event_type=LedgerEvent.EventType.ADMIN_NOTE,
                actor=payout.chef,
                payload={
                    "action": "payout_paid",
                    "payout_request_id": payout.pk,
                    "stripe_transfer_id": transfer_id,
                    "gross_eur": str(payout.gross_payout_eur),
                },
            )
        logger.info("PayoutRequest #%s paid: transfer %s", payout.pk, transfer_id)
    except ImportError:
        logger.error("stripe package not installed — cannot execute transfer for PayoutRequest #%s", payout.pk)
    except Exception:
        logger.exception("Stripe transfer failed for PayoutRequest #%s", payout.pk)
        raise


def get_chef_payout_statement(chef) -> dict:
    """Return a summary dict for a chef's reward/payout ledger page.

    Used in the chef profile payout statement view.
    """
    from .models import PayoutRequest, RewardRecord

    reward_summary = {}
    for status in RewardRecord.Status:
        reward_summary[status.value] = RewardRecord.objects.filter(
            recipient=chef, status=status
        ).aggregate(total=Sum("tokens_granted"), count=Count("pk"))

    payout_history = PayoutRequest.objects.filter(chef=chef).order_by("-requested_at")[:20]

    eligibility = check_payout_eligibility(chef)

    return {
        "reward_summary": reward_summary,
        "payout_history": payout_history,
        "eligibility": eligibility,
    }


def submit_content_report(
    reporter,
    content_kind: str,
    object_id: int,
    reason: str,
) -> "ContentReport":
    """Create a DSA/platform content report.

    reporter: the User (not RecipeAuthor) submitting the report.
    content_kind: one of ContentReport.ContentKind values.
    object_id: PK of the reported object.
    reason: free-text reason (shown to moderators).
    Returns the created ContentReport.
    """
    from .models import ContentReport, LedgerEvent

    report = ContentReport.objects.create(
        reporter=reporter,
        content_kind=content_kind,
        object_id=object_id,
        reason=reason,
        status=ContentReport.Status.PENDING,
    )

    reporter_author = getattr(reporter, "recipe_author", None)
    LedgerEvent.objects.create(
        event_type=LedgerEvent.EventType.CONTENT_REPORT,
        actor=reporter_author,
        payload={
            "report_id": report.pk,
            "content_kind": content_kind,
            "object_id": object_id,
        },
    )
    return report


# ── Reward Agreement ─────────────────────────────────────────────────────────

REWARD_AGREEMENT_TEXT_v1 = """CHEF BATTLE REWARD AGREEMENT

By accepting this agreement you confirm that you have read and understood the following terms.

1. NATURE OF REWARDS
CulinEire Chef Battle Rewards (CBR) and Live Support Rewards (LSR) are discretionary platform rewards granted at the sole discretion of CulinEire. They are not money, not user funds, not e-money, and confer no legal right to payment.

2. CONVERSION AND PAYOUT
Approved reward tokens may be converted to real-money payouts at a rate of €0.025 per token, subject to a minimum threshold of 2,000 approved reward tokens. The payout rate may change for future reward grants; the rate is locked at request time.

3. ELIGIBILITY CONDITIONS
Payout requests are subject to: (a) age verification (18+); (b) completion of Stripe Connect onboarding; (c) no active fraud flags, suspensions, or compliance holds; and (d) acceptance of this agreement.

4. REVERSAL AND FORFEITURE
The platform reserves the right to reverse, void, or expire rewards at any time for breach of Chef Battles rules, fraudulent activity, chargebacks, or material policy violations.

5. TAX AND REPORTING (DAC7)
Payouts are subject to EU Directive 2021/514 (DAC7 / MRDP) reporting obligations. By accepting, you consent to the collection of your identity and income data and its annual reporting to Irish Revenue where applicable thresholds are met. Data is retained for 10 years.

6. GOVERNING LAW
This agreement is governed by the laws of Ireland. Disputes are subject to the exclusive jurisdiction of the Irish courts.

CulinEire is a trading name of Bearcave Limited, registered in Ireland."""


def accept_reward_agreement(chef, ip_address: str = "", user_agent: str = "") -> "ChefRewardAgreement":
    """Record a chef's acceptance of the Chef Reward Agreement and set the profile flag."""
    from .models import ChefBattleProfile, ChefRewardAgreement

    agreement = ChefRewardAgreement.objects.create(
        chef=chef,
        agreement_version="1.0",
        consent_text_snapshot=REWARD_AGREEMENT_TEXT_v1,
        ip_address=ip_address or None,
        user_agent=user_agent[:512] if user_agent else "",
    )
    ChefBattleProfile.objects.filter(author=chef).update(reward_agreement_accepted=True)
    logger.info("Chef %s accepted Reward Agreement v1.0", chef)
    return agreement


# ── Forbidden claims detection (PDF v6 §30) ──────────────────────────────────

_FORBIDDEN_PHRASES = [
    "safe for all allerg",
    "free from all allerg",
    "suitable for all allerg",
    "cures diabetes",
    "cures cancer",
    "prevents disease",
    "eliminates disease",
    "clinically proven",
    "medically proven",
    "doctor recommended",
    "guaranteed weight loss",
    "burn fat fast",
    "detox your body",
    "cleanse your body",
    "boost your immune system",
    "no risk",
    "100% safe",
    "completely safe for",
]


def check_forbidden_claims(text: str) -> list[str]:
    """Return list of forbidden phrases found in text (case-insensitive). Empty list = clean."""
    lower = (text or "").lower()
    return [phrase for phrase in _FORBIDDEN_PHRASES if phrase in lower]
