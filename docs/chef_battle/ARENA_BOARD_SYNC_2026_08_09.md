# Construction Board — cleanup and dependency synchronisation

**Ordered by the Owner, 2026-08-09**, immediately after Architecture
Normalisation closed at production v2.5.960. Documentation only: no Arena code,
no template, no backend, no database, no deployment.

Its purpose is narrow and worth stating, because it is not a code task and can
be mistaken for one: **every remaining card must assume the architecture that
now actually exists.** A board that still hands out `arena_deck_polish.css` as
the place the camera lives is not merely out of date — it is an instruction to
rebuild the thing the last three weeks removed.

---

## 1. The architecture every card now assumes

```
PAGE LAYOUT        .arena-command-deck__floor
      |            furniture · caption region and gap · octagon region · region movement
OCTAGON REGION     .arena-floor-stage
      |
OCTAGON LAYOUT     placeOctagon(svg, camera)
OWNER              |            scales and moves the COMPLETE camera component
CAMERA VIEWPORT    .arena-render-container      intrinsic side 440px, fit 0.79308
      |
SCENE              #arena-render                1500px · 50% 40% · rotateX(42deg) · 50% 62%
```

Two Arena stylesheets. One camera. The Master Console mirror is the same
component and differs only by configuration values.

**These are facts a card adapts to. They do not adapt to a card.**

---

## 2. Board before

| | |
|---|---|
| Rows in the dispatch queue | 38 |
| Of those, finished or deleted | 34 |
| Actionable | 4 — A19, VD1, MC02, G01 |
| Architecture Normalisation cards on the active board | 29 |
| Total rows a reader had to walk to find four pieces of work | 67 |

## 3. What the AN cleanup did

The twenty-nine cards left the active board as ONE closure line. Nothing was
destroyed:

| Preserved | Where |
|---|---|
| The 29 cards with their per-card evidence, verbatim | `ARENA_NORMALISATION_CARDS_ARCHIVE.md` |
| Closure declaration, before/after metrics, engineering evidence | `ARENA_NORMALISATION_REPORT.md` (sections A–K) |
| Final full-suite output | `ARENA_NORMALISATION_FINAL_SUITE.txt` |
| Releases and commits, v2.5.900 → v2.5.960 | `config/release_journal.py` |
| The frozen architecture and what may not be used to change it | `ARENA_VISUAL_DEBT.md` |

No `ARCHIVED` rows were created on the active board. The site board renders one
closure card in place of the 29-cell grid.

---

## 4. Dependency matrix — every remaining active card

### A19 — Owner visual acceptance, Arena Hall

| | |
|---|---|
| Product purpose | The Owner accepts the Arena Hall visually. |
| Classification | **A — INDEPENDENT** |
| Architecture dependency | none — nothing to implement |
| Stale references | none |
| Required update | dependency line only: `A18` → *architecture prerequisite satisfied* |
| Blocked by | nothing; it is his own act |
| Blocks | VD1, G01 |
| Status after sync | PENDING — WAITING FOR OWNER |

### VD1 — Final Arena visual/layout cleanup

| | |
|---|---|
| Product purpose | The large-desktop composition the Owner sees. UNCHANGED. |
| Classification | **C — NEEDS SYNCHRONISATION** |
| Architecture dependency | `PAGE_LAYOUT`, `OCTAGON_REGION` |
| Stale references | none in the card text; the risk was the board's cascade note, now replaced |
| Required update | implementation path stated: macro composition through PAGE LAYOUT; move the octagon by moving its REGION through `--arena-octagon-offset-y`, which translates and never resizes |
| Forbidden, written into the card | editing camera optics for page composition · changing accepted octagon internal geometry · a third stylesheet · restoring any deleted compensation · a constant chosen to make one screen look right |
| Blocked by | A19 |
| Blocks | G01 |
| Status after sync | OPEN — known visual debt, deliberately unfixed |

The card also carries the thing that must happen *first* and is not a fix: the
four candidate defects — the octagon's transparent box, its ink, the crowd rail,
the deck — have four different owners and must be told apart before anything is
touched.

### MC02 — The withdrawal seen LIVE on the arena

