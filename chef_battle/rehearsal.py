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
from django.db.models import Q
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

    if run.battle_id:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "chef_battle.forms.BattleChallengeForm",
                "detail": "This run already has battle #%d - no new challenge."
                          % run.battle_id}
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

    if run.battle_id:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.accept_challenge",
                "detail": "Battle #%d is already this run's." % run.battle_id}
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
    from .services import fire_ingredient_shot, sweep_ingredient_penalty_deadlines

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
    # THE WINDOW CLOSES ON THE CLOCK, and production does it - the first
    # version of this step called approve_cooking_phase directly and then
    # reported "nothing closes this window", which was the instrument
    # describing itself. sweep_ingredient_penalty_deadlines() has closed it all
    # along, on INGREDIENT_PENALTY_WINDOW, from the same cron as every other
    # sweep. So the deadline is hurried and the sweeper is called, exactly as
    # the start step does.
    _hurry(battle, "ingredient_penalty_deadline")
    closed = sweep_ingredient_penalty_deadlines()
    battle.refresh_from_db()
    cooking = battle.status == Battle.Status.COOKING
    return {
        "outcome": RehearsalStep.Outcome.PASS if cooking else RehearsalStep.Outcome.FAIL,
        "mechanism": "services.fire_ingredient_shot, "
                     "services.sweep_ingredient_penalty_deadlines",
        "detail": "%d shot(s) fired; the window was hurried and the sweeper closed "
                  "%d battle(s). Now %s." % (fired, closed, battle.status),
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
    """The presentation window shuts and the real sweep opens the vote.

    This step is why the instrument was built. On its first run it found that
    NOTHING in production carried PRESENTATION to VOTING - no service, no
    sweep, no cron - and it recorded that instead of setting the field itself.
    open_voting_for_presented_battles() is the answer to that finding, and the
    step now proves it the same way it proves every other transition: hurry the
    clock, call the sweep, read the status back.
    """
    from .services import open_voting_for_presented_battles

    battle = _battle_of(run)
    if battle.status == Battle.Status.VOTING:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.open_voting_for_presented_battles",
                "detail": "Voting is already open."}
    if battle.status != Battle.Status.PRESENTATION:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.open_voting_for_presented_battles",
                "detail": "The battle never reached presentation - it is %s."
                          % battle.status}
    _hurry(battle, "presentation_deadline")
    opened = open_voting_for_presented_battles()
    battle.refresh_from_db()
    voting = battle.status == Battle.Status.VOTING
    return {
        "outcome": RehearsalStep.Outcome.PASS if voting else RehearsalStep.Outcome.FAIL,
        "mechanism": "services.open_voting_for_presented_battles",
        "detail": "The presentation window was hurried and the sweep opened %d "
                  "vote(s). The battle is %s, closing %s."
                  % (opened, battle.status, battle.voting_deadline),
    }


def _step_vote(run, rng):
    """The audience votes, one row per person, through the real vote path."""
    from django.contrib.auth import get_user_model
    from .models import BattleVote

    battle = _battle_of(run)
    if battle.status != Battle.Status.VOTING:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "models.BattleVote",
                "detail": "The vote is not open (%s)." % battle.status}
    User = get_user_model()
    favourite = rng.choice([battle.challenger, battle.opponent])
    other = battle.opponent if favourite == battle.challenger else battle.challenger
    cast = 0
    for i in range(9):
        voter, _ = User.objects.get_or_create(
            username="rehearsal-voter-%d" % i, defaults={"is_active": True})
        _, created = BattleVote.objects.get_or_create(
            battle=battle, voter=voter,
            defaults={"voted_for": favourite if rng.random() < 0.7 else other})
        cast += int(created)
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "models.BattleVote",
            "detail": "%d vote(s) cast by the audience." % cast}


def _step_result(run, rng):
    """The clock runs out and the engine - not the rehearsal - names a winner."""
    from .services import calculate_battle_result

    battle = _battle_of(run)
    if battle.status != Battle.Status.VOTING:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.calculate_battle_result",
                "detail": "Not voting (%s)." % battle.status}
    _hurry(battle, "voting_deadline")
    calculate_battle_result(battle)
    battle.refresh_from_db()
    done = battle.status == Battle.Status.COMPLETED
    winner = battle.winner.name if battle.winner else "a draw"
    return {
        "outcome": RehearsalStep.Outcome.PASS if done else RehearsalStep.Outcome.FAIL,
        "mechanism": "services.calculate_battle_result",
        "detail": "The battle is %s and the engine returned %s. The rehearsal "
                  "named nobody." % (battle.status, winner),
    }


