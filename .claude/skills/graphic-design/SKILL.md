---
name: graphic-design
description: Visual judgement and art direction — deciding what a design should look like and why. Composition, hierarchy, proportion, typography as design, spacing and optical alignment, colour relationships, material language, lighting, depth. Use when choosing or critiquing a visual direction, when asked whether something looks designed, or before any drawing or coding begins. Contains no code and no measurement procedure.
---

# Art direction

The Owner's operating profile (`ops/onboarding/greenbear.md`, read from
`origin/main`) and `/AGENTS.md` outrank this file. His approved reference is the
visual authority; this file is about how to serve it.

## Shared rules for all six design skills

- **A tool is evidence, not competence.** Running a vectoriser, a diff, a
  screenshot pipeline or a measurement script proves something about the image.
  It proves nothing about whether the design is good. Never present tool output
  as design ability.
- **A crop of a reference is never presented as artwork you created.** If pixels
  came out of a supplied image, say so in the same sentence in which you deliver
  it. See `graphic-reconstruction` (independent build) and
  `pixel-perfect-graphic-reconstruction` (authorised extraction) for which one
  the task actually asked for.
- **No skill overrides another automatically.** There is no precedence
  mechanism, no versioning and no deprecation between these files. When two
  apply, both apply; when they conflict, the Owner and the operating profile
  decide.
- These files are not activated automatically. Open and read the one the task
  matches.

## What this skill is for

Judging and directing the **look**. It answers what should be true of the image.
It never answers how to draw it (`svg-design`), how to build it from a reference
(`graphic-reconstruction`), how to implement it (`frontend-design`) or how to
check it (`visual-qa`).

## Composition

- Decide the **structure** before the ornament: how many zones, what governs
  their order, where the eye enters and where it comes to rest.
- A composition has a **subject**. If everything is equally emphasised there is
  no subject and the result reads as a template.
- Give the subject room. Crowding is the most common way a good idea reads as
  cheap work.
- Symmetry is a decision, not a default. Prefer it when the object is an
  emblem, a plate, a seal; avoid it when the content has a natural reading order.
- Repeated elements need a **rhythm** — equal, or deliberately unequal. Almost
  equal is the one that looks like a mistake.

## Hierarchy

- Rank every element before styling any of it: primary, secondary, supporting,
  incidental. Write the ranking down; then check the rendered result reproduces
  it when squinted at.
- Hierarchy is carried by **size, weight, colour, spacing and position** — in
  that order of strength. Reaching for colour first is what produces a rainbow.
- Two elements at the same rank compete. If both must be primary, separate them
  in space rather than making both louder.

## Proportion

- Choose proportions from a **system**, not per element: a ratio, a modular
  scale, or the reference's own measured relationships.
- The relationship between an element and its container matters more than its
  absolute size. A frame that is 6% of a plate's height reads differently at
  every scale than one fixed at 6px — decide which the design means.
- Check proportion by **ratio, not by pixels**: label height to plate height,
  ornament to field, margin to content.

## Typography as design

- Type is chosen for **voice** first: what the letterforms say about the
  product. Only then for metrics.
- Set the **hierarchy** in type before the sizes: which line is spoken, which is
  read, which is a caption.
- **Tracking is a design decision.** Display capitals usually need positive
  tracking; text sizes usually need none. Letters that touch are a defect at any
  measured width, and the word space must remain visibly wider than the letter
  space.
- Mixing families needs a reason — a serif for voice against a sans for data is
  a reason; variety is not.
- Optical size matters: the same family at 9px and at 30px is not the same
  design. Small sizes need more space and less contrast in stroke weight.

## Spacing and optical alignment

- Space is the design. Decide the spacing scale first and keep to it.
- **Optical, not mathematical.** A round shape must overshoot a flat one to look
  aligned; a triangle pointing right must sit left of centre to look centred;
  punctuation hangs outside the measure.
- Vertical rhythm: align to baselines and to the type's own body, not to the
  bounding boxes of the elements that contain it.
- Equal gaps between unequal shapes do not look equal. Balance the **visual
  mass**, not the distance.

