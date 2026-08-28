# Arena measurement tooling

These are the instruments the Architecture Normalisation phase was measured
with. They lived in a session scratchpad and were lost every time a session
ended, which is how the same harness got rebuilt three times. They live in the
repository now.

Nothing here is production code. Nothing here is imported by the site. They are
read-only measuring instruments, and every one of them was written because a
claim needed evidence.

## Why a harness exists at all

The production Arena is staff-gated and answers 404 to an agent. To measure the
real thing without an account there are exactly two honest routes:

1. **The harness** — `dump_arena.py` renders the real arena view read-only
   through `RequestFactory` (no session, no login, no writes), and
   `build_harness.py` wraps that DOM in the real stylesheets and serves it over
   HTTP. Real DOM, real CSS, real renderer, but a local page.
2. **The production preview** — `chef_battle:arena_preview_current`, a
   token-gated read-only render of the real production Arena. It records no
   presence and creates no profile. The token is `ARENA_PREVIEW_SHARE_TOKEN` in
   the server's `.env`; it is a secret and is deliberately not in this
   repository.

Route 2 is the one that matters for performance claims: it is production. Route
1 is for cascade and geometry work, where a local page is enough. Do not
describe route-1 numbers as production numbers — that mistake was made in this
phase and had to be corrected in the report.

## The tools

| File | What it does |
|---|---|
| `dump_arena.py` | renders the arena view read-only to `arena_dom.html` |
| `build_harness.py` | wraps that DOM in the real stylesheets, rewrites `/static/` to a local server, cache-busts every asset |
| `build_console.py` | the same for the Master Console mirror, with the console's own stylesheet order |
| `an28_rig.py` | builds six load profiles — normal, hard reload, cold, CPU-blocked, late renderer, both — and the observer page |
| `an28_observer.html` | watches a page from before first paint and records when each element first becomes visible, and where |
| `audit_owners.py` | finds a second owner of a position: every CSS rule and JS statement that can move a component |
| `css_cross1.py` | single-selector conflicts between two stylesheets |
| `css_order_risk.py` | declarations a later identical selector already beats |
| `an18_audit.py` | classifies static assets by who names them |
| `an20_scan.py` | counts listeners, observers, timers and read/write interleaves |
| `an22_static.py` | the static-asset inventory |
| `an13_clean.py` | removes declarations the cascade already overrides, and refuses unless the applying set is byte-identical before and after |
| `an14_move_guard.py` | proves a rule was MOVED and not changed: no conflicting pair changed places |

`css_order_risk.py` reads a `scratchpad/css_supersede.py` that ended with the
session it was written in. `an13_clean.py` is the part of it that survived, and
it is in the repository for that reason.

## AN13 and AN14 are two different proofs, and the second is not optional

`an13_clean.py` proves a DELETION safe: the set of declarations that actually
apply — context, selector, property, value — is byte-identical before and after,
so only copies that already lost were cut.

That proof says nothing about a MOVE. Order decides between two DIFFERENT
selectors of EQUAL specificity writing the SAME property, and AN13's map is
keyed per selector, so it would not see the change:

```css
.a { color: red }      /* one element matches both */
.b { color: blue }     /* the lower one wins */
```

`an14_move_guard.py` is the missing half. It groups every declaration by
(context, property, specificity, importance) — inside such a group, and only
there, source order decides — and requires the relative order of the rules
within every group to be unchanged. It is deliberately conservative about
whether one element can match two selectors: it assumes it always can. Being too
strict costs a move that has to be done another way; being too permissive costs
the Owner his layout.

```bash
python3 ops/audits/arena/tools/an14_move_guard.py --selftest static/css/arena.css
python3 ops/audits/arena/tools/an14_move_guard.py /tmp/before.css static/css/arena.css
```

`ArenaStylesheetMoveGuardTests` in `chef_battle/tests.py` runs the selftest in
CI, because a guard nobody has watched fail is not a guard.

## Running them

```bash
# from the repository root, in WSL
export ARENA_HARNESS_OUT=/tmp/arena-harness      # anywhere writable
python3 ops/audits/arena/tools/dump_arena.py
python3 ops/audits/arena/tools/build_harness.py
python3 -m http.server 8765 --directory static & # the assets
python3 -m http.server 8793 --directory "$ARENA_HARNESS_OUT" &
# then open http://localhost:8793/b.html
```

## Two traps that cost real time

**A grep is not a measurement unless the file was written by the command that
claims to have written it.** A stale `/tmp/prev.html` from three weeks earlier
was read as today's production HTML and reported as a serious cache defect. It
was not. Check the mtime, or write to a fresh unique filename and verify the
byte count.

**`document.styleSheets` is not a reliable way to read the cascade here.**
Walking it once visited 151 rules out of roughly 2000 and the conclusion drawn
from that walk was wrong. Parse the served stylesheet text, or use the Python
tools in this directory, which read the files themselves.

**The browser pane does not composite when it is not fronted.** `requestAnimationFrame`
never fires, `setTimeout` is throttled to seconds, screenshots time out and
Chrome records no paint entries at all — so first paint and FCP cannot be
measured there. Use `MutationObserver` plus a short interval for anything
event-driven, front the tab when timing matters, and do not report a paint
metric the browser never recorded.
