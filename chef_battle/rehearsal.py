"""Scenario A of the arena rehearsal: a real battle, in the format of a test.

The Owner, 2026-09-04:

    A REAL BATTLE, BUT IN TEST FORMAT. Two test accounts - Jam O'Liver and
    CrestedTen - appear in the octagon and LIVE the scenario written in the
    Chef Battle rules from beginning to end, on the main Arena and not in the
    master console. We do not wait for timers, nobody goes shopping, and we sit
    and record the bugs and the gaps.

WHAT THIS MODULE IS. An instrument, not an engine. Every step below performs
its move through the SAME production form, view or service a person uses; the
combat engine decides the fight, the sweepers make the timed transitions, and
nothing here scores anything. When a step finds that production has no way to
do the thing at all, it records MISSING_MECHANISM and moves on - it does not
invent a shortcut, because a shortcut would hide exactly the hole the run
exists to find.

HOW TIME IS HANDLED, and why it is not a bypass. The rules put twelve hours on
a challenge, forty-eight on preparation and thirty minutes between "both ready"
and the first course. The rehearsal does not skip those transitions - it makes
them DUE, by moving the battle's own deadline into the past, and then calls the
real sweeper that a cron calls every fifteen minutes. The transition is
performed by production code, on production rules; only the clock is hurried.

WHAT IS NEVER DONE HERE: no force_status, no winner set by hand, no fabricated
combat result, and `greenbear` never appears in a battle - AGENTS.md 1a and 18.
"""
from __future__ import annotations

import io
import random
import uuid

from django.db import transaction
from django.utils import timezone

from .models import Battle, BattleIngredient, RehearsalRun, RehearsalStep
from .services import OperatorActionError, _require_owner

# The Owner's own two test chefs. They already exist on production; the
# rehearsal finds them and refuses to invent them, because an account it made
# up would not be the account he watches.
REHEARSAL_CHEFS = ("jam-oliver", "crestedten")

# Every row the rehearsal creates carries this in a free-text field, so a purge
# can find its own litter by an exact mark rather than by guesswork.
REHEARSAL_MARK = "REHEARSAL"

INGREDIENTS = [
    "1kg lamb shoulder", "6 rooster potatoes", "3 carrots", "2 onions",
    "1 bunch thyme", "500ml lamb stock",
]
MAX_COMBAT_ROUNDS = 30


class RehearsalError(OperatorActionError):
    """A rehearsal could not continue. Distinct so the console can say so."""


# -- the record --------------------------------------------------------------

def _record(run, *, key, title, outcome, mechanism="", detail=""):
    position = run.steps.count() + 1
    step = RehearsalStep.objects.create(
        run=run, position=position, key=key, title=title,
        outcome=outcome, mechanism=mechanism, detail=detail or "",
    )
    if outcome == RehearsalStep.Outcome.FORCED:
        run.is_tainted = True
        run.save(update_fields=["is_tainted"])
    return step


def _chefs():
    from django.conf import settings
    from recipes.models import RecipeAuthor

    found = {a.slug: a for a in RecipeAuthor.objects.filter(slug__in=REHEARSAL_CHEFS)}
    missing = [s for s in REHEARSAL_CHEFS if s not in found]
    if missing:
        raise RehearsalError(
            "The rehearsal chefs are missing: %s. They are the Owner's own test "
            "accounts and the rehearsal will not invent them." % ", ".join(missing)
        )
    # AGENTS.md 18: the Owner's account is not a fighter, in a rehearsal least
    # of all. This is belt and braces - his slug is not in the list above - but
    # the guard is cheap and the rule is absolute.
    for slug in REHEARSAL_CHEFS:
        if slug == settings.OWNER_SLUG:
            raise RehearsalError("The Owner's account may never enter a battle.")
    return found[REHEARSAL_CHEFS[0]], found[REHEARSAL_CHEFS[1]]


def _placeholder_image(label: str):
    from django.core.files.base import ContentFile
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1200, 800), (28, 46, 38))
    ImageDraw.Draw(img).text((40, 380), "REHEARSAL - %s" % label, fill=(244, 238, 226))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return ContentFile(buf.getvalue(), name="rehearsal-%s.jpg" % label)


