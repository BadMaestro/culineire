---
name: svg-design
description: Constructing original vector artwork — deliberate paths and contours, nested silhouettes, consistent corner and bevel geometry, gradients from one light source, masks, clipping, filters, reusable symbols, material rendering, controlled texture, clean scaling. Use when drawing a new decorative element, emblem, frame or icon. Emitting valid SVG is not evidence that the artwork is good.
---

# Constructing vector artwork

The Owner's operating profile (`ops/onboarding/greenbear.md`, from
`origin/main`), `/AGENTS.md` and `docs/TECHNICAL_STANDARDS.md` outrank this file.

## Shared rules for all six design skills

- **A tool is evidence, not competence.** Valid SVG, a clean XML tree, a small
  file size and a successful render prove the file works. They prove nothing
  about whether the artwork is any good. Judge it by looking (`graphic-design`).
- **A crop of a reference is never presented as artwork you created.** Pixels
  lifted from a supplied image are an extracted asset, and saying so is part of
  delivering it.
- **No skill overrides another automatically.** There is no precedence
  mechanism between these files.
- These files are not activated automatically. Open and read the one that
  matches the task.

## Decide before drawing

Come to this skill with the direction already decided by `graphic-design`:
what the object is, what it is made of, where the light comes from. Drawing
without those three produces shapes, not an object.

Write down, in one line each: **silhouette, material, light direction,
band order, level of detail.** Every path afterwards serves one of them.

## Paths and contours

- **Construct, do not sketch.** Every point has a reason: a corner of the
  silhouette, the start of a facet, a tangent. Paths with arbitrary control
  points cannot be corrected later because nothing says where they should be.
- **Declare each contour once** in `<defs>` and draw it with `<use>`. Nested
  silhouettes are the backbone of a cast object: outer edge, moulding, seat,
  engraved line, face — each a contour, drawn largest first so every later layer
  covers the interior of the one before it. No layer then needs an even-odd
  ring, and no path data is written twice.
- Reserve `fill-rule="evenodd"` for a shape that genuinely needs a hole — a
  highlight that must ride one band and stop.
- Keep coordinates on a grid you chose. Fractional coordinates are for
  deliberate half-pixel placement, never for accumulated drift.

## Corner and bevel geometry

- Corner treatment must be **one decision applied everywhere**: chamfer, round,
  mitre, or cut, at one size. Mixed corner treatments read as an accident.
- **Inset chamfers are not offset by the inset.** An inward offset of `d` on a
  45° chamfer shortens the cut by `d · (2 − √2) = 0.586 · d`. Offsetting by `d`
  makes concentric contours converge at the corners and the frame comes apart
  exactly there. Compute every inner cut.
- Anisotropic frames — thicker on the top and foot than at the ends — give every
  contour its own cut. Work them out one at a time.
- A bevel is two facets. Give each its own value; a single blended ramp reads as
  a smudge, not an edge.

## Gradients and one light source

- Every gradient in one asset answers the **same** light. A file with a highlight
  at the top-left and another at the bottom-right has no light, it has two
  accidents.
- **A radial falls off with distance; a linear does not.** A corner glint written
  as a diagonal linear ramp still carries a quarter of its value at mid-height
  and turns a dark band pale.
- Use `gradientUnits="userSpaceOnUse"` when stops must land on specific rows.
  Hard stops one unit apart reproduce a cast edge; a smooth ramp reproduces a
  blend. They are different materials — do not smooth a stepped edge because the
  file looks cleaner.
- **Name gradients for the surface**, not the position: `g-mould`, `g-seat`,
  `g-line`, `g-face`, `g-ends`, `g-lit`. The next reader needs to know which
  physical surface a stop belongs to.
- A frame has a **top/foot face** and an **end wall**, and they are lit
  differently. One vertical gradient down the whole source gives the end wall the
  top-to-foot ramp, so the object goes dull from the middle down and loses its
  rim. Give the end walls their own layer.

## Masks, clipping, filters, symbols

- `clipPath` for a hard boundary, `mask` for a soft one. Choosing the wrong one
  is why an edge is either aliased or foggy.