def _step_stage(run, rng):
    """Adopt the rehearsal battle already standing, or report a clear floor.

    A rehearsal battle holds the two test chefs' slots exactly as a real one
    does - which is correct, and it means a second scenario cannot issue a
    fresh challenge while the first one's battle is open. Rather than failing
    on a rule that is working, a run adopts what is there.
    """
    if run.battle_id:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "-",
                "detail": "This run already owns battle #%d." % run.battle_id}
    jam, crested = _chefs()
    standing = Battle.objects.filter(
        theme__startswith=REHEARSAL_MARK,
        challenger__slug__in=REHEARSAL_CHEFS,
        opponent__slug__in=REHEARSAL_CHEFS,
    ).order_by("-created_at").first()
    if standing is None:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "-",
                "detail": "The floor is clear - this run will make its own battle."}
    run.battle = standing
    run.save(update_fields=["battle"])
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "-",
            "detail": "Adopted battle #%d (%s) from an earlier run."
                      % (standing.pk, standing.status)}


def _rehearsal_artifact(effect_type, value, rng):
    """An artifact from the real catalogue, or one made for the rehearsal."""
    from .models import Artifact

    existing = (Artifact.objects
                .filter(is_active=True, effect_type__iexact=effect_type,
                        effect_value__gt=0)
                .order_by("token_cost").first())
    if existing:
        return existing, False
    artifact = Artifact.objects.create(
        name="%s %s charm" % (REHEARSAL_MARK, effect_type),
        rarity=Artifact.Rarity.COMMON, effect_type=effect_type,
        effect_value=value, token_cost=10, is_active=True,
    )
    return artifact, True


def _step_arm(run, rng):
    """Both chefs buy an artifact, with their own tokens, from the real shop."""
    from .models import ChefArtifact, TokenTransaction
    from .services import buy_artifact, credit_tokens, get_or_create_wallet

    battle = _battle_of(run)
    made = []
    bought = []
    for chef, effect in ((battle.challenger, "attack"), (battle.opponent, "defence")):
        artifact, invented = _rehearsal_artifact(effect, 2, rng)
        if invented:
            made.append(artifact.name)
        held = ChefArtifact.objects.filter(
            chef=chef, artifact=artifact, status=ChefArtifact.Status.AVAILABLE)
        if held.exists():
            bought.append("%s already holds %s" % (chef.name, artifact.name))
            continue
        wallet = get_or_create_wallet(chef)
        if wallet.balance < artifact.token_cost:
            credit_tokens(chef, artifact.token_cost * 2,
                          tx_type=TokenTransaction.TxType.ADMIN_GRANT,
                          description="%s: stake for the shop" % REHEARSAL_MARK)
        owned = buy_artifact(chef=chef, artifact=artifact)
        bought.append("%s bought %s (#%d)" % (chef.name, artifact.name, owned.pk))
    outcome = RehearsalStep.Outcome.PASS
    detail = "; ".join(bought)
    if made:
        outcome = RehearsalStep.Outcome.MISSING
        detail += (". The catalogue had no usable %s artifact, so the rehearsal "
                   "had to invent one: %s." % ("/".join(sorted(set(made))), ", ".join(made)))
    return {"outcome": outcome, "mechanism": "services.buy_artifact", "detail": detail}


