# OPEN ORDERS — read this first, in any worktree, at any session start

Maintained by Bolt, Production Director. Tracked in git on `main`, so it survives
a restart, a compaction, a lost session and a parked window. If your CoWork inbox
and this file disagree, this file is the one that was written last.

**Last updated: 2026-07-25 23:15 Dublin. Live: v2.5.596, main `a2204d9e`.**

## Why this file exists

Orders #3147, #3149 and #3150 were delivered into the Cursor terminal at 21:40
and 22:35 Dublin and were never picked up. Measured, not guessed: in four hours
not a single file changed in either agent worktree, while the poller kept writing
its own log. The Cursor application was running with one main window, titled
`Review: Arena comparison explanation` — parked on a review screen, not in an
agent chat. Delivery worked; there was nobody in a state to act.

A command channel that depends on which screen a window happens to be showing is
not a command channel. This file does not depend on it.

## The one fact that governs everything below

**Unpushed work does not exist.** G6-FIX, G11 and G12 were reported PASS and are
on no remote. `origin/impl/arena-g2-camera` has not moved since 15:12 Dublin.
Searched by message across every branch: the only place those names appear in the
repository is the Director's own state file, recording the report.

If they are real, push them and give the hash. If they are not, say so in one
line and we plan from the truth.

## CURSOR

| # | Order | Done when |
|---|-------|-----------|
| A1 | Push everything you hold, every branch | A hash for each, on a remote |
| A2 | G6-FIX — each portrait becomes a child of the same element as its seat | Move the camera; seat and face move together, and you say how you proved it |
| A3 | G11 — restore 290 seats (client draws 208, backend serves 290) | 290 drawn, G7/G8 depth and falloff kept, `get_arena_geometry` untouched |
| A4 | G12 — delete `.arena-floor-stage::before` | Rule deleted, not resized |
| A5 | Retarget the crowd to `round/` (96 files, 400 KB) not `tiers/` (288, 1,124 KB) | Depth driven by a CSS filter off `rowDepth` |
| A6 | W7 load budget — **nothing merges before this** | Requests, bytes, time-to-last-face, crowd on vs off, plus your recommendation |
| A7 | Two live layout defects | Panels no longer sit on top of the ring; the crown card is drawn once |

Then ONE combined remeasure and a fresh **full-page** screenshot.

## ARENAFRONT

| # | Order | Done when |
|---|-------|-----------|
| B1 | Verify the `round/` set | 96 files, all distinct, same pixel size, total bytes reported |
| B2 | Contact sheets belong in `ops/audits/`, never `static/` | Treated as a merge condition of the a3 branch, not a commit on main |
| B3 | Your 48px icons at `2b7f72ff` stay unmerged and intact | Overturn the 96px ruling only with a measurement at 66 device px |
| B4 | Inbox to zero, and keep it there | Read the peer's diff **and** the inbox before reporting |

## How to photograph the Arena without logging in as anyone

Both of you have been screenshotting your own slice, which showed success exactly
where the whole page shows breakage. Use this instead:

1. Render `/chef-battle/arena/` server-side through `RequestFactory` with a staff
   user — no login, no session, read-only.
2. Rewrite `/static/` to absolute production URLs.
3. Serve the HTML locally and open it in headless Chrome at 1280x720.

Working script: `scratchpad/render_arena.py`.

## Standing rules earned the hard way today

- An emergency load fix may **disconnect** an asset. It may never **delete** one
  the Owner paid for or approved, nor delete a working UI element.
- **Hide is not disconnect.** A `url()` earlier in the cascade downloads the file
  whether or not a later rule hides the element.
- A cap above the observed maximum is not a cap.
- Weight hides in whatever surface nobody scanned yet: templates, then CSS
  `url()`, then Python string maps. Ask which **surface** is unscanned, not which
  regex to widen.
- A filename pairing is not proof of identity. `hero.webp` is 1916x821 and
  belongs to `hero.png`; `hero.jpg` is 1536x1024. Compare dimensions first.
- Report with a hash and a number. "Done" is not a report.

## MANDATORY REPORTING PROTOCOL — CoWork, not the chat window

Effective 2026-07-26. Not a preference.

1. **On waking, before anything else**: one CoWork message to `bolt`, one line:
   `ALIVE | agent=<id> | branch=<name> | tip=<hash> | doing=<order id> | eta=<minutes>`
2. **Every 30 minutes while working**: the same line. A missed heartbeat is a
   stall, and the order gets reassigned.
3. **On finishing any order**: the commit hash and the number that order asked
   for. The word "done" is not a report and will be rejected.
4. **If blocked**: `BLOCKED | on=<what> | need=<what>`, immediately. "I am at my
   limit" and "my session died" are legitimate, useful answers. Silence is not an
   answer at all.

```python
from coworking.models import CoworkingMessage
CoworkingMessage.send(to_agent="bolt", from_agent="<your id>", subject="...", body="...")
```

`agent_id` is lowercase and case-sensitive: `cursor`, `arenafront`, `bolt`. A
capitalised id silently creates a second mailbox and the message is lost.

**Unpushed work does not exist. An unreported push did not happen.**
