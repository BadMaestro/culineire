---
name: svg-design
description: Author SVG assets and sprite symbols for this project — nested contours, gradients, 9-slice sources, reusable symbols. Use when creating or editing files under static/images/arena/ or the symbols in templates/chef_battle/_arena_deck_svg.html, or when a decorative element needs real vector geometry rather than a CSS approximation.
---

# Authoring SVG here

`/AGENTS.md` is canonical and wins over this file. `docs/TECHNICAL_STANDARDS.md`
governs how code is written; this file adds only what is specific to vector work.

## Where vector lives in this repo

- `templates/chef_battle/_arena_deck_svg.html` — the sprite: `<defs>` gradients
  and `<symbol>`s, referenced with `<use href="#id">`. Symbols compose other
  symbols (`#ad-medallion` uses `#ad-crown`). New work follows that pattern.
- `static/images/arena/*.svg` — standalone assets referenced from CSS, e.g. a
  9-slice `border-image-source`.

## Structure

**Declare each contour once, draw largest-first.** Four nested octagons become
four `<path>` elements in `<defs>` and six `<use>` calls; every later layer
covers the interior of the one before it, so no layer needs an even-odd ring and
no path data is written twice. Give even-odd to the one shape that genuinely
needs a hole — a light that must ride one band and stop.

**Name gradients for what they are**, not for where they sit: `g-mould`,
`g-seat`, `g-line`, `g-face`, `g-ends`, `g-lit`. The next reader needs to know
which physical surface a stop belongs to.

**Write the measurement in the comment.** Every colour in the plate SVGs is a
row of `overlay_mockup.png` with its coordinate recorded. That is what let a
later pass discover the rows had been read from the wrong column and correct all
ten of them in one edit.

## Gradients

- **`gradientUnits="userSpaceOnUse"` when stops must land on specific rows.**
  Hard stops one row apart (`0.0196` = 1/51) reproduce a cast edge; a smooth
  ramp reproduces a blend. They are different materials — do not smooth a
  stepped edge because it looks cleaner in the file.
- **Match the gradient's range to the slice that will draw it.** See
  `graphic-reconstruction` for the 9-slice arithmetic.
- **A radial falls off with distance; a linear does not.** A corner glint
  written as a 135° linear ramp still carries a quarter of its white at
  mid-height and turns a dark seat into pale grey.

## Two surfaces that get confused

A frame has a **top/foot face** and an **end wall**, and they are lit
differently. A single vertical gradient down the whole source gives the end wall
the top-to-foot ramp, so the plate goes dull from the middle down and loses its
rim. The reference's ends were the brightest gold on the object — (219,186,143)
at mid-height against a rendered (188,149,97).

Give the end walls their own horizontal layer, reaching zero by the cap.
Deleting it because a length-wise falloff arrived in CSS is a mistake that has
already been made here: the two are different claims and both hold.

## Contact contours

A chamfer needs a dark contour on the **floor side** of the cut — two pixels,
and only on the cuts, not on the straight ends, because only the corner facet
turns away from the light. Without it the corners dissolve into the background
and the silhouette reads as a clipped box.

Draw it **outside** the silhouette path, inside the corner slices, and make it
**semi-transparent rather than a colour** so it darkens whatever background it
lands on — the deck is graded.

Watch the width: a 2px band along a diagonal antialiases into three or four and
the shape then reads larger at every corner than it is. 1.4px straddling the cut
renders as one crisp pixel.

## Rules that are not style preferences

- **No `style=""` attributes.** CSP `style-src` is `'self'` plus
  fonts.googleapis.com. Presentation attributes (`fill`, `stroke`,
  `fill-opacity`) are attributes, not inline CSS, and are fine. One was already
  removed from this sprite under AN21.
- **Colour literals belong in the asset.** An SVG loaded through
  `border-image: url()` is an independent document; CSS custom properties do not
  cross into it. `TECHNICAL_STANDARDS` §7's "do not scatter raw literals" governs
  the stylesheet — in the asset the literals are the artwork, and the discipline
  is to document each one's source instead.
- **Django comment style in the sprite.** `{% comment %}` blocks, not XML
  comments, and no multi-line `{# #}`.
- **Watch line endings.** The plate SVGs are CRLF. A regex written with `\n`
  silently matches nothing, and an edit that "did nothing" looks exactly like an
  edit that did.
- **Weight counts.** `chef_battle.test_static_image_weight` scans CSS `url()`,
  so a new asset is gated. Keep assets to a few KB.

## Related

`graphic-reconstruction` for the measurement discipline, `frontend-design` for
how the asset is wired into CSS.