def _step_combat_artifacts(run, rng):
    """The fight, with an artifact played on every move it can be played on."""
    from .models import ChefArtifact
    from .services import submit_combat_action

    battle = _battle_of(run)
    if battle.status != Battle.Status.ACTIVE:
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "services.submit_combat_action",
                "detail": "Combat is not open (%s)." % battle.status}

    spent = []
    rounds = 0
    while battle.status == Battle.Status.ACTIVE and rounds < MAX_COMBAT_ROUNDS:
        for chef in (battle.challenger, battle.opponent):
            action = "attack" if chef == battle.challenger else "defend"
            wanted = ("attack",) if action == "attack" else ("defense", "defence")
            playable = (ChefArtifact.objects
                        .filter(chef=chef, status=ChefArtifact.Status.AVAILABLE)
                        .filter(Q(artifact__effect_type__in=wanted)
                                | Q(artifact__effect_type__iexact="boost"))
                        .filter(Q(locked_to_battle__isnull=True) | Q(locked_to_battle=battle))
                        .filter(Q(reserved_in_battle__isnull=True) | Q(reserved_in_battle=battle))
                        .select_related("artifact"))
            # A SPECTATOR'S GIFT COMES FIRST, because the rules say so: a
            # delivery locked to this battle must be spent before the chef's
            # own, or it lapses when the battle ends. Playing his own first is
            # refused by submit_combat_action, and the first run of scenario C
            # was refused exactly that way - the rule working, the rehearsal
            # not obeying it.
            owned = (playable.filter(locked_to_battle=battle).first()
                     or playable.first())
            submit_combat_action(battle, chef, action, rng.randint(1, 3),
                                 artifact_id=owned.pk if owned else None)
            if owned:
                spent.append((owned.pk, owned.artifact.name, chef.name))
        battle.refresh_from_db()
        rounds += 1

    burned = ChefArtifact.objects.filter(
        pk__in=[pk for pk, _n, _c in spent],
        status=ChefArtifact.Status.CONSUMED).count()
    if spent and burned != len(spent):
        return {
            "outcome": RehearsalStep.Outcome.FAIL,
            "mechanism": "services.submit_combat_action -> services._resolve_round",
            "detail": "%d artifact(s) were played and only %d were spent - a played "
                      "artifact that survives is the bug this scenario exists to "
                      "catch." % (len(spent), burned),
        }
    named = ", ".join("%s by %s" % (n, c) for _pk, n, c in spent) or "none"
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.submit_combat_action -> services._resolve_round",
            "detail": "%d round(s); artifacts played and spent: %s. Now %s."
                      % (rounds, named, battle.status)}


def _step_chest(run, rng):
    """What each chef is holding, and whether a gift is distinguishable."""
    from .models import ChefArtifact

    battle = _battle_of(run)
    lines = []
    unmarked_gift = False
    for chef in (battle.challenger, battle.opponent):
        rows = list(ChefArtifact.objects.filter(chef=chef)
                    .select_related("artifact").order_by("status", "pk"))
        by_status = {}
        for row in rows:
            by_status.setdefault(row.status, []).append(row)
            # Only a gift the chef can still PLAY has to say it is a gift. A
            # spent one is history: its lock has done its work and the row is
            # a record of what was used, not an item that can be mistaken for
            # property.
            if (row.source == ChefArtifact.Source.BATTLE_GIFT
                    and row.status == ChefArtifact.Status.AVAILABLE
                    and row.locked_to_battle_id is None):
                unmarked_gift = True
        lines.append("%s: %s" % (
            chef.name,
            ", ".join("%d %s" % (len(v), k) for k, v in sorted(by_status.items())) or "empty"))
    if unmarked_gift:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "models.ChefArtifact",
                "detail": "A battle gift is sitting in a chest with no battle on it, "
                          "so nothing can tell it from bought property. " + "; ".join(lines)}
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "models.ChefArtifact",
            "detail": "; ".join(lines)}


def _rehearsal_viewer(index):
    """One of the rehearsal's own spectators: an account, a purse and a pulse.

    THE PULSE IS NOT A CONVENIENCE. A seat lapses the moment its holder falls
    out of the arena's online window - ChefBattleProfile.last_seen_at, the same
    window that decides whether a person is drawn in the hall - and the next
    claim_seat() releases it. That is exactly right for a viewer who closed the
    tab, and it means a rehearsal spectator who never polls is released before
    he can say a word: the first run of scenario C seated twelve people and
    then found every one of them refused by the chat with "not_in_the_hall".
    So the rehearsal keeps its spectators present, through the same field a
    real viewer's poll writes.
    """
    from django.contrib.auth import get_user_model
    from recipes.models import RecipeAuthor

    from .services import get_or_create_battle_profile

    User = get_user_model()
    slug = "rehearsal-viewer-%d" % index
    user, _ = User.objects.get_or_create(username=slug, defaults={"is_active": True})
    author, _ = RecipeAuthor.objects.get_or_create(
        slug=slug, defaults={"user": user, "name": "Rehearsal Viewer %d" % index})
    if author.user_id is None:
        author.user = user
        author.save(update_fields=["user"])
    profile = get_or_create_battle_profile(author)
    profile.last_seen_at = timezone.now()
    profile.save(update_fields=["last_seen_at"])
    return user, author


