"""The runway: a countdown and a live pace for scenario runs on the arena.

THE OWNER, 2026-08-06: «перед началом эмуляции выводи на живую арену - 3 - 2 -
1 - и поехали, с шагом в 5 секунд».

Two problems had to be solved together, because the second one makes the first
one pointless on its own.

**The countdown cannot be delivered tick by tick.** The arena polls every ten
seconds. A server that shipped "3", then "2", then "1" would need three polls
inside three seconds and would get one. So the server does not send the digits:
it sends the MOMENT the run begins, once, and the browser counts down to it off
its own clock. One delivery, three ticks, and a watcher who arrives late sees
the right number rather than a stale one.

**A five-second step cannot be seen through a ten-second poll.** Half the steps
would land between polls and never be drawn - the Owner would be told a thing
happened and would watch nothing happen, which is the whole complaint this work
started from. So while a run is live the arena polls FASTER, and it goes back to
its ordinary cadence the moment the run ends. The window is the run's own, not a
setting somebody has to remember to turn off: it expires by itself.

Storage is the cache, not a table. The runway is a few seconds of state about
something happening right now; it must never outlive a restart, and a schema
change needs the Owner's word every time (AGENTS.md section 8). The production
cache is file-based on a shared directory, so a script started from the console
and the web process that answers the poll see the same key.
"""

from django.core.cache import cache
from django.utils import timezone

#: One key holds the whole runway. There is one arena.
RUNWAY_KEY = "chef_battle:arena_runway"

#: How long a runway survives without being refreshed. Long enough for a run,
#: short enough that a crashed script cannot leave the arena sprinting forever.
RUNWAY_TTL_SECONDS = 900

#: What the arena polls at while a run is live. The ordinary cadence is ten
#: seconds (arena_render.js POLL_INTERVAL); two is what makes a five-second step
#: visible with room to spare, and it applies only while `until` is in the future.
LIVE_POLL_MS = 2000

#: Digits before the off. The Owner asked for three.
COUNTDOWN_FROM = 3


def start_countdown(*, lead_seconds: int = 12, label: str = "", steps: int = 0):
    """Arm the runway: the arena counts down and then paces itself.

    `lead_seconds` is the gap between arming and the off. It must be longer than
    one poll or the browser will not have heard about the countdown before it is
    over - twelve is one ordinary poll plus room for a slow one.
    """
    now = timezone.now()
    starts_at = now + timezone.timedelta(seconds=lead_seconds)
    payload = {
        "starts_at": starts_at.isoformat(),
        "until": (starts_at + timezone.timedelta(seconds=max(steps, 1) * 30)).isoformat(),
        "label": label,
        "count_from": COUNTDOWN_FROM,
        "poll_ms": LIVE_POLL_MS,
    }
    cache.set(RUNWAY_KEY, payload, RUNWAY_TTL_SECONDS)
    return payload


def announce(text: str, *, seconds: int = 6):
    """Put one line on the arena for a few seconds, mid-run.

    This is how a step says what it is while it happens, instead of the Owner
    being told afterwards what he was supposed to have seen.
    """
    runway = cache.get(RUNWAY_KEY) or {}
    runway["note"] = text
    runway["note_until"] = (
        timezone.now() + timezone.timedelta(seconds=seconds)
    ).isoformat()
    runway.setdefault("poll_ms", LIVE_POLL_MS)
    runway.setdefault(
        "until", (timezone.now() + timezone.timedelta(seconds=seconds + 30)).isoformat()
    )
    cache.set(RUNWAY_KEY, runway, RUNWAY_TTL_SECONDS)
    return runway


def clear():
    """End the run. The arena drops back to its ordinary ten seconds at once."""
    cache.delete(RUNWAY_KEY)


def current():
    """What the arena payload should carry, or None when nothing is running.

    Expiry is decided HERE and not in the browser: a tab left open overnight must
    not keep polling every two seconds because it never heard the run had ended.
    """
    runway = cache.get(RUNWAY_KEY)
    if not runway:
        return None

    now = timezone.now()
    until = runway.get("until")
    if until and _parse(until) and _parse(until) < now:
        cache.delete(RUNWAY_KEY)
        return None

    out = {
        "starts_at": runway.get("starts_at"),
        "count_from": runway.get("count_from", COUNTDOWN_FROM),
        "label": runway.get("label", ""),
        "poll_ms": runway.get("poll_ms", LIVE_POLL_MS),
    }
    note_until = runway.get("note_until")
    if runway.get("note") and note_until and _parse(note_until) and _parse(note_until) > now:
        out["note"] = runway["note"]
    return out


def _parse(value):
    from django.utils.dateparse import parse_datetime

    try:
        return parse_datetime(value)
    except (TypeError, ValueError):
        return None
