# Bolt — session handoff, 2026-08-09

Written because the Owner is moving the work to VS Code. A new session starts
with an empty scratchpad and no memory of this one, so everything that mattered
is in the repository rather than in a temporary directory.

Read `/AGENTS.md` first, as always. This file is not a substitute for the
cold-start set; it is what the cold-start set cannot tell you.

---

## 1. Where the work stands

| | |
|---|---|
| Production | **v2.5.960**, commit `23b9043e` |
| `origin/main` | ahead of production by documentation-only commits |
| Architecture Normalisation | **CLOSED**, 29/29, by the Owner on 2026-08-09 |
| Construction Board | cleaned and synchronised; four actionable cards |
| Arena architecture | **FROZEN** — do not change it |

The last commits, newest first:

- `ea021954` the performance comparison, measured on production and corrected
- `e623b79d` the closed AN project taken off the active queue, the rest synchronised
- `472c12cb` normalisation recorded as CLOSED
- `23b9043e` **the last release** — the closure pass, deployed as v2.5.960

Anything after `23b9043e` is documentation and has not been deployed. That is
deliberate: a version bump is required before shipping, not before recording.
The site's copy of the board catches up at the next release.

---

## 2. The frozen architecture

Do not change any of this without the Owner saying so in the same breath.

```
PAGE LAYOUT        .arena-command-deck__floor
                   furniture · caption region and gap · octagon region · region movement
      |
OCTAGON REGION     .arena-floor-stage          moved by translate, never resized by it
      |
OCTAGON LAYOUT     placeOctagon(svg, camera)   scales and moves the COMPLETE
OWNER                                          camera component into its region
      |
CAMERA VIEWPORT    .arena-render-container     intrinsic side 440px, scene fit 0.79308
      |
SCENE              #arena-render               perspective 1500px · origin 50% 40%
                                               rotateX(42deg) · transform-origin 50% 62%
```

Two Arena stylesheets, `arena.css` and `arena_atmosphere.css`. One camera. The
Master Console mirror is the SAME component and differs only by two values it
sets on it: `--arena-camera-tilt: 0deg`, `--arena-camera-perspective: none`.

**The accepted composition is the product contract**, at 1440x900 and 1280x800
alike. At 1280x800: octagon `305,284,659,454`, ladder `935,372,148,220`,
caption `350,235,416,51`.

Where the two camera constants come from, because they look arbitrary and are
not: the camera has exactly two intrinsic quantities, and two accepted facts pin
them — the octagon's own proportion 659x454, which every viewport side satisfies
at exactly one fit and so is a *curve*, and where the rank ring lands inside
that box, which picks the point on it. At 440px the fit is 0.79308. At 284px the
outline still matches and the ladder lands 6px wrong.

Guarded by `ArenaOwnershipGuardTests`, `ArenaCameraIsOwnedByTheOctagonTests` and
`ArenaLifecycleMechanismCountTests` in `chef_battle/tests.py`.

---

## 3. What is actually open

Four cards. Nothing else.

| Card | State | Blocked by |
|---|---|---|
| **A19** | Owner visual acceptance | nobody — it is his own act |
| **VD1** | large-desktop composition, known visual debt | A19 |
| **MC02** | the withdrawal seen live on the arena | the Owner's nine steps, still TO SPEC |
| **G01** | release gate, product evidence of contract §14 | A19, B03, R02 |

Full classification, dependency matrix and execution order:
`docs/chef_battle/ARENA_BOARD_SYNC_2026_08_09.md`.

**VD1 is not a caching problem.** That hypothesis was raised, investigated and
closed as false on 2026-08-09; the Owner has ruled it must not be attributed to
caching again. It is a real visual debt item and its first act is diagnosis: the
octagon's transparent box, its ink, the crowd rail and the deck are four
different defects and must be told apart before anything is touched.

---

## 4. The environment, and what changes in VS Code

Nothing in the toolchain depends on the editor. What does matter:

- **Paths.** The repository is `E:\CulinEire Project\CulinEire\CulinEire`, and
  the same tree is `/mnt/e/CulinEire Project/CulinEire/CulinEire` inside WSL.
- **Python.** Always `./venv/bin/python` inside WSL, never the Windows one.
  `./venv/bin/pip` does not work; use `python -m pip`.
- **Tests.** `--parallel 8` on this workstation, PostgreSQL, never on the
  server (one core). No full suite without the Owner's word.
- **Deploy.** `ssh -i ~/.ssh/culineire_linode root@80.85.84.156
  "bash /srv/culineire/scripts/deploy.sh"` from WSL. Claim
  `.agent-chat/deploy.lock` first, bump the footer version, and never run
  Django on the server as root.
- **Line endings.** The repository keeps CRLF. Read with `newline=""` and write
  the original ending back, or the diff becomes the whole file.
- **Measurement tooling.** `ops/audits/arena/tools/`, with its own README. It
  used to live in a session scratchpad and was rebuilt from scratch three times
  before it was put here.

---

## 5. Mistakes from this session, kept because they cost time

- **A grep is not a measurement unless the file was written by the command that
  claims to have written it.** A `/tmp/prev.html` from three weeks earlier was
  read as today's production HTML and reported to the Owner as a serious cache
  defect. It was not one. Check the mtime, or write to a fresh unique filename.
- **Harness numbers are not production numbers.** AN7 and AN27 were closed on
  a 1280x800 harness measurement compared against a 1440x900 production
  baseline, and described as before-and-after. They are not comparable. Section
  L of the normalisation report is the real comparison.
- **"Impossible" needs the same evidence as any other claim.** I reported twice
  that no production measurement could be taken, when
  `chef_battle:arena_preview_current` had been in the codebase the whole time.
- **A test that reads comments finds every ghost it was written to bury.** Two
  guard tests failed on prose describing what had been removed. Strip comments
  before scanning code.
- **The browser pane does not composite unless fronted**: no rAF, throttled
  timers, no screenshots, and no paint entries at all.
- **Longhand before shorthand.** `margin-top: var(...)` followed by `margin: 0`
  wipes your own input.
- **`inset: 0` resolves against the padding box**, so padding on the parent
  cannot move such a child.
- **PREPARE MEANS PREPARE.** Asked to get ready for a compact once, I started
  the next card instead.

---

## 6. Standing rules the Owner has stated in his own words

- Reply in Russian. Facts, not narration. He asked for half the words.
- Never offer a rollback as a way out.
- A reply ends the work run (`AGENTS.md` 19): work continuously, answer once.
- Do not decide for him where sources disagree — ask, and wait.
- Version parity: Bolt takes the EVEN numbers, adding two to his own last.
- `greenbear` is his own account. Untouchable, including indirectly
  (`AGENTS.md` 1a and 18). `is_staff`, `is_superuser`,
  `has_bearseeker_privileges` and `has_arena_console_access` are his to set and
  no agent writes them by any means (section 20).