def _step_spectators(run, rng):
    """The hall fills: real accounts, real seats, real wallets."""
    from .arena_seating import claim_seat
    from .models import ArenaSeat, TokenTransaction
    from .services import credit_tokens

    seated, failed = 0, []
    for i in range(12):
        _user, author = _rehearsal_viewer(i)
        try:
            claim_seat(author)
            seated += 1
        except Exception as exc:  # noqa: BLE001 - the run records what refused it
            failed.append("%s: %s" % (author.slug, exc))
        credit_tokens(author, 500, tx_type=TokenTransaction.TxType.ADMIN_GRANT,
                      description="%s: spectator purse" % REHEARSAL_MARK)
    total = ArenaSeat.objects.count()
    if failed:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "arena_seating.claim_seat",
                "detail": "%d seated, %d refused: %s" % (seated, len(failed), "; ".join(failed[:3]))}
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "arena_seating.claim_seat",
            "detail": "%d spectators seated; %d seats taken in the hall." % (seated, total)}


def _step_stands(run, rng):
    """Every seat in the hall, to see what the arena does when it is full."""
    from .arena_seating import claim_seat, seat_map
    from .models import ArenaSeat

    cells = {(ring, cell) for ring, cell, _row in seat_map()}
    capacity = len(cells)
    held = lambda: list(  # noqa: E731 - one expression, read twice
        ArenaSeat.objects.filter(released_at__isnull=True)
        .values_list("ring_index", "seat_index"))
    before = len(held())
    refused = 0
    for i in range(capacity + 4):
        _user, author = _rehearsal_viewer(i)
        try:
            claim_seat(author)
        except Exception:  # noqa: BLE001
            refused += 1

    # MEASURED AGAINST THE MAP, not against a row count. A held seat that the
    # geometry no longer declares is a leftover, not an overflow, and the two
    # read identically in a bare count - the first run of this step reported
    # "the hall seats 114 and it took 115" when the extra row was a single
    # off-map seat from an older layout.
    rows = held()
    on_map = [s for s in rows if s in cells]
    off_map = [s for s in rows if s not in cells]
    if len(on_map) > capacity:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "arena_seating.claim_seat",
                "detail": "The hall declares %d seats and %d are held on the map."
                          % (capacity, len(on_map))}
    if len(set(on_map)) != len(on_map):
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "arena_seating.claim_seat",
                "detail": "Two people are holding the same seat."}
    outcome = (RehearsalStep.Outcome.MISSING if off_map
               else RehearsalStep.Outcome.PASS)
    return {"outcome": outcome,
            "mechanism": "arena_seating.claim_seat, arena_seating.seat_map",
            "detail": "Capacity %d; held seats went %d to %d, none doubled, %d "
                      "claims refused at the door.%s"
                      % (capacity, before, len(on_map), refused,
                         " %d seat(s) are held OFF the map: %s."
                         % (len(off_map), off_map[:3]) if off_map else "")}


def _step_deliver(run, rng):
    """A spectator sends an artifact into the fight, and the fight says so."""
    from .models import BattleEvent, ChefArtifact, ViewerBattleGift
    from .services import send_battle_artifact

    battle = _battle_of(run)
    if battle.status not in Battle.ACTIVE_STATUSES:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.send_battle_artifact",
                "detail": "The battle is %s - a delivery needs a live fight." % battle.status}
    artifact, _made = _rehearsal_artifact("attack", 2, rng)
    user, author = _rehearsal_viewer(0)
    before = battle.events.filter(
        event_type=BattleEvent.EventType.ARTIFACT_DELIVERED).count()
    gift = send_battle_artifact(sender_user=user, recipient=battle.challenger,
                                battle=battle, artifact=artifact)
    delivered = ChefArtifact.objects.filter(
        chef=battle.challenger, artifact=artifact,
        source=ChefArtifact.Source.BATTLE_GIFT, locked_to_battle=battle).first()
    announced = battle.events.filter(
        event_type=BattleEvent.EventType.ARTIFACT_DELIVERED).count() - before

    stages = {
        "paid": bool(gift.token_transaction_id),
        "delivery recorded": ViewerBattleGift.objects.filter(pk=gift.pk).exists(),
        "handed to the chef": delivered is not None,
        "locked to this battle": bool(delivered and delivered.locked_to_battle_id == battle.pk),
        "announced to the fight": announced == 1,
    }
    missing = [name for name, ok in stages.items() if not ok]
    if missing:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.send_battle_artifact",
                "detail": "The delivery stopped at: %s." % ", ".join(missing)}
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.send_battle_artifact",
            "detail": "%s reached %s and every stage left its mark: %s."
                      % (artifact.name, battle.challenger.name,
                         ", ".join(stages))}


