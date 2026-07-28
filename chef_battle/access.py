from __future__ import annotations

import secrets
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def valid_share_token(provided, expected) -> bool:
    """Constant-time check for an unlisted share-link path segment.

    The credential is the URL segment itself, so this is the whole gate. Two
    rules make it safe: an empty or unset ``expected`` never matches (a
    misconfigured deployment must not serve to a caller who guessed an empty
    segment), and the comparison is constant-time (a plain ``==`` leaks the
    secret's prefix through timing on an endpoint anyone can reach).

    It is obscurity, not authentication: whoever holds the link, and whoever
    they forward it to, gets in. Rotation is changing the configured value.
    """
    expected = (expected or "").strip()
    if not expected:
        return False
    return secrets.compare_digest(str(provided), expected)


def is_battle_visible(request) -> bool:
    """
    Chef Battles is visible when:
    - CHEF_BATTLE_ENABLED is True (public launch), OR
    - the user is staff/superuser or a bearseeker author (dark-launch
      operator preview).

    Bearseeker authors are test operators and the sitewide UI already shows
    them the Arena entrance. Including them here removes the gate leak where
    that entrance led to a 404; it does not widen the audience advertised by
    the UI. Anonymous visitors and ordinary authenticated authors remain
    excluded. Chef enrollment is a participation state, never a visibility
    grant.

    The Arena Master Console stays behind ``has_arena_console_access``
    (superuser + owner/flag), which is stricter than this gate — so nothing
    here opens the console to a bare staff or bearseeker user.
    """
    if getattr(settings, "CHEF_BATTLE_ENABLED", False):
        return True
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    author = getattr(user, "recipe_author_profile", None)
    return bool(author is not None and author.has_bearseeker_privileges)


def has_arena_console_access(request) -> bool:
    """
    Arena Master Console access (decision gate DG-01, P00_DECISIONS.yaml):
    - The owner (superuser + OWNER_SLUG) ALWAYS has access — the whole site
      is always visible to the owner, feature flags never hide it from them.
    - Other operators need superuser + RecipeAuthor.has_arena_console_access,
      AND the ARENA_MASTER_CONSOLE_ENABLED kill switch must be on.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return False
    author = getattr(user, "recipe_author_profile", None)
    if author is None:
        return False
    if author.slug == settings.OWNER_SLUG:
        return True
    return (
        getattr(settings, "ARENA_MASTER_CONSOLE_ENABLED", False)
        and author.has_arena_console_access
    )


def arena_console_guard(view_func):
    """
    View decorator for Arena Master Console views: Http404 for anyone who
    fails the DG-01 access check (same failure mode as the moderation tools).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not has_arena_console_access(request):
            raise Http404
        return view_func(request, *args, **kwargs)
    wrapper.chef_battle_access_checked = True
    return wrapper