def _hurry(battle, field, *, seconds_ago=5):
    """Make a deadline DUE instead of skipping the transition it guards."""
    setattr(battle, field, timezone.now() - timezone.timedelta(seconds=seconds_ago))
    battle.save(update_fields=[field, "updated_at"])


def _battle_of(run):
    if run.battle_id is None:
        raise RehearsalError("This run has no battle yet - accept the challenge first.")
    run.battle.refresh_from_db()
    return run.battle


# -- the steps ---------------------------------------------------------------
#
# Each returns a dict for the record. They run one per operator press, so the
# Owner can look at the arena between any two of them.

def _step_cast(run, rng):
    from .services import get_or_create_battle_profile

    jam, crested = _chefs()
    for author in (jam, crested):
        profile = get_or_create_battle_profile(author)
        if not profile.enrolled_at:
            profile.enrolled_at = timezone.now()
            profile.save(update_fields=["enrolled_at"])
    return {
        "outcome": RehearsalStep.Outcome.PASS,
        "mechanism": "services.get_or_create_battle_profile",
        "detail": "%s and %s are enrolled and on the floor." % (jam.name, crested.name),
    }


def _step_recipe(run, rng):
    """Jam O'Liver writes the dish, through the authoring form a person uses."""
    from recipes.forms import RecipeAuthoringForm
    from recipes.models import Recipe

    jam, _crested = _chefs()
    existing = Recipe.objects.filter(
        author=jam, source_note__startswith=REHEARSAL_MARK, is_deleted=False,
    ).order_by("-created_at").first()
    if existing:
        return {
            "outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "recipes.forms.RecipeAuthoringForm",
            "detail": "Reusing the rehearsal dish '%s' (#%d)." % (existing.title, existing.pk),
        }

    form = RecipeAuthoringForm(
        data={
            "title": "Rehearsal Lamb and Rooster Potatoes",
            "short_description": "The dish the rehearsal cooks. Not a real recipe.",
            "hero_image_alt_text": "A rehearsal placeholder image.",
            "category": Recipe.Category.choices[0][0],
            "difficulty": Recipe.Difficulty.MEDIUM,
            "prep_time_minutes": 20, "cook_time_minutes": 90,
            "servings": 4, "calories": 620,
            "ingredients": "\n".join(INGREDIENTS),
            "method": "Brown the lamb.\nAdd the roots.\nBraise until it gives.",
            "source_type": Recipe.SourceType.OTHER,
            "source_note": "%s - arena rehearsal test data, not a real recipe." % REHEARSAL_MARK,
            "image_rights_status": Recipe.ImageRightsStatus.OWN,
            "confirm_own_work": True,
            "confirm_image_rights": True,
            "confirm_rules": True,
        },
        files={"hero_image": _placeholder_image("dish")},
    )
    if not form.is_valid():
        return {
            "outcome": RehearsalStep.Outcome.FAIL,
            "mechanism": "recipes.forms.RecipeAuthoringForm",
            "detail": "The authoring form a chef uses rejected the rehearsal dish: %s"
                      % form.errors.as_text(),
        }
    recipe = form.save(commit=False)
    recipe.author = jam
    # THE OWNER'S RULING, 2026-09-04: "for the test, the recipe does not need
    # approving." So the rehearsal does not queue it for moderation - it stands
    # approved, because the challenge form will only carry an approved recipe.
    recipe.status = Recipe.Status.APPROVED
    recipe.save()
    form.save_additional_categories(recipe)
    return {
        "outcome": RehearsalStep.Outcome.MISSING,
        "mechanism": "recipes.forms.RecipeAuthoringForm",
        "detail": (
            "Dish #%d written and standing approved. BUT he asked for it to stay "
            "officially unpublished and hidden, and a Recipe has no such state: "
            "status carries both 'a battle may use it' and 'the site shows it', so "
            "approving it for the challenge form also publishes it. There is no "
            "hide-from-the-site field to set." % recipe.pk
        ),
    }