## Colour relationships

- A palette is a set of **relationships**, not a list of colours. Decide the
  temperature, the value range and how many hues are allowed before choosing any
  swatch.
- Value does the work: a design that fails in greyscale fails. Check hierarchy
  with the colour removed.
- Accents earn their saturation by being rare. If everything is gold, nothing is.
- Colours belong to materials and light, not to elements. The "same" gold in a
  highlight and in a shadow are different values of one material.
- In this project the direction is fixed: dark hall, gold accents, light
  parchment floor, green challenger, red opponent, Playfair Display, Inter. Do
  not build a parallel visual system.

## Material language

- Name the material before rendering it: cast metal, engraved brass, parchment,
  enamel, glass, cloth. The name decides the highlight shape, the edge
  behaviour, the noise and the colour of the shadow.
- Materials must be **consistent across the composition**. Two objects in one
  scene are lit by one light and made of a stated set of materials.
- Metal has a **value inversion** at its edges — bright where it faces the light,
  abruptly dark where it turns away. Plastic and paper do not.
- Do not simulate a material you have not decided on. "Slightly shiny" is how a
  generic component happens.

## Lighting direction and consistency

- Choose one light direction for the whole composition and hold it. Every
  highlight, every bevel and every shadow obeys it.
- **Light has a sign.** A warm surface turning away from the light becomes
  *darker and warmer*, not grey. Modelling falloff as neutral black at low alpha
  greys the material and lightens dark faces — both wrong. Model it as a
  multiply.
- Light varies **along** a surface as well as across it. A frame lit from above
  is not one value from end to end.
- A cast shadow is evidence of a raised object. Verify the design intends the
  object to be raised before adding one; an object set into a surface has none.

## Depth, bevels, shadows, highlights

- Depth is built from **band order**, not from blur: outer edge, moulding, seat,
  engraved line, face. Get the order and the widths right and the object reads as
  solid without a single shadow.
- A bevel is two facets meeting: one catches light, one loses it, and the
  transition is where the eye reads the angle.
- A **contact contour** — a dark line where an object meets its background —
  does more for depth than any drop shadow, and only on the facets that turn
  away from the light.
- Highlights are shaped by the surface: a radial glint on a dome, a running line
  on a cylinder, a hard band on a chamfer.
- Prefer a small, correct set of layers to a large approximate one.

## Avoiding the generic-component look

Ask, before reporting anything finished:

> If the reference were removed, would this still look like a generic component
> anyone could produce?

The tells:

- `border-radius` where the design has a chamfer, a mitre or a cut.
- A shadow added to make something flat look raised.
- Gradients that are "a bit lighter at the top" instead of a decided surface.
- Arbitrary accent colour with no relationship to the palette.
- Glassmorphism, blur and backdrop-filter used as atmosphere.
- Everything in a rounded box with a border and a shadow.
- The default hover: lift and deepen the shadow. Look at what the system already
  does — in this project state changes **material**, not position.
- Decoration added to raise apparent complexity. Every element is justified by
  the design or the system; nothing else counts.

## Finding the highest-impact difference

When a result is wrong, rank the causes by how much of the image they change:

1. **Silhouette** — the outline of the object.
2. **Value structure** — which areas are light and dark, at a squint.
3. **Proportion and placement** of the major parts.
4. **Material and lighting** consistency.
5. **Typography** — voice, weight, spacing, word gaps.
6. **Ornament** geometry.
7. **One- and two-pixel placement.**

Fix in that order. A perfect ornament on a wrong silhouette is wasted work.

## Technical correctness is not visual quality

A result can be valid CSS, valid SVG, dimensionally exact and statistically
close, and still be bad. These are different questions:

| question | answered by |
|---|---|
| Does it run, validate, and match the numbers? | tests, `visual-qa` measurements |
| Does it look designed? | this file, by looking |

Never report the first as if it answered the second.

## Combine with

`svg-design` once the direction is decided and something must be drawn.
`visual-qa` to check a rendered result against the direction.
`frontend-design` for what the medium can carry.
