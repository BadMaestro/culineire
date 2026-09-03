---
name: visual-qa
description: Run a visual QA pass on UI against a reference or against the design system — find discrepancies, rank them by visual importance, prove each one with a measurement, and fix top-down. Use when asked to review, compare, check fidelity, or when the Owner says a result is "70%" or "not identical yet".
---

# Visual QA

`/AGENTS.md` is canonical and wins over this file. Visual QA is the agent's own
job here, not the Owner's — his operating profile put it on us (see
`ops/onboarding/greenbear.md`, read from `origin/main`).

## The shape of a pass

1. Look at it as a designer first. Name what is wrong in words.
2. **Prove the rig is honest** before calling any of it a defect.
3. Turn each impression into a number.
4. Rank by visual importance, not by ease of fixing.
5. Fix top-down, re-measuring after each.
6. Report what was fixed, what was accepted, and why.

## Step 2 is not optional

Half the "defects" in the Arena command-bar review were the harness: a viewport
5% too wide, a forced height that displaced a bracket, a cached stylesheet, a
predicate that caught a bead instead of a plate, an edge detector whose baseline
pixel sat on a graded floor. Details in `graphic-reconstruction`.

When a check fails, the question is *which of the two is wrong*. Both answers
are legitimate; neither may be assumed. Record the answer in the rig, with the
evidence, so the next pass does not re-litigate it.

**A passing check can also be an accident.** Two chamfer checks passed for a
while because an over-strong falloff was darkening the region enough to trip the
detector early. When the falloff was corrected they failed — and the correct
reading was that they had never been measuring what they claimed.

## Probes that work

- **Cross-section down a column** through a frame: prints the band order and
  every tone, and makes an off-by-one in a 1px band obvious.
- **Profile along a row** across the whole element: this is what reveals
  length-wise lighting, which a single column cannot see.
- **Longest contiguous run** for extents, never "first pixel that differs".
- **Delta against the local background**, not against a fixed value, when the
  background is graded.
- **Ink-mask correlation** for type: render every candidate family/weight across
  a sweep of size and tracking and score its ink against the reference's, pixel
  for pixel. Cap height read off a 7px antialiased raster is worth ±1px, which
  is ±14% of the size — width-and-height arithmetic cannot separate one family
  from another. Load each family/weight explicitly first; canvas falls back
  silently and will return one identical answer for every candidate.
- **A/B pixel delta** for a state change: hovering and diffing tells you how
  many pixels answer and where. 95 pixels in one corner is not feedback; 560
  across the whole frame is.

## Ranking

Rank by what the eye lands on, not by what is easy:

1. Things that change the material read of the whole object (flat vs lit).
2. Things that break a silhouette (a missing contact contour, a lost rim).
3. Wrong tone in a large area.
4. Wrong geometry in a small decorative part (a mitre at 45° that should be
   steep).
5. One- and two-pixel placement.

Fix in that order and re-measure between; later fixes are often measured against
the earlier ones.

## Accepting a difference

Some differences are correct to accept, and each needs a stated reason and a
number:

- **A trade.** Clipping a falloff to the frame cost 0.3 of a point on the plate
  and bought 0.43 on the frame — take it, and say so.
- **An alignment floor.** Pinning a composition at one x made two corner checks
  read 2px early while four text blocks landed; at the other x the corners
  landed and the text went out and the score fell. That is a resolution floor,
  not a defect.
- **A ceiling.** The reference against itself, shifted one pixel, scores 95.99%
  / 92.42%. Do not chase past the ceiling.

Record accepted differences in the checker with the evidence, at the tolerance
the evidence justifies — never silently.

## Do not invent detail to close a gap

Diagonal striations were visible on a dark face at 4×. Measured, the face varies
±3 with no directional structure: raster noise, not a brushed texture. Adding a
hatch would have been decoration dressed as fidelity.

## Related

`graphic-design` for the art-direction questions this pass cannot answer with a
number, `graphic-reconstruction` for the measurement toolkit.