- Filters are expensive and change rasterisation. Prefer geometry and gradients;
  reach for `feGaussianBlur` only when the design calls for a genuinely soft
  event, and give it a bounded filter region.
- **Reusable symbols**: `<symbol>` + `<use>`, symbols composing other symbols.
  Draw a repeated part once. Give it a viewBox so it scales predictably.
- Opacity on a group is not the same as opacity on its parts: the group
  composites once, the parts composite separately and overlap.

## Material rendering

- Decide the material, then render its behaviour:
  - **Metal** — bright facing the light, abruptly dark turning away, a hard
    specular band, a warm dark rather than a grey one.
  - **Engraved line** — dark on the lit side, light on the shaded side; reversed
    at the foot of the object.
  - **Parchment / stone** — low contrast, no specular, value carried by the
    surface not the edge.
  - **Glass / enamel** — a dome highlight offset from centre toward the light,
    and a darker turn at the rim.
- **Contact contour**: a short dark band on the background side of a facet that
  turns away from the light. It separates the object from its ground and does
  more for depth than a drop shadow. Apply it only to the facets that turn away.
  Semi-transparent, so it darkens whatever ground it lands on.
- Watch the width of a diagonal band: 2px along a 45° cut antialiases into three
  or four and the object then reads larger at every corner than it is. About
  1.4px straddling the cut renders as one crisp pixel.

## Controlled texture and detail

- Detail is a budget. Spend it where the eye lands — the corners, the edge, the
  emblem — and leave the field quiet.
- Texture must be a **decision** with a stated grain and amplitude. Noise added
  "to make it less flat" reads as dirt.
- Do not add texture that a measurement shows is not in the design. Raster noise
  in a reference is not a brushed finish.
- At small sizes, remove detail rather than shrink it: two crisp bands beat five
  blurred ones.

## Clean scaling and rasterisation

- Decide the **delivery size** first and draw for it. Vector is resolution
  independent; its *appearance* is not, because hinting, antialiasing and 1px
  features are size-dependent.
- One- and two-unit bands must land on whole device pixels at the delivery size,
  or they blur. Fix the size of the artwork rather than letting it scale
  fractionally.
- Check the asset at 1× and at the sizes it will actually be used, not only
  zoomed in.
- Test the rasterised result in the real renderer, not only in a viewer.

## When SVG is the wrong medium

SVG is right for: defined edges, facets, chamfers, engraved lines, emblems,
anything that must scale or be recoloured, anything small in bytes.

SVG is **wrong** for:

- **Gradient-dense photographic surfaces.** Measured on a cast-metal plate in
  this project, an automatic vectoriser lost 66% of the distinct colours; on a
  27px emblem it destroyed the shape at every setting tried. If the artwork is
  genuinely photographic, deliver a raster asset — and say that it is one.
- **Fine noise or film grain**, which becomes thousands of paths.
- **Anything whose value comes from the exact pixels of a supplied image** —
  that is extraction, and it belongs to
  `pixel-perfect-graphic-reconstruction` under the Owner's authorisation, not
  here.

Measure before proposing a vectoriser, and measure before refusing one.

## Project constraints

- **No `style=""` attributes.** CSP `style-src` is `'self'` plus
  fonts.googleapis.com. Presentation attributes (`fill`, `stroke`,
  `fill-opacity`) are attributes, not inline CSS, and are fine.
- An SVG loaded through `border-image: url()` is an independent document; CSS
  custom properties do not cross into it. Literals inside such an asset are the
  artwork; document each one's source in a comment.
- In the sprite `templates/chef_battle/_arena_deck_svg.html` use `{% comment %}`
  blocks, never multi-line `{# #}`.
- Assets under `static/images/arena/` are gated by
  `chef_battle.test_static_image_weight`. Keep them to a few KB.
- Several files here are CRLF. A regex written with `\n` matches nothing, and an
  edit that did nothing looks exactly like an edit that did.

## Combine with

`graphic-design` before drawing, for the direction.
`graphic-reconstruction` when the drawing must reproduce a reference
independently. `frontend-design` for wiring the asset into the page.
`visual-qa` for the review of the rendered result.
