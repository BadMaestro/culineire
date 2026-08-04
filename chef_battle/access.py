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
    - the user is a SUPERUSER - a "(Bear)seeker Super User" in the Owner's own
      naming, the top of the three tiers this site has.

    THE RULE, from the Owner, 2026-08-04, in his own three tiers:

      Author                    - sees NOTHING of Chef Battles
      (Bear)seeker Admin        - sees NOTHING of Chef Battles
      (Bear)seeker Super User   - sees the whole application

    The only things outside this gate are the rules page and the sitewide news.
    Everything else in the app - arena, galleries, shop, profiles, rankings -
    is superuser-only until he opens it.

    WHAT THIS CORRECTS. Until v2.5.798 this returned True for `is_staff` and
    for any author holding `has_bearseeker_privileges`. Both were wider than
    the product contract, which has read `recipe_author_without_staff: false`
    since 2026-07-20. The bearseeker branch had already been removed once, on
    2026-07-21 (f3edd724, "Arena access: staff/superuser-only"), and was put
    back five days later by 5169c08b under a one-line commit message with no
    rationale and no recorded decision - while AGENTS.md section 8 requires the
    Owner's explicit word for every change to an access gate. On production it
    was admitting two live accounts carrying no staff and no superuser bit.

    The flag it trusted does not mean what the old docstring claimed either. It
    called bearseekers "test operators"; `RecipeAuthor.has_bearseeker_privileges`
    is labelled "Can moderate site content" - a site moderator, not a tester.

    `is_staff` goes for the same reason: staff is not the Owner's top tier.

    Chef enrollment is a participation state and was never a visibility grant.

    The Arena Master Console stays stricter still, behind
    ``has_arena_console_access``: the Owner always, and another superuser only
    after HE authorises that account. Being a superuser opens the application;
    it does not open the console.
    """
    if getattr(settings, "CHEF_BATTLE_ENABLED", False):
        return True
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser)


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
    # Public by intent, and the Owner named these two himself on 2026-08-04 as
    # the ONLY things an Author or an anonymous visitor may see of Chef Battles:
    # the rules, and the sitewide news (which is the newsfeed app, not a route
    # here). Everything else in this app moved behind the gate in v2.5.798.
    "battle_rules": "Public rules page, no user data. Owner-named exception.",
    "battle_guide": "Permanent redirect to the rules page. Owner-named exception.",
    "chef_battle_profile": (
        "Permanent redirect to /recipes/author/<slug>/, which is a recipes page, "
        "not a Chef Battles one. It renders nothing from this app and exists to "
        "keep old links alive, so it shows an Author nothing they could not "
        "already reach."
    ),

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
