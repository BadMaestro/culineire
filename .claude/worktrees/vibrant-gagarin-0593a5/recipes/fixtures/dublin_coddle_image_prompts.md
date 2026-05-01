# Image prompts — Dublin Coddle

Source recipe: `recipes/fixtures/dublin_coddle.json`
Shared brand anchor + universal negative prompt + quality gate live in
`recipes/fixtures/IMAGE_STYLE_ANCHOR.md`. Use this file alongside that one.

Recipe-specific negative prompt to **add on top of** the universal one:

```
beef, lamb, mutton, chicken, fish, seafood, cheese topping, cream sauce,
roux, browned crust, dark brown gravy, stout, beer, wine, carrots in the
pot, peas, sweetcorn, mushrooms, garlic visible, oven dish, baked top
```

(Coddle is unmistakably a *pale* dish — the cooking liquid is a clear
sausage-and-ham broth, never a brown gravy. Most AI generators default to
"stew = brown gravy" and need active correction.)

## Shots (5)

### 1. Hero shot — bowl of finished coddle

```
overhead three-quarter view of a deep cream-coloured bowl filled with
Dublin Coddle: pale chunks of cured pink ham and pinkish-grey pork
sausages (skin on, not browned), surrounded by tender pale-yellow potato
slices and translucent soft onion pieces, in a clear pale-amber broth.
Plenty of fresh chopped flat-leaf parsley on top. A wooden spoon resting
inside. Beside it, a thick slice of buttered Irish soda bread on a
wooden board. Dark slate worktop, soft window light. Photoreal.
size: 1024 x 640
```

### 2. Mise en place — raw ingredients

```
overhead flat-lay on dark slate: 8 thick slices of pink cured ham on
parchment, 16 thin pale pink-grey raw pork sausages neatly aligned, a
small board of peeled and thickly sliced starchy white potatoes, four
peeled yellow onions roughly chopped on another board, a small bowl of
finely chopped fresh flat-leaf parsley, a saucer of salt and a peppermill.
No tomato. No carrot. Soft side daylight.
size: 1024 x 1024
```

### 3. Process — meats poaching in the pot

```
overhead view into a wide heavy stainless or enamelled saucepan on a gas
hob: pink raw ham chunks and pale pink-grey pork sausages floating in
clear water just reaching a vigorous boil. Light foam at the surface.
Steam rising. No vegetables yet. Photoreal, side daylight.
size: 1024 x 640
```

### 4. Process — layered ingredients before the broth goes back

```
overhead view straight down into the saucepan after step 2: at the bottom,
the poached ham and sausages; above them, half-built layers of pale-white
sliced potatoes, raw onion pieces, scattered chopped parsley, a pinch of
salt and pepper visible. The pan is off the heat, the reserved broth in a
glass jug to one side, ready to be poured back. No carrots, no peas. Slate
worktop, soft daylight.
size: 1024 x 640
```

### 5. Detail — close-up after the long simmer

```
extreme close-up at 30°, into the same saucepan after 65 minutes of
gentle simmering: the broth has reduced and clings to the potato slices
as a glossy pale sauce, the parsley on top has wilted just slightly into
the surface, the sausages have lost their raw pinkish-grey to a pale
fawn but are not browned, the ham edges are slightly translucent. Steam
curling upward, lit from the side. No spoon, no hands.
size: 1024 x 640
```

## Suggested alt/caption per shot

| sort_order | alt_text                                                                 | caption                                                                      |
|------------|--------------------------------------------------------------------------|------------------------------------------------------------------------------|
| 1          | Bowl of pale Dublin Coddle with pork sausages, ham, potatoes and parsley | Finished coddle, pale and brothy, served with buttered soda bread            |
| 2          | Raw ingredients for Dublin Coddle laid out on a slate worktop            | Mise en place: ham, pork sausages, potatoes, onions and parsley — no carrots |
| 3          | Pork sausages and ham poaching in water in a heavy saucepan              | Step 1: a five-minute boil to season the broth and pull out salt             |
| 4          | Layered ingredients in a saucepan before the broth is poured back        | Layering the potatoes, onions and parsley on top of the poached meats        |
| 5          | Close-up of finished coddle in the pot, broth reduced and glossy         | After an hour of gentle simmering — pale, savoury, never browned             |

## Recipe-specific quality gate (add to universal)

- Liquid is **pale clear broth**, not brown gravy. If it's brown, regenerate.
- Sausages are **pink-grey or pale fawn**, never seared brown.
- Vegetables in pot are **only potato + onion + parsley**. Reject any
  carrot, leek, celery, peas, mushrooms, garlic.
- Cookware is a regular saucepan or enamelled casserole, not a roasting tin.
