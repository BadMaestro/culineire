from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import is_moderator
from monitoring.tracker import get_client_ip
from recipes.authoring import get_author_for_user
from recipes.models import RecipeAuthor

from .access import chef_battle_guard
from .forms import BattleChallengeForm, BattleEntryForm
from .models import Battle, BattleChallenge, BattleEvent, BattleVote, ChefBattleProfile
from .selectors import (
    get_active_battles,
    get_battle_vote_counts,
    get_expired_active_battles,
    get_public_events,
    get_rankings,
    get_received_challenges,
    get_recent_completed_battles,
    get_sent_challenges,
    get_top_profiles,
)
from .services import (
    accept_challenge,
    calculate_battle_result,
    create_battle_event,
    get_or_create_battle_profile,
    hash_request_value,
    refuse_challenge,
    reveal_entries_if_ready,
)


def _battlefield_status(count: int, *, target: int = 1) -> str:
    if count >= target:
        return "done"
    if count > 0:
        return "active"
    return "pending"


def _build_battlefield_progress():
    challenge_count = BattleChallenge.objects.count()
    pending_challenges = BattleChallenge.objects.filter(status=BattleChallenge.Status.PENDING).count()
    refused_challenges = BattleChallenge.objects.filter(status=BattleChallenge.Status.REFUSED).count()
    battle_count = Battle.objects.count()
    active_battles = Battle.objects.filter(status__in=[Battle.Status.ACTIVE, Battle.Status.VOTING, Battle.Status.SCHEDULED]).count()
    completed_battles = Battle.objects.filter(status=Battle.Status.COMPLETED).count()
    entry_count = Battle.objects.filter(entries__isnull=False).distinct().count()
    vote_count = BattleVote.objects.count()
    event_count = BattleEvent.objects.filter(is_public=True).count()
    profile_count = ChefBattleProfile.objects.count()
    feature_enabled = getattr(settings, "CHEF_BATTLE_ENABLED", False)

    phases = [
        {
            "title": "Phase 0 - Sandbox Gate And Branch Discipline",
            "items": [
                {"label": "Chef Battle isolated from production", "detail": "Work remains in feature/chef-battle and reaches main only through a reviewed pull request.", "status": "manual"},
                {"label": "Feature flag defaults off", "detail": "CHEF_BATTLE_ENABLED defaults to False, so live production does not load battle URLs or homepage battle queries.", "status": "done"},
                {"label": "Sandbox enablement", "detail": "Enable CHEF_BATTLE_ENABLED=True only in the production-hosted Sandbox after migrations are applied.", "status": "done" if feature_enabled else "manual"},
                {"label": "Production release rule", "detail": "No Chef Battle deploy to live production until sandbox QA, PR review, and explicit merge to main.", "status": "manual"},
            ],
        },
        {
            "title": "Phase 1 - MVP Battle Loop",
            "items": [
                {"label": "Battle data model", "detail": "Profiles, challenges, battles, entries, votes, events, moves, artifacts and seasons have an initial schema.", "status": "done"},
                {"label": "Challenge flow", "detail": f"{challenge_count} challenge(s) created; {pending_challenges} pending; {refused_challenges} refused.", "status": _battlefield_status(challenge_count)},
                {"label": "Battle room", "detail": f"{battle_count} battle room(s) created; {active_battles} active/scheduled/voting; {completed_battles} completed.", "status": _battlefield_status(battle_count)},
                {"label": "Recipe/article submissions", "detail": f"{entry_count} battle(s) currently have at least one submitted entry.", "status": _battlefield_status(entry_count)},
                {"label": "Public voting", "detail": f"{vote_count} vote(s) recorded. MVP rule: one authenticated vote or protected anonymous session per battle.", "status": _battlefield_status(vote_count)},
                {"label": "7-day MVP timer", "detail": "Concept 3.0 recommends 7 days for authors and audience; current implementation still needs timer adjustment.", "status": "pending"},
                {"label": "Manual battle moderation", "detail": "First 20-30 battles should be manually checked for theme fit, spam, image rights, recipe quality and rule violations.", "status": "pending"},
            ],
        },
        {
            "title": "Phase 2 - Make Battles Sound Across The Site",
            "items": [
                {"label": "Battle event feed", "detail": f"{event_count} public battle event(s) available for the arena, profiles and news-style surfaces.", "status": _battlefield_status(event_count)},
                {"label": "Chef profile battle record", "detail": f"{profile_count} chef battle profile(s) exist with rank, rating, wins, losses, refusals and moves.", "status": _battlefield_status(profile_count)},
                {"label": "Homepage battle block", "detail": "Homepage battle visibility is implemented behind CHEF_BATTLE_ENABLED and should stay sandbox-only until PR approval.", "status": "done"},
                {"label": "Newsfeed integration", "detail": "Challenge, refusal, battle start, submission and completion events can create site news entries.", "status": "done"},
                {"label": "Live visitor notifications", "detail": "Optional later layer: surface challenge wins, new crowns and final-hour voting through live pop-ups.", "status": "pending"},
            ],
        },
        {
            "title": "Phase 3 - Sandbox Launch Preparation",
            "items": [
                {"label": "First 5-10 sandbox battles", "detail": f"{completed_battles}/5 completed sandbox-style battles. Public launch should not feel empty.", "status": _battlefield_status(completed_battles, target=5)},
                {"label": "Founding Chef programme", "detail": "Define Founding Chef criteria, profile marker, invite copy and founder visibility rules.", "status": "pending"},
                {"label": "Battle rules and moderation checklist", "detail": "Write public rules for challenges, refusals, image rights, vote abuse, spam and respectful rivalry.", "status": "pending"},
                {"label": "Outreach list", "detail": "Prepare 30-50 Irish food creators, local chefs, students and bloggers for direct invite outreach.", "status": "pending"},
                {"label": "AllFresh / sponsor pilot", "detail": "Draft one sponsor-ready battle concept, value proposition and sample landing copy.", "status": "pending"},
            ],
        },
        {
            "title": "Later Phases - Deliberately Not MVP",
            "items": [
                {"label": "Attacks, blocks and battle moves", "detail": "Keep this out of MVP until basic voting battles have real participation data.", "status": "manual"},
                {"label": "Artifacts and cosmetics", "detail": "Artifacts should be earned through gameplay; cosmetics can become non-pay-to-win monetisation later.", "status": "manual"},
                {"label": "Seasons and tournaments", "detail": "Add only after ordinary battles produce history, rivals, winners and audience interest.", "status": "manual"},
            ],
        },
    ]

    items = [item for phase in phases for item in phase["items"]]
    completed_items = [item for item in items if item["status"] == "done"]
    active_items = [item for item in items if item["status"] != "done"]
    done_count = len(completed_items)
    total_count = len(items)
    percent = round((done_count / total_count) * 100) if total_count else 0

    copy_lines = [
        "CulinEire Chef Battle battlefield handoff",
        f"Progress: {done_count}/{total_count} items complete ({percent}%).",
        "Branch rule: Codex works only in feature/chef-battle; main is production-only and receives Chef Battle only through reviewed PR.",
        "MVP rule: keep the first launch simple - chef profile, challenge, battle room, two submissions, 7-day timer, voting, result, events.",
        "Do not add attacks, blocks, artifacts, paid energy, seasons or tournaments to MVP.",
        "",
        "Current metrics:",
        f"- Chef profiles: {profile_count}",
        f"- Challenges: {challenge_count} ({pending_challenges} pending, {refused_challenges} refused)",
        f"- Battles: {battle_count} ({active_battles} active/scheduled/voting, {completed_battles} completed)",
        f"- Battles with entries: {entry_count}",
        f"- Votes: {vote_count}",
        f"- Public events: {event_count}",
        "",
        "Open / manual work:",
    ]
    for phase in phases:
        open_items = [item for item in phase["items"] if item["status"] != "done"]
        if not open_items:
            continue
        copy_lines.append(f"{phase['title']}:")
        for item in open_items:
            copy_lines.append(f"- [{item['status']}] {item['label']} - {item['detail']}")

    return {
        "phases": phases,
        "items": items,
        "active_items": active_items,
        "completed_items": completed_items,
        "done_count": done_count,
        "total_count": total_count,
        "percent": percent,
        "copy_text": "\n".join(copy_lines),
        "metrics": {
            "profile_count": profile_count,
            "challenge_count": challenge_count,
            "battle_count": battle_count,
            "completed_battles": completed_battles,
            "vote_count": vote_count,
            "event_count": event_count,
            "feature_enabled": feature_enabled,
        },
    }


