# Arena Battle Plan — Design Arena integration onto `main`

**Status:** ACTIVE. This file and the moderation build board are the dispatch
contract for the Arena. The Owner gives an agent **one card at a time**. The
agent returns its exact commit, files, visible result, checks and evidence.

Last reconciled: 2026-08-08 · Production baseline: **v2.5.950**
· Next assignable card: none — B01 went to Bolt on the Owner's word, 2026-08-07.

**MC01 was built and then DELETED on the Owner's order the same day (v2.5.842).** It walked the withdrawal through the Master Console as step cards — three columns of text per step. Nothing in it was factually wrong; being a description was the problem. His words: he wants the steps seen LIVE ON THE ARENA, not read. The panel, its module, its stylesheet, its stepper and its tests are gone — no dead code left behind. What replaces it is MC02 and `docs/chef_battle/ARENA_EMULATION_VISUAL_STEPS.md`, which is a specification and never a screen: nine rows naming the one thing he must be able to SEE at each step, driven by the existing `emulation.py` (`start_emulation`, `emulation_step`) through the real services. Most rows are TO SPEC and stay that way until he says what they look like. That blocker is gone: A09 closed on 2026-08-06 - the approach in v2.5.844 and the fighter who stayed visible in v2.5.847 - so an emulated bout now has two chefs standing in it.

**Bolt's session of 2026-08-05/06, in order.** X04: the roadmap advertised five
token packages topping out at Executive 1400T/EUR80 while `token_config.py` has
eight, to Legend Chef 12800T/EUR768 — the row is derived from the catalogue now
(v2.5.819). X01: the upcoming-battles list, absent from the payload, the
selectors and the template, built and then rebuilt twice to the Owner's design —
a sub-line under the phase steps, then pills of two halves with a face and a
name in each, three to a row, two rows, soonest climbing to the top right
(v2.5.822 → v2.5.825). `?demo=next` fills both rows from real enrolled chefs for
inspection (v2.5.827) and is now largely redundant, see the repeal below.
**AGENTS.md 2.10.0** (v2.5.829): the Owner repealed the line forbidding
data-writing on production to prove a visual result — arena functionality is
exercised on production, continuously and across all of it, with his words
recorded verbatim in section 8. Console mirror (v2.5.831): the console built its
own `arena_data` from a hand-listed copy that had lost `vip_sponsors`,
`spirit_count` and `upcoming`, and loaded one stylesheet where the arena loads
five — one assembly and one set of sheets now, flat and effect-free by his
instruction, twelve panels each carrying an `i` that explains itself after a
two-second rest.

**Open, and his to rule on: browser zoom.** Above 100% the arena appears to
shrink while everything else grows, and below 100% the reverse. Measured on the
same window, 966×918 against 644×612 (what 1.5× zoom leaves of it): the deck
goes 746px → 660px physical, −11%, while a `rem`-sized phase step goes 35 → 52,
+50%. The cause is A07 itself — the deck is `calc(100svh - header)`, and a box
measured by the viewport cannot scale with zoom because the viewport does not.
He has parked it as-is for now. The candidate fix is
`min(100svh - header, N rem)`: zoom works until the arena fills the screen, then
stops, and A07's no-scroll rule still holds.

**X01 is DONE (v2.5.822 → v2.5.825, Bolt).** The arena now shows who is fighting whom next.
The Owner named the upcoming-battles list as half of what the arena is for and
nothing answered it — no payload key, no selector, no template block. Upcoming
is narrower than "not finished": `SCHEDULED` **and** `start_time` still ahead.
A scheduled battle whose time has passed is one the arena is already showing,
and `WAITING` is a battle that started and is late, not one that is coming. The
key is in `PUBLIC_ARENA_STATE_KEYS`, or the poll would have emptied the panel
thirty seconds after load. Its placement — left rail, under the crown ladder —
is provisional: the approved reference has no such panel, so there was nothing
to measure against, and moving it is CSS only.

**A07 is DONE (v2.5.812) and it was one multiplier.** The Owner defined the card
on 2026-08-05: *the arena fits the screen whole, on every screen.*
`arena_command_deck.css` was sizing the deck at `(100svh − header) * 1.28` with a
`min-height: 42rem`, deliberately growing the stage past one viewport so the
octagon stayed large and the page scrolled. That trade is reversed. Measured live
on production at 2133×958 — deck bottom **1187 → 959**, crowd rail **1186 → 958**
against a 958 viewport — at the cost he chose: the octagon goes 848×665 → 671×520.

**Its earlier attempt, kept because it settles the camera.** v2.5.792 put the
Design Template's camera on the Arena — `rotateX(57deg)`, `perspective 1600px` —
and the Owner reverted it within the hour. The camera stays `rotateX(42deg)`. The
reference floor is a 1120×1120 **square**, the same as this SVG's viewBox, so its
2.375 aspect is produced by that camera and not by a wider octagon; the target is
not available at 42°, which is why A07 shipped as a framing card and not a
geometry one. See v2.5.792/793 in the journal.

**Two cascade facts A09 will need, measured on the live page, not read off the
source.** The camera is set by `arena_deck_polish.css:3666` — last one wins — and
two blocks above it (1912, 2277) drop `rotateX` altogether; `arena_render.css`
does not own it. The floor container's `clamp(480px, 56vw, 94vh)` in
`arena_render.css` loses to `height: auto` from `arena_atmosphere.css` at higher
specificity, and the container is absolute with `top/bottom: 0`, so it fills its
grid cell and nothing more.