def _step_challenge(run, rng):
    """CrestedTen issues the challenge, through the real challenge form."""
    from recipes.models import Recipe

    from .forms import BattleChallengeForm
    from .models import BattleChallenge

    jam, crested = _chefs()
    open_challenge = BattleChallenge.objects.filter(
        challenger=crested, opponent=jam, status=BattleChallenge.Status.PENDING,
    ).first()
    if open_challenge:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "chef_battle.forms.BattleChallengeForm",
                "detail": "Challenge #%d already stands." % open_challenge.pk}

    # The challenger needs an approved recipe of his own to carry into the
    # battle - the form requires it, and that requirement is the product rule,
    # not an accident, so the rehearsal obeys it rather than loosening it.
    theme_recipe = Recipe.objects.filter(
        author=crested, status=Recipe.Status.APPROVED, is_deleted=False,
    ).order_by("-created_at").first()
    if theme_recipe is None:
        return {
            "outcome": RehearsalStep.Outcome.FAIL,
            "mechanism": "chef_battle.forms.BattleChallengeForm",
            "detail": "%s has no approved recipe to carry into a battle, and the "
                      "challenge form requires one." % crested.name,
        }

    form = BattleChallengeForm(
        data={
            "opponent": jam.pk,
            "task_kind": BattleChallenge.TaskKind.NEW_RECIPE,
            "theme_recipe": theme_recipe.pk,
            "theme": "%s: Lamb, done properly" % REHEARSAL_MARK,
            "battle_type": BattleChallenge.BattleType.PHOTO,
            "message": "A rehearsal challenge. Everything about it is real except "
                       "the reason for it.",
        },
        challenger=crested,
    )
    if not form.is_valid():
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "chef_battle.forms.BattleChallengeForm",
                "detail": "The challenge form rejected it: %s" % form.errors.as_text()}
    challenge = form.save()
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "chef_battle.forms.BattleChallengeForm",
            "detail": "Challenge #%d sent to %s, standing for twelve hours."
                      % (challenge.pk, jam.name)}


def _step_accept(run, rng):
    from .models import BattleChallenge
    from .services import accept_challenge

    jam, crested = _chefs()
    challenge = BattleChallenge.objects.filter(
        challenger=crested, opponent=jam, status=BattleChallenge.Status.PENDING,
    ).order_by("-created_at").first()
    if challenge is None:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.accept_challenge",
                "detail": "There is no pending challenge to accept."}
    try:
        battle = accept_challenge(challenge)
    except ValueError as exc:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.accept_challenge",
                "detail": "Acceptance refused: %s" % exc}
    run.battle = battle
    run.save(update_fields=["battle"])
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.accept_challenge",
            "detail": "Battle #%d exists, %s, starting %s."
                      % (battle.pk, battle.status, battle.start_time)}


def _step_entry(run, rng):
    """The challenged chef attaches his own dish during the preparation window.

    Accepting the challenge attaches the CHALLENGER's recipe and only his. The
    other chef brings his own, which is what the dish written back at step 2
    was for - and without it he reaches the cooking phase with no entry to
    photograph at all.
    """
    from recipes.models import Recipe

    from .services import submit_battle_entry

    battle = _battle_of(run)
    jam, _crested = _chefs()
    if battle.entries.filter(author=jam).exists():
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.submit_battle_entry",
                "detail": "%s has already entered his dish." % jam.name}
    recipe = Recipe.objects.filter(
        author=jam, source_note__startswith=REHEARSAL_MARK, is_deleted=False,
    ).order_by("-created_at").first()
    if recipe is None:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.submit_battle_entry",
                "detail": "The rehearsal dish is gone - step 2 has to run first."}
    entry = submit_battle_entry(
        battle=battle, author=jam, recipe=recipe,
        battle_statement="%s answers with his own dish." % jam.name,
    )
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.submit_battle_entry",
            "detail": "Entry #%d attached for %s. Both chefs are now in."
                      % (entry.pk, jam.name)}


def _step_ready(run, rng):
    """Both chefs press Ready - through the view that owns that logic.

    The readiness gate lives in `views.battle_set_ready` and nowhere else:
    there is no service for it. So the rehearsal calls the view, with a real
    request for each chef, rather than writing the two flags itself.
    """
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore
    from django.test import RequestFactory

    from .views import battle_set_ready

    battle = _battle_of(run)
    if battle.status != Battle.Status.SCHEDULED:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "views.battle_set_ready",
                "detail": "Already past readiness (%s)." % battle.status}

    factory = RequestFactory()
    for author in (battle.challenger, battle.opponent):
        request = factory.post("/chef-battle/battles/%d/ready/" % battle.pk)
        request.user = author.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        battle_set_ready(request, pk=battle.pk)
    battle.refresh_from_db()
    return {
        "outcome": RehearsalStep.Outcome.MISSING,
        "mechanism": "views.battle_set_ready",
        "detail": (
            "Both chefs are ready and the start was pulled in. Recorded as a gap "
            "because the readiness rule exists ONLY inside the view - there is no "
            "service another surface (console, sweeper, this rehearsal) can call, "
            "so every other caller has to fake an HTTP request to reach it."
        ),
    }


