"""Real spectator seating for the Arena oval stands (Owner mockup redesign).

Chef ranks sit on the octagon floor cells. Spectators sit in an oval around
that floor (``get_arena_geometry()["spectator_oval"]``), not in chef cells.
Capacity is derived from the oval seat list — journal honesty if it differs
from the legacy 544 polar-ring figure.
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

    Each entry is ``(ring_index, seat_index, row)``. Oval geometry prefers the
    explicit ``spectator_oval.seats`` list when present; otherwise falls back
    to polar spectator rings (legacy).
    """
    geometry = get_arena_geometry()
    oval = geometry.get("spectator_oval") or {}
    seats_spec = oval.get("seats")
    if seats_spec:
        # Front = lowest row number per side, then ring id, then cell.
        ordered = sorted(
            seats_spec,
            key=lambda s: (s["row"], s["ring"], s["cell"]),
        )
        return [(s["ring"], s["cell"], s["row"] + 1) for s in ordered]

    seats: list[tuple[int, int, int]] = []
    for ring in geometry["rings"]:
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


def _offmap_seat_ids() -> list[int]:
    """Held seats the geometry no longer declares.

    AR4 removed the left and right seat banks, so anyone holding one of those
    rings is sitting where the hall no longer draws a seat: invisible on the
    floor, yet still counted against capacity until their online window lapses.
    Freeing them is the same act as freeing a lapsed seat — the seat stops
    existing, so the hold stops with it. No seat that the map still declares is
    ever touched here.
    """
    valid = {(ring, cell) for ring, cell, _row in seat_map()}
    return [
        pk
        for pk, ring, cell in ArenaSeat.objects.filter(released_at__isnull=True)
        .values_list("pk", "ring_index", "seat_index")
        if (ring, cell) not in valid
    ]


def get_active_seat(viewer) -> ArenaSeat | None:
    """The seat this viewer currently holds, or None."""
    return ArenaSeat.objects.filter(viewer=viewer, released_at__isnull=True).first()


def release_lapsed_seats() -> int:
    """Free seats whose holders have left, and seats the map no longer has.

    Returns how many seats were released. Call only from an explicitly
    state-changing request path; read-only render helpers must remain queries.
    """
    stale = set(_lapsed_seat_ids(_online_cutoff())) | set(_offmap_seat_ids())
    if not stale:
        return 0
    return (
        ArenaSeat.objects.filter(pk__in=stale, released_at__isnull=True)
        .update(released_at=timezone.now())
    )


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
    stands or quietly consume the hall. The purge runs BEFORE that shortcut:
    otherwise a viewer holding a seat AR4 deleted would be handed it straight
    back, and idempotency would preserve the one hold worth breaking.

    Concurrency is settled by the database, not by a lock we hope covers every
    caller: two simultaneous claims may both pick the same free seat, and the
    partial unique constraint rejects the loser, which then retries against a
    map that no longer offers it. The retry budget is the whole hall, so the
    only way to leave this loop empty-handed is a genuinely full arena.
    """
    if viewer is None or getattr(viewer, "pk", None) is None:
        raise ArenaSeatingError("A seat requires a saved viewer.")

    seats = seat_map()
    # Only the off-map purge runs ahead of the idempotency shortcut, and only
    # because such a seat no longer exists to be given back. The lapsed purge
    # stays behind it: this caller is here, now, and their own last_seen_at can
    # trail the request that is claiming — releasing their seat on that basis
    # would walk them to a different one, which is the thing idempotency exists
    # to prevent.
    offmap = _offmap_seat_ids()
    if offmap:
        ArenaSeat.objects.filter(pk__in=offmap).update(released_at=timezone.now())

    existing = get_active_seat(viewer)
    if existing is not None:
        return existing

    with transaction.atomic():
        lapsed = _lapsed_seat_ids(_online_cutoff())
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
