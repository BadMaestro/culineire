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
    - the user is STAFF, which on this site means a "(Bear)seeker Admin" or a
      "(Bear)seeker Super User" - everyone above the AUTHOR tier.

    THE RULE, from the Owner, 2026-08-04, in his own three tiers and his own
    definition of what separates them - `is_staff`:

      AUTHOR                    is_staff False  - sees NOTHING of Chef Battles
      (Bear)seeker Admin        is_staff True   - sees the application
      (Bear)seeker Super User   is_staff True   - sees the application
      GreenBear                 IDDQD           - everything, plus the console,
                                                  and he alone grants the
                                                  console to another Super User

    The only things outside this gate are the rules page and the sitewide news.
    Everything else - arena, galleries, shop, profiles, rankings - is behind it.

    `is_superuser` is accepted as well, defensively: a superuser is above every
    tier by definition and must never be locked out by a missing staff bit.

    WHAT THIS CORRECTS, AND IT TOOK TWO PASSES ON THE SAME DAY. Until v2.5.798
    the gate trusted `has_bearseeker_privileges`, a field labelled "Can moderate
    site content" - a site MODERATOR flag, not a Chef Battles one - which the
    product contract had excluded since 2026-07-20 under
    `recipe_author_without_staff: false`. It had been removed once, on
    2026-07-21 (f3edd724), and put back five days later by 5169c08b under a
    one-line commit message with no rationale and no recorded decision, which
    AGENTS.md section 8 forbids for any access gate.

    v2.5.798 then closed it to `is_superuser` alone, and that was too narrow:
    it read the Owner's "only a Super User sees the WHOLE application" as
    "nobody below sees any of it". He corrected it the same hour. The tiers are
    separated by `is_staff`, and Admins belong inside.

    THE DATA DID NOT MATCH THE MODEL EITHER, which is the part worth carrying:
    both of this site's Admins had `is_staff` FALSE while the moderation panel
    listed them as Admins, because the panel groups on
    `has_bearseeker_privileges` and never reads `is_staff` - and the panel's
    "Grant (Bear)seeker Privileges" action set the moderator flag WITHOUT the
    staff bit, while "Grant Superuser" set both. Fixed in accounts/views.py in
    the same release; the two existing accounts were corrected by the Owner's
    order. So the model was right all along and the code implemented half of it.

    Chef enrollment is a participation state and was never a visibility grant.

    The Arena Master Console stays stricter than any of this, behind
    ``has_arena_console_access``: the Owner always, by OWNER_SLUG, and another
    Super User only after HE authorises that account. Passing this gate opens
    the application; it does not open the console.
    """
    if getattr(settings, "CHEF_BATTLE_ENABLED", False):
        return True
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_staff or user.is_superuser)


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
    "content_report_submit": "login_required; DSA reporting endpoint, validates its own input.",
    "artifact_generate_image": "login_required; staff/moderator AND is_battle_visible() checked in the view (F26, 2026-08-11).",

    # Poll and action endpoints that call is_battle_visible directly, because
    # the guard's suspended-POST branch would stack a banner on every poll.
    "arena_state": "Calls is_battle_visible directly; guard would add a banner per 20s poll.",
    "arena_ping": "Calls is_battle_visible directly; heartbeat endpoint.",
    "arena_take_seat": "Calls is_battle_visible directly.",
    "arena_react": "Calls is_battle_visible directly.",
    "arena_blast": "Calls is_battle_visible directly.",
    "battle_chat_poll": "Calls is_battle_visible directly; previously leaked chat to anonymous.",
    "arena_chat_feed": (
        "Calls is_battle_visible directly, the same shape as arena_state and "
        "battle_chat_poll: a delta poll every few seconds, where the guard's "
        "suspended-POST branch would stack a banner per poll. Reach is applied "
        "per listener inside the view, so a line the reader is too far away to "
        "hear never leaves the server (2026-08-18)."
    ),
    "arena_chat_send": (
        "Calls is_battle_visible directly, then refuses anyone not signed in "
        "(403 not_authenticated) and anyone without a seat in the hall "
        "(403 not_in_the_hall) before a single character is stored."
    ),
    "cooking_moderation": (
        "Moderator-only, checked with is_moderator AND is_battle_visible in the "
        "view (F8, 2026-08-11) - is_moderator alone admits has_bearseeker_"
        "privileges regardless of is_staff, a general site-moderation flag, not "
        "a Chef Battle one."
    ),
    "cooking_moderation_approve": "Same is_moderator AND is_battle_visible check as cooking_moderation (F8).",
    "vote_review": (
        "Moderator-only, the same is_moderator AND is_battle_visible check as "
        "cooking_moderation, 404 otherwise. G13, 2026-08-11: listed rather than "
        "decorated for the same reason as its siblings - it is reached from the "
        "moderation panel, not from an arena page. Read-only by design."
    ),
    "battle_withdraw_resolve": (
        "login_required + require_POST, and moderator-only: the view raises "
        "Http404 through is_moderator AND is_battle_visible (F8, 2026-08-11) "
        "before it reads anything. It is listed here rather than decorated "
        "because it is reached from the moderation panel, not from a battle "
        "page, and chef_battle_guard would answer a moderator's POST with the "
        "battle-visibility banner."
    ),
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
