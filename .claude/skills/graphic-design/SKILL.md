---
name: graphic-design
description: Art direction for CulinEire UI — judging whether something reads as intentionally designed or as assembled from generic CSS primitives, and deciding what an element earns the right to be. Use for design critique, "does this look AI-generated", material and lighting decisions, and hover/state gestures.
---

# Art direction

`/AGENTS.md` is canonical and wins over this file. The Owner's approved mockup
is the visual authority (`TECHNICAL_STANDARDS` §7); this file is about how to
serve it, not about overruling it.

## The question to ask

> If the reference image were removed, would this still look like a generic
> AI-generated web component?

Answer it honestly before reporting anything finished.

## The tells

- `border-radius` where the reference has a chamfer, a mitre, or a cut.
- `box-shadow` and `drop-shadow` used to make a flat thing look raised.
- Gradients that are "a bit lighter at the top" rather than a measured surface.
- Arbitrary gold. Every gold in the Arena is a measured token or it is wrong.
- Glassmorphism, `backdrop-filter`, blur used as atmosphere.
- Cards. Everything in a rounded box with a border and a shadow.
- Default hover: lift two pixels, deepen the shadow.
- Decoration added to raise apparent complexity.

## Invented shadows

Check whether the reference has one before adding one. Walk down from the foot
of the element and read the background: if it goes −4, 0, +3, +5, +6, +8, +9 it
is getting *lighter* — that is the page's own vignette and there is no shadow
at all. A shadow put there anyway (−25, −12, −3) is a shadow invented to make a
flat rectangle look raised, and the object in question was not raised. It was
set into the floor.

If a `filter` is removed, remember what it was silently providing: a stacking
context. `isolation: isolate` replaces that for a `mix-blend-mode` child.

## Light has a sign

A gold surface turning away from a light goes **darker and warmer**. It does not
go grey. Modelling the falloff as a neutral dark at low alpha:

- moves every band toward grey rather than into shadow;
- *lifts* a dark face instead of deepening it (55 → 88);
- and makes the edge of the object disappear where the reference has its most
  saturated gold.

Multiply instead. The factor is measurable: divide the reference's end value by
its middle value, band by band.

## States change material, not position

Look at what the system already does before choosing a gesture. In the Arena,
`.arena-live-centre` and `.arena-rank-spine__step` both answer with a change of
material; nothing moves. A two-pixel lift is the web's default and belongs to
nothing here — and a plate seated in a floor has nowhere to rise to.

Prefer moving the light the artwork already has. Then check it is loud enough
to read: measure how many pixels answer and where. A gesture confined to one
corner is true to the model and useless as feedback.

## Every element earns its place

An element is justified by the reference or by the established design system.
Nothing else counts — not "it looks a bit bare", not symmetry, not balance.
Conversely, do not simplify away something the reference does have because it is
awkward to build: the thread, the mitres, the gem and the contact contours are
all in the mockup, and each was the difference between a component and an object.

## Where the Arena's direction is fixed

Dark hall, gold accents, light parchment floor, green challenger, red opponent,
Playfair Display, Inter. Do not create a parallel visual system, and do not
treat colours from unapproved screenshots or legacy dark-Arena styles as
authority (`TECHNICAL_STANDARDS` §7).

The octagon geometry and the Arena colours are frozen; the Design Template is
what gets implemented. The 3D mockup is not buildable and the vendored prototype
was rejected — measuring against either has already cost this project a whole
matrix of work.

## Related

`visual-qa` to turn a judgement into a measurement, `graphic-reconstruction` for
material-versus-light, `frontend-design` for the implementation.
