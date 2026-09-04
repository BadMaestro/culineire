---
name: graphic-reconstruction
description: Building artwork independently from a visual reference, when the deliverable must be created rather than extracted. Decompose the reference into geometry, material, light, typography and decoration, then build each. Use when the Owner supplies a mockup or a picture and wants the thing itself made. Reusing pixels from the reference is prohibited under this skill.
---

# Independent reconstruction from a reference

The Owner's operating profile (`ops/onboarding/greenbear.md`, from
`origin/main`) and `/AGENTS.md` outrank this file.

## Shared rules for all six design skills

- **A tool is evidence, not competence.** A measurement, a diff or a passing
  check proves a fact about the image. It proves nothing about whether the work
  is good.
- **A crop of a reference is never presented as artwork you created.** Under
  this skill, no pixel of the reference reaches the deliverable at all — see the
  prohibition below.
- **No skill overrides another automatically.** There is no precedence
  mechanism between these files.
- These files are not activated automatically. Open and read the one the task
  matches.

## Which task is this

Use this skill when the deliverable must be **independently created**: the
Owner supplied a picture of what he wants and expects the thing itself to be
made. If instead he authorised reuse of the original artwork, that is extraction
and belongs to `pixel-perfect-graphic-reconstruction`. If you cannot tell, ask
one question before drawing anything — the two produce different deliverables
and only one of them demonstrates that the artwork can be made.

## The prohibition

Under this skill, **the reference is a specification, not a source of pixels.**

Prohibited:

- embedding any part of the reference in the deliverable;
- cropping, slicing or matting the reference into an asset;
- auto-tracing the reference and shipping the result;
- resampling the reference into a texture, a 9-slice source, a gradient stop
  table or a data URI;
- any of the above followed by a description that implies the artwork was drawn.

Permitted, and expected:

- measuring the reference to derive geometry, tone and spacing;
- viewing it magnified to understand construction;
- naming its colours and using those values in artwork you construct;
- diffing your build against it to find errors.

The distinction to state in the delivery: a **created asset** is one whose every
path, stop and pixel was produced by construction; an **extracted asset** is one
containing pixels from the supplied image. Never let the second be mistaken for
the first.

## Decompose before building

Read the reference into five layers and write one line for each. Do not begin
drawing until all five are written.

1. **Geometry** — the silhouette and its construction: corner treatment and its
   size, the number of nested contours, the width of each band, the aspect of
   the whole. Derive these from edges, not from a guess.
2. **Material** — what each surface is made of, in words, and what that implies
   for its edge behaviour and highlight shape.
3. **Light** — one direction for the whole object; which facets face it, which
   turn away; whether the light varies along the object as well as across it;
   whether anything is cast onto the ground.
4. **Typography** — family voice, weight, size, tracking, case, the hierarchy
   between lines, and the relationship of the text block to the object.
5. **Decoration** — the discrete ornaments, their geometry, and their placement
   relative to the structure rather than to the canvas.

Then build in that order. Geometry wrong makes everything after it wasted.

## Build the artwork

- Construct with `svg-design` for vector work, with the medium chosen by what
  the material actually is.
- Where a band varies along the object, that variation is **light**, and light
  is a layer of its own — it is not baked into every band as a constant. Keep
  the material's own value in the artwork and put the falloff in a layer that
  knows the object's width.
- Model falloff as a **multiply**, not as neutral black at low alpha: a warm
  surface turning away gets darker and warmer, and neutral alpha both greys the
  material and lifts dark faces.
- Take a band's colour where it is at its **plateau**, not inside its own
  falloff. Reading a tone near the end of an object reads it already shaded.

## Render and inspect at the delivery size

- Inspect at **1× at the delivery size, on the intended background**, before any
  magnified inspection. A design is judged where it will be seen.
- Then magnify to find construction errors — but never accept a result because
  it looks right at 6×.
- Confirm the render environment reproduces the delivery conditions: the correct
  viewport, the correct scale, the current assets. `visual-qa` owns that check;
  do not skip it because the artwork is yours.

## Iterate by visual impact

Rank what is wrong by how much of the image it changes — silhouette, value
structure, proportion and placement, material and lighting, typography, ornament,
then sub-pixel placement — and fix in that order. `graphic-design` holds the
ranking; `visual-qa` holds the procedure for producing it.

Re-derive after each fix. Later corrections are measured against earlier ones,
and a change that improves the silhouette can move everything measured before it.

## Lessons this project already paid for

- **Prove the render harness before trusting a single number.** A viewport that
  silently reverted, a forced height that displaced a positioned child, a cached
  stylesheet, a cached asset, and a stale inline override that served an old file
  were each mistaken for defects in the artwork. Details in `visual-qa`.
- **A predicate must find the feature in the reference first.** A constant
  background colour and a fitted background surface both selected an entire
  graded floor. Locate objects by the derivative — an edge is a step, and a
  background does not step.
- **Measure extents by the longest contiguous run**, never by the first pixel
  that differs; a nearby ornament otherwise counts as part of the object.
- **A named-property list beats a mean.** Extents, band order, tones, node
  positions, word gaps. A mean difference is dominated by large flat areas and
  the eye is not.
- **Know the ceiling.** A reference compared against itself, shifted one pixel,
  scored 95.99%/92.42% here. A pixel score cannot reach 100%, and chasing the
  last point is chasing antialiasing rather than design.
- **Sweep parameters on one page.** Render every candidate as its own copy of the
  element, stacked, and capture once — not one browser round trip per value.
  Custom properties set on an ancestor are shadowed by a declaration on the
  element that owns them, and strip offsets must be read off the page.

## Combine with

`graphic-design` for the direction and the impact ranking.
`svg-design` for constructing the artwork.
`visual-qa` for the review procedure and harness verification.
`frontend-design` for delivering the result into the page.
`pixel-perfect-graphic-reconstruction` only if the Owner reclassifies the task
as authorised reuse of his artwork.
