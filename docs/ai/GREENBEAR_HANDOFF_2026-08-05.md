# GreenBear handoff — 2026-08-05

Production **v2.5.820**. Constitution **AGENTS.md v2.6.0**. Onboarding package
**1.5d**. Read everything from `origin/main`, never from a working tree.

## Do this before anything else

```bash
git config core.hooksPath .githooks
git config user.name "GreenBear"
```

`core.hooksPath` is local config, so a fresh clone starts with the signing hook
OFF and an unsigned commit cannot be repaired afterwards without the history
rewrite section 6 forbids.

## The law that outranks everything

**`greenbear` is the Owner's own account** — superuser id 1, slug `greenbear`,
holder of the Arena crown. AGENTS.md **§18**: his account, presence, page,
`is_god_author` and `god_mode.css` are untouchable, indirect changes included.
Do not refactor `"greenbear"` into `settings.OWNER_SLUG`. When a slug, path or
asset says `greenbear`, it means THE OWNER, not the agent that shares the name.

**§20**: `is_staff`, `is_superuser`, `has_bearseeker_privileges` and
`has_arena_console_access` are his to set, in the site's own panel. No agent
writes them by any means, and building a tool that makes it easier is itself the
violation.

**§19**: a reply ends the work run. Work continuously, answer once.

## Where the board stands

**A09 is NEXT and unassigned** — live challenger/opponent composition. The Owner
assigns it; no agent self-assigns and no agent assigns another.

Everything before it is DONE: A00–A08, AR0–AR5, A11, A12. A13/A14 depend only on
A06 and are startable. A07 closed at v2.5.812.

**A09 has its number, and it is not the one A06 first gave.** Re-measured on the
served reference 2026-08-05: the fighters are **two blocks, 190 × 212, centred at
x 700 and x 1220** — exactly 260 px either side of the 1920 canvas centre,
symmetric to the pixel. A06's "four plinth blocks in two symmetric pairs" were
**cells of the reference's own 52-cell floor grid**, verified by matching each
block against the children of the element that has exactly 52 of them. The real
fighters are the two `image-slot` elements, which sit outside that grid. A06 §6a
carries the correction.

**Only x transfers.** 260 px is camera-free — `rotateX` leaves x alone. The y
does not: that block is 212 tall against 190 wide and stands upright above the
crown, while our floor fighters lie flat on the floor plane on purpose. Reading
its y as a floor offset is the same error that produced A07's withdrawn target.

Production draws floor fighters only while the centre is an `active_battle` or a
`facing_pair`. The centre has been a crown on every measurement day so far, so
there are none to photograph, and injecting one is forbidden by the card. What
A06 measured as "fighters" — one 66.4 × 69.8 cell avatar at cx 831 — was a chef
seated in a rank ring.

## What A07 established, because A09 works in the same files

The arena fits the screen whole. `arena_command_deck.css` had sized the deck at
`(100svh − header) * 1.28` with `min-height: 42rem` — deliberately past one
viewport, letting the page scroll. Now `100svh − var(--arena-header-h)`, one
style at every width, no media query, and `fitScene()` rescales into what is
left. Measured on production before → after at 2133×958: deck bottom 1187 → 959,
crowd rail 1186 → 958, page 1571 → 1344. The octagon paid 848×665 → 671×520.

**Not verified: narrow viewports.** The browser would not resize below the
desktop window, so the phone claim rests on `svh` plus a measured header, not on
a measurement. Worth closing when someone can measure a real narrow viewport.

## Landmines, measured on the live page, still live

1. **`arena_render.css` does not own the camera.** `arena_deck_polish.css:3666`
   sets it last and wins; two blocks above it (1912, 2277) drop `rotateX`
   altogether. An override written into `arena_render.css` reads back unchanged
   and produces a silent "no effect".
2. **It does not own the floor container's height either.** Its
   `clamp(480px, 56vw, 94vh)` loses to `height: auto` from
   `arena_atmosphere.css` at higher specificity, and the container is absolute
   with `top/bottom: 0`, so it fills its grid cell and nothing more.