## 1. Current team and ownership

| Role | Responsibility |
|---|---|
| **Owner** | Final authority; assigns one atomic card and accepts visible results. |
| **GreenBear** | Visual CSS. |
| **Bolt** | Measurements and independent visual/regression checks. |

**Ember was retired by the Owner on 2026-08-04.** Its name stays on the DONE
rows in §4 and §5 — attribution is history and is not rewritten — and every
open card that suggested it is now **unassigned**: A09, A16, A17, A18, B01, B03,
R01, R02. A suggestion pointing at a retired agent reads as an owner and stops
the next agent from asking. Integration, JS, templates and backend wiring have
no standing owner; the Owner assigns them.

**There are no fixed roles and no deploy gate-holder.** The column above is a
typical focus, not a lock, and the §5 "suggested owner" is a suggestion. Any
agent may deploy their own work — one at a time, by the full Gate in §3.
Director, Cursor and ArenaFront are retired. Master Console is outside this
plan. One file has one owner during an active card; agents do not create
parallel long-lived branches.

## 2. Arena structure contract (v2 — 11-ring octagon)

Approved by the Owner 2026-07-29. This **supersedes** the former freeze
("eight rings", "do not change the existing octagon render method", "do not
change floor colours"): the eleven-ring structure below is now the target, and
the renderer may change to build it.

The octagon is **eleven rings**, centre outward:

| # | Ring | Fill (reference; implemented as tokens) |
|---|------|------|
| 1 | **Crown Holder** — crown + current holder's name (already live) | `#52422E` |
| 2 | **Moat** — service ring: `border:0`, no visible cells; a glowing lantern at each cell centre casts glints onto the gold ring | base `#52422E` |
| 3 | Culinary Master | `#7C674D` |
| 4 | Executive Chef | ↓ eight rank rings, one monotonic |
| 5 | Head Chef | gradient from `#7C674D` (ring 3) |
| 6 | Sous Chef | to `#EEE1CA` (ring 10): the six named |
| 7 | Chef De Partie | palette tans/beiges + two logically |
| 8 | Commis Chef | interpolated steps |
| 9 | Prep Chef | ↑ |
| 10 | Kitchen Porter | `#EEE1CA` |
| 11 | **VIP Guests** (Sponsors) | `#535252` steel |

Around the floor: **two rows of seats top and bottom** = authorised guests who
are **authors** (not chefs); behind them, **balconies** for unauthorised users —
bodiless spirits. The seat contract is rewritten for this new grid (drafted
separately, §2a).

Still in force (unchanged by v2):

- Camera `rotateX(42deg)`.
- Design **tokens** only, no raw hex — the palette above lands in tokens.
- Dark Launch intact: unauthorised and anonymous Arena requests remain 404.
- Never put fake fighters, rankings, gifts, viewers, streams or results in production.
- Effects (dust, gifts, rays, shimmer, crown light) preserved; Master Console untouched.
- No reference K banner; reuse existing CulinEire branding where a mark is required.
- Mobile Arena is frozen and is not a blocker for this desktop plan.
- **A screenshot is a single-use diagnostic, not a stored artifact (Owner,
  2026-08-04).** Take it, read the problem off it, delete it. Do not commit it.
  A stored screenshot ages into a confident lie: it keeps looking authoritative
  long after the page stopped looking like that, and 6.87 MB of exactly that
  was removed from `ops/audits/` in v2.5.806. Evidence of a visual state is the
  MEASUREMENT — a JSON of bounding boxes, diffable and re-runnable — plus the
  command that reproduces the view. Paid or approved imagery is not a
  screenshot and is never covered by this.
- **The media layer is CLOSED (Owner, 2026-08-03): below 901px the Arena stays
  exactly as it is.** One visual style, the desktop one, at every width. The 86
  `min-width: 901px` wrappers removed in v2.5.729/730 stay removed. Two scopes
  came back in v2.5.772 and only those two, because `placeRankSpine()` still
  tested both breakpoints and cleared the rank column's inline geometry while no
  stylesheet stood up to take over. There is no stage 2. Note also that
  indentation in the four Arena stylesheets no longer implies a media scope: 668
  lines sit indented at top level as the bodies of the removed wrappers, and
  reading one of them as scoped is how that defect stayed invisible for six days.
- **Never put fake anything in production, and that includes the audience.** The
  arena deck's `hydrateFixtures()` was disconnected in v2.5.782 after production
  measurement showed the server sending zeros while the page showed 2.4K viewers,
  3.7K votes, 620 gifts and a battle between two chefs who do not exist. It is
  switched off, not deleted, and three tests keep it that way — including one
  that keeps the function present, so it is not dead code to be tidied away.

## 2a. Seat & spectator contract (v2)

Approved by the Owner 2026-07-29. Replaces the "290 real-viewer oval" model.

- **Real interactive seats belong to authors** (authorised users who are not
  chefs): two rows top and two rows bottom around the floor. Front rows fill
  first; a logged-in author sees themselves seated.
- **VIP Guests** (ring 11) are reserved seats for **sponsors**.
- **Balconies** behind the author rows hold **unauthorised users as bodiless
  spirits** — atmospheric only, never impersonating a real/online user, with no
  interactive seat identity.
- The former fixed **290**-seat oval is superseded; capacity follows the two-row
  geometry, front rows first.
- Chefs occupy rank rings 3–10 by rank; the Crown Holder holds ring 1; the
  **Moat (ring 2) has no occupants** — lanterns only.

## 2b. Battle lifecycle choreography — where a chef stands, and when

**Owner, 2026-08-05, restating decisions he first recorded on 2026-07-02.** They
were written down all along, in
`docs/archive/pre-constitution-reset-2026-07-20/docs/chef_battle/ARENA_HALL_PLAN.md`
("Status: APPROVED PLAN — Owner decisions recorded 2026-07-02"). That file is
ARCHIVED, and §10 says an archived document cannot define current scope — so the
rules existed and governed nothing, which is why stage B2 below was never built
and why an agent asked him to repeat himself. They are moved here to be law
again. The same failure hid §18 for two weeks.

**1. Standing.** A chef who enters the arena stands in **his own ring**, the one
labelled with his rank. That is what the rank ladder beside the cells is for.

**2. Challenge.** A challenge may only be thrown at your **own rank or one rank
above or below** — already enforced server-side by
`check_rank_matchup()` in `chef_battle/services.py`, with the site Hero
unrestricted. When it is accepted, the two avatars **move towards each other
inside their own rings**: same rank — opposite cells of that ring; different
ranks — a vertically aligned pair across the two rings. They have NOT reached
the centre yet.

**3. Battle time.** Only when the battle's time arrives do both avatars leave
the ring for **two placeholders beside the centre**, and they stay there for the
duration. The centre carries **VS** and a **link to the battle page** — a
separate page the spectators go to in order to watch the fight. Chefs move, they
are never drawn twice.

**4. On completion** both return to their own ring cells.

**What the arena is for, and it is only this:** so that chefs, sponsors,
spectators, VIPs and spirits can **see each other**, and to show the **list of
upcoming battles**.

### One superseded line, named so nobody restores it

The 2026-07-02 record approved the centre opening a **popup embedded on the
arena**, explicitly "not a link to a separate page". **His instruction of
2026-08-05 reverses that: it is a link to a separate battle page.** The later
word wins (§2 of the constitution, source-of-truth order). `_arena_center()`
already emits both `battle_url` and `popup_url`; the link is the one that counts.

### The delta against the code, measured 2026-08-05

| Stage | Specified | Code today |
|---|---|---|
| Standing in own rank ring | yes | **holds** |
| Challenge limited to rank ±1 | yes | **holds** — `check_rank_matchup()` |
| Approach INSIDE the rings on accept | yes | **MISSING** |
| Move to the centre at battle time | yes | holds |
| Return to ring cells after | yes | holds |

`_arena_center()` returns `facing_pair` for `SCHEDULED`/`MENU_LOCKED` and
`active_battle` otherwise — but `stampFloorCentre()` handles both in **one
identical branch**, drawing both at the centre, and `isDisplaced()` empties a
chef's ring cell as soon as `chef.battle_id === center.battle_id`. So a chef
leaves his ring the moment a battle is scheduled and jumps straight to the
centre. **The approach stage was missing; it landed in v2.5.844 (A09).**

## 2c. The arena is a tabloid; the battle has its own page

**Owner, 2026-08-06.** The arena is **a board, not the show**: it says who is
here, who is fighting whom and what is coming. The fight itself happens on a page
of its own.

**The entry point is the centre cell.** When a battle STARTS, a click on the
centre takes every spectator off the arena and onto the battle's own page. Today
that click opens `ArenaBattleRoom` — an overlay popup over the arena floor
(`arena_render.js`, `stageCentre.popup_url`). That is a placeholder, and the
target is a page.

**The approved reference for that page already exists and is served:**

    /chef-battle/master/live-arena/preview/
    templates/chef_battle/live_arena_preview.html   (added 5c457b98, 2026-07-14)

It is console-gated and its data is a **labelled DEV FIXTURE** — invented chefs,
invented viewer counts — because it is a build canvas, not a live surface. **It
is not an orphan and it is not to be tidied away.** It carries the composition:
the CHEF #1 / VS / CHEF #2 header with rank, clan and country; two live stream
panes with viewer, like and comment chips; the supporter strip and Support Chef
buttons; the central TIME REMAINING countdown; and the three-column live chat
with its composer.

That composition is what cards **B01, B02 and B03** build against, with real
battle data replacing the fixture field by field. B02 is GreenBear's; B01 and B03
are unassigned.

What follows from "the arena is a tabloid": the arena keeps the ladder, the
upcoming board, the seats and the octagon, and does NOT grow a second copy of the
broadcast. Anything that belongs to watching a fight belongs on the battle page.

## 3. Slice gate

1. Start from current `origin/main` in one disposable worktree.
2. Implement one card only; check overlap before editing.
3. Run focused PostgreSQL tests, `manage.py check`, diff hygiene and the
   card-specific visual check. The full suite belongs to final gate G01, not
   every small slice.
4. Commit and push the exact slice. The deploy gate verifies origin commit,
   production version, recent deploys, rollback safety and postflight.
5. After a deployed slice, close its temporary branch/worktree. The shared
   repository truth is `origin/main`.
6. Update the card evidence and status in the same change.

**Slices run strictly one at a time, in the §5 table order (sequential
dependency).** Slice N+1 is not started until slice N is **DONE** (merged,
deployed and verified). Only one slice is ever in flight, and each agent holds
at most one card. Nobody starts the next card before the current one is DONE.

**Before taking a new card, go to the board first.** Confirm the previous card is
marked **DONE** in both §5 here and `ARENA_RELEASE_STAGES`/`ARENA_DESIGN_TASKS`
(`recipes/views.py`), and that the closing change is **deployed** to production.
Only then move to the next card. Closing the board is part of finishing a card,
not a separate afterthought — a card whose board row is not DONE-and-deployed is
not finished.

**No roles: any agent may deploy, one at a time, by the full Gate.** Before
shipping, the deploying agent proves three things: (1) **production is current**
— the base is `origin/main` and nothing is unshipped ahead of the served
version; (2) **nobody else is deploying right now** — claim the turn (shared
`deploy.lock`, or tell the Owner and wait for his word); (3) **it breaks nothing
and erases no important files** — focused PostgreSQL tests, `manage.py check` and
`git diff --check` are green, and no paid or approved asset is deleted.

## 4. Completed production foundation

| Card | Result | Evidence |
|---|---|---|
| A00 | Reference authority and immutable constraints reconciled | Plan/Deployment Project audit |
| A01 | Real 290-seat oval connected; one viewer count; stands visible | v2.5.676–v2.5.678 |
| A02 | Chef identity inside existing fighter plinths | v2.5.682 |
| A03 | Correct rank order and approved bevelled labels | v2.5.684–v2.5.685; non-interactive plinth correction v2.5.695 |
| A04 | Cell ripple and chef card anchored to any clicked cell | v2.5.687, v2.5.691; close control v2.5.695 |
| A05 | Independent left Cooking Widget; lifecycle rail separated; compact metrics | v2.5.689–v2.5.692; complete Cooking Widget corrected v2.5.699–v2.5.703 |
| AR2 | Floor palette settled — Owner ramp, moat/VIP tokens, neutral ink | v2.5.704–707, 709–722, 728 |
| A06 | Production vs Design-Arena measurement matrix (read-only) | ops/audits/arena/A06_remeasure_2026-08-04.md — reference floor aspect **2.375**, production **1.266**. The 2026-07-29 matrix is SUPERSEDED: it was measured against the rejected prototype and is kept as evidence only, not as a source. |
| AR0 | Arena CSS/JS dead-code inventory (read-only) | ops/audits/arena/AR0_dead_code_inventory_2026-07-29.md |
| AR1 | Arena owns its eleven-ring geometry; Sponsors grid no longer borrowed | v2.5.709–v2.5.710 |
| AR3 | Moat lit by eight lanterns; glint on the Crown plate | v2.5.736 |
| A08 | Crowd bowl depth, and the hall behind the seats populated | v2.5.775–779 |
| A07 | The arena fits the screen whole — deck bottom 1187 → 959 at 958 viewport | v2.5.812 |
| AR4 | Author seats: two rows top, two bottom; capacity 290 → 114 | v2.5.769 |
| AR5 | VIP sponsor ring; spirit balconies driven by a real anonymous count | v2.5.765–768, v2.5.778 |

## 5. Atomic dispatch queue

The build board contains the full action, files, visible result, acceptance,
forbidden changes and evidence for every row below.

| ID | Surface | Task | Suggested owner | Depends on | Status |
|---|---|---|---|---|---|
| A00 | Arena Hall | Reference authority and immutable constraints | Ember | — | DONE |
| A01 | Arena Hall | Recovered live scene baseline | Ember + GreenBear | A00 | DONE |
| A02 | Arena Hall | Chef identity inside existing floor plinths | Ember | A01 | DONE |
| A03 | Arena Hall | Rank spine order and approved plinth shape | Ember | A01 | DONE |
| A04 | Arena Hall | Cell click ripple and chef-card anchoring | Ember | A01 | DONE |
| A05 | Arena Hall | Broadcast ribbon, phase rail, metrics and identity | Ember | A00 | DONE |
| A06 | Arena Hall | Fresh production/reference measurement matrix | GreenBear | A05 | DONE |
| AR1 | Arena Hall | Eleven-ring octagon geometry (Crown, Moat, 8 ranks, VIP) | GreenBear | A06 | DONE |
| AR2 | Arena Hall | Eleven-ring palette tokens | GreenBear | AR1 | DONE |
| AR3 | Arena Hall | Moat ring (ring 2) with lanterns + gold-ring glints | GreenBear | AR1 | DONE |
| AR4 | Arena Hall | Author seat rows (two top, two bottom) | Bolt | AR1 | DONE |
| AR5 | Arena Hall | Spirit balconies + VIP sponsor ring | GreenBear + Bolt | AR4 | DONE |
| A07 | Arena Hall | Stage framing and full-octagon composition | GreenBear | AR5 | DONE |
| A08 | Arena Hall | Crowd bowl depth and atmospheric population | GreenBear | A06 | DONE |
| A09 | Arena Hall | Live challenger/opponent composition | Bolt + GreenBear | A07 | DONE |
| A10 | Arena Hall | Crown-holder hub composition | GreenBear | A07 | DONE |
| A11 | Furniture | Phase panel reference pass | Bolt | A06 | DONE |
| A12 | Furniture | Crown ladder panel reference pass | Bolt | A06 | DONE |
| A13 | Furniture | Recent gifts panel reference pass | GreenBear | A06 | DONE |
| A14 | Furniture | Bottom ticker and Join the Crowd composition | GreenBear | A06 | DONE |
| A15 | Arena Hall | Effects and artifacts preservation pass | GreenBear | A07–A10 | DONE |
| A16 | Arena Hall | CulinEire branding and K-mark audit | unassigned | A11–A14 | DONE |
| A17 | Integrity | Truthful visual state matrix | Bolt | A09–A16 | **DONE** — `docs/chef_battle/ARENA_TRUTHFUL_STATE_MATRIX.md`, measured on production |
| A18 | Integrity | Desktop accessibility and responsive gate | Bolt | A17 | **DONE** — 1920/1440/1280/375 swept, 0px overflow, keyboard verified with real Tab |
| A19 | Arena Hall | Owner visual acceptance — Arena Hall | Owner | A18 | PENDING |
| MC01 | Master Console | Battle Cancellation Simulation — the withdrawal, step by step | Bolt | v2.5.830 | **DELETED by the Owner** |
| MC02 | Arena | The withdrawal seen LIVE on the arena, not described — see `docs/chef_battle/ARENA_EMULATION_VISUAL_STEPS.md` | unassigned | A09 | **OPEN, awaiting the Owner's steps** |
| SA-A2 | Arena | An accepted challenge seats the pair in adjacent cells, each in his own ring | Bolt | — | DONE v2.5.844 |
| SA-A4 | Arena | That pairing is stable across leaving and returning | Bolt | SA-A2 | DONE v2.5.844 |
| SA-A6 | Arena | Both Ready pulls the match in to 15 minutes and the pill climbs the queue | Bolt | — | DONE v2.5.844 |
| B01 | Battle Broadcast | Broadcast shell and confrontation header | Bolt | A19 | **DONE v2.5.874** |
| B02 | Battle Broadcast | Streams, countdown and support furniture | GreenBear | B01 | DONE |
| B03 | Battle Broadcast | Broadcast chat and composer | GreenBear | B02 | DONE |
| R01 | Result / Winner | Champion and runner-up result shell | GreenBear | B03 | DONE |
| R02 | Result / Winner | Result metrics, status and chat | GreenBear | R01 | DONE |
| G01 | Release gate | Complete Design Arena regression and production evidence | Team + Owner | A19, B03, R02 | PENDING |

## 5a. ARCHITECTURE NORMALISATION (AN1 - AN29)

**Opened by the Owner, 2026-08-08.** Twenty-nine sections, numbered AN1 to AN29.
**Every card is a numbered section of his master task, in its order**, and the
`Master task` column says which one. Nothing here is invented: a card that
cannot name its section does not belong in this block. The state of each is what
was measured, not what was hoped.

### Why it exists — his verdict, 2026-08-07

> «то, что мы создаём, это по сути пазл, который мы должны двигать в любом
> направлении в котором нам нужно... а не 10 слоёв стоят друг на друге как
> карточный домик, а любой пиксель вправо или влево его разрушит - это в корне
> не правильное видение нашего проекта»

He then said: **«будем всё исправлять и чинить»** — the work is approved, and
this is where it is written down.

### The measured state this block starts from

Facts, not opinions. Each was counted on 2026-08-07/08, and each is a candidate
for a section rather than a section already assigned:

- **Seven arena stylesheets, 9425 lines.** `arena.css` 780, `arena_command_deck.css`
  747, `arena_effects.css` 134, `arena_hall.css` 257, **`arena_deck_polish.css`
  4345**, `arena_atmosphere.css` 955, `arena_render.css` 1316. Six are linked in
  `arena.html`; the seventh arrives from `_arena_render_ring.html`, so a `<link>`
  sits in the middle of `<body>` and the load order cannot be read in one place.
- **Which sheet wins is decided by a line in a template**, commented "polish then
  atmosphere". That is why correct rules have twice failed to reach the screen:
  one lost the cascade to `.page--arena`, one was cut away by `clip-path` after
  it was painted.
- **54 `z-index` declarations** across three of those sheets, 19 distinct values
  from -1 to 130, one `!important`.
- **The deck's vertical space had three owners that did not know about each
  other**: a CSS share for the caption (`top: 8.2%`), a CSS share for the floor
  (a 0.64 pad and a 0.51 composition centre), and a JS pass clawing a band back
  after the fact. Eight releases in one day (v2.5.890 to v2.5.904) went into one
  caption because each fix was right about its own piece and blind to the rest.
- **`--arena-shift-y` is applied inside `rotateX(42deg)`**, so a translation asked
  for in CSS pixels lands foreshortened by the cosine of that angle. Anything
  that positions by arithmetic instead of measurement is wrong by that factor.
- **A started refactor is parked, not merged**: `DeckBands`, one owner for the
  deck's vertical space, in `.agent-chat/bolt-deckbands-wip.patch`. Unverified.

### The sections

| # | Master task | State | Title | Evidence |
|---|---|---|---|---|
| **AN1** | §3 | DONE | Read-only inventory before any edit | origin/main, HEAD, production version, worktrees, branches, stash, untracked files, handoff documents, the board, live behaviour, and the fate of the DeckBands prototype. ARENA_NORMALISATION_BASELINE.md, at v2.5.910. |
| **AN2** | §4 | DONE | Recoverable backup with a TESTED rollback | backup/arena-pre-normalisation-2026-08-08 -> a1f40923, pushed to origin. Rehearsed in a detached worktree: footer read v2.5.910 and manage.py check was green. Migrations 218, chef_battle at 0085. |
| **AN3** | §5A | DONE | Codebase baseline - files, lines, selectors, observers, timers, measurements | 7 stylesheets / 8534 lines / 1110 live rules; 136 !important; 70 z-index declarations over 21 values; arena_render.js 3408 lines with 21 getBoundingClientRect calls, 6 ResizeObservers and 20 position writes. |
| **AN4** | §5B | DONE | CSS cascade map - every sheet, its loader, its order, contested ownership | 585 selector/property pairs with more than one owning file; 55 selectors written in three or more files; arena_render.css found linked from INSIDE the body, measuring last in the cascade. |
| **AN5** | §5C | DONE | JavaScript ownership map and dependency graph | Six functions read AND write layout in one pass; measureHeader alone does 10 reads and 5 writes; the fit, the ladder and the caption all re-enter through one call chain. |
| **AN6** | §5D | DONE | DOM/SVG initialisation order, with the ladder jump MEASURED | One layout shift at 943ms, CLS 0.0255, the rank spine travelling 441px right and 102px down from its stylesheet position to its JavaScript one. |
| **AN7** | §5E | PARTIAL | Performance baseline | Measured on a harness that carries the real arena DOM, the real stylesheets and the real renderer over HTTP, at 1280x800: FCP 544ms, LCP 544ms, DOMContentLoaded 283ms, load 406ms, CLS 0 with zero layout-shift entries, 4 long tasks, 2486 DOM nodes of which 1759 are the octagon's SVG, 136 requests. The first animation frame the page ever paints already has the rank ladder at its final box, 935,372,148,220, and already visible - there is no frame in which it is somewhere else. STILL MISSING, and it is a tool limit rather than an unfinished measurement: cold cache, CPU throttling and network throttling need CDP, and the production arena is staff-only so the browser here cannot open it at all - it answers 404. Every number above is therefore a harness number, honest for before-and-after comparison and not a statement about production. |
| **AN8** | §5F | DONE | Geometry baseline at the approved viewports | 1920x1080, 1440x900, 1280x800 and the Owner's own 1170x820. Every panel box and every intersection recorded, including the four overlaps that exist at his window. |
| **AN9** | §5G | PARTIAL | Twelve load and resize scenarios | Ten of the twelve scenarios are measured, up from four. Warm load and reload at 1280x800: CLS 0, zero shift entries, ladder 935,372,148,220 in the FIRST painted frame. 1280 -> 1920: ladder 1391,462,170,220, caption 747,235,416,53. A fresh load at 1920 is byte-identical to arriving there by resize. 1920 -> 1440 -> 1280x520 -> 1024 and back to 1280x800 returns the exact fresh-load numbers, so the tour converges rather than drifts. On the short screen that broke this before, 1280x520, the ladder now ends 1px ABOVE the fold where it used to hang 19px below it. At 1024 the header measures 172 rather than 146 and the deck overflows the viewport by 0px, which is A07 holding at a width where it used to fail. The two that remain are cold cache and CPU/network throttling: they need CDP, and the production arena is staff-only, so this browser cannot open it - it answers 404. |
| **AN10** | §6 | DONE | The complete pre-refactor test baseline, run once | 1750 tests, 2 pre-existing failures, 710.7s, PostgreSQL, --parallel 8, production dependency versions. Full output preserved beside the baseline report. |
| **AN11** | §7 | DONE | Arena ownership manifest - one responsibility, one owner | Thirteen responsibilities mapped to the real code. Five had more than one owner: ring colour, the camera, the page's vertical space, the ladder's position and z-order. Readiness had no owner at all. |
| **AN12** | §8 | DONE | Consolidate the Arena stylesheets | Seven stylesheets are two. arena.css carries the shell and the octagon renderer; arena_atmosphere.css carries the effects layer and the hall, and loads after it. The Master Console still loads arena.css ALONE, flat, by the Owner's ruling of 2026-08-08 - which is why the split falls here and not somewhere tidier, and why the earlier claim that four was the end state was wrong. Sixteen declarations written in two sheets at once were removed first, so no single selector sets the same property in any two files and no repackaging can change a winner. Proved in a real engine over the rendered arena DOM: 2435 elements, each with its ::before and ::after, 544 computed properties apiece, plus the 1759 SVG nodes re-measured with the stage forced to crown, active_battle, facing_pair and no state at all. Zero differences. The only rows that moved were two values the site's own JavaScript randomises per load, and the same rows move when the SAME file is loaded twice. It caught a real regression before it shipped: the live battle stage would have turned grey, because the atmosphere's `.arena-stage` fill and the renderer's `[data-state]` fills carry equal specificity and only the load order had ever separated them. |
| **AN13** | §8A | DONE | CSS cleanup rules | 584 declarations that a later rule with the IDENTICAL selector already overwrote are gone, and 135 rules left with nothing in them went with them: arena.css 6237 -> 5130 lines, 216KB -> 185KB. Equivalence proved rather than asserted - 2550 winning declarations before, the same 2550 after, 0 changed, the surviving rules in the same cascade order, brace balance 0. !important came out in AN8 (136 -> 58). A test now fails on any property written twice for one selector. |
| **AN14** | §8B | DONE | An explicit layer model instead of scattered z-index | 21 --arena-z-* tokens and 0 raw numbers left in the four sheets. The values are unchanged on purpose: this gave the ladder a home, it did not re-order it. |
| **AN15** | §9 | DONE | One page-level layout authority | The page's own geometry has an owner, and it is not the octagon. `static/js/arena_page_layout.js` publishes --arena-header-h - everything above the deck - and owns the four triggers that can change it: the site header's own box in border-box mode, the window, the moment the web fonts settle, and one late pass. The renderer subscribes and re-fits; it no longer contains the string `.ce-header` at all, which is the literal test of section 9's 'a widget does not measure its neighbours'. The formula and all four triggers are unchanged on purpose - moving ownership is not licence to move a pixel - and it was measured rather than assumed: the same page loaded with the old code and the new one gives octagon 305,284,659,454, ladder 935,372,148,220, caption 350,235,416,51 both times, and the only difference anywhere is that window.ArenaPageLayout now exists. Resizing to 1920 through the force path lands the ladder at 1390,463 and the caption at 747,235, which is the production baseline for that width. Nine tests hold it, including one that fails if the renderer ever goes looking for the header again. |
| **AN16** | §10 | DONE | Isolate the Octagon behind a public contract | The octagon is a component now, not a structure other files read. Three questions are the whole of what the page may ask - ArenaOctagon.region(svg) for where the floor landed, rankRegion(svg) for the eight rank rings, sponsorsCorner(svg) for the corner the Owner named on 2026-08-07 - and a question not on that list is one the page has no business asking. Until now the floor caption, the band reserved above it and the rank ladder each queried '.arena-cell[data-ring-kind="rank"]' inside the SVG for themselves, so three page-level functions knew that the octagon is built from cells, that a cell carries a ring kind, and what the kinds are called; renaming an attribute inside the octagon would have moved a caption in another file and nothing would have said so. Neither string appears in any of the three now. Proved identical in a real engine rather than argued: caption 350,235,416,51, ladder 935,372,148,220, octagon 305,284,659,454, the caption's and the ladder's own inline style strings, and the SVG's --arena-fit 0.5288 and --arena-shift-y -70.21px, all matching to the character before and after. The only difference anywhere on the page is that window.ArenaOctagon.region now exists. Four tests hold it. |
| **AN17** | §11 | DONE | The Rank Ladder: one source for order, identity, colour and position | Order and identity from the backend Rank model, the number from data-ring, the colour READ OFF the ring itself rather than copied, and the position only from placeRankSpine(). No CSS fallback position, no post-load jump, stable through resize. |
| **AN18** | §12 | DONE | Evidence-based dead-code audit in eight categories | Twenty-four arena assets - fifteen JavaScript modules and nine stylesheets - each classified from who names it: templates, Python, other static files, tests, and the symbols it exports. NOTHING is DEAD and nothing was deleted. The two that no caller anywhere touches are both deliberate, and no search could have told you so: arena_octant_prototype.js says in its own first line that it is an isolated geometry sandbox intentionally not loaded by production, and octagon_floor_template.js was disconnected on the Owner's instruction of 2026-07-30 that the arena share no code with the sponsors puzzle. UNKNOWN is empty - every asset resolved with evidence. Written up in docs/chef_battle/ARENA_DEAD_CODE_AUDIT.md. One finding is not code and is handed to AN22: 35 files and 3.2MB of stylesheets that no longer exist still sit in the server's staticfiles and still answer 200, because collectstatic copies and never deletes; the manifest references none of them. |
| **AN19** | §12A | DONE | Fixture and emulation code preserved - disabled is not dead | The emulation bots keep their accounts, profiles, history and their Master Console; ARENA_SHOW_EMULATION_BOTS brings them back. hydrateFixtures stays disconnected and is held in place by three tests. |
| **AN20** | §13 | DONE | JavaScript cleanup - a deliberate read phase and write phase | The observers half was already closed by AN15 and is now measured rather than claimed: arena_render.js holds ONE ResizeObserver, zero resize listeners, zero fonts.ready hooks, and its single remaining setTimeout is a 900ms ripple cleanup - nothing gates the first paint on a clock. On the read/write half: of eleven functions that touch layout in both directions, eight already measure before they write. One forced reflow was accidental and is gone - placeFloorCaption reset five inline styles on an absolutely positioned caption and then read every cell of the octagon, which no reset of an out-of-flow element can move, so the browser rebuilt the whole layout each pass to answer a question nothing had changed. Reading first is byte-for-byte identical, proved in a real engine: ladder, caption and octagon boxes, the caption's own inline style string and the SVG's --arena-fit and --arena-shift-y all match to the character. The three remaining interleaves are DELIBERATE and section 13 should not want them gone: each read depends on the write above it. You cannot measure a caption's natural width without clearing the width it was given, you cannot know whether the no-kicker variant fits without applying it and measuring, and the three-pass band reserve exists because --arena-shift-y is applied inside a rotateX(42deg) camera and arrives foreshortened. Guessing at those numbers instead of measuring them is what produced eight releases in one day for one caption. |
| **AN21** | §14 | DONE | Template cleanup | The arena templates carry markup and no CSS. Two style attributes had survived every earlier pass because both looked harmless - width:100% on the refresh gauge, position:absolute on the zero-size SVG holding the deck's icon sprite - and harmless is not the point: a declaration in a template is invisible to every tool that reads the stylesheets, appears in no cascade map, no !important audit and no superseded count, and beats all of them, because an element's own attribute outranks any rule that is not !important. Both are in arena.css now, the sprite behind a named class. The rest of section 14 was already audited and clean: no multi-line {# #} comment anywhere - the one-line Django comment that leaked eight lines of prose over the whole site's header is a lesson this file keeps - the duplicate ids are mutually exclusive branches, and no stylesheet is linked from the body. Three tests hold it, one of which refuses the next inline style attribute in any of the three arena templates. |
| **AN22** | §15 | DONE | Static asset inventory in four categories | 627 assets under static/, 117.3MB, in four categories, and not one file deleted, resized or re-encoded - section 15's own rule is that an original the company paid for is reported and never altered. REFERENCED 188 files / 53.6MB. ORIGINAL 28 / 43.9MB: a master nothing names beside the derivative everything names, categories/salads.png next to salads.webp. UNREFERENCED 411 / 19.8MB, and the breakdown is why that word is not UNUSED - 288 of them are the crowd's near/mid/far depth tiers, superseded by a decision the ring template records in writing, and the rest are old logo cuts and paid crowd faces beyond the 96 the template lists by name. One asset passes four megapixels: images/logo-social.png at 2085x2084, reported and untouched. The fourth category is the only defect: 35 files and 3.2MB of RESIDUE in the server's staticfiles for five stylesheets the repository no longer has, still answering 200, because collectstatic copies and never deletes. Not removed here - that is a production deletion outside an inventory - but the targeted, count-first command that removes exactly those and nothing else is written out in docs/chef_battle/ARENA_STATIC_INVENTORY.md. |
| **AN23** | §16 | DONE | Database and backend safety | No migration was introduced, no live battle or user data was touched, and the emulation switch was used instead of writing test data to production. |
| **AN24** | §17 | DONE | Two agents, one engineering team | Carpet message #3506 sent before any file was opened, carrying the split, the two-stylesheet target and the instruction not to build on the parked patch. GreenBear is away until Monday; both surfaces are mine, announced. |
| **AN25** | §18-20 | DONE | Commit discipline, no V2 files, no visual redesign | Eleven staged deploys, each complete and verified before the next began. No arena_v2 anything. Geometry pixel-identical to the baseline at every viewport after every stage. |
| **AN26** | §22 | PARTIAL | Final full test gate against the baseline | Green once at 1759 tests / 0 failures / 887.8s against a baseline of 1750 / 2 / 710.7s. To be re-run at the true end together with manage.py check and git diff --check. |
| **AN27** | §23 | PARTIAL | Final performance comparison, before to after | Code metrics are complete. Browser metrics are partial for the same reason as section 5E: no cold cache, no throttling, and no style-recalculation or layout timings without CDP. |
| **AN28** | §24-25 | PARTIAL | Initial-render and resize acceptance | Initial render passes on every measured viewport: 0 temporary ladder positions, 0 jumps, 0 CSS-to-JS transitions, 0 timeout hiding, CLS 0. Resize converges to the pixel. Cold cache and throttling remain unmeasured. |
| **AN29** | §26-29 | PARTIAL | The sixteen assertions, the final report, the success criteria | Thirteen of sixteen are YES with evidence. Two stylesheets is NO by the Owner's own amendment; one page-level layout authority and the removal of duplicate implementations are partial. The report is written and is to be updated at the end. |

**The Owner's rulings inside this block.**

- **2026-08-08, on the two-stylesheet target:** the Master Console mirror stays
  FLAT. It deliberately loads neither `arena_effects.css` nor
  `arena_atmosphere.css` - he asked for the mirror without the tilt and without
  the effects, to spare the operator's machine - so those two are not folded
  into the scene sheet. **His ruling decides WHERE the two files divide, not
  how many there are** - and the note that once stood here, saying the end
  state was four, was wrong for a day. There are two, since AN12:
  `arena.css` carries the shell and the octagon renderer, which is everything
  the mirror loads; `arena_atmosphere.css` carries the effects and the hall,
  which the mirror must never load. Section 8 of the master task is met, and so
  is section 26's fourth assertion.

**Rules for this block, until he says otherwise.**

0. **A finished section is written up the same working session it finishes** -
   title, status, owner, and the evidence that proves it. The Owner asked on
   2026-08-08 why completed cards were not marked and what the board was made
   for; the answer is that the board is the record, and a board that lags the
   work is the thing this project has already been bitten by (see the six days
   in section 1 of AGENTS.md).
1. An unstarted section is TO SPEC and carries nothing. No agent invents a title
   for work the Owner has not asked for.
2. Sections run in the order he gives them, one at a time, like every other card.
3. Normalisation is **invisible work**: unless a section says otherwise, the page
   must look the same after it as before, and the proof is a measurement taken
   before and after at 1170x820, 1440x900 and 1920x1080.
4. Nothing here touches `/AGENTS.md` section 8's excluded list - payments,
   payouts, migrations, schemas, access gates - without his word each time.

## 6. How to assign a card

Copy one expanded card from the build board. It is complete only when the agent
has returned:

- exact commit and changed files;
- the stated visible result;
- every acceptance statement checked;
- confirmation that every forbidden change was avoided;
- focused PostgreSQL/check/diff results and screenshot evidence when visual.

Do not assign a dependent card before its prerequisites are DONE.

## 7. Rollback

Pinned recovery tag `rollback/2026-07-28-stable-v2.5.675` resolves to
`3b4f88ad`. The former backup branch is no longer on origin; do not claim it as
rollback evidence. A board-only rollback is `git revert cb613759` followed by
the approved deploy procedure.
