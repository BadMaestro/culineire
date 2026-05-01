# Image prompts — Barm Brack

Source recipe: `recipes/fixtures/barm_brack.json`
Shared brand anchor + universal negative prompt + quality gate live in
`recipes/fixtures/IMAGE_STYLE_ANCHOR.md`. Use this file alongside that one.

Recipe-specific negative prompt to **add on top of** the universal one:

```
chocolate chips, frosting, icing, glaze of white sugar, cream cheese
topping, cinnamon roll, panettone shape, brioche shape, croissant,
hot cross bun cross on top, marzipan, fondant, christmas cake fondant,
American fruitcake density, dense fruitcake, dark molasses crumb,
nuts (walnuts, pecans, almonds), maraschino cherries, glace cherries
```

(Barm brack is **lighter** than English/American fruitcake — bread-like,
not dense. Most AI generators default to "fruit loaf = dense brown
fruitcake" and need active correction.)

## Shots (5)

### 1. Hero shot — sliced loaf with butter and tea

```
three-quarter view of a sliced barm brack loaf on a wooden board: tall
oval loaf with a dark golden glossy top, cut crumb showing a pale-amber
soft bread interior densely studded with sultanas, currants, and tiny
flecks of orange-yellow candied peel. Two slices have been cut, one lying
flat, smeared with cold salted butter showing little melt-pools. A
fluted china teacup of strong amber Irish breakfast tea beside it. Dark
slate worktop, soft daylight. Photoreal.
size: 1024 x 640
```

### 2. Mise en place — raw ingredients

```
overhead flat-lay on dark slate: a small white bowl of sultanas (golden
raisins), a small bowl of dark currants, a small dish of bright orange
chopped candied peel, a glass jug of warm milk with a small mound of
fresh yeast crumbled on top, a saucer of caraway seeds, a tiny dish of
ground allspice, a salt pinch dish, a measured pile of plain white flour,
a softened pat of butter on parchment, two whole eggs and one cracked
into a small glass bowl, and a small bowl of caster sugar. Soft daylight.
size: 1024 x 1024
```

### 3. Process — proofed dough showing fruit

```
overhead view straight down into a buttered ceramic mixing bowl: a soft,
domed risen yeast dough that has clearly doubled in size, smooth on top
with visible bumps where sultanas and currants press up underneath. A
linen tea towel pulled half off. Slate worktop, soft window light. No
hands in shot.
size: 1024 x 1024
```

### 4. Process — two loaves in their tins, glaze brush nearby

```
three-quarter view of two 450 g loaf tins side by side on a wooden cooling
rack, each holding a freshly baked barm brack loaf with a deeply golden,
glossy top, slight cracks on the surface where the loaf has risen. A
small saucepan of pale sugar syrup beside them with a soft pastry brush
resting on its rim. A linen napkin. Photoreal, soft daylight.
size: 1024 x 640
```

### 5. Detail — close-up of the crumb

```
extreme close-up at 30°: a single thick slice of barm brack standing
on a dark slate, showing the cut face — pale-amber soft bread crumb,
visible specks of caraway seed, dense scattered sultanas and currants,
small bright orange flecks of candied peel. The slice is generously
spread with cold salted butter, small dimples on the butter surface
catching the side light. No additional toppings.
size: 1024 x 640
```

## Suggested alt/caption per shot

| sort_order | alt_text                                                                               | caption                                                                                       |
|------------|----------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| 1          | A sliced barm brack loaf with butter and a cup of tea on a wooden board                | Sliced barm brack served the traditional way: cold salted butter and strong Irish tea         |
| 2          | Raw ingredients for barm brack laid out on a slate worktop                             | Mise en place: sultanas, currants, candied peel, warm milk and yeast, eggs, butter and spices |
| 3          | Risen yeast dough with visible fruit pressing up through the surface in a ceramic bowl | The dough after the first proof — doubled in size, fruit visible just under the skin          |
| 4          | Two freshly baked barm brack loaves cooling beside a pastry brush and sugar syrup      | Glazed straight from the oven with a brush of sugar syrup for a glossy finish                 |
| 5          | Close-up of a slice of barm brack showing crumb and dried fruit                        | The crumb close up: pale, soft, packed with sultanas, currants and candied peel               |

## Recipe-specific quality gate (add to universal)

- The loaf is a **bread**, not a dense English fruitcake. Crumb should be
  open and pale-amber, not dark and tight.
- Visible fruits are **sultanas (golden), currants (small dark), candied
  peel (bright orange)**. Reject if you see whole walnuts, pecans, almonds,
  glace cherries, or chocolate.
- Top is **glazed sugar-shiny**, not iced/frosted, no powdered sugar dust.
- Slice and butter are visible in the hero — barm brack is *meant* to be
  buttered.
- No cross on top (that's a hot cross bun, different recipe).