def _step_start(run, rng):
    """The clock runs out and the real sweeper begins the battle."""
    from .services import resolve_start_rituals

    battle = _battle_of(run)
    if battle.status != Battle.Status.SCHEDULED:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.resolve_start_rituals",
                "detail": "Already begun (%s)." % battle.status}
    _hurry(battle, "start_time")
    resolved = resolve_start_rituals()
    battle.refresh_from_db()
    began = battle.status != Battle.Status.SCHEDULED
    return {"outcome": RehearsalStep.Outcome.PASS if began else RehearsalStep.Outcome.FAIL,
            "mechanism": "services.resolve_start_rituals",
            "detail": "Start time hurried to now; the sweeper resolved %d battle(s) "
                      "and this one is %s." % (resolved, battle.status)}


def _step_menu(run, rng):
    from .services import declare_menu

    battle = _battle_of(run)
    if battle.status != Battle.Status.MENU_LOCKED:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.declare_menu",
                "detail": "Menus are behind us (%s)." % battle.status}
    declared = []
    for chef in (battle.challenger, battle.opponent):
        if battle.battle_ingredients.filter(chef=chef).exists():
            continue
        order = list(INGREDIENTS)
        rng.shuffle(order)
        declare_menu(
            battle=battle, chef=chef,
            ingredients=[{"name": name, "is_key": i < BattleIngredient.KEY_COUNT}
                         for i, name in enumerate(order)],
        )
        declared.append(chef.name)
        battle.refresh_from_db()
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.declare_menu",
            "detail": "Menus declared by %s. The battle is %s."
                      % (", ".join(declared) or "nobody new", battle.status)}


def _step_combat(run, rng):
    from .services import submit_combat_action

    battle = _battle_of(run)
    if battle.status != Battle.Status.ACTIVE:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.submit_combat_action",
                "detail": "Combat is not open (%s)." % battle.status}
    rounds = 0
    while battle.status == Battle.Status.ACTIVE and rounds < MAX_COMBAT_ROUNDS:
        for chef in (battle.challenger, battle.opponent):
            submit_combat_action(
                battle, chef, rng.choice(["attack", "defend"]), rng.randint(1, 3))
        battle.refresh_from_db()
        rounds += 1
    last = battle.combat_rounds.order_by("-round_number").first()
    score = "%d:%d" % (last.challenger_hits, last.opponent_hits) if last else "0:0"
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.submit_combat_action -> services._resolve_round",
            "detail": "The engine settled it in %d round(s); last round %s. Now %s."
                      % (rounds, score, battle.status)}


def _step_biathlon(run, rng):
    from .models import IngredientShot
    from .services import approve_cooking_phase, fire_ingredient_shot

    battle = _battle_of(run)
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.fire_ingredient_shot",
                "detail": "No penalty window open (%s)." % battle.status}
    targets = list(
        battle.battle_ingredients.filter(chef=battle.loser, is_eliminated=False)
        .order_by("position").values_list("pk", flat=True))
    rng.shuffle(targets)
    fired = 0
    for target_id in targets:
        if fired >= IngredientShot.MAX_SHOTS:
            break
        try:
            fire_ingredient_shot(battle=battle, shooter=battle.winner,
                                 target_ingredient_id=target_id)
            fired += 1
        except ValueError:
            pass
    approve_cooking_phase(battle, run.started_by)
    battle.refresh_from_db()
    return {
        "outcome": RehearsalStep.Outcome.MISSING,
        "mechanism": "services.fire_ingredient_shot, services.approve_cooking_phase",
        "detail": (
            "%d shot(s) fired and cooking approved. Recorded as a gap because the "
            "approval was made by the OPERATOR: nothing in production carries "
            "INGREDIENT_PENALTY to COOKING on its own when the window closes."
            % fired
        ),
    }