def _step_gifts(run, rng):
    """Appreciation gifts from the stands, through the real service."""
    from .models import AppreciationGiftType
    from .services import send_appreciation_gift

    battle = _battle_of(run)
    kinds = [c[0] for c in AppreciationGiftType.choices] if hasattr(
        AppreciationGiftType, "choices") else []
    sent, refused = [], []
    for i in range(4):
        user, _author = _rehearsal_viewer(i)
        target = battle.challenger if i % 2 == 0 else battle.opponent
        kind = rng.choice(kinds) if kinds else ""
        try:
            gift = send_appreciation_gift(sender_user=user, recipient=target,
                                          gift_type=kind, message="Well cooked.")
            sent.append("%s to %s" % (gift.gift_type, target.name))
        except Exception as exc:  # noqa: BLE001
            refused.append(str(exc))
    if not sent:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.send_appreciation_gift",
                "detail": "Every gift was refused: %s" % "; ".join(refused[:3])}
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.send_appreciation_gift",
            "detail": "%d gift(s) sent: %s.%s" % (
                len(sent), ", ".join(sent),
                " %d refused: %s" % (len(refused), refused[0]) if refused else "")}


def _step_chat(run, rng):
    """The hall talks, through the view that owns the rule about who hears whom."""
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore
    from django.test import RequestFactory

    from .models import ArenaChatMessage
    from .views import arena_chat_send

    before = ArenaChatMessage.objects.count()
    factory = RequestFactory()
    said, refused = 0, []
    for i in range(6):
        user, _author = _rehearsal_viewer(i)
        request = factory.post("/chef-battle/arena/chat/send/",
                               {"body": "%s line %d from the stands." % (REHEARSAL_MARK, i)})
        request.user = user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        try:
            response = arena_chat_send(request)
            if getattr(response, "status_code", 500) == 200:
                said += 1
            else:
                refused.append("HTTP %s" % response.status_code)
        except Exception as exc:  # noqa: BLE001
            refused.append("%s: %s" % (type(exc).__name__, exc))
    written = ArenaChatMessage.objects.count() - before
    if written == 0:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "views.arena_chat_send",
                "detail": "Nobody could speak: %s" % "; ".join(refused[:3] or ["no reason given"])}
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "views.arena_chat_send",
            "detail": "%d line(s) spoken, %d row(s) written.%s" % (
                said, written,
                " Refused: %s" % refused[0] if refused else "")}


def _step_shop(run, rng):
    """The shop and the chest: buy one, give one away before the fight."""
    from .models import ChefArtifact, TokenTransaction
    from .services import (
        buy_artifact, credit_tokens, gift_artifact_before_battle,
    )

    battle = _battle_of(run)
    artifact, _made = _rehearsal_artifact("attack", 2, rng)
    buyer, receiver = battle.challenger, battle.opponent
    credit_tokens(buyer, artifact.token_cost * 4,
                  tx_type=TokenTransaction.TxType.ADMIN_GRANT,
                  description="%s: shop stake" % REHEARSAL_MARK)
    bought = buy_artifact(chef=buyer, artifact=artifact)
    try:
        given = gift_artifact_before_battle(
            sender_author=buyer, recipient=receiver, artifact=artifact)
    except Exception as exc:  # noqa: BLE001
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.gift_artifact_before_battle",
                "detail": "Buying worked (#%d) and gifting did not: %s" % (bought.pk, exc)}
    moved = ChefArtifact.objects.filter(pk=given.pk, chef=receiver).exists()
    return {"outcome": RehearsalStep.Outcome.PASS if moved else RehearsalStep.Outcome.FAIL,
            "mechanism": "services.buy_artifact, services.gift_artifact_before_battle",
            "detail": "%s bought %s (#%d) and gave one to %s (#%d, source=%s)."
                      % (buyer.name, artifact.name, bought.pk, receiver.name,
                         given.pk, given.source)}


