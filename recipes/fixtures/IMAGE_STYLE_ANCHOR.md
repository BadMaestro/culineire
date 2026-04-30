# CulinEire Image Style Anchor

Shared brand style for **every** recipe gallery in CulinEire. Each recipe's
`<slug>_image_prompts.md` references this file instead of repeating it.

The goal of this anchor is **visual coherence across the whole site** — five
images of one recipe should look like the same photographer shot them, and so
should the galleries of all sixty cookbook recipes when laid side-by-side on
the home page.

---

## 1. Global style anchor (prepend / blend into every positive prompt)

> editorial food photography, natural daylight from a single window on the
> left, soft shadow, matte rustic Irish kitchen, dark slate worktop with
> linen cloth, 85 mm lens look, shallow depth of field, no text, no
> watermark, photoreal

For models with a tight prompt budget (FLUX.1 Krea-Dev caps at ~70 words),
shorten to:

> editorial food photography, soft window daylight from the left, dark
> slate worktop, linen cloth, 85 mm look, photoreal, rustic Irish kitchen,
> no text, no watermark

## 2. Universal negative prompt (any model that supports it)

> rice, pasta, noodles, tomato sauce, ketchup, paprika, bell pepper, chilli,
> courgette, broccoli, peas, sweetcorn, foam, gel, microgreens, edible
> flowers, geometric ring mould, restaurant plating, modern stainless
> steel pan, IKEA kitchen, fluorescent overhead light, oversharpened, HDR,
> fisheye, 3D render, illustration, cartoon, anime, watermark, signature,
> text, oversaturated, plastic look, hands of people unless requested,
> faces unless requested

Per-recipe `_image_prompts.md` files **add** their own negatives on top of
this list — for example "beef" is forbidden in lamb stew, "cheese topping"
is forbidden in coddle, etc.

## 3. Site dimensions cheat-sheet

| Use                                                  | Aspect  | Example FLUX size          |
|------------------------------------------------------|---------|----------------------------|
| Recipe card cover (`.recipe-card__image-wrapper`)    | 4 : 2.6 | 1024 × 672 (or 1024 × 640) |
| Detail page hero (`.detail-page__header` background) | 16 : 9  | 1024 × 576                 |
| Square / Instagram tile                              | 1 : 1   | 1024 × 1024                |
| Vertical / portrait detail                           | 4 : 5   | 1024 × 1280                |

## 4. Generator settings

| Tool                                   | Notes                                                                          |
|----------------------------------------|--------------------------------------------------------------------------------|
| FLUX.1 [Krea-Dev] (Hugging Face Space) | Prompt budget ~70 words. cfg 4.5, steps 28. Best fidelity for food.            |
| FLUX.1 [Schnell]                       | Quick test draft, 4 steps, lower fidelity.                                     |
| Qwen-Image                             | Strong at on-image text (rarely needed for recipes).                           |
| DALL-E 3 (via ChatGPT)                 | No native negative prompt — fold avoid-list into the positive as "without ..." |
| SDXL Base + refiner                    | cfg 6.5, steps 30. Use the negative prompt above directly.                     |
| Midjourney v6+                         | `--style raw --stylize 100` to keep it honest.                                 |
| Adobe Firefly                          | Commercially safe but less photorealistic; better for illustrated variants.    |

## 5. Quality gate ("200% logic check") — generic template

For **every** generated image, before saving as `RecipeImage`, verify:

1. **Ingredients match the recipe.** Every visible food item is on the
   recipe's ingredients list. Reject if there are extras (a tomato in a stew
   that has no tomato, a sprig of dill in a recipe that uses parsley).
2. **No banned items from the universal negative prompt.** Especially
   common AI hallucinations: stray rice grains, modern stainless cookware,
   chef-restaurant plating, mystery green herb.
3. **Proportions look human.** A "serves 4" portion should look like a
   real domestic pan / bowl size, not a banquet platter.
4. **No text, no watermark, no signature.** Some models invent fake brand
   labels — reject and regenerate.
5. **Hands and faces only when explicitly requested.** Otherwise the
   composition is empty of people.
6. **Cookware fits the era / register of the recipe.** Cast iron, enamel,
   wooden boards, ceramic — never neon-coloured silicone or polished
   restaurant steel.

If a generated image fails any check, regenerate with the failed item
appended to the negative prompt for that shot.

## 6. File-naming convention

When images are saved into `media/recipes/<author>/<recipe>/gallery/`,
use the `sort_order` field of `RecipeImage` and these conventions:

- `img1.jpg` — hero shot (sort_order 1)
- `img2.jpg` — mise en place (sort_order 2)
- `img3.jpg` — early process step (sort_order 3)
- `img4.jpg` — late process step (sort_order 4)
- `img5.jpg` — finished detail / serving (sort_order 5)

The model already enforces this via `recipe_gallery_upload_to()` in
`recipes/models.py` — just keep the `sort_order` honest.
