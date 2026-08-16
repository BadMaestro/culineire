# Arena — acceptance audit before the frontend

**By:** GreenBear · **Date:** 2026-08-15 · **Production at audit:** v2.5.1039
**Scope, set by the Owner:** *the ARENA only.* Stripe, the token economy and
the rest of Chef Battle are explicitly **not** acceptance factors for this gate
and are not judged here. The question this act answers is one question:

> **Can the Arena frontend be built on what exists now, and what must be known
> before the first line of it is written?**

**Verdict: YES — the Arena is accepted as a build base, with four conditions
listed in §7.** None of the four blocks starting; two of them must be settled
before the frontend's data layer is written, because they change what it binds
to.

---

## 1. What was measured, and how

Everything below is a measurement or a reading of the running code, not a
reading of a plan. Nothing was written to production; no page was rendered
through a shell on production (the standing prohibition); no Owner data was
touched.

| Instrument | What it produced |
|---|---|
| `chef_battle/test_arena_acceptance.py` (new, 9 tests) | payload contract, empty-hall honesty, geometry, query and size budgets, latch |
| Query capture at two crowd sizes (24 chefs/40 fans → 48/80) | N+1 verdict |
| `curl` against production | latch behaviour, asset transfer sizes |
| Source reading | renderer, deck, seating, popup, board cards |

---

## 2. The data layer — accepted

`_build_arena_payload()` is one builder feeding three surfaces (page, poll,
console). The page's context is **derived** from the poll's key tuple
(`PUBLIC_ARENA_STATE_KEYS`), so the first paint and every repaint cannot
disagree — the drift that produced a countdown on one surface and not the other
is closed structurally, not by discipline.

Measured on a hall of 24 online chefs and 40 spectators:

| Surface | Queries | Bytes |
|---|---|---|
| `GET /chef-battle/arena/` | **36** | 104 KB HTML |
| `POST /chef-battle/arena/state/` | **46** | **30.1 KB** JSON |

**No N+1.** Doubling the hall did not raise the query count (46 → 33; the drop
is the seat claim already being satisfied). The cost is per-request, not
per-chef, which is the property a frontend needs to plan around.

**Truthful empty state confirmed at the payload, not the pixels:** with nothing
happening, `center.type == "empty"`, `upcoming == []`, `spirit_count == 0` and
every ring is empty. The renderer's `LIVE_FIXTURE` — invented viewers, an
invented battle, the Owner's own name with three crowns — **is disconnected**
(Owner, 2026-08-03) and a test holds it disconnected. It remains in the file by
his decision, reversible in one line. It is not on screen.

---

## 3. The three findings

### AF1 — 71% of every poll is a constant (MEDIUM, fix before the frontend binds)

Of the 30.1 KB the poll returns every cycle, **21.4 KB is `geometry`** — and
the data-layer spec says of that key, in its own words, *static per deploy;
safe to read once per page load*. It is re-sent anyway, to every viewer, for
ever.

Compounding it: `POLL_INTERVAL` in `arena_render.js` is **10 000 ms**, not the
20 s the spec describes, and there is **no `visibilitychange` handling** — a
background tab keeps polling at full rate.

At 100 concurrent viewers that is ~4 600 queries/minute and ~18 MB/minute, of
which ~13 MB is a constant nobody needed. Cheap to fix and cheapest to fix
*before* a frontend hard-codes the shape: send `geometry` on first paint,
carry a `geometry_version` in the poll, and refetch only when it changes.

### AF2 — the battle popup computes four things it never shows (LOW)

`arena_battle_popup` builds `recent_chat` (20 rows), `can_vote`/`has_voted`,
the appreciation-gift catalogue and the viewer's token balance. The template
renders **none of them** — only the header, the two chefs, vote counts and
artifacts. So every popup open pays for a chat query and a wallet query that
are thrown away, and Hall-Plan stages **C3 (chat in the popup), C4 (voting in
the popup), C5 (gifts in the popup)** are *not built* even though the view is
already dressed for them. Either the frontend finishes them — the data is
already there — or the view stops paying for what it discards.

