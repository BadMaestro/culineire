"""What the hall does TOGETHER, and what the arena does about it.

P3 items 27, 28 and 29 (Owner 2026-08-26). Three rules from the brief shape
every line of this module, and each of them is a rule about restraint:

  * **never from one person.** A single reaction is one person's opinion and
    the arena does not answer opinions. The brief's own example is the bar:
    thirty or more of the same reaction inside ten seconds.
  * **never continuously.** An arena-wide effect fires at most once every
    ``ARENA_EFFECT_COOLDOWN`` seconds however loud the room is, so a room that
    is spamming gets one effect and then silence, which is also what stops
    spam being worth doing.
  * **brief, premium, lightweight.** The server sends a name and a number; the
    browser draws it for a second and a half over the floor and removes it. No
    payload grows with the size of the crowd.

NOTHING HERE TOUCHES THE OCTAGON. The effect is a sibling layer over the floor
stage, the same shape ``runwayLayer()`` in arena_render.js already uses, and
the geometry, hit areas and SVG internals are not read by this module at all.

NO POLLER AND NO SECOND ENDPOINT: the hall already asks the chat feed for new
lines every few seconds, so the answer to "is anything happening" rides back on
that request. A surge nobody is in the room to see is never computed.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

# THE OWNER'S OWN NUMBERS, from the brief, and configurable because the brief
# says they must be. They are module constants rather than settings because
# nothing outside this file has an opinion about them yet; the day one does,
# they move to settings and this comment is the record of why they were here.
SURGE_WINDOW_SECONDS = 10
SURGE_THRESHOLD = 30
GIFT_WINDOW_SECONDS = 20

# One effect per this many seconds, arena-wide. The brief says 10-20; the upper
# half of that range is chosen deliberately - an effect the room sees every ten
# seconds stops being an event and becomes weather.
ARENA_EFFECT_COOLDOWN = 15

# HOW LONG ONE EFFECT STAYS ON OFFER TO THE WHOLE HALL. Without this the first
# browser to poll would consume the effect and the other forty would be told
# nothing - an arena-wide moment shown to one person at random, which is the
# opposite of what items 27-29 are for. The effect is PUBLISHED for this many
# seconds, every poll inside the window is handed the same one with the same
# id, and the browser plays an id once.
EFFECT_SHOW_SECONDS = 6

_COOLDOWN_KEY = "arena:effect:last"
_LIVE_KEY = "arena:effect:live"
# The key a surge is remembered under, so one wave of thirty is announced once
# rather than on every poll for as long as it stays inside its own window.
_SURGE_KEY = "arena:effect:surge:%s"
# The gift a card has already been drawn for. Without it the SAME gift is
# announced twice: it stays inside its twenty-second window while the fifteen
# second cooldown expires underneath it, so the next poll finds it again and
# fires a second effect for one act. Found by reading the two windows against
# each other rather than by seeing it happen - on a quiet arena it would have
# looked like a bug in someone's eyes.
_GIFT_KEY = "arena:effect:gift:%s"


def _on_cooldown() -> bool:
    return cache.get(_COOLDOWN_KEY) is not None


def _start_cooldown() -> None:
    cache.set(_COOLDOWN_KEY, 1, ARENA_EFFECT_COOLDOWN)


def _reaction_surge():
    """The one reaction the hall is doing together right now, or nothing.

    Counted across the whole hall rather than per message: thirty people
    reacting to thirty different lines with the same emoji is the same wave as
    thirty reacting to one, and it is the wave the arena answers.
    """
    from .models import ArenaChatReaction

    since = timezone.now() - timedelta(seconds=SURGE_WINDOW_SECONDS)
    top = (
        ArenaChatReaction.objects
        .filter(created_at__gte=since)
        .values("emoji")
        .annotate(n=Count("id"))
        .order_by("-n")
        .first()
    )
    if not top or top["n"] < SURGE_THRESHOLD:
        return None
    # ONE WAVE, ONE EFFECT. Without this the same thirty reactions would fire
    # again on every poll for the whole ten seconds they stay in the window.
    key = _SURGE_KEY % top["emoji"]
    if cache.get(key) is not None:
        return None
    cache.set(key, 1, SURGE_WINDOW_SECONDS)
    return {"kind": "surge", "emoji": top["emoji"], "count": top["n"]}


def _gift_effect():
    """The most recent battle gift, once, if one has just landed.

    A gift is one person's act and is answered anyway - that is the difference
    between a reaction and a gift, and it is the Owner's own economy: tokens
    were spent. The cooldown above still applies, so a shower of gifts is one
    effect every fifteen seconds rather than a strobe.
    """
    from .models import ViewerBattleGift

    since = timezone.now() - timedelta(seconds=GIFT_WINDOW_SECONDS)
    gift = (
        ViewerBattleGift.objects
        .filter(sent_at__gte=since)
        .select_related("artifact", "recipient")
        .order_by("-sent_at")
        .first()
    )
    if gift is None:
        return None
    key = _GIFT_KEY % gift.pk
    if cache.get(key) is not None:
        return None
    cache.set(key, 1, GIFT_WINDOW_SECONDS)
    return {
        "kind": "gift",
        "artifact": gift.artifact.name,
        "rarity": gift.artifact.get_rarity_display(),
        "recipient": gift.recipient.name,
        "tokens": gift.tokens_spent,
    }


def current_effect():
    """The effect the whole hall is being shown right now, or None.

    PUBLISHED, NOT CONSUMED. Every seated viewer polls this endpoint on their
    own clock, so an effect that the first caller took away would be shown to
    one person and missed by everyone else. It is written into the cache for
    EFFECT_SHOW_SECONDS and handed to every poll inside that window with the
    same id; the browser plays an id once and ignores repeats.

    Cheap enough to run on every feed request: on a quiet arena it reads two
    cache keys and stops. Only when both are clear does it run the one
    aggregate over a ten-second slice of reactions.
    """
    live = cache.get(_LIVE_KEY)
    if live is not None:
        return live
    if _on_cooldown():
        return None
    effect = _reaction_surge() or _gift_effect()
    if effect is None:
        return None
    # The id is what lets a browser tell "still the same moment" from "another
    # one just like it" - two identical waves a minute apart are two effects.
    effect["id"] = "%s:%d" % (effect["kind"], int(timezone.now().timestamp()))
    cache.set(_LIVE_KEY, effect, EFFECT_SHOW_SECONDS)
    _start_cooldown()
    return effect