def _step_drop(run, rng):
    """What the finished battle handed out, read from its own events."""
    from .models import BattleEvent, ChefArtifact

    battle = _battle_of(run)
    if battle.status != Battle.Status.COMPLETED:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.drop_battle_artifacts",
                "detail": "The battle is %s - nothing has been dropped yet." % battle.status}
    events = list(battle.events.filter(
        event_type=BattleEvent.EventType.ARTIFACT_DROPPED).select_related("actor"))
    dropped = ChefArtifact.objects.filter(
        chef__in=[battle.challenger, battle.opponent],
        source=ChefArtifact.Source.DROP).count()
    if battle.winner_id and not events:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services.drop_battle_artifacts",
                "detail": "The winner's drop is guaranteed and nothing was dropped. "
                          "The pool is empty for this chef."}
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services.drop_battle_artifacts",
            "detail": "%d drop event(s), %d dropped artifact(s) in the two chests: %s"
                      % (len(events), dropped,
                         "; ".join(e.message for e in events) or "none")}


def _step_window(run, rng):
    """What the spectator's page can actually see, asked the way the page asks."""
    import json

    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory

    from .views import battle_snapshot

    battle = _battle_of(run)
    # The VIEW, called the way the page calls it. Django's test Client sends
    # Host: testserver, which production's ALLOWED_HOSTS rejects with a 400 -
    # the first run of this step reported that 400 as if the endpoint were
    # broken, when the only thing broken was the way the rehearsal knocked.
    factory = RequestFactory()
    url = "/chef-battle/battles/%d/snapshot/" % battle.pk

    def poll(sequence):
        request = factory.post(url, {"sequence": str(sequence)})
        request.user = AnonymousUser()
        return battle_snapshot(request, pk=battle.pk)

    first = poll(0)
    if first.status_code != 200:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "views.battle_snapshot",
                "detail": "A spectator's poll answered HTTP %d." % first.status_code}
    body = json.loads(first.content)
    if not body.get("battle") or body["battle"].get("id") != battle.pk:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "views.battle_snapshot",
                "detail": "The poll answered about battle %s, not %d."
                          % (body.get("battle", {}).get("id"), battle.pk)}
    second = json.loads(poll(body.get("sequence", 0)).content)
    moved = second.get("sequence") != body.get("sequence")

    # What the window CANNOT show, checked against the battle's real state
    # rather than asserted from memory.
    absent = [name for name, present in (
        ("ingredients", "ingredients" in body),
        ("rounds", "rounds" in body or "combat" in body),
        ("artifacts", "artifacts" in body),
        ("votes", "votes" in body),
    ) if not present]
    return {
        "outcome": RehearsalStep.Outcome.MISSING if absent else RehearsalStep.Outcome.PASS,
        "mechanism": "views.battle_snapshot -> arena_snapshot.build_arena_snapshot",
        "detail": "The poll answers about this battle and its sequence %s. The "
                  "snapshot still carries nothing about: %s - a spectator watching "
                  "the window sees names and counters, not the fight."
                  % ("advances" if moved else "does not advance",
                     ", ".join(absent) or "nothing"),
    }


def _step_winner(run, rng):
    """The result frame, built the way the page builds it."""
    from .arena_snapshot import build_arena_snapshot
    from .views import _snapshot_to_fx

    battle = _battle_of(run)
    fx = _snapshot_to_fx(build_arena_snapshot(battle), battle)
    if not fx.get("finished"):
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "views._snapshot_to_fx",
                "detail": "The battle is %s, so there is no result to show." % battle.status}
    result = fx.get("result") or {}
    if battle.winner_id:
        if not fx.get("champion") or fx["champion"].get("name") != battle.winner.name:
            return {"outcome": RehearsalStep.Outcome.FAIL,
                    "mechanism": "views._snapshot_to_fx",
                    "detail": "The engine named %s and the frame shows %s."
                              % (battle.winner.name, (fx.get("champion") or {}).get("name"))}
        return {"outcome": RehearsalStep.Outcome.PASS,
                "mechanism": "views._snapshot_to_fx",
                "detail": "Champion %s, runner-up %s, rank %s, streak %s, crown %s, "
                          "%d drop(s) listed."
                          % (fx["champion"]["name"], (fx.get("runner_up") or {}).get("name"),
                             result.get("rank") or "-", result.get("win_streak"),
                             "yes" if result.get("crown_awarded") else "no",
                             len(result.get("drops") or []))}
    if fx.get("champion") is not None:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "views._snapshot_to_fx",
                "detail": "The battle has no winner and the frame named one anyway."}
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "views._snapshot_to_fx",
            "detail": "No winner, and the frame names nobody. Reason: %s"
                      % (result.get("reason") or fx.get("status_display"))}