def _step_cook(run, rng):
    from .services import submit_cooked_photo

    battle = _battle_of(run)
    if battle.status != Battle.Status.COOKING:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.submit_cooked_photo",
                "detail": "Not cooking (%s)." % battle.status}
    for chef in (battle.challenger, battle.opponent):
        entry = battle.entries.filter(author=chef).first()
        if entry and entry.cooked_photo:
            continue
        submit_cooked_photo(battle=battle, author=chef,
                            photo=_placeholder_image(chef.slug),
                            real_photo_confirmed=True)
    battle.refresh_from_db()
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.submit_cooked_photo",
            "detail": "Both dishes photographed and submitted. The battle is %s."
                      % battle.status}


def _step_moderate(run, rng):
    from .models import BattleEntry
    from .services import operator_moderate_entry

    battle = _battle_of(run)
    pending = list(battle.entries.exclude(
        moderation_status=BattleEntry.ModerationStatus.APPROVED))
    for entry in pending:
        operator_moderate_entry(
            entry_id=entry.pk, operator_author=run.started_by,
            new_status=BattleEntry.ModerationStatus.APPROVED,
            reason="Rehearsal: photo approved.", correlation_id=run.run_id,
        )
    battle.refresh_from_db()
    return {
        "outcome": RehearsalStep.Outcome.MISSING,
        "mechanism": "services.operator_moderate_entry",
        "detail": (
            "%d photo(s) approved and the battle is %s. Recorded as a gap because "
            "the only way to approve a dish is an OWNER-only console action - a "
            "moderator has no path to it, so on a real evening this step has "
            "nobody to perform it but him." % (len(pending), battle.status)
        ),
    }


def _step_voting(run, rng):
    """The one place the rehearsal cannot move: nothing opens the vote."""
    battle = _battle_of(run)
    if battle.status == Battle.Status.VOTING:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "-",
                "detail": "Voting is already open."}
    return {
        "outcome": RehearsalStep.Outcome.MISSING,
        "mechanism": "NONE - searched services, state_machine, management commands",
        "detail": (
            "The battle is %s and it will stay there. NOTHING in production carries "
            "PRESENTATION to VOTING: no service, no sweeper, no cron. The only "
            "writer of Status.VOTING outside the vote itself is the console "
            "emulator, which sets the field directly. The rehearsal stops here "
            "rather than doing the same - stepping over it would hide the hole."
            % battle.status
        ),
    }


SCENARIO_A = (
    ("cast", "The two chefs take the floor", _step_cast),
    ("recipe", "Jam O'Liver writes the dish", _step_recipe),
    ("challenge", "CrestedTen issues the challenge", _step_challenge),
    ("accept", "The challenge is accepted", _step_accept),
    ("entry", "Jam O'Liver attaches his dish", _step_entry),
    ("ready", "Both chefs press Ready", _step_ready),
    ("start", "The clock runs out and the battle begins", _step_start),
    ("menu", "Both menus are declared", _step_menu),
    ("combat", "The combat engine settles Stage 1", _step_combat),
    ("biathlon", "The ingredient biathlon is played", _step_biathlon),
    ("cook", "Both dishes are cooked and photographed", _step_cook),
    ("moderate", "The photos are moderated", _step_moderate),
    ("voting", "The vote opens", _step_voting),
)


# -- the operator surface ----------------------------------------------------

def start_rehearsal(*, operator_author, scenario="A", seed=None,
                    correlation_id="") -> RehearsalRun:
    _require_owner(operator_author)
    if scenario != RehearsalRun.Scenario.A:
        raise RehearsalError("Only scenario A exists so far.")
    with transaction.atomic():
        if RehearsalRun.current() is not None:
            raise RehearsalError(
                "A rehearsal is already in flight. Abort it before starting another.")
        run = RehearsalRun.objects.create(
            run_id=uuid.uuid4().hex[:12],
            scenario=scenario,
            seed=int(seed) if seed else random.SystemRandom().randrange(1, 2 ** 31),
            started_by=operator_author,
        )
    return run


