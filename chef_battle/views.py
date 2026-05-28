from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from monitoring.tracker import get_client_ip
from recipes.authoring import get_author_for_user
from recipes.models import RecipeAuthor

from .forms import BattleChallengeForm, BattleEntryForm
from .models import Battle, BattleChallenge, BattleEvent, BattleVote, ChefBattleProfile
from .services import (
    accept_challenge,
    calculate_battle_result,
    create_battle_event,
    get_or_create_battle_profile,
    hash_request_value,
    refuse_challenge,
    reveal_entries_if_ready,
)


def battle_home(request):
    now = timezone.now()
    expired_battles = Battle.objects.filter(status__in=[Battle.Status.ACTIVE, Battle.Status.VOTING], end_time__lte=now)
    for battle in expired_battles[:20]:
        calculate_battle_result(battle)

    active_battles = (
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(status__in=[Battle.Status.ACTIVE, Battle.Status.VOTING, Battle.Status.SCHEDULED])
        .order_by("end_time")[:12]
    )
    recent_battles = (
        Battle.objects.select_related("challenger", "opponent", "winner")
        .filter(status=Battle.Status.COMPLETED)
        .order_by("-updated_at")[:10]
    )
    leaders = (
        ChefBattleProfile.objects.select_related("author")
        .order_by("-rating", "-wins", "author__name")[:10]
    )
    events = (
        BattleEvent.objects.select_related("battle", "actor", "target")
        .filter(is_public=True)
        .order_by("-created_at")[:12]
    )

    return render(request, "chef_battle/home.html", {
        "active_battles": active_battles,
        "recent_battles": recent_battles,
        "leaders": leaders,
        "events": events,
    })


