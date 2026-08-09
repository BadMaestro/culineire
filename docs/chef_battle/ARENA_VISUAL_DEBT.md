# Arena visual debt — deferred to the final visual/layout cleanup

**Opened by the Owner, 2026-08-09**, in the same instruction that froze the
architecture:

> Do not adjust the Octagon or surrounding Arena composition for the current
> viewport. Record the visible overflow as known visual debt for the final
> Arena visual/layout cleanup. Freeze the current architecture and continue
> with the backend/integration work.

This file exists so that the item is not lost and not silently fixed. Nothing
in it is a licence to change the composition. Every entry names what is
observed, what is already known about it from measurement, and what it must NOT
be repaired with before the cleanup card is opened.

---

## VD1 — Visible overflow at the Owner's current viewport

**Reported by:** the Product Owner, 2026-08-09, from what he sees.
**Measured by Bolt:** NOT MEASURED. His viewport is the one that shows it, and
the acceptance work of the same day was measured at 1280x800 and 1920x1080 on
the harness, where the arena fits the deck. Reporting it as measured would be
the fault `AGENTS.md` warns about: a fact is a measurement, and "I did not find
it" is not "it is not there".

**What is known from measurement, and is not in dispute:**

- The octagon's box is a tilted square under `rotateX(42deg)`. Its BOX is
  larger than its ink and its corners are transparent, so its bounding
  rectangle deliberately overlaps its neighbours' rows. This is Region Model A,
  the Owner's own decision of 2026-08-08, and it is why the octagon is allowed
  to span the writing's row and the row beneath it.
- At 1280x800 the octagon occupies y 284..738 inside a region running 235..799.
- At 1920x1080 it occupies y 306..989 inside a region running 235..1079.
- `REGION_MAX_Y = 0.95` is a ceiling, not a target: on a short screen the
  octagon is scaled down rather than allowed to leave its region. It does not
  decide the size when there is room, which means it is invisible at both
  viewports above and would be the first thing to check at his.
- The deck is exactly `100svh - var(--arena-header-h)`, and
  `--arena-header-h` is measured live rather than assumed since A18 — the fault
  it replaced was an overflow by exactly the height of the site utility bar.

**What the cleanup card must establish first:** his viewport's width and height,
and whether what overflows is the octagon's transparent box, its ink, the crowd
rail, or the deck itself. Those are four different defects with four different
owners and they must not be treated as one.

**What it must NOT be repaired with:**

- a tuned constant, or any number chosen to make one screen look right;
- a change to the camera's four accepted values — 1500px, 50% 40%,
  rotateX(42deg), 50% 62%;
- a change to the accepted composition at 1280x800, which is the product
  contract: octagon 305,284,659,454 · ladder 935,372,148,220 · caption
  350,235,416,51;
- cross-system compensation of the kind the acceptance audit removed, where one
  component measures another and moves it.

---

## VD2 — AN28 is still PARTIAL

Cold cache and CPU/network throttling on the production Arena remain unmeasured.
They need CDP against the production page, and the Arena answers 404 to
everything but staff. Recorded on the board against AN28; repeated here so the
visual cleanup card inherits it rather than rediscovering it.

---

## The frozen architecture

Frozen by the Owner on 2026-08-09 at **v2.5.958**. The chain below is not to be
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