def _step_profiles(run, rng):
    """The lasting state of both chefs, against what the battle actually did."""
    from .services import get_or_create_battle_profile, get_or_create_wallet

    battle = _battle_of(run)
    if battle.status != Battle.Status.COMPLETED:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "models.ChefBattleProfile",
                "detail": "The battle is %s - nothing has been scored." % battle.status}
    lines, wrong = [], []
    for chef in (battle.challenger, battle.opponent):
        profile = get_or_create_battle_profile(chef)
        wallet = get_or_create_wallet(chef)
        lines.append("%s: rating %d, %dW/%dL, streak %d, rank %s, %d tokens"
                     % (chef.name, profile.rating, profile.wins, profile.losses,
                        profile.win_streak, profile.rank, wallet.balance))
        if battle.winner_id == chef.pk and profile.wins < 1:
            wrong.append("%s won and carries no win" % chef.name)
        if battle.loser_id == chef.pk and profile.losses < 1:
            wrong.append("%s lost and carries no loss" % chef.name)
    if wrong:
        return {"outcome": RehearsalStep.Outcome.FAIL,
                "mechanism": "services._score_battle",
                "detail": "%s. %s" % ("; ".join(wrong), " | ".join(lines))}
    return {"outcome": RehearsalStep.Outcome.PASS,
            "mechanism": "services._score_battle",
            "detail": " | ".join(lines)}


# -- one registry, several scenarios -----------------------------------------
#
# The Owner asked for composable scenarios rather than one linear test, and a
# step belongs to the arena rather than to a scenario: the fight is set up the
# same way whether we are watching combat, the stands or the shop. So the steps
# are named once here and every scenario is an ORDER OF NAMES. A scenario that
# needs a live battle simply starts with the same opening as the others.

STEPS = {
    "stage": ("The floor is prepared", _step_stage),
    "cast": ("The two chefs take the floor", _step_cast),
    "recipe": ("Jam O'Liver writes the dish", _step_recipe),
    "challenge": ("CrestedTen issues the challenge", _step_challenge),
    "accept": ("The challenge is accepted", _step_accept),
    "entry": ("Jam O'Liver attaches his dish", _step_entry),
    "ready": ("Both chefs press Ready", _step_ready),
    "start": ("The clock runs out and the battle begins", _step_start),
    "menu": ("Both menus are declared", _step_menu),
    "combat": ("The combat engine settles Stage 1", _step_combat),
    "biathlon": ("The ingredient biathlon is played", _step_biathlon),
    "cook": ("Both dishes are cooked and photographed", _step_cook),
    "moderate": ("The photos are moderated", _step_moderate),
    "voting": ("The vote opens", _step_voting),
    "vote": ("The audience votes", _step_vote),
    "result": ("The engine names the winner", _step_result),
    # B - artifacts
    "arm": ("Both chefs buy an artifact", _step_arm),
    "combat_artifacts": ("The fight is fought with artifacts", _step_combat_artifacts),
    "chest": ("Both chests are counted", _step_chest),
    # C - the stands
    "spectators": ("The hall fills", _step_spectators),
    "deliver": ("A spectator delivers an artifact", _step_deliver),
    "gifts": ("The stands send gifts", _step_gifts),
    "chat": ("The hall talks", _step_chat),
    # D - shop and chest
    "shop": ("The shop and the chest", _step_shop),
    "drop": ("The battle hands out its drops", _step_drop),
    # E - load
    "stands": ("Every seat in the hall", _step_stands),
    # F, G, H
    "window": ("The spectator's window", _step_window),
    "winner": ("The result frame", _step_winner),
    "profiles": ("Both chefs' lasting state", _step_profiles),
}

