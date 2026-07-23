"""Real spectator seating for the Arena stands (Stage 3C backend foundation).

The stands already had a shape and a capacity — ``selectors.get_arena_geometry``
declares eight spectator rings of 40, 48, 56, 64, 72, 80, 88 and 96 seats, 544
in total — but no memory: ``views._get_spectators`` returned whoever was online
ordered by ``-last_seen_at`` and the renderer poured that list into seats in
order, so a viewer's seat moved every time somebody else's heartbeat landed.
This module gives a claimed seat an owner and keeps it.

Three rules do the work:

* the seat map comes from ``get_arena_geometry()``, never from a constant here;
* a claim is idempotent — the same viewer asking again gets the seat they
  already hold, not a second one;
* front rows fill first, so the hall fills from the rail outwards.

Liveness reuses the arena's existing online window rather than adding a clock:
a held seat lapses once its occupant drops out of the same 180-second window
that already decides who is standing in the hall at all.
"""
from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ArenaSeat, ChefBattleProfile
from .selectors import ARENA_ONLINE_THRESHOLD_SECONDS, get_arena_geometry


class ArenaSeatingError(Exception):
    """Base class for seating refusals the view turns into a 4xx."""


class ArenaFull(ArenaSeatingError):
    """Every seat the geometry declares is held by a live viewer."""


def seat_map() -> list[tuple[int, int, int]]:
    """The authoritative seat order, front row first.

    Each entry is ``(ring_index, seat_index, row)`` where ring_index is the
    ring's own index in the arena geometry and row is 1 at the rail. Allocation
    walks this list in order, which is what "front seats first" means in code.
    """
    seats: list[tuple[int, int, int]] = []
    for ring in get_arena_geometry()["rings"]:
        if ring["kind"] != "spectator":
            continue
        for cell in range(ring["segments"]):
            seats.append((ring["index"], cell, ring["row"]))
    return seats


def seating_capacity() -> int:
    """Total real seats. Derived, so widening the stands widens this too."""
    return len(seat_map())


def _online_cutoff():
    return timezone.now() - timezone.timedelta(seconds=ARENA_ONLINE_THRESHOLD_SECONDS)


def _lapsed_seat_ids(cutoff) -> list[int]:
    """Held seats whose occupant has left the arena's online window.

    Their holder is no longer present by the arena's own existing definition,
    so the seat is free for the next viewer. Nothing new is being decided here:
    the same window already governs whether a person is drawn in the hall.
    """
    live_ids = set(
        ChefBattleProfile.objects
        .filter(last_seen_at__isnull=False, last_seen_at__gte=cutoff)
        .values_list("author_id", flat=True)
    )
    return list(
        ArenaSeat.objects.filter(released_at__isnull=True)
        .exclude(viewer_id__in=live_ids)
        .values_list("pk", flat=True)
    )


def get_active_seat(viewer) -> ArenaSeat | None:
    """The seat this viewer currently holds, or None."""
    return ArenaSeat.objects.filter(viewer=viewer, released_at__isnull=True).first()


def release_seat(viewer) -> bool:
    """Give up this viewer's seat. True if one was held."""
    updated = (
        ArenaSeat.objects
        .filter(viewer=viewer, released_at__isnull=True)
        .update(released_at=timezone.now())
    )
    return bool(updated)


def claim_seat(viewer) -> ArenaSeat:
    """Seat a real, authenticated viewer, front rows first.

    Idempotent: a viewer who already holds a seat gets that same seat back, so
    the poll that runs every twenty seconds cannot walk somebody around the
    stands or quietly consume the hall.

    Concurrency is settled by the database, not by a lock we hope covers every
    caller: two simultaneous claims may both pick the same free seat, and the
    partial unique constraint rejects the loser, which then retries against a
    map that no longer offers it. The retry budget is the whole hall, so the
    only way to leave this loop empty-handed is a genuinely full arena.
    """
    if viewer is None or getattr(viewer, "pk", None) is None:
        raise ArenaSeatingError("A seat requires a saved viewer.")

    existing = get_active_seat(viewer)
    if existing is not None:
        return existing

    seats = seat_map()
    with transaction.atomic():
        cutoff = _online_cutoff()
        lapsed = _lapsed_seat_ids(cutoff)
        if lapsed:
            ArenaSeat.objects.filter(pk__in=lapsed).update(released_at=timezone.now())

    for _attempt in range(len(seats)):
        taken = set(
            ArenaSeat.objects.filter(released_at__isnull=True)
            .values_list("ring_index", "seat_index")
        )
        free = next(
            ((ring, cell) for ring, cell, _row in seats if (ring, cell) not in taken),
            None,
        )
        if free is None:
            raise ArenaFull("The arena stands are full.")
        try:
            with transaction.atomic():
                return ArenaSeat.objects.create(
                    viewer=viewer, ring_index=free[0], seat_index=free[1],
                )
        except IntegrityError:
            # Either somebody took that seat between the read and the write, or
            # this viewer was seated concurrently by their own second request.
            # The second case is the idempotency guarantee, so honour it before
            # trying again for the first.
            mine = get_active_seat(viewer)
            if mine is not None:
                return mine
            continue

    raise ArenaFull("The arena stands are full.")


def public_seat(seat: ArenaSeat) -> dict:
    """The seat as the hall may show it.

    Deliberately the same three public author fields the arena payload has
    always carried for a spectator — display name, profile slug, avatar — plus
    where the person is sitting. No email, no username, no account id, no
    session or request fingerprint: nothing here that the arena page does not
    already publish about a visible spectator.
    """
    rows = {ring["index"]: ring.get("row") for ring in get_arena_geometry()["rings"]}
    author = seat.viewer
    return {
        "ring": seat.ring_index,
        "cell": seat.seat_index,
        "row": rows.get(seat.ring_index),
        "name": author.name,
        "slug": author.slug,
        "avatar_url": author.display_avatar_url,
    }
