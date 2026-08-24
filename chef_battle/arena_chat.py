"""Who hears whom in the arena stands.

The Owner's rule, 2026-08-17, in his own terms: from the cell an author stands
in, he is heard three cells to the right and three to the left; if there is more
than one ring, also three up or three down, by the compass. Anyone further away
does not get the words at all -- they see "Talking Something" over the speaker's
head instead.

This is not a game mechanic and not a limit imposed on anyone. It is the nature
of hearing, and the hall reproduces it (his words, same day): in a real room the
people beside you are audible and the far side is a murmur. Everything below
follows from taking that seriously.

Two consequences shape this module:

* **Reach is decided on the server.** A viewer out of range never receives the
  text, only the fact that someone is speaking. Sending everything and hiding it
  in CSS would mean the words are one "view source" away from a person the Owner
  said must not hear them.

* **Sideways distance is angular, not index arithmetic.** The spectator rows do
  not hold the same number of cells (56 and 58 today), so cell 10 of one row and
  cell 10 of the next are not above one another. "Three cells" is measured as the
  angle three cells subtend on the speaker's own ring -- the compass reading the
  Owner asked for -- which stays true when the counts differ and when a ring
  wraps past its own zero.
"""

from __future__ import annotations

import math

from chef_battle.selectors import get_arena_geometry

# The Owner's numbers. Three cells along the ring, three rings across.
HEARING_CELLS = 3
HEARING_RINGS = 3


def _spectator_rings() -> dict[int, dict]:
    """Spectator rings by ring index, with their cell counts and row order.

    ``row`` is what "three up or three down" counts. It comes from the geometry
    rather than from the ring index so that renumbering the rings -- which has
    happened once already -- cannot silently change who can hear whom.
    """
    geometry = get_arena_geometry()
    rings = {}
    for ring in geometry["rings"]:
        if ring.get("kind") != "spectator":
            continue
        rings[ring["index"]] = {
            "segments": max(int(ring.get("segments") or 0), 1),
            "row": int(ring.get("row") or 1),
        }
    return rings


def _rank_rings() -> set[int]:
    """Ring indices belonging to the chefs' octagon.

    A chef's cell is decided by the scatter from his slug and he cannot get up
    and move, so the hall's hearing cannot apply to him (see ``can_hear``).
    """
    return {
        ring["index"] for ring in get_arena_geometry()["rings"]
        if ring.get("kind") == "rank"
    }


def _bearing(cell: int, segments: int) -> float:
    """The compass bearing of a cell, in radians, matching the renderer.

    Kept in lockstep with ``_oval_seat_list()`` in selectors.py, which places a
    cell at ``(cell + 0.5) / count`` of a full turn.
    """
    return ((cell + 0.5) / segments) * math.tau


def _angular_gap(a: float, b: float) -> float:
    """Shortest angle between two bearings, so a ring wraps at its own zero."""
    gap = abs(a - b) % math.tau
    return min(gap, math.tau - gap)


def can_hear(speaker_ring: int, speaker_cell: int,
             listener_ring: int, listener_cell: int) -> bool:
    """True when a listener in one seat hears the words spoken from another.

    A seat always hears itself.

    The limit on a spectator is not a penalty and is not a game mechanic: it is
    HOW HEARING WORKS, and the hall reproduces it (the Owner, 2026-08-17). A
    person three seats away is audible and a person thirty seats away is not,
    and someone free to walk over to a conversation lives under that honestly.

    A CHEF HEARS EVERYTHING (the Owner, same day). Not because distance would be
    unfair to him, but because he is fixed in place: his cell in a rank ring is
    set by the scatter from his slug so it holds still across polls, and he
    cannot walk anywhere. The one thing that makes real hearing livable -- moving
    closer -- is the thing he does not have, so the hall carries every line to
    him instead.

    A row pointing at geometry that no longer exists hears nothing and is heard
    by nobody -- the stands and the octagon are the only places this conversation
    happens.
    """
    if (speaker_ring, speaker_cell) == (listener_ring, listener_cell):
        return True

    rank = _rank_rings()
    if listener_ring in rank:
        return True

    # And the hall hears HIM from anywhere. A chef on the floor is what the room
    # came to watch, and the same fixed cell that stops him walking closer would
    # otherwise leave him readable by nobody but the handful of seats nearest the
    # octagon -- reading everything and answering into silence.
    if speaker_ring in rank:
        return True

    rings = _spectator_rings()
    speaker = rings.get(speaker_ring)
    listener = rings.get(listener_ring)
    if speaker is None or listener is None:
        return False

    if abs(speaker["row"] - listener["row"]) > HEARING_RINGS:
        return False

    reach = _bearing(HEARING_CELLS, speaker["segments"]) - _bearing(0, speaker["segments"])
    gap = _angular_gap(
        _bearing(speaker_cell, speaker["segments"]),
        _bearing(listener_cell, listener["segments"]),
    )
    # A hair of tolerance: the third cell is inside the reach, and floating
    # point must not be what decides whether the Owner's third neighbour hears.
    return gap <= reach + 1e-9


# ---------------------------------------------------------------------------
# Where a person is standing, and what the hall lets them read
# ---------------------------------------------------------------------------

# A speaker's seat is stored on the line, but a CHEF's exact cell never matters:
# he is outside the distance rule in both directions, so any cell in his rank
# ring answers every question this module asks about him. That is fortunate,
# because the octagon decides a chef's cell in the RENDERER, by scattering his
# slug, and the server has never known which one he landed on.
CHEF_CELL = 0