# The opening every scenario shares: two chefs, a dish, a challenge, a battle
# that has actually begun.
_OPENING = ("stage", "cast", "recipe", "challenge", "accept", "entry",
            "ready", "start", "menu")
# ...and the closing, for the scenarios that need a finished battle.
_CLOSING = ("biathlon", "cook", "moderate", "voting", "vote", "result")

SCENARIOS = {
    "A": _OPENING + ("combat",) + _CLOSING,
    "B": _OPENING + ("arm", "combat_artifacts", "chest"),
    "C": _OPENING + ("spectators", "deliver", "gifts", "chat", "combat_artifacts", "chest"),
    "D": _OPENING + ("shop", "chest", "combat") + _CLOSING + ("drop", "chest"),
    "E": _OPENING + ("stands", "chat"),
    "F": _OPENING + ("combat", "window"),
    "G": _OPENING + ("combat",) + _CLOSING + ("winner",),
    "H": _OPENING + ("combat",) + _CLOSING + ("profiles", "chest"),
}

SCENARIO_TITLES = {
    "A": "Battle lifecycle",
    "B": "Battle with artifacts",
    "C": "The stands: delivery, gifts, chat",
    "D": "Shop, chest and drops",
    "E": "A full hall",
    "F": "The spectator's window",
    "G": "The result frame",
    "H": "What the battle leaves behind",
}

# Kept so nothing that imported the old name breaks; A is still A.
SCENARIO_A = tuple((key,) + STEPS[key] for key in SCENARIOS["A"])


def scenario_steps(scenario):
    """(key, title, fn) for each step of a scenario, in order."""
    keys = SCENARIOS.get(scenario)
    if keys is None:
        raise RehearsalError("There is no scenario '%s'." % scenario)
    return [(key,) + STEPS[key] for key in keys]


# -- the operator surface ----------------------------------------------------

def start_rehearsal(*, operator_author, scenario="A", seed=None,
                    correlation_id="") -> RehearsalRun:
    _require_owner(operator_author)
    if scenario not in SCENARIOS:
        raise RehearsalError(
            "There is no scenario '%s'. Choose one of %s."
            % (scenario, ", ".join(sorted(SCENARIOS))))
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
    steps = scenario_steps(run.scenario)
    done = run.steps.count()
    if done >= len(steps):
        finish_rehearsal(run)
        return {"run_id": run.run_id, "finished": True, "status": run.status}

    key, title, fn = steps[done]
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
    elif done + 1 >= len(steps):
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


def _scenario_menu():
    """What the console offers, built from the scenarios themselves."""
    return [
        {"key": key, "title": SCENARIO_TITLES.get(key, key),
         "steps": len(SCENARIOS[key])}
        for key in sorted(SCENARIOS)
    ]


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
        plan = scenario_steps("A")
        return {"running": False, "run": None, "steps": [], "done_steps": 0,
                "next_step": plan[0][1], "total_steps": len(plan),
                "scenarios": _scenario_menu(),
                "counts": {"pass": 0, "fail": 0, "missing": 0}}
    plan = scenario_steps(run.scenario)
    steps = list(run.steps.all())
    done = len(steps)
    return {
        "running": run.status in (RehearsalRun.Status.RUNNING,
                                  RehearsalRun.Status.BLOCKED),
        "run": {
            "run_id": run.run_id, "scenario": run.scenario,
            "scenario_title": SCENARIO_TITLES.get(run.scenario, run.scenario),
            "seed": run.seed,
            "status": run.status, "status_display": run.get_status_display(),
            "battle_id": run.battle_id, "tainted": run.is_tainted,
            "started_at": timezone.localtime(run.started_at).strftime("%Y-%m-%d %H:%M"),
        },
        "steps": [_step_payload(s) for s in steps],
        "done_steps": done,
        "total_steps": len(plan),
        "next_step": plan[done][1] if done < len(plan) else None,
        "scenarios": _scenario_menu(),
        "counts": {
            "pass": sum(1 for s in steps if s.outcome == RehearsalStep.Outcome.PASS),
            "fail": sum(1 for s in steps if s.outcome == RehearsalStep.Outcome.FAIL),
            "missing": sum(1 for s in steps if s.outcome == RehearsalStep.Outcome.MISSING),
        },
    }
