# Image prompts — Traditional Irish Stew

Source recipe: `recipes/fixtures/traditional_irish_stew.json`
Purpose: a fixed set of prompts that strictly visualise *this* recipe (lamb-or-mutton with carrots, leeks, potatoes, pearl barley and herbs, layered and slow-simmered in a heavy casserole). Every shot below is to be **literally faithful** to the ingredients and method — no substitutions.

## Global style anchor (apply to every shot)

Use the same anchor in every image so the recipe's gallery stays visually coherent.

```
editorial food photography, natural daylight from a single window on the left,
soft shadow, matte rustic Irish kitchen, dark slate worktop with linen cloth,
85mm lens look, shallow depth of field, no text, no watermark, no human hands
visible unless prompt says otherwise, photoreal, true-to-recipe, ingredients
exactly as listed in Traditional Irish Stew (lamb or mutton on the bone,
pearl barley, thyme, parsley, leeks, carrots, onions, potatoes, butter, stock)
```

## Universal negative prompt (Stable Diffusion / FLUX with neg prompt support)

```
beef, chicken, pork, sausages, fish, seafood, rice, pasta, noodles, tomato,
tomato sauce, paprika, bell pepper, chilli, courgette, broccoli, peas,
cream sauce, cheese topping, gravy boat, parsley sprig garnish on top of
plate as decoration, fries, chips, bread basket, garlic visible, modern
stainless steel pan, IKEA kitchen, restaurant plating, geometric ring mould,
microgreens, edible flowers, foam, gel, smoke effects, neon, oversharpened,
HDR, fisheye, 3D render, illustration, cartoon, anime, watermark, signature,
people, hands of people, oversaturated, plastic look
```

## Shots

### 1. Hero shot — finished bowl

```
close three-quarter view of a deep cream-coloured ceramic bowl filled with
Traditional Irish Stew: chunky pieces of bone-in lamb (or mutton) on the
neck and scrag-end, surrounded by thick floury potato slices, carrot rounds,
soft leek pieces, a few translucent onions, and a scatter of plump pearl
barley grains in a thick golden-amber gravy. Tiny green flecks of fresh
thyme and chopped flat-leaf parsley on the surface. Steam rising. A wooden
spoon resting half inside. Soft natural light, dark linen napkin, beside a
torn piece of Irish soda bread on a wooden board.
aspect ratio 4:2.6 (matches site card aspect-ratio)
```

### 2. Mise en place — raw ingredients laid out

```
overhead flat-lay on a dark slate worktop showing every raw ingredient of
Traditional Irish Stew, each in its own small white bowl or directly on the
slate, neatly arranged but not aggressively styled:
- 900 g of bone-in mutton or lamb pieces (scrag end and neck), pinkish-red
  with visible bone and a marbled fat cap, raw
- a small bowl with 2 tablespoons of plain flour
- a tiny dish with salt and another with cracked black peppercorns
- 3 yellow onions, two whole and one halved
- 4 orange carrots, unpeeled, washed
- 2 leeks, white and pale green, trimmed
- 5 medium starchy potatoes (Maris Piper / Rooster type), washed
- 1 tablespoon of pearl barley in a tiny dish
- a small bunch of fresh thyme sprigs
- a small bunch of flat-leaf parsley
- a glass jug of pale amber lamb stock
- a small ramekin of melted butter
no measuring cups or spoons in the frame other than the small ones noted.
soft daylight, slight steam-free, no human hands.
aspect ratio 1:1
```

### 3. Process — layered casserole before liquid

```
overhead view, closer than mise en place, looking straight down into a
black enamelled cast-iron Dutch oven (heavy lidded casserole, well-used,
not new). Inside, the stew is being assembled in visible layers, partially
built: at the bottom a layer of browned lamb pieces, then a quarter of
sliced raw onions, sliced raw orange carrots in disks, sliced raw leeks
in white-and-green rings, a dusting of salt and black pepper, then a layer
of thickly sliced raw white potatoes; a second layer is just starting
above. A few raw pearl barley grains scattered. Sprigs of fresh thyme
visible between the layers. No liquid yet. The pan is on a worn wooden
table, a bunch of parsley and a small wooden spoon to the side.
warm side light from a single window.
aspect ratio 4:2.6
```

