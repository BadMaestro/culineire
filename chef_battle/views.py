from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import is_moderator
from monitoring.tracker import get_client_ip
from recipes.authoring import get_author_for_user
from recipes.models import RecipeAuthor

from .access import chef_battle_guard
from .forms import BattleChallengeForm, BattleEntryForm
from .models import Artifact, Battle, BattleChatMessage, BattleChallenge, BattleEntry, BattleEvent, BattleVote, ChefBattleProfile, TokenWallet
from .selectors import (
    get_active_battles,
    get_battle_vote_counts,
    get_expired_active_battles,
    get_hall_of_fame_battles,
    get_hall_of_fame_chefs,
    get_public_events,
    get_rankings,
    get_received_challenges,
    get_recent_completed_battles,
    get_sent_challenges,
    get_top_profiles,
)
from .services import (
    MOVES_MIN_TO_CHALLENGE,
    _notify_chef,
    accept_challenge,
    approve_cooking_phase,
    calculate_battle_result,
    check_level_matchup,
    create_battle_event,
    fire_ingredient_shot,
    get_battles_awaiting_cooking_approval,
    get_biathlon_state,
    get_or_create_battle_profile,
    hash_request_value,
    place_ingredient_lock,
    refuse_challenge,
    reveal_entries_if_ready,
    submit_cooked_photo,
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
    active_battles = Battle.objects.filter(status__in=Battle.ACTIVE_STATUSES).count()
    completed_battles = Battle.objects.filter(status=Battle.Status.COMPLETED).count()
    entry_count = Battle.objects.filter(entries__isnull=False).distinct().count()
    vote_count = BattleVote.objects.count()
    event_count = BattleEvent.objects.filter(is_public=True).count()
    profile_count = ChefBattleProfile.objects.count()
    artifact_count = Artifact.objects.count()
    chat_message_count = BattleChatMessage.objects.count()
    wallet_count = TokenWallet.objects.count()
    hero_count = ChefBattleProfile.objects.filter(is_hero=True).count()
    feature_enabled = getattr(settings, "CHEF_BATTLE_ENABLED", False)

    phases = [
        {
            "title": "Phase 0 - Sandbox Gate And Branch Discipline",
            "items": [
                {"label": "Chef Battle in production via main branch", "detail": "Chef Battle shipped to main, deployed to production, URLs live. Branch discipline followed throughout.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Feature flag in place", "detail": "CHEF_BATTLE_ENABLED controls homepage queries and battle URLs. Currently enabled on production.", "status": "done" if feature_enabled else "pending", "completed_at": "2026-06-10"},
                {"label": "Sandbox enablement confirmed", "detail": "CHEF_BATTLE_ENABLED=True applied on production server after all migrations verified.", "status": "done" if feature_enabled else "pending", "completed_at": "2026-06-10"},
                {"label": "Production release followed QA", "detail": "All Chef Battle deploys went through local check, migration verification and smoke test before push.", "status": "done", "completed_at": "2026-06-10"},
            ],
        },
        {
            "title": "Phase 1 - MVP Battle Loop",
            "items": [
                {"label": "Battle data model", "detail": "Profiles, challenges, battles, entries, votes, events, moves, artifacts and seasons have an initial schema.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Challenge flow", "detail": f"Feature built and live. Live: {challenge_count} challenge(s), {pending_challenges} pending, {refused_challenges} refused.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Battle room", "detail": f"Feature built and live. Live: {battle_count} battle(s), {active_battles} active, {completed_battles} completed.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Recipe submissions", "detail": f"Feature built and live. Live: {entry_count} battle(s) with at least one entry.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Public voting", "detail": f"Feature built and live. Live: {vote_count} vote(s) recorded. One vote per battle per session.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "7-day battle timer", "detail": "5 days for submissions + 2 days for voting = 7-day total battle window.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Manual battle moderation", "detail": "First 20-30 battles should be manually checked for theme fit, spam, image rights, recipe quality and rule violations.", "status": "pending"},
            ],
        },
        {
            "title": "Phase 2 - Make Battles Sound Across The Site",
            "items": [
                {"label": "Battle event feed", "detail": f"Feature built and live. Live: {event_count} public battle event(s) on arena, profiles and news surfaces.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Chef profile battle record", "detail": f"Feature built and live. Live: {profile_count} chef battle profile(s) with rank, rating, wins, losses, refusals and moves.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Homepage battle block", "detail": "Homepage battle block live behind CHEF_BATTLE_ENABLED.", "status": "done", "completed_at": "2026-06-12"},
                {"label": "Newsfeed integration", "detail": "Challenge, refusal, battle start, submission and completion events create site news entries.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Live visitor notifications", "detail": "Polling every 45s surfaces pending challenges and unread battle messages as a toast while browsing.", "status": "done", "completed_at": "2026-06-12"},
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
            "title": "Phase 4 - Combat Mechanics",
            "items": [
                {"label": "Full battle status lifecycle", "detail": "menu_locked, active, biathlon, ingredient_penalty, cooking, presentation, voting, completed phases all wired.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Biathlon mechanic", "detail": "Winner of cooking submission shoots up to 3 times at opponent ingredients. Locks protect chosen items.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Ingredient combat (locks and hits)", "detail": "Each chef locks 2 ingredients before combat; hits land on unlocked slots; killed ingredients replaced or removed.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Cooking phase with photo upload", "detail": "After biathlon, chefs photograph finished dishes. Moderator approves before presentation.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Cooking moderation", "detail": "Moderator checklist confirms real cooking happened, image rights are clear and rules were followed.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Chef levels (1-5 + CulinEire Hero)", "detail": f"Level system live: 3 wins per level, Hero at 15+ wins. {hero_count} CulinEire Hero chef(s) currently.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Level matchup guard", "detail": "Challenges between chefs more than 1 level apart are blocked to protect newer chefs.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Hall of Fame", "detail": f"Top 10 battles and top 20 chefs visible at /chef-battle/hall-of-fame/. {completed_battles} completed battle(s) recorded.", "status": "done", "completed_at": "2026-06-12"},
                {"label": "Visual asset set", "detail": "SVG icons for all 5 levels, CulinEire Hero, 5 rarities, attack/defence types, crown, Michelin star and token.", "status": "done", "completed_at": "2026-06-12"},
            ],
        },
        {
            "title": "Phase 5 - Economy And Audience Engagement",
            "items": [
                {"label": "Token economy", "detail": f"TokenWallet, TokenTransaction and TokenPackage models live. {wallet_count} wallet(s) created.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "200 combat artifacts", "detail": f"{artifact_count} artifact(s) loaded: 100 attack and 100 defence across 5 rarities (Common 10T to Legendary 400T).", "status": "done" if artifact_count >= 200 else _battlefield_status(artifact_count), "completed_at": "2026-06-12"},
                {"label": "Viewer gifts and appreciation", "detail": "Audience can send flowers, coffee, beer, whiskey and cocktails (5-20T). Battle artifact gifts also supported.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Battle live chat", "detail": f"Live chat on battle pages with 8s polling. {chat_message_count} message(s) sent so far. Works for logged-in and anonymous viewers.", "status": "done", "completed_at": "2026-06-12"},
                {"label": "Token package pricing", "detail": "100T=10 EUR up to 1400T=80 EUR. Packages defined, Stripe integration pending.", "status": "active"},
                {"label": "Stripe token purchase", "detail": "Stripe checkout flow for token packages not yet wired. Requires Stripe live key and webhook.", "status": "pending"},
                {"label": "Artifact gifting UI", "detail": "Backend service for artifact and appreciation gift sending is built. Battle detail UI panel not yet exposed.", "status": "pending"},
            ],
        },
        {
            "title": "Phase 6 - Seasons, Clans And Sponsorship",
            "items": [
                {"label": "Seasons and leaderboards", "detail": "Add only after ordinary battles produce history, rivals, winners and audience interest.", "status": "pending"},
                {"label": "Clan / team battles", "detail": "Team-based battle formats after individual battle mechanics are stable and tested.", "status": "pending"},
                {"label": "Sponsor battle integration", "detail": "Named sponsor battles, branded themes and sponsor landing pages after AllFresh pilot.", "status": "pending"},
                {"label": "Cosmetics and prestige items", "detail": "Profile frames, animated banners and crowns as non-pay-to-win prestige cosmetics.", "status": "pending"},
                {"label": "TikTok / Instagram live integration", "detail": "Stream cooking phase live. Requires platform account verification and API approval.", "status": "pending"},
            ],
        },
    ]

    items = [item for phase in phases for item in phase["items"]]
    completed_items = sorted(
        [item for item in items if item["status"] == "done"],
        key=lambda x: x.get("completed_at", ""),
        reverse=True,
    )
    active_items = [item for item in items if item["status"] != "done"]
    countable_items = [item for item in items if item["status"] != "manual"]
    done_count = len(completed_items)
    total_count = len(countable_items)
    percent = round((done_count / total_count) * 100) if total_count else 0

    copy_lines = [
        "CulinEire Chef Battle battlefield handoff",
        f"Progress: {done_count}/{total_count} items complete ({percent}%).",
        "",
        "Current metrics:",
        f"- Chef profiles: {profile_count} ({hero_count} CulinEire Hero)",
        f"- Challenges: {challenge_count} ({pending_challenges} pending, {refused_challenges} refused)",
        f"- Battles: {battle_count} ({active_battles} active, {completed_battles} completed)",
        f"- Battles with entries: {entry_count}",
        f"- Votes: {vote_count}",
        f"- Public events: {event_count}",
        f"- Artifacts loaded: {artifact_count}",
        f"- Token wallets: {wallet_count}",
        f"- Chat messages: {chat_message_count}",
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
            "hero_count": hero_count,
            "challenge_count": challenge_count,
            "battle_count": battle_count,
            "completed_battles": completed_battles,
            "vote_count": vote_count,
            "event_count": event_count,
            "artifact_count": artifact_count,
            "wallet_count": wallet_count,
            "chat_message_count": chat_message_count,
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

    profile = get_or_create_battle_profile(author)
    if not profile.infinite_moves and profile.battle_moves < MOVES_MIN_TO_CHALLENGE:
        messages.error(
            request,
            f"You need at least {MOVES_MIN_TO_CHALLENGE} energy to issue a challenge. "
            f"You have {profile.battle_moves}. Publish recipes or articles to earn more."
        )
        return redirect("chef_battle:challenge_list")

    if request.method == "POST":
        form = BattleChallengeForm(request.POST, challenger=author)
        if form.is_valid():
            level_error = check_level_matchup(author, form.cleaned_data["opponent"])
            if level_error:
                messages.error(request, level_error)
                return render(request, "chef_battle/challenge_form.html", {"form": form})
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
            _notify_chef(
                author, challenge.opponent,
                subject=f"You have been challenged to a Chef Battle: {challenge.theme}",
                body=(
                    f"{author.name} has challenged you to a Chef Battle!\n\n"
                    f"Theme: {challenge.theme}\n"
                    f"Battle type: {challenge.get_battle_type_display()}\n"
                    + (f"\nMessage: {challenge.message}\n" if challenge.message else "")
                    + f"\nAccept or refuse in your challenges inbox: "
                    f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}"
                    + reverse("chef_battle:challenge_list")
                ),
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
        and battle.status in {Battle.Status.MENU_LOCKED, Battle.Status.ACTIVE, Battle.Status.VOTING}
        and timezone.now() <= battle.submission_deadline
    )

    from .services import get_combat_state, get_or_create_battle_profile
    combat_state = get_combat_state(battle)
    is_participant = bool(viewer_author and battle.author_is_participant(viewer_author))
    user_battle_moves = 0
    viewer_has_moved = False
    opponent_has_moved = False
    if is_participant:
        profile = get_or_create_battle_profile(viewer_author)
        user_battle_moves = profile.battle_moves
        from .models import BattleCombatAction
        round_chef_ids = set(
            BattleCombatAction.objects.filter(
                battle=battle, round_number=combat_state["current_round"]
            ).values_list("chef_id", flat=True)
        )
        viewer_has_moved = viewer_author.pk in round_chef_ids
        opponent_has_moved = bool(round_chef_ids - {viewer_author.pk})

    from .models import AppreciationGiftType, APPRECIATION_GIFT_COST
    appreciation_gifts = [
        {"type": k, "label": AppreciationGiftType(k).label, "cost": v, "emoji": {
            "flowers": "💐", "coffee": "☕", "beer": "🍺", "cocktail": "🍹", "whiskey": "🥃",
        }.get(k, "🎁")}
        for k, v in APPRECIATION_GIFT_COST.items()
    ]
    viewer_token_balance = 0
    if viewer_author:
        from .models import TokenWallet
        wallet = TokenWallet.objects.filter(chef=viewer_author).first()
        viewer_token_balance = wallet.balance if wallet else 0

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
        "is_participant": is_participant,
        "combat_state": combat_state,
        "user_battle_moves": user_battle_moves,
        "viewer_has_moved": viewer_has_moved,
        "opponent_has_moved": opponent_has_moved,
        "appreciation_gifts": appreciation_gifts,
        "viewer_token_balance": viewer_token_balance,
        "active_statuses": Battle.ACTIVE_STATUSES,
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


@chef_battle_guard
@login_required
def my_moves(request):
    from django.db.models import Sum
    from .models import BattleMoveTransaction
    from .services import (
        MOVES_CONTENT_DAILY_CAP, MOVES_CONTENT_WEEKLY_CAP,
        _content_moves_total, _CONTENT_REASONS,
    )

    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author profile required.")
        return redirect("home")

    profile = get_object_or_404(ChefBattleProfile, author=author)
    transactions = (
        BattleMoveTransaction.objects
        .filter(chef=author)
        .order_by("-created_at")[:100]
    )

    now = timezone.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = (now - timezone.timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    return render(request, "chef_battle/my_moves.html", {
        "profile": profile,
        "transactions": transactions,
        "daily_earned": _content_moves_total(author, day_start),
        "weekly_earned": _content_moves_total(author, week_start),
        "daily_cap": MOVES_CONTENT_DAILY_CAP,
        "weekly_cap": MOVES_CONTENT_WEEKLY_CAP,
    })


@chef_battle_guard
@login_required
def notifications_poll(request):
    """Return unread battle notification count for live polling."""
    from django.http import JsonResponse
    from messaging.models import Message
    author = get_author_for_user(request.user)

    unread_battle_msgs = (
        Message.objects
        .filter(recipient=request.user, is_read=False, subject__icontains="battle")
        .count()
    )
    pending_challenges = 0
    if author:
        pending_challenges = BattleChallenge.objects.filter(
            opponent=author,
            status=BattleChallenge.Status.PENDING,
        ).count()

    total = unread_battle_msgs + pending_challenges
    items = []
    if pending_challenges:
        items.append({"text": f"{pending_challenges} battle challenge{'s' if pending_challenges != 1 else ''} waiting", "url": "/chef-battle/"})
    if unread_battle_msgs:
        items.append({"text": f"{unread_battle_msgs} unread battle message{'s' if unread_battle_msgs != 1 else ''}", "url": "/messages/"})

    return JsonResponse({"count": total, "items": items})


@chef_battle_guard
@login_required
@require_POST
def battle_combat_action(request, pk):
    """Chef submits their combat action for the current round."""
    from django.http import JsonResponse
    from .services import submit_combat_action, get_combat_state

    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)
    if not author or not battle.author_is_participant(author):
        return JsonResponse({"ok": False, "error": "Not a participant."}, status=403)

    action_type = request.POST.get("action_type", "")
    try:
        moves_invested = int(request.POST.get("moves_invested", 1))
    except (ValueError, TypeError):
        moves_invested = 1

    try:
        submit_combat_action(battle, author, action_type, moves_invested)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    state = get_combat_state(battle)
    return JsonResponse({
        "ok": True,
        "challenger_hits": state["challenger_hits"],
        "opponent_hits": state["opponent_hits"],
        "current_round": state["current_round"],
        "rounds": [
            {
                "round_number": r.round_number,
                "outcome": r.outcome,
                "log_message": r.log_message,
            }
            for r in state["rounds"]
        ],
    })


@chef_battle_guard
@login_required
def battle_state_poll(request, pk):
    """Lightweight GET endpoint — returns current combat state for auto-poll."""
    from django.http import JsonResponse
    from .services import get_combat_state
    from .models import BattleCombatAction

    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)
    state = get_combat_state(battle)

    viewer_has_moved = False
    viewer_moves = 0
    if author and battle.author_is_participant(author):
        viewer_has_moved = BattleCombatAction.objects.filter(
            battle=battle, chef=author, round_number=state["current_round"]
        ).exists()
        from .services import get_or_create_battle_profile
        viewer_moves = get_or_create_battle_profile(author).battle_moves

    combat_winner = None
    if battle.status == Battle.Status.AWAITING_SUBMISSIONS:
        ch = state["challenger_hits"]
        op = state["opponent_hits"]
        if ch > op:
            combat_winner = battle.challenger.name
        elif op > ch:
            combat_winner = battle.opponent.name
        else:
            combat_winner = "Draw"

    return JsonResponse({
        "ok": True,
        "status": battle.status,
        "viewer_moves": viewer_moves,
        "challenger_hits": state["challenger_hits"],
        "opponent_hits": state["opponent_hits"],
        "challenger_name": battle.challenger.name,
        "opponent_name": battle.opponent.name,
        "current_round": state["current_round"],
        "viewer_has_moved": viewer_has_moved,
        "combat_winner": combat_winner,
        "rounds": [
            {
                "round_number": r.round_number,
                "outcome": r.outcome,
                "log_message": r.log_message,
            }
            for r in state["rounds"]
        ],
    })


@login_required
def biathlon(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        messages.error(request, "The biathlon phase is not active for this battle.")
        return redirect(battle.get_absolute_url())
    viewer_author = get_author_for_user(request.user)
    if not battle.author_is_participant(viewer_author):
        raise PermissionDenied
    state = get_biathlon_state(battle)
    return render(request, "chef_battle/biathlon.html", {
        "battle": battle,
        "state": state,
        "is_winner": viewer_author and battle.winner_id == viewer_author.pk,
        "is_loser": viewer_author and battle.loser_id == viewer_author.pk,
    })


@login_required
@require_POST
def biathlon_lock(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    viewer_author = get_author_for_user(request.user)
    try:
        index = int(request.POST.get("ingredient_index", -1))
        place_ingredient_lock(battle=battle, chef=viewer_author, ingredient_index=index)
        messages.success(request, "Lock placed.")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    return redirect("chef_battle:biathlon", pk=pk)


@login_required
@require_POST
def biathlon_shoot(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    viewer_author = get_author_for_user(request.user)
    try:
        index = int(request.POST.get("target_index", -1))
        shot = fire_ingredient_shot(battle=battle, shooter=viewer_author, target_index=index)
        if shot.bounced:
            messages.warning(request, "Your shot bounced off a lock!")
        else:
            messages.success(request, "Direct hit!")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    return redirect("chef_battle:biathlon", pk=pk)


@login_required
def cooking_moderation(request):
    if not is_moderator(request.user):
        raise PermissionDenied
    battles = get_battles_awaiting_cooking_approval()
    return render(request, "chef_battle/cooking_moderation.html", {"battles": battles})


@login_required
@require_POST
def cooking_moderation_approve(request, pk):
    if not is_moderator(request.user):
        raise PermissionDenied
    battle = get_object_or_404(Battle, pk=pk)
    try:
        approve_cooking_phase(battle, request.user)
        messages.success(request, f"Cooking phase approved for: {battle.theme}")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("chef_battle:cooking_moderation")


@login_required
def cooking_submit(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)
    if not author or not battle.author_is_participant(author):
        raise PermissionDenied

    if battle.status != Battle.Status.COOKING:
        messages.error(request, "This battle is not in the cooking phase.")
        return redirect("chef_battle:battle_detail", pk=pk)

    try:
        my_entry = battle.entries.get(author=author)
    except BattleEntry.DoesNotExist:
        raise PermissionDenied

    if request.method == "POST":
        photo = request.FILES.get("cooked_photo")
        if not photo:
            messages.error(request, "Please select a photo to upload.")
        else:
            try:
                submit_cooked_photo(battle=battle, author=author, photo=photo)
                messages.success(request, "Your cooked dish photo has been submitted!")
            except ValueError as e:
                messages.error(request, str(e))
        return redirect("chef_battle:battle_detail", pk=pk)

    return render(request, "chef_battle/cooking_submit.html", {
        "battle": battle,
        "my_entry": my_entry,
    })


@chef_battle_guard
def hall_of_fame(request):
    battles = get_hall_of_fame_battles(limit=10)
    chefs = get_hall_of_fame_chefs(limit=20)
    return render(request, "chef_battle/hall_of_fame.html", {
        "battles": battles,
        "chefs": chefs,
    })


@require_POST
def battle_chat_send(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    if battle.status not in Battle.ACTIVE_STATUSES | {Battle.Status.COMPLETED}:
        return redirect("chef_battle:battle_detail", pk=pk)

    from .models import BattleChatMessage
    body = request.POST.get("body", "").strip()[:300]
    if not body:
        return redirect("chef_battle:battle_detail", pk=pk)

    if request.user.is_authenticated:
        display_name = request.user.get_full_name() or request.user.username
    else:
        display_name = request.POST.get("display_name", "").strip()[:60] or "Anonymous"

    BattleChatMessage.objects.create(
        battle=battle,
        author=request.user if request.user.is_authenticated else None,
        display_name=display_name,
        body=body,
    )
    return redirect("chef_battle:battle_detail", pk=pk)


def battle_chat_poll(request, pk):
    from django.http import JsonResponse
    from .models import BattleChatMessage
    battle = get_object_or_404(Battle, pk=pk)
    since_id = int(request.GET.get("since", 0))
    msgs = (
        BattleChatMessage.objects
        .filter(battle=battle, id__gt=since_id, is_hidden=False)
        .order_by("created_at")[:40]
    )
    return JsonResponse({
        "messages": [
            {
                "id": m.id,
                "display_name": m.display_name,
                "body": m.body,
                "created_at": m.created_at.strftime("%H:%M"),
            }
            for m in msgs
        ]
    })


@login_required
@require_POST
def send_appreciation_gift_view(request, pk):
    from .models import AppreciationGiftType
    from .services import send_appreciation_gift
    battle = get_object_or_404(Battle, pk=pk)
    recipient_slug = request.POST.get("recipient_slug", "")
    gift_type = request.POST.get("gift_type", "")
    recipient = get_object_or_404(RecipeAuthor, slug=recipient_slug)
    if not battle.author_is_participant(recipient):
        messages.error(request, "Invalid recipient.")
        return redirect("chef_battle:battle_detail", pk=pk)
    try:
        send_appreciation_gift(
            sender_user=request.user,
            recipient=recipient,
            gift_type=gift_type,
            message=request.POST.get("message", ""),
        )
        messages.success(request, f"Gift sent to {recipient.name}!")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("chef_battle:battle_detail", pk=pk)


def chef_battle_profile(request, slug):
    from django.db.models import Q, Count
    from .models import AppreciationGiftType, APPRECIATION_GIFT_COST
    author = get_object_or_404(RecipeAuthor, slug=slug)
    profile = get_object_or_404(ChefBattleProfile, author=author)
    battles = (
        Battle.objects
        .filter(Q(challenger=author) | Q(opponent=author))
        .select_related("challenger", "opponent", "challenge")
        .order_by("-created_at")[:20]
    )
    # Aggregate gifts by type
    gift_counts = (
        author.appreciation_gifts
        .values("gift_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    gift_display = [
        {
            "type": g["gift_type"],
            "label": AppreciationGiftType(g["gift_type"]).label,
            "count": g["total"],
            "emoji": {"flowers": "💐", "coffee": "☕", "beer": "🍺", "cocktail": "🍹", "whiskey": "🥃"}.get(g["gift_type"], "🎁"),
        }
        for g in gift_counts
    ]
    viewer_author = get_author_for_user(request.user) if request.user.is_authenticated else None
    return render(request, "chef_battle/chef_profile.html", {
        "profile": profile,
        "author": author,
        "battles": battles,
        "gift_display": gift_display,
        "is_own_profile": viewer_author and viewer_author.pk == author.pk,
    })
