# Arena visual debt

**VD1 IS CANCELLED. Owner ruling, 2026-08-16.** Told that the overflow he
reported on 2026-08-09 was still carried here awaiting his viewport size, he
answered that it is long gone and that nothing is to be done with it, and
instructed GreenBear to delete the item. VD1 is therefore not deferred, not
blocked on a measurement and not waiting on anyone: **it does not exist.**
Nothing in this file reopens it, and no future card inherits it.

**A18's two accessibility gaps are cancelled by the same ruling** — the missing
focus rings on four of the first six deck controls, and the 9.2px rank chips,
both found on production 2026-08-07 and deferred by the Owner to Stage 3 on
2026-08-10. They are struck, not carried.

What survives here is **VD2** and **the frozen architecture**, and the freeze is
why this file still exists. The Owner's instruction of 2026-08-09 that opened it
stands unchanged in that one respect:

> Freeze the current architecture and continue with the backend/integration
> work.

---

## VD2 — AN28's production observation is OWNER-ONLY VISUAL ACCEPTANCE

**Reclassified by the Owner, 2026-08-09.** AN28 is DONE as an engineering card:
the startup defect was re-tested under six load profiles and passed every one.
What remains is observation of the LIVE page, and because the Arena is
staff-gated that is his to do and not an open engineering item.

**Narrowed 2026-08-09.** The blanket claim that nothing could be measured on
production was wrong: `chef_battle:arena_preview_current` renders the real Arena
read-only behind a share token, and the full performance comparison was taken
through it - section L of the normalisation report. What is left is narrower.

Cold cache and CPU/network throttling on the production Arena remain unmeasured,
and so do first paint and FCP.
They need CDP against the production page, and the Arena answers 404 to
everything but staff. Recorded on the board against AN28.

---

## The frozen architecture

Frozen by the Owner on 2026-08-09 and CLOSED at **v2.5.960**, the completed
normalisation release. The chain below is not to be
re-opened by a visual repair:

    PAGE LAYOUT      the rows, the caption's gap, the octagon's region,
                     and the region's deliberate movement
          |
    OCTAGON REGION   a rectangle, moved by translate and never resized by it
          |
    OCTAGON LAYOUT   scales and moves the COMPLETE camera component into it
          |
    CAMERA VIEWPORT  its own intrinsic side, 440px, and its own scene fit,
                     0.79308 — both solved from the accepted composition
          |
    SCENE            perspective 1500px, origin 50% 40%, rotateX(42deg),
                     transform-origin 50% 62%

The camera knows nothing of the caption, the page furniture, the grid rows or
the page offsets, and page layout redefines none of the camera's optics. Proved
by measurement and held by `ArenaCameraIsOwnedByTheOctagonTests`.

The four accepted camera values — 1500px, 50% 40%, rotateX(42deg), 50% 62% —
and the accepted composition at 1280x800 — octagon 305,284,659,454 · ladder
935,372,148,220 · caption 350,235,416,51 — remain the product contract. VD1's
cancellation changes none of them; it removes a card, not the freeze.
