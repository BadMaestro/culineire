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

from django.db import models

from chef_battle.arena_cards import card_payload
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


class DirectMessageRefused(Exception):
    """Why a private conversation may not be opened. Carries a machine reason."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def may_direct_message(sender, recipient) -> None:
    """Raise DirectMessageRefused unless `sender` may write to `recipient`.

    EVERY rule here is a server rule, and this function is the only place they
    live, so the endpoint that opens a conversation and any later caller cannot
    disagree about who may talk to whom.

    Order matters. A block is checked before a policy because it is the
    stronger statement and because its answer must not depend on what the
    blocked person can infer: both a block and a closed door return the same
    shape of refusal.
    """
    from chef_battle.models import ChatBlock, ChefBattleProfile

    if sender is None or recipient is None:
        raise DirectMessageRefused("not_authenticated")
    if sender.pk == recipient.pk:
        raise DirectMessageRefused("cannot_message_yourself")

    # Either direction. Blocking somebody must also stop them writing to you -
    # a wall you can be spoken through is not a wall.
    if ChatBlock.objects.filter(
        models.Q(owner=recipient, blocked=sender) | models.Q(owner=sender, blocked=recipient)
    ).exists():
        raise DirectMessageRefused("blocked")

    profile = ChefBattleProfile.objects.filter(author=recipient).first()
    policy = getattr(profile, "dm_policy", ChefBattleProfile.DirectMessagePolicy.ANYONE)
    if policy == ChefBattleProfile.DirectMessagePolicy.NOBODY:
        raise DirectMessageRefused("recipient_accepts_no_messages")
    if policy == ChefBattleProfile.DirectMessagePolicy.TEAM:
        tags = team_tags_for({sender.pk, recipient.pk})
        mine = tags.get(sender.pk) or {}
        theirs = tags.get(recipient.pk) or {}
        # Same clan, or same alliance. An empty tag matches nothing: two chefs
        # in no clan at all are not thereby team-mates.
        same_clan = bool(mine.get("clan_tag")) and mine.get("clan_tag") == theirs.get("clan_tag")
        same_alliance = (
            bool(mine.get("alliance_tag"))
            and mine.get("alliance_tag") == theirs.get("alliance_tag")
        )
        if not (same_clan or same_alliance):
            raise DirectMessageRefused("recipient_accepts_team_only")


def open_direct_conversation(sender, recipient):
    """The private room these two share, creating it the first time.

    Idempotent by participation rather than by a stored pair key: the room is
    whichever DIRECT conversation both already sit in, so opening a thread
    twice cannot produce two rooms with half the history in each.
    """
    from django.db import transaction

    from chef_battle.models import ChatConversation, ChatParticipant

    may_direct_message(sender, recipient)

    existing = (
        ChatConversation.objects
        .filter(
            kind=ChatConversation.Kind.DIRECT,
            participants__author=sender,
        )
        .filter(participants__author=recipient)
        .first()
    )
    if existing is not None:
        return existing

    with transaction.atomic():
        conversation = ChatConversation.objects.create(
            kind=ChatConversation.Kind.DIRECT,
        )
        ChatParticipant.objects.create(conversation=conversation, author=sender)
        ChatParticipant.objects.create(conversation=conversation, author=recipient)
    return conversation


def participates_in(author, conversation_id):
    """The conversation, if this author is in it. None otherwise.

    THE ONLY DOOR. An id in a request proves nothing on its own, so every read
    and every write resolves it through here: no row in ChatParticipant and the
    conversation does not exist as far as the caller is concerned. That is what
    turns walking the id space into a 404 instead of a leak.
    """
    from chef_battle.models import ChatConversation

    if author is None or not conversation_id:
        return None
    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        return None
    return (
        ChatConversation.objects
        .filter(pk=conversation_id, participants__author=author)
        .first()
    )


def speaker_role(speaker_user) -> str:
    """"admin", "moderator" or "" - decided HERE, on the server.

    The client is told what a line IS and never gets to say so: a browser that
    posts {"role": "admin"} changes nothing, because nothing downstream reads a
    role from a request.

    RED IS FOR ADMIN ONLY. A moderator gets a MOD badge and the ordinary colour
    of whatever channel they are speaking in - the Owner's spec is explicit
    that moderator messages must not go red, because red is the site speaking
    officially and a moderator hiding a message is not that.

    "Moderator" here means somebody actually holding the chat permission, not
    somebody holding is_staff. Staff already reads as admin above, and the
    whole point of phase 4 was that a staff flag is not chat authority.
    """
    if speaker_user is None:
        return ""
    if speaker_user.is_superuser or speaker_user.is_staff:
        return "admin"
    if speaker_user.has_perm("chef_battle.moderate_arena_chat"):
        return "moderator"
    return ""


def reaction_summary(message_ids, viewer=None) -> dict[int, dict]:
    """`{message_id: {emoji: {"count": n, "mine": bool}}}` for these lines.

    Two queries for a whole page, never one per line: this is read on every
    poll. The counts are COUNTs over rows rather than a stored tally, so a
    double tap cannot inflate anything and "did I react" needs no second table.
    """
    from django.db.models import Count

    from chef_battle.models import ArenaChatReaction

    message_ids = [mid for mid in message_ids if mid]
    if not message_ids:
        return {}

    out: dict[int, dict] = {}
    rows = (
        ArenaChatReaction.objects
        .filter(message_id__in=message_ids)
        .values("message_id", "emoji")
        .annotate(total=Count("id"))
    )
    for row in rows:
        out.setdefault(row["message_id"], {})[row["emoji"]] = {
            "count": row["total"], "mine": False,
        }

    if viewer is not None:
        mine = ArenaChatReaction.objects.filter(
            message_id__in=message_ids, author=viewer,
        ).values_list("message_id", "emoji")
        for message_id, emoji in mine:
            entry = out.setdefault(message_id, {}).setdefault(
                emoji, {"count": 0, "mine": False},
            )
            entry["mine"] = True
    return out


def personal_hidden(viewer) -> tuple[set[int], set[int]]:
    """`(muted_ids, blocked_ids)` for this ONE reader.

    Personal and one-directional: nobody else's feed changes, and neither the
    muted nor the blocked person is ever told. Applied on the SERVER, because a
    preference enforced only in a browser is enforced only until somebody opens
    the network tab.

    The two are kept APART because they earn different treatment. A mute is a
    preference, so the words still travel and the reader may choose Show. A
    block is a wall, so the words do not travel at all - there is nothing to
    reveal and nothing to recover from the response.
    """
    from chef_battle.models import ChatBlock, ChatMute

    if viewer is None:
        return set(), set()
    muted = set(
        ChatMute.objects.filter(owner=viewer).values_list("muted_id", flat=True)
    )
    blocked = set(
        ChatBlock.objects.filter(owner=viewer).values_list("blocked_id", flat=True)
    )
    return muted, blocked


def private_lines(messages, viewer=None) -> list[dict]:
    """A direct conversation's messages, for a participant.

    NO REACH. Reach reproduces a room: how far a voice carries across the
    stands. A private thread is not a room, so the rule has nothing to
    reproduce and every line is simply read. The CALLER has already proved
    participation via participates_in() - this function does not re-authorise,
    it renders.
    """
    muted_ids, blocked_ids = personal_hidden(viewer)
    reactions = reaction_summary([m.pk for m in messages], viewer)
    tags_by_author = team_tags_for({m.speaker_id for m in messages})
    out = []
    for message in messages:
        speaker_user = getattr(message.speaker, "user", None)
        role = speaker_role(speaker_user)
        # Red, and the reach exemption, are ADMIN only - a moderator speaks in
        # the ordinary colour of the room and wears a MOD badge instead.
        is_admin = role == "admin"
        tags = tags_by_author.get(message.speaker_id) or {}
        row = {
            "id": message.id,
            "name": message.display_name,
            "slug": message.speaker.slug,
            "clan_tag": tags.get("clan_tag", ""),
            "alliance_tag": tags.get("alliance_tag", ""),
            # ADMIN still outranks the channel: an Admin writing privately is
            # red, not purple. The precedence is the same everywhere.
            "role": role,
            "channel": "private",
            "heard": True,
            "at": message.created_at.isoformat(),
            "reactions": reactions.get(message.pk, {}),
            "muted": message.speaker_id in muted_ids,
            "blocked": message.speaker_id in blocked_ids,
            # Only a moderator is ever handed a hidden line; for everyone else
            # this is always false, because the row never reaches them at all.
            "hidden": message.is_hidden,
            # "" for a spoken line, which is what every row written before P3
            # carries and what the renderer's own default already expected.
            # Always "" in a private room - a card is an announcement to the
            # hall and is never written into a conversation - but the key is
            # sent so both feeds hand the renderer the same shape.
            "kind": message.kind,
        }
        if message.speaker_id not in blocked_ids:
            row["body"] = message.body
            # Same rule as the hall: a block withholds the file, not just the
            # words. There is no reach to apply in a private room.
            media = _media_row(message)
            if media:
                row["media"] = media
        out.append(row)
    return out


def audible_lines(listener_seat, messages, tags_by_author=None, viewer=None) -> list[dict]:
    """The feed as ONE listener may read it.

    Out of range the words are not included at all. The line still appears --
    the person can see that somebody across the hall is talking -- but it
    carries ``heard: false`` and no body, and the renderer draws "Talking
    Something" over the speaker instead. Sending the text and hiding it in CSS
    would leave it one view-source away from someone who must not read it.

    ``viewer`` is the reader's own author row, and everything personal to them -
    their mutes, their blocks, which reactions are theirs - is resolved here
    rather than in the browser, for the same reason.
    """
    if listener_seat is None:
        return []
    listener_ring, listener_cell = listener_seat
    muted_ids, blocked_ids = personal_hidden(viewer)
    reactions = reaction_summary([m.pk for m in messages], viewer)
    if tags_by_author is None:
        tags_by_author = team_tags_for({m.speaker_id for m in messages})
    out = []
    for message in messages:
        # THE ROLE IS DECIDED HERE, ON THE SERVER. The client is told what a
        # line IS; it never gets to say what it is. A browser that posts
        # {"role": "admin"} changes nothing, because nothing downstream reads a
        # role from the client - the renderer colours what this field says.
        speaker_user = getattr(message.speaker, "user", None)
        role = speaker_role(speaker_user)
        # Red, and the reach exemption, are ADMIN only - a moderator speaks in
        # the ordinary colour of the room and wears a MOD badge instead.
        is_admin = role == "admin"
        # AN ANNOUNCEMENT THE NEIGHBOURS ALONE CAN HEAR IS NOT AN ANNOUNCEMENT.
        # Reach is the rule for people talking among themselves in the stands;
        # an Admin speaking to the hall is not doing that. Owner kept reach for
        # ordinary chat (2026-08-24) and this is the one exception it needs to
        # stay useful. Direct messages will bypass it too, for the same reason:
        # they are not spoken across a room at all.
        # A CARD IS HEARD EVERYWHERE, for the same reason an Admin is. Reach is
        # the rule for people talking among themselves in the stands; the
        # fight's own moments are not that conversation, and a result card only
        # three rows of seats could read would be a worse announcement than no
        # announcement at all.
        heard = is_admin or bool(message.kind) or can_hear(
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
            "role": role,
            "channel": "public",
            "ring": message.ring_index,
            "cell": message.seat_index,
            "heard": heard,
            "at": message.created_at.isoformat(),
            "reactions": reactions.get(message.pk, {}),
            # Personal, and one-directional: true for this reader only.
            "muted": message.speaker_id in muted_ids,
            "blocked": message.speaker_id in blocked_ids,
            # Only a moderator is ever handed a hidden line; for everyone else
            # this is always false, because the row never reaches them at all.
            "hidden": message.is_hidden,
            # "" for a spoken line, which is what every row written before P3
            # carries and what the renderer's own dispatch already defaults to.
            "kind": message.kind,
        }
        # A CARD'S FACTS COME FROM THE BATTLE, not from the chat row. The row
        # keeps the sentence so the log reads with no join; everything the card
        # states about the fight - who, against whom, who won, where to go - is
        # read off the event and the battle it points at.
        if message.kind:
            row["card"] = card_payload(message)
        # The line this one answers, as a short quote. One level: a reply
        # carries its parent's name and a preview, and the parent's own parent
        # is not this reader's problem.
        parent = message.reply_to
        if parent is not None and not parent.is_hidden:
            row["reply_to"] = {
                "id": parent.pk,
                "name": parent.display_name,
                # The preview obeys the SAME reach rule as the line itself -
                # quoting is not a way to read what you could not hear.
                "preview": (
                    parent.body[:60]
                    if can_hear(parent.ring_index, parent.seat_index,
                                listener_ring, listener_cell)
                    else ""
                ),
            }
        # A block withholds the words entirely; a mute only folds them away, so
        # Show has something to reveal. See personal_hidden().
        if heard and message.speaker_id not in blocked_ids:
            row["body"] = message.body
            # AN ATTACHMENT TRAVELS UNDER EXACTLY THE SAME RULE AS THE WORDS,
            # and it has to: a URL is the file. Sending the address to somebody
            # too far away to hear the line, or to somebody who blocked its
            # author, would hand them the picture and leave the hiding to CSS -
            # which is the mistake this whole module exists to refuse.
            media = _media_row(message)
            if media:
                row["media"] = media
        out.append(row)
    return out


def _media_row(message):
    """The attachment as the client may read it, or None.

    Deliberately not a method on the model: what a URL means here is decided
    per READER by the two functions above, and a model property would invite a
    caller to reach for it without asking whether this reader may have it.
    """
    if not message.media_kind or not message.media:
        return None
    try:
        url = message.media.url
    except ValueError:                       # a row whose file went missing
        return None
    row = {
        "kind": message.media_kind,
        "url": url,
        "width": message.media_width,
        "height": message.media_height,
    }
    if message.media_poster:
        try:
            row["poster"] = message.media_poster.url
        except ValueError:
            pass
    return row