| | |
|---|---|
| Product purpose | Each step of a withdrawal shown by ACTION on the arena, driven by the existing `emulation.py` through the real services. UNCHANGED. |
| Classification | **C — NEEDS SYNCHRONISATION** |
| Architecture dependency | `SCENE`, `READINESS` |
| Stale references | none by name; the standing risk is a second camera for the console |
| Required update | the console mirror is the SAME camera component and may differ ONLY by the values it sets on it (`--arena-camera-tilt`, `--arena-camera-perspective`); no independent camera CSS, no independent scene geometry, no duplicate octagon; scene overlays belong to the REGION, because the viewport carries the placement scale |
| Blocked by | the Owner's steps — most rows in `ARENA_EMULATION_VISUAL_STEPS.md` are TO SPEC |
| Blocks | nothing |
| Status after sync | OPEN — awaiting the Owner's steps |

### G01 — Release gate

| | |
|---|---|
| Product purpose | Complete Design Arena regression and production evidence. UNCHANGED. |
| Classification | **D — PARTIALLY SUPERSEDED** |
| Architecture dependency | none directly; it consumes the others' results |
| Stale references | none |
| Required update | the engineering half is satisfied — the final gate is green on the shipped candidate, 1799 tests, 0 failures, 2 skipped, PostgreSQL. What remains is the PRODUCT evidence of §14 of the contract: access policy, state and action parity, vote and reveal integrity, moderation, migration readiness, console compatibility, feature flags, legal gates, rollback. |
| Blocked by | A19, B03, R02 |
| Blocks | public release |
| Status after sync | PENDING |

### The 34 finished rows (A00–A18, AR1–AR5, SA-A2/A4/A6, B01–B03, R01–R02, MC01)

| | |
|---|---|
| Classification | **A — INDEPENDENT** (historical) |
| Required update | none — they are the record of what shipped, not work |

---

## 5. Classification totals

| Class | Count | Cards |
|---|---|---|
| A — Independent | 35 | A19 and the 34 historical rows |
| B — Compatible | 0 | — |
| C — Needs synchronisation | 2 | VD1, MC02 |
| D — Partially superseded | 1 | G01 |
| E — Fully superseded | 0 | — |
| F — Conflicts with the frozen architecture | 0 | — |
| Needs Owner clarification | 1 | MC02's nine steps, most of them TO SPEC |

No card conflicts with the frozen architecture, and none was fully superseded by
it. That is worth recording rather than glossing: the normalisation removed
implementations, not product requirements, so no product intent died with them.

---

## 6. Second pass — cross-card checks

| Check | Result |
|---|---|
| A card depends on a card that was superseded | none — nothing was superseded |
| A card expects old CSS another card now owns | none after the cascade note was replaced |
| Two cards planning the same new component | none — VD1 is composition, MC02 is choreography |
| Two cards proposing different owners for one layout area | none — PAGE LAYOUT owns page composition, and both cards now say so |
| A card scheduled before its prerequisite | none |
| Order changed by the normalisation being done | yes: every `blocked_by: ANxx` relationship is gone |
| Duplicate active cards solving the same problem | none |

---

## 7. Execution order after synchronisation

Order, not a schedule, and not to be executed:

1. **A19** — the Owner's visual acceptance. Nothing to implement; it gates the
   two below.
2. **VD1** — the visual/layout cleanup, once he has accepted or named what he
   wants changed. Its first act is diagnosis, not repair.
3. **MC02** — once his steps exist. Independent of VD1 and could run in
   parallel if he assigns both, since one touches page composition and the other
   touches choreography over the scene.
4. **G01** — the release gate, after A19, B03 and R02, on the product evidence
   of §14.

Outside the queue, as maintenance debt with no card: the 35 files and 3.2MB of
staticfiles residue, with its count-first removal command already written out in
`ARENA_STATIC_INVENTORY.md`.

---

## 8. Owner decisions needed

1. **MC02's nine visual steps.** Most rows in
   `docs/chef_battle/ARENA_EMULATION_VISUAL_STEPS.md` are marked TO SPEC. What
   is ambiguous is precisely what he must SEE at each step — not how it is
   built. That is product intent, and inferring it to make the board tidy is
   the one thing this pass may not do.
2. **VD1's viewport.** The overflow is on his screen. Its width and height, and
   which of the four candidates is actually overflowing, are facts only he can
   supply; everything measured here fits.

Nothing else on the board is ambiguous.

---

## 9. What this pass did not touch

Arena CSS, Arena JS, Arena templates, backend product code, the database,
production behaviour. Production stays at v2.5.960. No deployment: the site's
copy of the board picks this up at the next release, and until then the
markdown board — which `AGENTS.md` section 1 names as the board — is correct.
