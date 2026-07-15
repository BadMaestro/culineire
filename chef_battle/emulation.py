"""Battle emulation for the Arena Master Console (owner-only).

Drives a complete battle between two dedicated bot chefs through the REAL
domain services — nothing is short-circuited, so every screen, poll, event
and invariant behaves exactly as in a live battle. One `emulation_step`
call advances exactly one lifecycle stage, letting the owner watch each
phase in the console and on the public arena.

Bots are isolated accounts (emu-chef-alpha / emu-chef-beta); no tokens are
purchased, no payouts are possible, no real user data is touched.
"""
from __future__ import annotations

import io
import random

from django.db import transaction
from django.utils import timezone

from .models import (
    Battle, BattleEntry, BattleVote, ChefBattleProfile,
    IngredientLock, IngredientShot,
)
from .services import (
    OperatorActionError, _operator_event, _require_owner,
    approve_cooking_phase, fire_ingredient_shot, place_ingredient_lock,
    reveal_entries_if_ready, submit_battle_entry, submit_combat_action,
    submit_cooked_photo, calculate_battle_result,
)

EMU_THEME_PREFIX = "EMULATION"
EMU_CHEFS = (
    ("emu-chef-alpha", "EMU Chef Alpha"),
    ("emu-chef-beta", "EMU Chef Beta"),
)
EMU_INGREDIENTS = [
    "500g potatoes", "2 leeks", "100g butter", "200ml cream",
    "1 loaf soda bread", "fresh parsley",
]
MAX_COMBAT_ROUNDS = 30


def _get_or_create_bot(slug: str, name: str):
    from django.contrib.auth import get_user_model
    from recipes.models import RecipeAuthor

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username=slug, defaults={"is_active": True},
    )
    author, _ = RecipeAuthor.objects.get_or_create(
        slug=slug, defaults={"user": user, "name": name},
    )
    if author.user_id is None:
        author.user = user
        author.save(update_fields=["user"])
    profile, _ = ChefBattleProfile.objects.get_or_create(author=author)
    changed = []
    if not profile.enrolled_at:
        profile.enrolled_at = timezone.now()
        changed.append("enrolled_at")
    if not profile.infinite_moves:
        profile.infinite_moves = True  # bots never run out of energy
        changed.append("infinite_moves")
    if changed:
        profile.save(update_fields=changed)
    return author


def _bot_recipe(author, tag: str):
    from recipes.models import Recipe

    slug = f"emu-dish-{author.slug}-{tag}"
    recipe, _ = Recipe.objects.get_or_create(
        slug=slug,
        defaults={
            "title": f"EMU Dish {author.name} {tag}",
            "author": author,
            "short_description": "Emulation-only test dish.",
            "ingredients": "\n".join(EMU_INGREDIENTS),
            "method": "Step one: emulate.\nStep two: serve.",
            "status": Recipe.Status.DRAFT,  # never public
            "source_type": Recipe.SourceType.OTHER,
            "source_note": "Battle emulation test data. Not a real recipe.",
        },
    )
    return recipe


def _placeholder_photo(name: str):
    from django.core.files.base import ContentFile
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 480), (34, 58, 46))
    draw = ImageDraw.Draw(img)
    draw.text((40, 220), f"EMULATION PHOTO — {name}", fill=(247, 242, 234))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return ContentFile(buf.getvalue(), name=f"emu-{name}.jpg")


def start_emulation(*, operator_author, correlation_id="") -> Battle:
    """Create a fresh SCHEDULED emulation battle between the two bots."""
    _require_owner(operator_author)

    existing = Battle.objects.filter(
        theme__startswith=EMU_THEME_PREFIX,
        status__in=list(Battle.ACTIVE_STATUSES) + [
            Battle.Status.INGREDIENT_PENALTY, Battle.Status.PAUSED,
        ],
    ).first()
    if existing:
        raise OperatorActionError(
            f"Emulation battle #{existing.pk} is already running "
            f"({existing.status}). Finish or cancel it first."
        )

    alpha = _get_or_create_bot(*EMU_CHEFS[0])
    beta = _get_or_create_bot(*EMU_CHEFS[1])
    now = timezone.now()
    battle = Battle.objects.create(
        challenger=alpha,
        opponent=beta,
        theme=f"{EMU_THEME_PREFIX} {now:%Y-%m-%d %H:%M}",
        status=Battle.Status.SCHEDULED,
        start_time=now,
        submission_deadline=now + timezone.timedelta(days=1),
        voting_deadline=now + timezone.timedelta(days=2),
        end_time=now + timezone.timedelta(days=3),
    )
    _operator_event(
        battle=battle, operator_author=operator_author,
        action="emulation_start", before="-", after=battle.status,
        reason="Owner started a battle emulation",
        correlation_id=correlation_id,
        extra={"bots": [alpha.slug, beta.slug]},
    )
    return battle