### AF3 — the spec's own words are stale in three places (LOW)

`arena_data_layer_spec.md` already carries two corrections (X21, X22). Three
more statements no longer match the code and would mislead whoever binds to it:
the poll cadence (20 s → 10 s), the empty-centre type (`open` → `empty`), and
`facing_pair`, which `_arena_center()` can no longer produce while the renderer
still has a branch for it. The new acceptance test pins the first two so they
cannot drift again unnoticed.

---

## 4. Presence and seating — accepted

Seats are real rows with a partial unique constraint; concurrency is settled by
the database and a retry over the whole hall, not by an optimistic lock — and
an eight-thread barrier test already proves eight simultaneous claims land in
eight distinct seats. Claiming is idempotent, so the poll cannot walk a viewer
around the stands. Lapsed and off-map seats are purged in the right order
(off-map before the idempotency shortcut, lapsed after it).

Capacity is **derived from the geometry**, so widening the stands widens the
hall with no second number to update.

---

## 5. The gate — accepted

Every Arena surface answers **404**, not 403, while `CHEF_BATTLE_ENABLED` is
shut: page, poll, ping, seat, popup. Verified anonymously against production
(`/chef-battle/arena/` → 404) and pinned by a new test that walks all five.
The latch is one-way by the Owner's ruling and nothing here treats it as a kill
switch.

---

## 6. Assets — accepted with a note

| File | On disk | Over the wire |
|---|---|---|
| `arena.css` | 245 KB | **58 KB** (gzip, 30-day cache) |
| `arena_render.js` | 155 KB | gzip on |
| `arena_atmosphere.css` | 34 KB | gzip on |

Compression and caching are live, so the transfer cost is a fifth of the
apparent one. The **maintenance** cost is the real note for a frontend: a
155 KB single-file renderer and a 245 KB stylesheet are not a comfortable base
for a new team member, and any rebuild should plan to split them along the
layer boundaries the spec already names (geometry / data binding / effects).

---

## 7. The four conditions on this acceptance

1. **Settle AF1 before the frontend's data layer is written.** Moving
   `geometry` out of the poll changes the contract the frontend binds to; doing
   it after is a rewrite, doing it now is an afternoon.
2. **Decide C3/C4/C5** (chat, voting, gifts inside the arena popup): finish
   them or strip the view's dead work. The frontend needs to know whether the
   popup is a window or a room.
3. **The pre-battle timeline (T19–T21) is not built.** The Owner's own ruling
   of 2026-08-15 — 48 hours of preparation on acceptance, position in the NEXT
   BATTLE strip *being* the timer, 30 minutes on the second Ready — is on the
   board and measured against the code: two of the eight stages are missing and
   one carries the wrong number. **This is the largest visible Arena gap and it
   is frontend-shaped.**
4. ~~Two accessibility items stay deferred by his 2026-08-10 decision: focus
   rings on four of the first six deck controls, and 9.2 px rank chips.~~
   **CANCELLED by the Owner, 2026-08-16.** Told on that day that these were
   among the last items still carried on the Arena, he answered that they are
   long gone and that nothing is to be done with them. Struck, not deferred:
   the frontend rebuild does not inherit them and Stage 3 does not hold them.

---

## 8. What is explicitly NOT in this acceptance

- Stripe, payouts, refunds and the token economy — the Owner's instruction.
- ~~`VD1`, the overflow at his own viewport, which he froze as visual debt.~~
  **CANCELLED by the Owner, 2026-08-16 — long gone, nothing to be done, card
  deleted.** It is out of this acceptance because it no longer exists, not
  because it was excluded from scope.
- The Hall-Plan stages beyond the popup (B2–B5 teleport choreography, D1
  antechamber): the renderer has displacement and a teleport flash, the
  choreography itself is not built and is not claimed here.

---

## 9. Evidence

- `chef_battle/test_arena_acceptance.py` — 9 tests, PostgreSQL, parallel.
- Numbers in §2 are printed by those tests (`[MEASURED]` lines), not estimated.
- Production checks: anonymous 404 on the Arena; asset sizes and encodings from
  response headers.