def seat_of(author) -> tuple[int, int] | None:
    """The (ring, cell) this author speaks and listens from, or None.

    None means the person is not in the hall at all - not enrolled, and holding
    no seat - and such a person neither speaks nor hears.
    """
    from chef_battle.models import ArenaSeat, ChefBattleProfile
    from chef_battle.selectors import rank_to_ring_index

    profile = ChefBattleProfile.objects.filter(author=author).first()
    if profile is not None and profile.enrolled_at is not None:
        ring = rank_to_ring_index(profile.rank)
        return (ring, CHEF_CELL) if ring else None

    return (
        ArenaSeat.objects
        .filter(viewer=author, released_at__isnull=True)
        .values_list("ring_index", "seat_index")
        .first()
    )


def team_tags_for(author_ids) -> dict[int, dict]:
    """`{author_id: {"clan_tag": .., "alliance_tag": ..}}` for these authors.

    THE TAGS ARE RESOLVED, NEVER SNAPSHOTTED. A chat line stores who spoke and
    what they said; what team they belong to is answered from the membership
    tables at read time. A chef who leaves a clan stops wearing its badge on
    every line at once, including the ones already on screen, and nobody has to
    rewrite history to make that true.

    The chain is the existing one, with its own uniqueness already enforced by
    the membership models: author -> ACTIVE ClanMembership -> Clan -> ACTIVE
    AllianceMembership -> Alliance. A membership that is pending, or one a chef
    has left, is not an identity and is not read here.

    One query for clans and one for alliances regardless of how many lines the
    feed carries - this runs on every poll, so it does not get to be N+1.
    """
    from chef_battle.models import AllianceMembership, ClanMembership

    author_ids = {aid for aid in author_ids if aid}
    if not author_ids:
        return {}

    clan_rows = (
        ClanMembership.objects
        .filter(chef_id__in=author_ids, status=ClanMembership.Status.ACTIVE)
        .values_list("chef_id", "clan_id", "clan__tag")
    )
    by_author = {}
    clan_ids = set()
    for chef_id, clan_id, clan_tag in clan_rows:
        by_author[chef_id] = {"clan_id": clan_id, "clan_tag": clan_tag or ""}
        clan_ids.add(clan_id)

    alliance_tag_by_clan = {}
    if clan_ids:
        alliance_tag_by_clan = {
            clan_id: (tag or "")
            for clan_id, tag in AllianceMembership.objects
            .filter(clan_id__in=clan_ids, left_at__isnull=True)
            .values_list("clan_id", "alliance__tag")
        }

    return {
        chef_id: {
            "clan_tag": row["clan_tag"],
            "alliance_tag": alliance_tag_by_clan.get(row["clan_id"], ""),
        }
        for chef_id, row in by_author.items()
    }


def audible_lines(listener_seat, messages, tags_by_author=None) -> list[dict]:
    """The feed as ONE listener may read it.

    Out of range the words are not included at all. The line still appears --
    the person can see that somebody across the hall is talking -- but it
    carries ``heard: false`` and no body, and the renderer draws "Talking
    Something" over the speaker instead. Sending the text and hiding it in CSS
    would leave it one view-source away from someone who must not read it.
    """
    if listener_seat is None:
        return []
    listener_ring, listener_cell = listener_seat
    if tags_by_author is None:
        tags_by_author = team_tags_for({m.speaker_id for m in messages})
    out = []
    for message in messages:
        # THE ROLE IS DECIDED HERE, ON THE SERVER. The client is told what a
        # line IS; it never gets to say what it is. A browser that posts
        # {"role": "admin"} changes nothing, because nothing downstream reads a
        # role from the client - the renderer colours what this field says.
        speaker_user = getattr(message.speaker, "user", None)
        is_admin = bool(
            speaker_user is not None
            and (speaker_user.is_superuser or speaker_user.is_staff)
        )
        # AN ANNOUNCEMENT THE NEIGHBOURS ALONE CAN HEAR IS NOT AN ANNOUNCEMENT.
        # Reach is the rule for people talking among themselves in the stands;
        # an Admin speaking to the hall is not doing that. Owner kept reach for
        # ordinary chat (2026-08-24) and this is the one exception it needs to
        # stay useful. Direct messages will bypass it too, for the same reason:
        # they are not spoken across a room at all.
        heard = is_admin or can_hear(
            message.ring_index, message.seat_index, listener_ring, listener_cell,
        )
        tags = tags_by_author.get(message.speaker_id) or {}
        row = {
            "id": message.id,
            "name": message.display_name,
            "slug": message.speaker.slug,
            # Three separate values, never one pre-joined string: the badge is
            # the renderer's job, and an empty tag must vanish rather than
            # print as "[]".
            "clan_tag": tags.get("clan_tag", ""),
            "alliance_tag": tags.get("alliance_tag", ""),
            # ADMIN > PRIVATE > PUBLIC. Only the first and last exist yet;
            # "private" arrives with direct messages and slots in between
            # without the renderer changing shape.
            "role": "admin" if is_admin else "",
            "channel": "public",
            "ring": message.ring_index,
            "cell": message.seat_index,
            "heard": heard,
            "at": message.created_at.isoformat(),
        }
        if heard:
            row["body"] = message.body
        out.append(row)
    return out