@chef_battle_guard
@login_required
def battlefield_progress(request):
    if not is_moderator(request.user):
        raise PermissionDenied

    return render(
        request,
        "chef_battle/battlefield_progress.html",
        {"battlefield_progress": _build_battlefield_progress()},
    )


@chef_battle_guard
def battle_home(request):
    for battle in get_expired_active_battles():
        calculate_battle_result(battle)

    active_battles = get_active_battles()
    recent_battles = get_recent_completed_battles()
    leaders = get_top_profiles()
    events = get_public_events()

    return render(request, "chef_battle/home.html", {
        "active_battles": active_battles,
        "recent_battles": recent_battles,
        "leaders": leaders,
        "events": events,
    })


@chef_battle_guard
@login_required
def challenge_list(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author profile required before entering Chef Battle.")
        return redirect("home")

    sent = get_sent_challenges(author)
    received = get_received_challenges(author)
    return render(request, "chef_battle/challenge_list.html", {
        "author": author,
        "sent_challenges": sent,
        "received_challenges": received,
    })


@chef_battle_guard
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


@chef_battle_guard
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


@chef_battle_guard
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

    vote_counts = get_battle_vote_counts(battle)
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


@chef_battle_guard
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


@chef_battle_guard
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


@chef_battle_guard
def rankings(request):
    profiles = get_rankings()
    return render(request, "chef_battle/rankings.html", {"profiles": profiles})
