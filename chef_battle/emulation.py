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
    Battle, BattleEntry, BattleIngredient, BattleVote, ChefBattleProfile,
    IngredientShot,
)
from .services import (
    OperatorActionError, _operator_event, _require_owner,
    approve_cooking_phase, declare_menu, fire_ingredient_shot,
    submit_battle_entry, submit_combat_action,
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

    alpha = _get_or_create_bot(*EMU_CHEFS[0])
    beta = _get_or_create_bot(*EMU_CHEFS[1])

    with transaction.atomic():
        # F53, 2026-08-11: the "one already running" check and the battle it
        # creates had no lock and no transaction between them - a double-
        # click could pass the check twice before either battle existed,
        # starting two emulation battles at once. There is no single row
        # that naturally represents "an emulation is running" to lock, so
        # lock one of the two bots' own profile rows instead: every
        # emulation always uses the SAME two bots, so a second concurrent
        # start blocks here until the first commits, then correctly sees
        # its battle in the check below.
        ChefBattleProfile.objects.select_for_update().get(author=alpha)
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


@transaction.atomic
def emulation_step(*, battle_id, operator_author, correlation_id="") -> dict:
    """Advance the emulation battle by exactly one lifecycle stage.

    F53, 2026-08-11: wrapped in one transaction, with the battle row locked
    for its whole duration - a double-click on the step button, or this call
    racing a Master Console Cancel on the same emulation battle, used to have
    nothing serialising them, so a concurrent cancellation could be silently
    overwritten by an in-flight step. The domain services called from each
    branch below (approve_cooking_phase, calculate_battle_result, etc.) take
    the same row lock themselves; re-acquiring it here first is safe - a
    connection never blocks on a lock it already holds.
    """
    _require_owner(operator_author)
    try:
        battle = Battle.objects.select_related("challenger", "opponent").select_for_update().get(
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
        # T11, 2026-08-15: THE EMULATOR NOW REALLY DECLARES THE MENUS. Its own
        # note has always said "menus declared" and it never declared one -
        # it submitted entries and moved on, so an emulated battle reached the
        # biathlon with no BattleIngredient rows at all. That was invisible
        # while the biathlon shot at raw recipe TEXT lines; it is fatal now
        # that the winner shoots at the loser's declared list, and it is why
        # production carried five old lock/shot rows against zero declared
        # ingredients. Each bot declares the same six ingredients with the
        # first two marked key - both chefs, exactly KEY_COUNT, before Stage 1,
        # which is the rule declare_menu itself enforces.
        for bot in (alpha, beta):
            if not battle.entries.filter(author=bot).exists():
                submit_battle_entry(
                    battle=battle, author=bot,
                    recipe=_bot_recipe(bot, tag),
                    battle_statement=f"{bot.name} enters the emulation.",
                )
        # declare_menu is what carries MENU_LOCKED -> ACTIVE, and it must run
        # while the battle is still MENU_LOCKED, so it goes after the entries
        # exist and before anything else touches the status.
        #
        # reveal_entries_if_ready is NOT called here any more, and that is the
        # whole reason this step is ordered rather than incidental: it used to
        # be what advanced MENU_LOCKED -> ACTIVE when no menu was ever
        # declared. Now that declare_menu does that, calling reveal on an
        # ACTIVE battle whose entries already carry dish_submitted_at would
        # take the OTHER branch and jump straight to VOTING - skipping combat,
        # the biathlon and cooking entirely. The real flow reveals when the
        # battle leaves ACTIVE for VOTING, and so does the emulator now.
        for bot in (alpha, beta):
            if not battle.battle_ingredients.filter(chef=bot).exists():
                declare_menu(
                    battle=battle, chef=bot,
                    ingredients=[
                        {"name": name, "is_key": index < BattleIngredient.KEY_COUNT}
                        for index, name in enumerate(EMU_INGREDIENTS)
                    ],
                )
                battle.refresh_from_db()
        detail = {"note": "both menus declared (two blocks each), combat begins"}

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
        # T11: no locking step - both bots blocked two ingredients back at
        # declare_menu. Only the Stage 1 winner shoots, at the loser's own
        # declared list, and a shot at one of his two blocks bounces.
        loser, winner = battle.loser, battle.winner
        targets = list(
            battle.battle_ingredients.filter(chef=loser, is_eliminated=False)
            .order_by("position").values_list("pk", flat=True)
        )
        random.shuffle(targets)
        shots = 0
        for target_id in targets:
            if shots >= IngredientShot.MAX_SHOTS:
                break
            try:
                fire_ingredient_shot(
                    battle=battle, shooter=winner, target_ingredient_id=target_id,
                )
                shots += 1
            except ValueError:
                pass
        approve_cooking_phase(battle, operator_author)
        battle.refresh_from_db()
        detail = {"note": f"biathlon played ({shots} shots fired), cooking approved"}

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


# ── MC01, scenario B: the withdrawal, run for real ───────────────────────────
#
# The Owner deleted the first MC01 on the day it shipped: it walked the
# withdrawal through the console as step cards, three columns of text per step,
# and being a DESCRIPTION was the whole problem. He checks the product by
# looking at the arena.
#
# So this is the same three steps as `withdrawal_service`, performed rather than
# narrated: the bot asks, the other bot answers, a moderator rules. Everything
# goes through the real service - the allowance is really spent, the battle
# really ends CANCELLED, the penalty is really applied by penalise() - so what
# he sees on the arena is what a chef would cause.
#
# WHAT IT DELIBERATELY DOES NOT DO: decide what any of it LOOKS like. The rows
# of ARENA_EMULATION_VISUAL_STEPS.md for this scenario are TO SPEC and stay that
# way until he says what should appear on the screen. This builds the states; he
# says how they read.

WITHDRAWAL_STEPS = ("ask", "answer", "verdict")


def emulation_withdrawal_step(*, battle_id, operator_author, step,
                              with_penalty=True, correlation_id="") -> dict:
    """Perform one step of a withdrawal on the emulation battle.

    step="ask"     - the challenger bot asks to withdraw, spending an allowance
    step="answer"  - the opponent bot answers, with or without a penalty
    step="verdict" - the operator, as moderator, closes it
    """
    from .models import BattleWithdrawal
    from .withdrawal_service import (
        decide_withdrawal, open_withdrawal_for, request_withdrawal,
        resolve_withdrawal, withdrawals_left, WithdrawalNotAllowed,
    )

    _require_owner(operator_author)
    if step not in WITHDRAWAL_STEPS:
        raise OperatorActionError(f"Unknown withdrawal step '{step}'.")
    try:
        battle = Battle.objects.select_related("challenger", "opponent").get(pk=battle_id)
    except Battle.DoesNotExist:
        raise OperatorActionError("Battle not found.")
    if not battle.theme.startswith(EMU_THEME_PREFIX):
        raise OperatorActionError("Not an emulation battle.")

    before = battle.status
    open_request = open_withdrawal_for(battle)

    try:
        if step == "ask":
            if open_request is not None:
                raise OperatorActionError("This battle already has an open withdrawal.")
            withdrawal = request_withdrawal(
                battle=battle, author=battle.challenger,
                reason="Emulation: the kitchen flooded an hour before service.",
            )
            detail = {
                "note": "withdrawal asked for",
                "allowance_left": withdrawals_left(battle.challenger),
            }
        elif step == "answer":
            if open_request is None:
                raise OperatorActionError("Nothing to answer - ask first.")
            withdrawal = decide_withdrawal(
                withdrawal=open_request, author=battle.opponent,
                with_penalty=bool(with_penalty),
                opponent_reason=("Emulation: this is the third time." if with_penalty else ""),
            )
            detail = {"note": f"other chef answered: {withdrawal.opponent_decision}"}
        else:
            if open_request is None:
                raise OperatorActionError("Nothing to rule on.")
            if open_request.status != BattleWithdrawal.Status.AWAITING_MODERATOR:
                raise OperatorActionError("The other chef has not answered yet.")
            uphold = open_request.opponent_decision == BattleWithdrawal.OpponentDecision.WITH_PENALTY
            withdrawal = resolve_withdrawal(
                withdrawal=open_request,
                moderator=getattr(operator_author, "user", None),
                uphold_penalty=uphold,
                note="Emulation: moderator upheld the other chef's answer.",
            )
            detail = {
                "note": "moderator closed it",
                "penalty_applied": withdrawal.penalty_applied,
            }
    except WithdrawalNotAllowed as exc:
        raise OperatorActionError(str(exc)) from exc

    battle.refresh_from_db()
    _operator_event(
        battle=battle, operator_author=operator_author,
        action=f"emulation_withdrawal_{step}", before=before, after=battle.status,
        reason=detail.get("note", ""), correlation_id=correlation_id, extra=detail,
    )
    return {"battle_id": battle.pk, "step": step, "before": before,
            "after": battle.status, **detail}
