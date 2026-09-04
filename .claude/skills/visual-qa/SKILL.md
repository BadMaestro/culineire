---
name: visual-qa
description: Reviewing a rendered result — look at the whole thing first, describe what a human perceives as wrong, rank by visual impact, verify the harness is showing the current assets at the intended viewport and delivery scale, and only then measure. Use before reporting any visual work finished. Dimensions, command success and diff statistics are never proof of success.
---

# Visual QA

The Owner's operating profile (`ops/onboarding/greenbear.md`, from
`origin/main`) makes visual QA this agent's own job — the Owner is not the test
process.

## Shared rules for all six design skills

- **A tool is evidence, not competence.** A diff, a screenshot pipeline and a
  measurement script produce facts. They are not a verdict.
- **A crop of a reference is never presented as artwork you created.**
- **No skill overrides another automatically.**
- These files are not activated automatically. Open and read the one that
  matches the task.

## The order. It is not negotiable.

### 1. Look at the complete rendered result

At **1×, at the delivery size, on its real background, whole** — not a crop, not
magnified, not a statistic. Open the image and look at it yourself before
anything else and before sending it anywhere.

Twice in one task a comparison was sent without being looked at, and the defect
was obvious in it both times.

### 2. Describe what a human perceives as wrong, in words

Write plain sentences, with no numbers: *"the letters are running together",
"the frame is heavier than the reference", "there is a pale bar floating inside
the plate", "the connector reads as a broken zigzag rather than a taut thread",
"the corners dissolve into the background"*.

If nothing can be described in words, either it is right or you have not looked
long enough. A number cannot be substituted at this step.

### 3. Rank by visual impact

1. **Silhouette** — the outline of the object.
2. **Value structure** — the light and dark areas seen at a squint.
3. **Proportion and placement** of the major parts.
4. **Material and lighting** consistency.
5. **Typography** — voice, weight, spacing, word gaps.
6. **Ornament** geometry.
7. **One- and two-pixel placement.**

Fix in that order, re-looking between fixes. A perfect ornament on a wrong
silhouette is wasted work. `graphic-design` holds the reasoning behind this
ranking.

### 4. Verify the harness is showing the current assets

Before any measurement is trusted, confirm what the page actually loaded:

- List the resolved URLs of the stylesheet and every asset it references, and
  check they are the files just changed. A stale inline override in a test page
  served a superseded asset for a whole round of conclusions here.
- Cache-bust the stylesheet **and** each asset it references by `url()`; busting
  the stylesheet does not bust an image inside it.
- Confirm the harness adds nothing of its own: no forced heights, no invented
  background, no flattened layout that displaces a positioned child.

### 5. Check the intended viewport and delivery scale

- Read the computed root font size out of the page and compare it with the
  reference's or the design's.
- This project scales type from the viewport
  (`clamp(11px, calc(0.625vw + 7px), 16px)`). A viewport that silently reverted
  to 1920 put the root at 16px against a reference captured at 14.9563 and made
  every derived number 7% wrong — twice in one task, the second time after the
  rule had been written down. **Check it every session, not once.**

### 6. Only now, measure

Measurement confirms and localises what looking already found. It does not
replace it, and it never leads.

Probes that work:

- **Difference image, amplified and looked at.** Black is a match; a doubled
  edge is an offset; a bright block is a defect.
- **Count the ink gaps** for type — the columns with no ink inside the line's
  box. A build matching the reference's width and ink bounding box exactly had
  two gaps where the reference had eight, because its letters were touching.
- **Cross-section down a column** through a frame: the band order and every tone.
- **Profile along a row** across the whole element: this is what reveals
  lengthwise lighting, which a column cannot see.
- **Longest contiguous run** for extents, never the first differing pixel.
- **Delta against the local background**, not a fixed value, on a graded ground.
- **Region-by-region scores** — a frame is outvoted by a face, and the
  background the harness paints is not the component.
- **A/B delta for a state change** — how many pixels answer, and where.

**When a check fails, establish which is wrong: the build or the rig.** Record
the answer with its evidence. Never widen a tolerance to hide a defect, and
never change artwork to satisfy a broken instrument.

**A passing check can also be an accident.** Two corner checks here passed only
because an over-strong effect tripped the detector early; when the effect was
corrected they failed, and the correct reading was that they had never measured
what they claimed.

### 7. Never declare success on these alone

Not proof of success: a percentage, a passing check list, a low mean difference,
a successful command, a matching dimension, a clean deploy, your own impression.
Every one of them was produced in quantity here for work rejected on sight.

Success is: the whole thing looked at, at delivery size, and nothing describable
in words is wrong.

## Accepting a difference

Some differences are correct to accept. Each needs a stated reason and evidence:

- **A trade** — one region improves at another's measured cost; state both.
- **A resolution floor** — no single alignment satisfies two constraints at once;
  state the two.
- **A ceiling** — a reference against itself, shifted one pixel, scored
  95.99%/92.42% here; do not chase past it.

Record accepted differences in the checker with the evidence, at the tolerance
the evidence justifies — never silently.

## Do not invent detail to close a gap

Diagonal striations were visible on a dark surface at 4×; measured, that surface
varies ±3 with no directional structure. It was raster noise, not a brushed
finish, and adding a hatch would have been decoration dressed as fidelity.

## Combine with

`graphic-design` for the judgement a measurement cannot make.
`pixel-perfect-graphic-reconstruction` for the exact-fidelity probes.
`frontend-design` for reviewing across viewports and states.