3. `filter: none !important` on every arena cell (`arena_atmosphere.css`) kills
   any filter on the floor.
4. A CSS declaration beats an SVG presentation attribute.
5. **Indentation in the Arena stylesheets does not imply a media scope** — 668
   lines sit indented at top level as the bodies of removed `@media` wrappers.
   Check real brace depth, not leading whitespace.
6. PowerShell `Get-Content | Set-Content` double-encodes UTF-8. Never round-trip
   a file through it; verify by reading bytes, not by reading the diff.
7. **`arena_render.css` is loaded from inside the body**
   (`_arena_render_ring.html:201`), after every head stylesheet — so source
   order does not match the `<head>` list.

## The queue, and the mistake that made this rule explicit

**`.agent-chat/deploy.lock` is claimed BEFORE the version bump**, not after the
work is done. Check it is free, write it, then bump, test, push, deploy, release.
A lock written after the bump reserves nothing: a number was taken twice on
2026-08-05 because the bump happened first and a test run was long enough for it
to move. Second belt, not a substitute — `git fetch` and read `origin/main`'s
footer immediately before the push. Owner's ruling: a number taken twice is not
a collision, it is an agent who did not check the queue.

## How he wants the work done (his words)

Orphaned file → bin it, roll back if it breaks. Batch small fixes into **one**
deploy. Short journal rows. **Halve the text** in every reply to him — same
facts, half the words. Do not put another agent in the account of your own
missed check.

Still not simplified, because the failures behind them are real: the §8 gate
before every deploy, never two deploys under one version, and never touching
privileges or the access gate without his word.

## Open

- **A09, unassigned.** Nothing starts without his word.
- Narrow-viewport verification of A07 (above).
- `/tmp/gb_start.sh` on production is root-owned, called by nothing since the
  Stop hook was removed, and not removable as `deploy`. Harmless; `/tmp` clears
  on reboot.

## The poller that was running for eleven days, and how I missed it twice

The Stop hook that sshed to production **as root** to restart a CoWork poller was
removed on his order, 2026-08-05, along with `.claude/check_poller.sh`.

**I then reported "no poller runs anywhere: no process, no cron, no unit". That
was false, and it was in this file.** The daemon was running the whole time —
`root /srv/culineire/venv/bin/python /tmp/gb_daemon.py`, pid 4002094, **989,808
seconds of uptime, eleven and a half days**, parented to init, writing a 1.5 MB
`/tmp/gb_inbox.log` that was last appended to at 09:57 that morning. A standing
§5 violation running as root on production, which is also the account that
poisons the file cache and 500s the whole site.

**Two measurement errors, both mine, both worth copying into the next agent's
habits:**

1. I searched `ps` for `agent_inbox|gb_start|poll`. The process is named
   `gb_daemon.py` and matched none of them, so an empty result read as "nothing
   runs" when it meant "nothing matches my guesses". **A negative from a pattern
   is a fact about the pattern.** Search by what it would be started BY — here,
   the interpreter path `/srv/culineire/venv/bin/python` — and read the whole
   list.
2. Twice I counted `pgrep -f gb_daemon | wc -l` and got a non-zero answer from
   **my own command matching itself** — the exact trap in 17.15.11. Print the
   match list with `ps -o user=,ppid=,cmd= -p <pid>` before believing a count,
   and kill by PID.

Killed by PID, verified gone, and 122 `gb_*` files (2.1 MB, 16–20 July) removed
from `/tmp` — 49 as `deploy`, 73 as root on his explicit order. Site checked
after: `/`, `/recipes/` and `/chef-battle/rules/` all 200, unit active, load
0.04. Nothing can restart it: no cron entry, no unit, and the hook is gone.

## Rollback

`rollback/2026-07-28-stable-v2.5.675` — annotated tag, commit `3b4f88ad`.
Today's releases revert individually; see journal rows v2.5.807–816.
