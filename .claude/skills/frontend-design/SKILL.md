---
name: frontend-design
description: Turning finished visual artwork into a real production interface — component structure, asset boundaries, live typography, layout, responsive behaviour that preserves visual character, interaction states, accessibility and rendering behaviour. Use when building or changing UI in this codebase. Correct CSS is the floor, not the deliverable.
---

# Building the interface

The Owner's operating profile (`ops/onboarding/greenbear.md`, from
`origin/main`), `/AGENTS.md` and `docs/TECHNICAL_STANDARDS.md` outrank this file.

## Shared rules for all six design skills

- **A tool is evidence, not competence.** Passing tests, valid CSS, a clean
  diff and a successful deploy prove the code works. They prove nothing about
  whether the interface looks designed.
- **A crop of a reference is never presented as artwork you created.**
- **No skill overrides another automatically.**
- These files are not activated automatically. Open and read the one that
  matches the task.

## Frontend design is not CSS correctness

The deliverable is an interface that carries the design at every size, in every
state, for every user. Code that validates, matches the numbers and ships is the
minimum condition, not the goal. When the two conflict — a rule that is elegant
against a rule that preserves the design — the design wins and the reason is
written down.

## Component structure

- Decide the component's **parts** before its styles: the container, the
  decorative shell, the semantic content, the ornaments, the states.
- One element, one job. An element that is simultaneously the touch target, the
  artwork, the layout container and the text block cannot be changed later
  without breaking one of the four.
- **Separate decorative artwork from semantic content**, always:
  - artwork goes on the shell — a background, a border-image, an SVG, a
    pseudo-element — and is `aria-hidden` or has no text at all;
  - text stays real HTML so it is selectable, translatable and readable by a
    screen reader;
  - never rebuild artwork out of dozens of HTML elements, and never replace
    artwork with a CSS approximation because it is quicker.
- Keep a component's CSS gathered in one place. Do not relocate a gathered block
  as a side effect of another change.

## Asset boundaries

Decide, per element, what carries it, and write the reason down:

| carried by | when |
|---|---|
| **SVG** | defined edges, facets, emblems, anything recoloured or scaled |
| **Raster asset** | genuinely photographic or gradient-dense surfaces |
| **CSS** | layout, state, and any effect that must know the element's size |
| **HTML** | every piece of text |

Boundary rules that have cost time here:

- An SVG loaded through `border-image: url()` is a separate document; CSS custom
  properties do not reach inside it.
- A 9-slice's middle column is **stretched**, so whatever it holds is one value
  across the element. Anything that varies along the length must be a CSS layer.
- `border-image-slice: … fill` paints the middle over the **padding** box, which
  starts at `border-width`. A border narrower than the slice lets the fill cover
  the frame art at the ends.
- Static files go through `ManifestStaticFilesStorage`; the served name is
  hashed. Verify the live file, not the source file.

## Live typography

- The type in the page is not the type in the mockup: it is subject to the real
  font files, the real weights, hinting and subpixel rendering.
- **Use only weights the project actually loads.** Requesting one that is not
  loaded yields a synthesised or snapped weight that looks nearly right and
  measures wrong. Loaded here: Playfair Display 400/600/700, Inter 400/500/600,
  Libre Bodoni 400, Dancing Script 600/700.
- Set tracking and word spacing as design values and then **look at the rendered
  words**: letters must not touch, and the word space must stay visibly wider
  than the letter space at every size the component reaches.
- Type that scales with the viewport changes its own metrics; check the smallest
  and largest sizes it will actually reach, not one.

## Layout

- Grid and flex for structure; explicit placement when an element inherits a
  `grid-area` from an earlier layout.
- Size a component from its own content where the design says it should follow
  its text, and cap it where the design says it should not stretch.
- Keep artwork geometry in units that land on whole device pixels at the
  delivery size. A one-pixel band on a `rem` that resolves to 50.9 at one width
  and 51.2 at another blurs at both.

## Responsive behaviour that preserves visual character

Responsive is not proportional shrinking. Decide, per property, whether it
**scales, stays fixed, reflows, repositions, simplifies or disappears** — and
record the decision:

- **Fixed** — one- and two-pixel artwork bands, and frame thicknesses.
- **Scales** — type, icons, inner spacing, so an element follows its content.
- **Capped** — an element that fills a 1920px screen is stretched, not
  responsive. Cap the inline size and centre it; check the proportions against
  the design at that width.
- **Reflows / simplifies / disappears** — below the breakpoint, columns
  collapse, connectors and their nodes are removed rather than shrunk, and type
  goes to a pixel floor.

**The character must survive.** If the object reads as a cast plate at 1440 and
as a grey rounded box at 390, the responsive work failed even with no overflow.
Check the small sizes by looking, not only by measuring.

Set the breakpoint by measurement: add up what the layout actually needs at the
smallest root size it will see, and re-derive it when element widths change.
Test at 1920, 1440, 1280, 1024, tablet and 390, and check each for overflow,
collisions and broken connectors.

## Interaction states

- Every interactive element needs rest, hover, focus-visible, active and
  disabled, and each must be visible on its own background.
- Match the system's gesture. In this project, state changes **material**, not
  position; a two-pixel lift with a deeper shadow is the web's default and
  belongs to nothing here.
- A state change must be loud enough to read. A gesture confined to one corner
  is true to the model and useless as feedback.
- Honour `prefers-reduced-motion`.

## Accessibility

- 44px minimum touch target on every screen.
- A visible `:focus-visible` indicator that nothing clips — note that
  `clip-path` on the element clips its outline; put clipping on a pseudo-element
  instead.
- Full keyboard operation, and focus order that follows the visual order.
- Decorative artwork is `aria-hidden`; meaning never lives only in an ornament.
- Contrast checked against the artwork behind the text, not against a flat
  colour.

## Rendering behaviour

- **Painting order.** A positioned pseudo-element paints above inline content.
  If a lighting layer must not tint the label, give the label its own layer
  deliberately.
- **`mix-blend-mode` needs containment**: `isolation: isolate` on the parent, or
  a `filter`, which does it as a side effect. Removing the filter removes the
  containment.
- **Animating a custom property** requires `@property` with a `syntax`;
  unregistered, the transition snaps.
- A custom property declared on an element is not overridable from an ancestor.
- Verify in the real renderer at the real size; a viewer is not the browser.

## Traps that have cost real time here

- Blanket `color: inherit`.
- Multi-line `{# #}` comments in Django templates.
- Container queries adding no specificity.
- An element carrying `grid-area` from an earlier layout.
- `position: relative` reviving a base `left: 50%`.
- Dropping `text-transform` and reading the markup's own case.
- A hardcoded `?v=` cache-buster that clearing the cache will not bypass.
- A service worker serving yesterday's file.
- A stale inline override in a test page serving a superseded asset.
- CRLF files and regexes written with `\n`.

## Combine with

`graphic-design` for whether the built result reads as designed.
`svg-design` or `pixel-perfect-graphic-reconstruction` for where the assets came
from. `visual-qa` for the review at every viewport.