# Routed chef_battle views that deliberately carry neither chef_battle_guard nor
# arena_console_guard, each with the reason. A guard-by-decorator scheme is
# fail-open: a view added without the decorator is simply public, and nothing
# says so out loud. This list makes the absence deliberate — test_every_routed_
# view_is_guarded_or_listed fails on any routed view that is neither guarded nor
# named here, so a new endpoint cannot become public by omission.
#
# Adding a name here is a decision about who may reach a page. It is not a
# formality, and it is not a way to silence the test.
UNGUARDED_BY_DESIGN = {
    # Public by intent: reference material about the game, no user data.
    "battle_rules": "Public rules page, no user data.",
    "battle_guide": "Permanent redirect to the rules page.",
    "artifact_gallery": "Public artifact catalogue; staff-only generation is checked inside.",
    "artifact_detail": "Public, linkable reference page for one artifact.",
    "appreciation_gallery": "Public gift catalogue with costs.",
    "chef_battle_profile": "Permanent redirect to the author page, keeps old links alive.",

    # These carry their own credential. The visibility gate would break them.
    "arena_preview_current": "The share-token URL segment IS the credential; 404s when unset or wrong.",
    "arena_preview_prototype": "Same share-token credential as the current-arena preview.",
    "token_stripe_webhook": "Called by Stripe, not a browser; authenticated by webhook signature.",

    # Signed-in surfaces that authorise per object: author profile, battle
    # participation, moderator status or a fraud gate, checked in the view.
    "age_verification": "login_required; requires the caller's own author profile.",
    "chef_enroll": "login_required; onboarding for the caller's own account.",
    "enroll_success": "login_required; confirmation for the caller's own enrolment.",
    "reward_agreement": "login_required; PermissionDenied without an author profile.",
    "payout_statement": "login_required; PermissionDenied without an author profile.",
    "battle_chest": "login_required; shows only the caller's own artifacts.",
    "changing_room": "login_required; shows only the caller's own state.",
    "battle_changing_room": "login_required; PermissionDenied unless a battle participant.",
    "battle_recipe_attach": "login_required; participant-checked in the view.",
    "biathlon": "login_required; PermissionDenied unless a battle participant.",
    "content_report_submit": "login_required; DSA reporting endpoint, validates its own input.",
    "send_appreciation_gift_view": "login_required; runs the fraud gates including suspension.",
    "send_viewer_battle_gift_view": "login_required; runs the fraud gates including suspension.",
    "token_checkout_create": "login_required; wallet is resolved from the caller.",
    "artifact_generate_image": "login_required; staff/moderator checked in the view.",

    # Poll and action endpoints that call is_battle_visible directly, because
    # the guard's suspended-POST branch would stack a banner on every poll.
    "arena_state": "Calls is_battle_visible directly; guard would add a banner per 20s poll.",
    "arena_ping": "Calls is_battle_visible directly; heartbeat endpoint.",
    "arena_take_seat": "Calls is_battle_visible directly.",
    "arena_react": "Calls is_battle_visible directly.",
    "arena_blast": "Calls is_battle_visible directly.",
    "battle_chat_poll": "Calls is_battle_visible directly; previously leaked chat to anonymous.",
    "cooking_moderation": "Moderator-only, checked with is_moderator in the view.",
    "cooking_moderation_approve": "Moderator-only, checked with is_moderator in the view.",
}


def _suspended_redirect_target(request) -> str:
    """Where to send a suspended user whose POST was refused.

    Not back to ``request.path``. Many arena actions are POST-only
    (``@require_POST``), so redirecting a refused POST to its own URL lands the
    browser on a GET the view does not accept, and the user is told they are
    suspended by a bare 405. The referring page is where they actually were, so
    prefer it, and only when it is on this site — an attacker-supplied Referer
    must never become an open redirect.
    """
    referer = request.META.get("HTTP_REFERER") or ""
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return referer
    return reverse("chef_battle:arena")


def chef_battle_guard(view_func):
    """
    View decorator: raises Http404 for any user who cannot see Chef Battles.
    Suspended accounts are redirected with an error message on POST actions.
    Apply to every chef_battle view.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_battle_visible(request):
            raise Http404
        user = getattr(request, "user", None)
        if user and user.is_authenticated and request.method == "POST":
            try:
                profile = user.recipe_author_profile.battle_profile
            except Exception:
                profile = None
            # Deliberately outside the try: a suspension must not be swallowed
            # by an exception handler that exists only to tolerate a missing
            # profile. Previously any error raised while building the redirect
            # let the request fall through into the view.
            if profile is not None and profile.is_suspended:
                messages.error(
                    request,
                    "Your arena account is currently suspended. "
                    "Please contact us if you believe this is an error.",
                )
                return redirect(_suspended_redirect_target(request))
        return view_func(request, *args, **kwargs)
    # Marked so the URLconf can be audited at runtime instead of by reading
    # source: functools.wraps copies __dict__ outward, so the flag survives
    # decorators stacked above this one.
    wrapper.chef_battle_access_checked = True
    return wrapper
