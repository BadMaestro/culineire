---
name: graphic-reconstruction
description: Rebuild a raster reference (a mockup PNG, a screenshot, a supplied artwork) as production vector + CSS at measured fidelity. Use when the task says "match the reference", "100% identical", "reconstruct this component", or when a mockup image is the authority for something being built. Covers harness honesty, the chamfer offset law, what a 9-slice can and cannot carry, and separating material from light.
---

# Reconstructing a raster reference

`/AGENTS.md` is canonical. Nothing here overrides it; where this file and the
constitution differ, the constitution wins and this file is corrected in the
same task. This is agent procedure, not product doctrine — it defines no rule
about the game, the arena or the business.

## The order that works

1. **Measure the reference.** Not "look at it". Cross-sections, extents, tones.
2. **Prove the harness before trusting a single number.** See below.
3. **Author the geometry** as vector, contours computed rather than guessed.
4. **Transcribe the material** — band by band, from the right place.
5. **Add the light** as a separate layer, because it is a separate fact.
6. **Score the parts separately.** A thin feature is outvoted by a large one.

## Prove the harness first — this is where the hours go

Every "defect" found before the harness is verified may be the harness. In one
Arena task the following were all mistaken for component faults:

- **The viewport was the wrong width.** The Arena scales its root font from the
  viewport (`clamp(11px, calc(0.625vw + 7px), 16px)`). Rendering the 1273px
  mockup's component at a 1400px viewport gives a root of 15.75px against the
  mockup's 14.96 — the whole composition 5% oversized, and every width, gap and
  glyph "wrong" by that 5%.
- **The harness forced a height.** `height: 100px` on the bar moved a bracket
  that hangs off `50%` of it down by 5px. The bracket was not misplaced.
- **The harness served yesterday's CSS.** And busting the stylesheet does not
  bust an SVG referenced by `url()` inside it — that needs its own buster.
  A stale file reads exactly like a change that did nothing.
- **A predicate measured the wrong thing.** A "plate width" scan caught the
  thread's bead 4px past the chamfer, because any dark pixel counted. Use the
  longest contiguous run, not the first hit.
- **A baseline pixel was not the background.** An edge detector compared each
  row against `px[x0, y]`, and on a graded floor that pixel is not neutral.

Rule: when a check fails, the first question is *which of the two is wrong*,
and the answer gets recorded either way. Never widen a tolerance to hide a real
defect; never "fix" artwork to satisfy a broken rig.

## The chamfer offset law

An inward offset of `d` on a 45° chamfer shortens the cut by

    d · (2 − √2) = 0.586 · d

not by `d`. Offsetting by `d` makes concentric contours converge at the corners
and the frame comes apart exactly there. Compute every inner cut.

For anisotropic insets (3px top/foot, 2px at the ends, as a cast frame usually
has) each contour has its own cut and they must be worked out one at a time.

## What a 9-slice can and cannot carry

`border-image` is the right mechanism for a chamfered frame on a box whose width
changes: the corner slices keep the corners undistorted. But:

- **The middle column is stretched.** Whatever it holds is ONE value from the
  left cap to the right cap. Any lighting that varies along the length cannot
  live in the artwork — it has to be a CSS layer over the whole box.
- **Anything in the middle column with a radius larger than the cap gets
  smeared the full width.** A corner glint of radius 30 on an 18px cap paints
  18% white across the entire plate. Reach zero at the cap's own edge.
- **A gradient must be defined over the rows the slice actually draws.** If the
  fill slice is source rows 18–33 and the gradient is declared over 0–51, only
  its middle third is used and the ramp flattens to nothing.
- **Check whether the source is stretched at all.** At 18 + 15 + 18 = 51 against
  a 51px box there is no vertical stretch, and a gradient authored over the full
  height renders 1:1 — a "flat face" diagnosed at that point was reference noise.

## Material and light are different facts

The single largest fidelity failure in the Arena command bar was painting every
band of the frame one flat colour. The reference is lit: its foot line runs
(145,124,94) near one end, (194,179,157) in the middle, (169,150,127) near the
other; the top moulding's highlight runs 210 → 248 → 232.

So:

- **The artwork carries the MIDDLE value of every band** — the material.
- **A CSS layer over the whole border box carries the light** — the only part
  that has to know how wide the plate is.

And light has a sign. Gold turning away from a light gets *darker and warmer*,
not greyer. A neutral dark at low alpha moves every band toward grey and, worse,
*lifts* a dark face (55 → 88). Multiply instead: (0.91, 0.86, 0.76) is the
reference's own factor between the middle of the moulding and its end, and the
same factor takes the face 55 → 50.

Clip the falloff to the frame ring, not the whole plate. Over the whole plate it
multiplies the face too — invisible on a dark plate, a 30-unit bruise on a cream
one (239 → 205 where the reference holds 224–233). One plate hides the fault of
the other when they are scored together.

## Transcribe colours from the lit middle

Reading band tones down a column 32px from the end of a plate reads them
*inside the falloff*, and every one comes out ~20 units off. Sample where the
band is at its plateau, and let the light layer produce the falloff.

## Scoring

- Score the **frame rows separately from the face**. The frame is a thin
  minority of the pixels and is outvoted; a change that clearly improves the
  material can lower the whole-plate number while raising the frame's.
- **Always include a control** in a parameter sweep — the "no change" variant.
  Without it a sweep tells you which setting is best, never whether any of them
  beats doing nothing.
- **Know the ceiling.** The reference compared against itself shifted one pixel
  scored 95.99% (x) / 92.42% (y). A pixel score cannot reach 100% and chasing
  the last point past ~94.5% is chasing antialiasing.
- The meaningful metric is a **named-property check list** — extents, tones,
  band order, node positions — not the pixel mean.

## Sweeping parameters without a morning of round trips

Render every candidate as its own copy of the band, stacked on one page, and
screenshot once. Twenty-four browser round trips to try twenty-four numbers is
not a measurement. Two traps: custom properties set on an ancestor are shadowed
by a declaration on the element that owns them, and the strip offsets must be
read off the page rather than assumed.

## Related

`svg-design` for authoring the asset, `visual-qa` for the review pass,
`graphic-design` for whether the result reads as designed at all.
