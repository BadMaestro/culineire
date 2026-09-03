---
name: frontend-design
description: Implementing Arena UI in this codebase — Django templates, vanilla JS, two stylesheets, tokens, container queries, responsive rules, and the CSS mechanisms that carry vector artwork. Use when writing or changing arena.css, arena.html or the deck templates.
---

# Implementing Arena UI here

`/AGENTS.md` is canonical and wins over this file; `docs/TECHNICAL_STANDARDS.md`
is the standard. This file records the mechanisms and traps specific to this
codebase. It is project-scoped and does not replace the general frontend-design
plugin skill.

## The stack, and what is not in it

Django templates, existing HTML/CSS and vanilla JavaScript. No React, no SCSS,
no build step, no new stylesheet — two is the number. `ManifestStaticFilesStorage`
serves static files. CSP `style-src` is `'self'` plus fonts.googleapis.com, so no
`style=""` anywhere in shipped markup.

Fonts actually loaded: Playfair Display 400/600/700, Inter 400/500/600, Libre
Bodoni 400, Dancing Script 600/700. Asking for Inter 800 or Playfair 500 gets a
synthesised or snapped weight — it will look almost right and measure wrong.

## Division of labour

- **SVG** — complex decorative geometry.
- **HTML** — semantic text and content, so it stays selectable and readable by
  a screen reader.
- **CSS** — layout, state, responsive behaviour, and any lighting that has to
  know how wide the element is.

Do not rebuild SVG geometry out of dozens of HTML elements, and do not replace
reconstructed artwork with a CSS approximation.

## Mechanisms worth knowing

**9-slice frame.** `border-image-source: url(...)` +
`border-image-slice: N fill` + `border-image-width` over a real `border-width`.
Its limits are in `graphic-reconstruction`; the short version is that the middle
column is stretched and carries one value.

**A layer over the border box.** An absolutely positioned child is bounded by
the *padding* box, so it cannot reach the border — where a moulding and an
engraved line live. Negative insets put a pseudo-element on the border box:

    inset: calc(-1 * var(--cmd-frame-y)) calc(-1 * var(--cmd-frame-x));

**Clip a pseudo-element, never the element.** `clip-path` on the element itself
cuts its border-image and its label with it, and clips the focus outline. Hold
the shape in a custom property and apply it to `::before`/`::after`:

    .thing { --ring: polygon(evenodd, <outer>, <inner>); }
    .thing::after { clip-path: var(--ring); }

Derive the inner contour from the same numbers the artwork draws, so the two
cannot drift apart.

**`mix-blend-mode` needs containment.** Give the parent `isolation: isolate` (or
a `filter`, which does it as a side effect) or the blend reaches the page behind
it. If you remove a `filter`, add the isolation explicitly.

**Animating a custom property** requires `@property` with a `syntax`; an
unregistered property is a token to the animation engine and the transition
snaps instead of easing.

**Painting order.** A positioned pseudo-element paints above inline content. If
a lighting layer should not tint the label and the icon, give those
`position: relative; z-index: 1` — deliberately, with the reason written down.

## Tokens

Colours derived from the approved mockup are **named tokens**, not literals in a
gradient (`TECHNICAL_STANDARDS` §7). Component tokens live on the component's
own root element. Put the measurement in the comment — the coordinate it was
read from — so a later pass can check it rather than re-guess it.

Note that a custom property declared on an element is **not** overridable from
an ancestor. Setting it on a wrapper to sweep values silently does nothing.

## Responsive is not proportional shrinking

Decide, per property, whether it scales, stays fixed, reflows, repositions or
disappears:

- **Fixed** — one- and two-pixel artwork bands. A plate height on a rem that
  resolves to 50.9 at one width and 51.2 at another puts a moulding edge on a
  half pixel and blurs it.
- **Scales** — type, icons, inner padding, so an element follows its own text.
- **Capped** — a bar that fills 1920px is not responsive, it is stretched. Cap
  the inline size and centre it; measure the result against the reference's own
  proportions (a connector 73px in the mockup was 489px before the cap).
- **Reflows / disappears** — at the stack breakpoint, columns collapse,
  connectors and their nodes go, and type switches to a **pixel floor** rather
  than continuing to shrink.

Set the breakpoint by measurement, not by convention: add up what the three
columns actually need at the smallest root size they will see. Use the Arena's
container query (`@container arena-command-area`), and re-derive the number when
element widths change.

Test at 1920, 1440, 1280, 1024, tablet and 390, and check for overflow,
collisions and broken connectors at each — not one screenshot size
(`TECHNICAL_STANDARDS` §6).

## Accessibility is not negotiable

44px minimum target on every screen, visible `:focus-visible` ring that nothing
clips, keyboard operation, `prefers-reduced-motion` honoured. A hover gesture
that changes only material still needs its focus ring.

## Traps that have cost real time here

- Blanket `color: inherit`.
- Multi-line `{# #}` comments in templates.
- Custom properties resolved where they are declared, not where they are used.
- Container queries adding no specificity.
- A caption carrying `grid-area` from an earlier layout, landing in row 2.
- `position: relative` reviving a base `left: 50%`.
- Dropping `text-transform: uppercase` and reading the markup's own case.
- `arena_render.js`'s `?v=` cache-buster is hardcoded — bump the string;
  clearing caches will not do it.
- A service worker serving yesterday's file.
- CRLF files and regexes written with `\n`.

## Related

`svg-design` for the asset, `visual-qa` for the review, `graphic-design` for
whether the result reads as designed.