def rehearsal_step(*, operator_author, correlation_id="") -> dict:
    """Perform the next step of the run in flight, and record what it proved."""
    _require_owner(operator_author)
    run = RehearsalRun.current()
    if run is None:
        raise RehearsalError("No rehearsal is running.")
    done = run.steps.count()
    if done >= len(SCENARIO_A):
        finish_rehearsal(run)
        return {"run_id": run.run_id, "finished": True, "status": run.status}

    key, title, fn = SCENARIO_A[done]
    # The seed plus the step's own name: the same seed replays the same battle,
    # and one step's randomness does not shift because another step ran twice.
    rng = random.Random("%s:%s" % (run.seed, key))
    try:
        result = fn(run, rng)
    except Exception as exc:  # noqa: BLE001 - a run records its own failure
        result = {"outcome": RehearsalStep.Outcome.FAIL, "mechanism": "-",
                  "detail": "%s: %s" % (type(exc).__name__, exc)}
    step = _record(run, key=key, title=title, **result)

    if step.outcome == RehearsalStep.Outcome.FAIL:
        run.status = RehearsalRun.Status.FAILED
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
    elif done + 1 >= len(SCENARIO_A):
        finish_rehearsal(run)
    return {"run_id": run.run_id, "step": _step_payload(step),
            "status": run.status, "finished": run.finished_at is not None}


def finish_rehearsal(run) -> RehearsalRun:
    outcomes = set(run.steps.values_list("outcome", flat=True))
    if run.is_tainted or RehearsalStep.Outcome.FAIL in outcomes:
        run.status = RehearsalRun.Status.FAILED
    elif (RehearsalStep.Outcome.MISSING in outcomes
          or RehearsalStep.Outcome.UI_MISMATCH in outcomes):
        # Findings, not a crash. The run did its job; the arena did not.
        run.status = RehearsalRun.Status.BLOCKED
    else:
        run.status = RehearsalRun.Status.PASSED
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "finished_at"])
    return run


def abort_rehearsal(*, operator_author, correlation_id="") -> dict:
    _require_owner(operator_author)
    run = RehearsalRun.current()
    if run is None:
        raise RehearsalError("No rehearsal is running.")
    run.status = RehearsalRun.Status.ABORTED
    run.finished_at = timezone.now()
    run.note = (run.note + "\nAborted by the operator.").strip()
    run.save(update_fields=["status", "finished_at", "note"])
    return {"run_id": run.run_id, "status": run.status}


def _step_payload(step):
    return {
        "position": step.position, "key": step.key, "title": step.title,
        "outcome": step.outcome, "outcome_display": step.get_outcome_display(),
        "mechanism": step.mechanism, "detail": step.detail,
        "at": timezone.localtime(step.created_at).strftime("%H:%M:%S"),
    }


def rehearsal_state() -> dict:
    """What the console shows. Read-only, and cheap enough to poll."""
    run = RehearsalRun.current() or RehearsalRun.objects.select_related(
        "battle").order_by("-started_at").first()
    if run is None:
        return {"running": False, "run": None, "steps": [], "done_steps": 0,
                "next_step": SCENARIO_A[0][1], "total_steps": len(SCENARIO_A),
                "counts": {"pass": 0, "fail": 0, "missing": 0}}
    steps = list(run.steps.all())
    done = len(steps)
    return {
        "running": run.status in (RehearsalRun.Status.RUNNING,
                                  RehearsalRun.Status.BLOCKED),
        "run": {
            "run_id": run.run_id, "scenario": run.scenario, "seed": run.seed,
            "status": run.status, "status_display": run.get_status_display(),
            "battle_id": run.battle_id, "tainted": run.is_tainted,
            "started_at": timezone.localtime(run.started_at).strftime("%Y-%m-%d %H:%M"),
        },
        "steps": [_step_payload(s) for s in steps],
        "done_steps": done,
        "total_steps": len(SCENARIO_A),
        "next_step": SCENARIO_A[done][1] if done < len(SCENARIO_A) else None,
        "counts": {
            "pass": sum(1 for s in steps if s.outcome == RehearsalStep.Outcome.PASS),
            "fail": sum(1 for s in steps if s.outcome == RehearsalStep.Outcome.FAIL),
            "missing": sum(1 for s in steps if s.outcome == RehearsalStep.Outcome.MISSING),
        },
    }