### 4. Process — pouring stock over the layered stew

```
side view at 30° above the rim of the same black cast-iron Dutch oven,
fully assembled with layered lamb/mutton, onions, carrots, leeks, potatoes,
pearl barley and thyme. A small white enamel jug is pouring a steady
stream of pale amber lamb stock over the top. A small ramekin of melted
butter waits beside the pan. Stove is gas, blue flame just visible at the
bottom edge. Background slightly out of focus, warm rustic.
aspect ratio 4:2.6
```

### 5. Detail — surface of the cooked stew in the pan

```
extreme close-up, 30° angle, into the cast-iron Dutch oven after 2 hours
of simmering: the lid is just lifted (lid not in frame). The stew has the
classic rustic top — bumps of soft potato, glints of orange carrot, soft
green leek pieces, dark-glazed bones and meat barely visible under a thick
amber gravy that catches the light. Tiny pearl barley grains floating.
Steam curling upward, lit from the side. Fresh thyme leaves and chopped
parsley have been scattered on top. No spoon, no hands.
aspect ratio 16:10
```

## Suggested generator settings

| Tool | Notes |
|---|---|
| FLUX.1 [dev] / [pro] | Best prompt fidelity for food. Use `cfg ≈ 3.5`, steps 28–32, 1024×768 or 1024×1024. |
| DALL-E 3 (via ChatGPT) | Excellent at "step diagram" honesty. No native negative prompt — fold the avoid-list into the positive prompt as "without ...". |
| SDXL Base + refiner | Decent baseline. Use the negative prompt above. Set `cfg 6.5`, steps 30. Add `LoRA: foodphotography` if available. |
| Midjourney v6+ | Visually strongest, weakest at strict ingredient fidelity. Append `--style raw --stylize 100` to keep it honest. |
| Adobe Firefly | Commercially safe output. Less photorealistic; good for illustrated variants. |

## Output format for the site

The site uses `RecipeImage` model — fields needed per image:
- `image` (the file)
- `alt_text` — see suggested below
- `caption` — see suggested below
- `sort_order` — 1..5 for the five shots in order above

Suggested alt/caption pairs:

| # | sort_order | alt_text | caption |
|---|---|---|---|
| 1 | 1 | Bowl of Traditional Irish Stew with lamb, root vegetables and pearl barley in golden gravy | Finished stew, served deep with soda bread and a wooden spoon |
| 2 | 2 | Raw ingredients for Traditional Irish Stew laid out on a slate worktop | Mise en place: lamb on the bone, pearl barley, leeks, carrots, onions, potatoes, herbs and stock |
| 3 | 3 | Layered raw ingredients for Irish stew inside a cast-iron Dutch oven | Building the stew: meat at the bottom, then onions, carrots, leeks, salt and pepper, potatoes |
| 4 | 4 | Pouring lamb stock over a layered Irish stew before simmering | Stock goes over the assembled layers, with melted butter to follow |
| 5 | 5 | Close-up of the cooked Irish stew surface in a cast-iron pot, garnished with thyme and parsley | After 2 hours of slow simmering: rustic top, amber gravy, herbs scattered |

## Quality gate before saving to the site

For every image, before adding it as `RecipeImage`, check:

1. Visible meat type matches the recipe (lamb/mutton **on the bone**, not boneless cubes). Reject beef-pink, chicken, fish.
2. Visible grain in the bowl/pot is **pearl barley** (small ivory pebbles), not rice (long thin grains) and not bulgur (cracked, not round).
3. Visible vegetables = onions, carrots, leeks, potatoes only. Reject any tomato, bell pepper, courgette, peas, garlic cloves, herbs other than thyme/parsley.
4. Cookware is **cast iron** or heavy enamelled casserole, never modern stainless steel.
5. No edible-flower / microgreen / foam / gel / chef-restaurant plating.
6. Hands and faces only if the brief explicitly asked for them (none of the five do).

If a generated image fails any of these, regenerate with the failed item appended to the negative prompt.
