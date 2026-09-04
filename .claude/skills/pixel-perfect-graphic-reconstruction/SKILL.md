---
name: pixel-perfect-graphic-reconstruction
description: Exact implementation fidelity against a supplied reference — classifying which task was actually requested, calibrating the render pipeline, and the measurements that catch what the eye catches. Use when a result must match a reference exactly and "close" is not acceptable. Extracting pixels from a mockup is permitted only with the Owner's explicit authorisation.
---

# Exact fidelity

The Owner's operating profile (`ops/onboarding/greenbear.md`, from
`origin/main`) and `/AGENTS.md` outrank this file.

**This skill does not supersede, cancel or override any other skill.** There is
no precedence, versioning or deprecation mechanism between skill files. An
earlier version of this file claimed to supersede `graphic-reconstruction`; that
claim was false and is removed.

## Shared rules for all six design skills

- **A tool is evidence, not competence.** A lossless pipeline, a diff, a
  vectoriser and a measurement script produce facts about images. None of them
  is design ability, and none may be reported as if it were.
- **A crop of a reference is never presented as artwork you created.** An
  extracted asset is declared as extracted, every time it is delivered.
- **No skill overrides another automatically.**
- These files are not activated automatically. Open and read the one the task
  matches.

## 1. First determine which task was requested

Do this before touching an image. The four tasks have different deliverables and
only one of them permits reusing the reference's pixels.

| task | what is delivered | reference pixels | skill that leads |
|---|---|---|---|
| **Original artwork creation** | a new design, no reference to match | none exist | `graphic-design` + `svg-design` |
| **Independent reconstruction** | artwork built to match a reference | **prohibited** | `graphic-reconstruction` |
| **Authorised extraction** | assets cut from the Owner's own artwork | **only with his explicit word** | this file |
| **Frontend implementation** | a UI built from finalised assets | supplied as assets | `frontend-design` |

If the request does not say which, ask one short question. Assuming extraction
because it is faster is how a crop gets delivered as a drawing.

**Extraction is authorised only when the Owner explicitly says the original
artwork may be reused.** A mockup being available is not authorisation. The
artwork being hard to draw is not authorisation.

**Extraction is never evidence of drawing or reconstruction ability.** When
delivering extracted assets, say plainly that the pixels came from his image.

## 2. Calibrate the pipeline, and re-calibrate every session

Prove the renderer is lossless once, against a known answer:

    PNG → browser → screenshot → PNG,  max |diff| must be 0

It is, with Playwright, `scale: "css"`, an element screenshot and no device
scaling. After that, a difference you measure is real.

**Then, at the start of every measuring session:**

- Read the computed root font size out of the page and compare it with the
  reference's. This project scales type from the viewport
  (`clamp(11px, calc(0.625vw + 7px), 16px)`), so a viewport that silently
  reverted to 1920 puts the root at 16px against a reference captured at
  14.9563 — every width, inset and size derived after that is 7% wrong. This
  happened twice in one task, the second time after the rule was written down.
- Confirm the harness is serving the **current** assets. An inline override left
  in a test page served a superseded file for an entire round of conclusions.
  List the asset URLs the page actually resolved, do not assume them.
- Confirm the harness imposes nothing of its own: no forced heights, no invented
  background, no flattened layout that moves a positioned child.
- Cache-bust the stylesheet **and** every asset it references by `url()`.
  Busting the stylesheet does not bust an image inside it.

## 3. If — and only if — extraction is authorised

- **9-slice frame that changes width:** assemble the source rather than cropping
  it whole — a left cap, one stretchable middle column taken from a part
  carrying no content, a right cap.
- **Fixed ornament:** matte it off its own background — estimate the background
  from the crop's border ring, set alpha from the departure from it, un-multiply
  the colour. Verify by recompositing onto that background and diffing; under
  2/255 is achievable.
- **A rule or repeat:** a one-pixel column tiled, so even the softness of the
  line is the original's.
- **`border-image-slice: … fill` paints the middle over the padding box**, which
  begins at `border-width`. A 6px border under a 16px cap therefore lets the fill
  cover ten of the sixteen pixels of frame at every end. Make the border equal
  the slice, or do not use `fill`.
- Record, in the asset's own directory or in the commit, that these are
  extracted assets and from which file.

## 4. Measure what the eye measures — after looking, never instead of looking

`visual-qa` owns the order: look first, describe first, rank first. These are
the probes that work once that is done.

- **Count the ink gaps; do not measure the width.** For a line of type, find the
  columns with no ink inside its box. A reference "ENTER ARENA" had eight such
  gaps including a four-pixel word space; a build with the *same 72px width* and
  the *same ink bounding box* had two, because its letters were touching. Width,
  bbox and mean error all reported exact. The gaps reported what the Owner saw
  instantly.
- **Row and column means across a part**, compared line by line. A stray band 20
  units brighter than the reference is invisible in a mean and obvious here.
- **A difference image, amplified and looked at** — not reduced to a number.
  Black is a match, a doubled edge is an offset, a bright block is a defect.
- **Score regions separately.** A frame is a thin minority of the pixels and is
  outvoted by the face; the background the harness paints is not the component.
- **Include a control in every parameter sweep** — the unchanged variant.
  Without it a sweep says which setting is best, never whether any beats none.

## 5. Identify type by constraint, not by fit

Sweep candidate family, weight, size and tracking, and require **one setting to
reproduce every string at once**. A single string can be fitted by almost any
family with the right tracking, which is how a wrong weight survived several
passes here. Then check the gaps (§4).

Load each family and weight explicitly before measuring; canvas falls back
silently and returns one identical answer for every candidate. Use only weights
the project actually loads.

## 6. Geometry from edges, never from a background model

Find an object's box with the horizontal and vertical derivative and look for
the step. A constant background colour and a fitted background surface both
failed on a graded floor and selected the whole image. Test a predicate against
the reference alone first: if it cannot find the feature there, the predicate is
broken, not the build.

## 7. What is not evidence of success

Not evidence: a percentage, a passing check list, a low mean difference, a
successful command, a dimension that matches, your own impression. All of these
were produced in quantity for work that was rejected on sight.

## What went wrong, so it is not repeated

1. Measured the harness, not the component — wrong viewport, forced height,
   cached CSS, cached asset, and a stale inline override serving an old file.
2. Never opened the real page until the work was rejected.
3. Let width-matching stand in for typography twice: a larger size at zero
   tracking, then letters touching at the right width.
4. Delivered extracted crops in a context where independent construction was
   what the Owner wanted, and did not name the difference.
5. Sampled points already tuned; a difference map over the whole area would have
   shown the truth on the first day.
6. Reported percentages as progress. They were true and meant nothing.
7. Tuned until two disagreeing checks both passed — fitting the instrument.
8. Sent a comparison image without looking at it.

## Combine with

`visual-qa` for the order of the review and the harness checks.
`graphic-reconstruction` when the answer to §1 is independent construction.
`frontend-design` for implementing whatever assets result.
`graphic-design` to decide whether the result is any good.