@login_required
def challenge_list(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author profile required before entering Chef Battle.")
        return redirect("home")

    sent = BattleChallenge.objects.select_related("opponent").filter(challenger=author).order_by("-created_at")[:20]
    received = BattleChallenge.objects.select_related("challenger").filter(opponent=author).order_by("-created_at")[:20]
    return render(request, "chef_battle/challenge_list.html", {
        "author": author,
        "sent_challenges": sent,
        "received_challenges": received,
    })


@login_required
def challenge_create(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author profile required before creating a Chef Battle challenge.")
        return redirect("home")

    if request.method == "POST":
        form = BattleChallengeForm(request.POST, challenger=author)
        if form.is_valid():
            challenge = form.save()
            get_or_create_battle_profile(author)
            get_or_create_battle_profile(challenge.opponent)
            create_battle_event(
                event_type=BattleEvent.EventType.CHALLENGE_CREATED,
                challenge=challenge,
                actor=author,
                target=challenge.opponent,
                message=f"{author.name} challenged {challenge.opponent.name} to Chef Battle: {challenge.theme}.",
                publish_to_news=True,
            )
            messages.success(request, "Chef Battle challenge sent.")
            return redirect("chef_battle:challenge_list")
    else:
        initial = {}
        opponent_id = request.GET.get("opponent")
        if opponent_id:
            initial["opponent"] = opponent_id
        form = BattleChallengeForm(challenger=author, initial=initial)

    return render(request, "chef_battle/challenge_form.html", {"form": form})


@require_POST
@login_required
def challenge_respond(request, pk):
    author = get_author_for_user(request.user)
    challenge = get_object_or_404(BattleChallenge, pk=pk, opponent=author)
    if challenge.status != BattleChallenge.Status.PENDING:
        messages.warning(request, "This challenge has already been answered.")
        return redirect("chef_battle:challenge_list")
    if challenge.expires_at <= timezone.now():
        challenge.status = BattleChallenge.Status.EXPIRED
        challenge.save(update_fields=["status"])
        messages.warning(request, "This challenge has expired.")
        return redirect("chef_battle:challenge_list")

    action = request.POST.get("action")
    if action == "accept":
        battle = accept_challenge(challenge)
        messages.success(request, "Challenge accepted. The battle room is live.")
        return redirect(battle.get_absolute_url())
    if action == "refuse":
        refuse_challenge(challenge)
        messages.warning(request, "Challenge refused and recorded.")
        return redirect("chef_battle:challenge_list")

    messages.error(request, "Unknown challenge response.")
    return redirect("chef_battle:challenge_list")


def battle_detail(request, pk):
    battle = get_object_or_404(
        Battle.objects.select_related("challenger", "opponent", "winner", "loser"),
        pk=pk,
    )
    if battle.end_time <= timezone.now() and battle.status != Battle.Status.COMPLETED:
        battle = calculate_battle_result(battle)
    else:
        reveal_entries_if_ready(battle)
        battle.refresh_from_db()

    vote_counts = {
        row["voted_for"]: row["total"]
        for row in battle.votes.values("voted_for").annotate(total=Count("id"))
    }
    entries = battle.entries.select_related("author", "recipe", "article").order_by("submitted_at")
    events = battle.events.select_related("actor", "target").filter(is_public=True).order_by("-created_at")[:20]
    viewer_author = get_author_for_user(request.user) if request.user.is_authenticated else None
    viewer_entry = None
    if viewer_author:
        viewer_entry = battle.entries.filter(author=viewer_author).first()
    can_submit = bool(
        viewer_author
        and battle.author_is_participant(viewer_author)
        and not viewer_entry
        and battle.status in {Battle.Status.ACTIVE, Battle.Status.VOTING}
        and timezone.now() <= battle.submission_deadline
    )

    return render(request, "chef_battle/battle_detail.html", {
        "battle": battle,
        "entries": entries,
        "events": events,
        "vote_counts": vote_counts,
        "votes_for_challenger": vote_counts.get(battle.challenger_id, 0),
        "votes_for_opponent": vote_counts.get(battle.opponent_id, 0),
        "viewer_author": viewer_author,
        "viewer_entry": viewer_entry,
        "can_submit": can_submit,
    })


@login_required
def battle_entry_submit(request, pk):
    author = get_author_for_user(request.user)
    battle = get_object_or_404(Battle, pk=pk)
    if not battle.author_is_participant(author):
        raise PermissionDenied
    if battle.entries.filter(author=author).exists():
        messages.warning(request, "You have already submitted an entry for this battle.")
        return redirect(battle.get_absolute_url())
    if timezone.now() > battle.submission_deadline:
        messages.error(request, "The submission deadline has passed.")
        return redirect(battle.get_absolute_url())

    if request.method == "POST":
        form = BattleEntryForm(request.POST, author=author, battle=battle)
        if form.is_valid():
            entry = form.save()
            reveal_entries_if_ready(battle)
            create_battle_event(
                event_type=BattleEvent.EventType.ENTRY_SUBMITTED,
                battle=battle,
                actor=author,
                target=battle.opponent_for(author),
                message=f"{author.name} submitted an entry for Chef Battle: {battle.theme}.",
                publish_to_news=True,
            )
            messages.success(request, "Battle entry submitted.")
            return redirect(battle.get_absolute_url())
    else:
        form = BattleEntryForm(author=author, battle=battle)

    return render(request, "chef_battle/entry_form.html", {"battle": battle, "form": form})


@require_POST
def battle_vote(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    if battle.status not in {Battle.Status.ACTIVE, Battle.Status.VOTING}:
        messages.error(request, "Voting is not open for this battle.")
        return redirect(battle.get_absolute_url())
    if not battle.entries.filter(is_revealed=True).exists():
        messages.error(request, "Voting opens after entries are revealed.")
        return redirect(battle.get_absolute_url())

    voted_for = get_object_or_404(RecipeAuthor, pk=request.POST.get("voted_for"))
    if voted_for.pk not in {battle.challenger_id, battle.opponent_id}:
        messages.error(request, "Choose one of the battle chefs.")
        return redirect(battle.get_absolute_url())

    user = request.user if request.user.is_authenticated else None
    voter_author = get_author_for_user(user) if user else None
    if voter_author and voter_author.pk == voted_for.pk:
        messages.error(request, "Chefs cannot vote for themselves.")
        return redirect(battle.get_absolute_url())

    ip_hash = hash_request_value(get_client_ip(request) or "")
    ua_hash = hash_request_value(request.META.get("HTTP_USER_AGENT", ""))
    vote = BattleVote(
        battle=battle,
        voter=user,
        voted_for=voted_for,
        ip_hash=ip_hash,
        user_agent_hash=ua_hash,
    )
    try:
        vote.full_clean()
        vote.save()
    except (IntegrityError, ValidationError):
        messages.warning(request, "Your vote for this battle has already been recorded.")
        return redirect(battle.get_absolute_url())

    create_battle_event(
        event_type=BattleEvent.EventType.VOTE_CAST,
        battle=battle,
        actor=None,
        target=voted_for,
        message=f"A vote landed for {voted_for.name} in Chef Battle: {battle.theme}.",
        is_public=False,
    )
    messages.success(request, "Vote recorded.")
    return redirect(battle.get_absolute_url())


def rankings(request):
    profiles = ChefBattleProfile.objects.select_related("author").order_by("-rating", "-wins", "author__name")[:100]
    return render(request, "chef_battle/rankings.html", {"profiles": profiles})