def emulation_step(*, battle_id, operator_author, correlation_id="") -> dict:
    """Advance the emulation battle by exactly one lifecycle stage."""
    _require_owner(operator_author)
    try:
        battle = Battle.objects.select_related("challenger", "opponent").get(
            pk=battle_id)
    except Battle.DoesNotExist:
        raise OperatorActionError("Battle not found.")
    if not battle.theme.startswith(EMU_THEME_PREFIX):
        raise OperatorActionError("Not an emulation battle.")

    before = battle.status
    alpha, beta = battle.challenger, battle.opponent
    detail = {}

    if before == Battle.Status.SCHEDULED:
        battle.challenger_ready = True
        battle.opponent_ready = True
        battle.status = Battle.Status.MENU_LOCKED
        battle.save(update_fields=[
            "challenger_ready", "opponent_ready", "status", "updated_at"])
        detail = {"note": "both bots marked ready (antechamber)"}

    elif before == Battle.Status.MENU_LOCKED:
        tag = f"{battle.pk}"
        for bot in (alpha, beta):
            if not battle.entries.filter(author=bot).exists():
                submit_battle_entry(
                    battle=battle, author=bot,
                    recipe=_bot_recipe(bot, tag),
                    battle_statement=f"{bot.name} enters the emulation.",
                )
        reveal_entries_if_ready(battle)
        battle.refresh_from_db()
        detail = {"note": "menus declared and revealed, combat begins"}

    elif before == Battle.Status.ACTIVE:
        rounds = 0
        while battle.status == Battle.Status.ACTIVE and rounds < MAX_COMBAT_ROUNDS:
            for bot in (alpha, beta):
                submit_combat_action(
                    battle, bot,
                    random.choice(["attack", "defend"]),
                    random.randint(1, 3),
                )
            battle.refresh_from_db()
            rounds += 1
        last = battle.combat_rounds.order_by("-round_number").first()
        detail = {
            "note": f"combat resolved in {rounds} round(s)",
            "hits": f"{last.challenger_hits}:{last.opponent_hits}" if last else "0:0",
        }

    elif before == Battle.Status.INGREDIENT_PENALTY:
        loser, winner = battle.loser, battle.winner
        n = len(EMU_INGREDIENTS)
        lock_indices = random.sample(range(n), IngredientLock.MAX_LOCKS)
        for idx in lock_indices:
            if battle.ingredient_locks.filter(chef=loser).count() >= IngredientLock.MAX_LOCKS:
                break
            try:
                place_ingredient_lock(battle=battle, chef=loser, ingredient_index=idx)
            except ValueError:
                pass
        shots = 0
        for idx in random.sample(range(n), n):
            if shots >= IngredientShot.MAX_SHOTS:
                break
            try:
                fire_ingredient_shot(battle=battle, shooter=winner, target_index=idx)
                shots += 1
            except ValueError:
                pass
        approve_cooking_phase(battle, operator_author)
        battle.refresh_from_db()
        detail = {"note": "biathlon played (locks + shots), cooking approved"}

    elif before == Battle.Status.COOKING:
        from .services import operator_moderate_entry
        for bot in (alpha, beta):
            entry = BattleEntry.objects.get(battle=battle, author=bot)
            if not entry.cooked_photo:
                submit_cooked_photo(
                    battle=battle, author=bot,
                    photo=_placeholder_photo(bot.slug),
                    real_photo_confirmed=True,
                )
        for bot in (alpha, beta):
            entry = BattleEntry.objects.get(battle=battle, author=bot)
            if entry.moderation_status != BattleEntry.ModerationStatus.APPROVED:
                operator_moderate_entry(
                    entry_id=entry.pk, operator_author=operator_author,
                    new_status=BattleEntry.ModerationStatus.APPROVED,
                    correlation_id=correlation_id,
                )
        battle.refresh_from_db()
        detail = {"note": "cooked photos submitted and approved"}

    elif before == Battle.Status.PRESENTATION:
        battle.status = Battle.Status.VOTING
        battle.save(update_fields=["status", "updated_at"])
        detail = {"note": "voting opened"}

    elif before == Battle.Status.VOTING:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        favourite = random.choice([alpha, beta])
        created = 0
        for i in range(random.randint(5, 9)):
            voter, _ = User.objects.get_or_create(
                username=f"emu-voter-{i}", defaults={"is_active": True})
            target = favourite if random.random() < 0.7 else (
                beta if favourite is alpha else alpha)
            _, was_created = BattleVote.objects.get_or_create(
                battle=battle, voter=voter, defaults={"voted_for": target})
            created += int(was_created)
        calculate_battle_result(battle)
        battle.refresh_from_db()
        detail = {"note": f"{created} synthetic vote(s) cast, result calculated",
                  "winner": battle.winner.slug if battle.winner else None}

    else:
        raise OperatorActionError(
            f"Emulation battle is '{before}' — no automatic step from here. "
            "Use Resume/Cancel or start a new emulation.")

    _operator_event(
        battle=battle, operator_author=operator_author,
        action="emulation_step", before=before, after=battle.status,
        reason=detail.get("note", ""), correlation_id=correlation_id,
        extra=detail,
    )
    return {"battle_id": battle.pk, "before": before,
            "after": battle.status, **detail}
