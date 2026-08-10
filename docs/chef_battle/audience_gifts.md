# AUDIENCE GIFTS — Viewers Can Gift to Chefs

## Author note
Defined by project creator.

---

## Concept

Spectators watching a live battle can send gifts to a chef of their choice
using platform tokens. Two gift categories exist:

- **Combat artifacts** — go into the chef's battle inventory, used in combat
- **Appreciation gifts** — symbolic gestures (flowers, drinks), shown as
  animated notifications in the battle chat; no combat effect

This creates real-time audience participation and a monetisation layer
tied to battle excitement.

---

## How it works

1. Viewer opens the battle page
2. Clicks **"Gift Artifact"** button next to a chef's name
3. Sees a shop panel with available artifacts (filtered by rarity tiers
   the viewer can afford)
4. Selects an artifact and pays (real money or platform credits — TBD)
5. Artifact instantly appears in the chef's combat inventory
6. A public gift notification appears in the battle chat:
   "🎁 @username gifted [Artifact Name] to Chef X!"
7. Chef can use the gifted artifact on their next combat move

---

## Payment: Platform Tokens

Gifts are paid with **CulinEire Tokens** (see `token_economy.md`).
Viewers buy token packages once via Stripe, then spend freely.

### Combat artifacts

| Rarity | Artifact price | **Delivery fee** | **Total charged** |
|--------|----------------|------------------|-------------------|
| Common | 10 tokens | 10 tokens | **20 tokens** |
| Uncommon | 25 tokens | 25 tokens | **50 tokens** |
| Rare | 60 tokens | 60 tokens | **120 tokens** |
| Epic | 150 tokens | 150 tokens | **300 tokens** |
| Legendary | 400 tokens | — | **prize only, cannot be bought** |

> **SETTLED, X13, Owner 2026-08-10: THE DELIVERY FEE IS THE RULE AND THE CODE
> IS RIGHT.** In his words: doubling is correct when the artifact is delivered
> into an OPEN battle — it is the price of the right to make a gift while the
> fight is running. `send_battle_artifact()` has charged
> `token_cost + delivery_fee` (equal amounts) all along; this document listed
> only the artifact price and never mentioned the fee, which is what made the
> two look like they disagreed. No code changed. The artifact price column is
> unchanged and still matches `Artifact.RARITY_TOKEN_COST` exactly.

### Appreciation artifacts
A separate artifact category — not combat items. These are collectible
tokens of appreciation that viewers gift to chefs. They have no combat
effect but are permanently added to the chef's profile as a display
collection (trophies from the audience).

> **SETTLED, X12, Owner 2026-08-10: THE PRICES IN THE CODE ARE THE RIGHT ONES.**
> The table below used to read 5 / 5 / 10 / 15 / 20 tokens, between 2.5 and 16
> times cheaper than what a viewer is actually charged, and it was missing the
> sixth gift entirely. `APPRECIATION_GIFT_COST` in `chef_battle/models.py` is
> the canonical source and always was. No price changed; this document is
> corrected to describe what is charged.

Canonical source: `chef_battle/models.py` → `APPRECIATION_GIFT_COST`.

| Gift | Emoji | Token cost | Creates a pending LSR |
|------|-------|------------|------------------------|
| Coffee | ☕ | 20 tokens | yes |
| Virtual Beer Toast | 🍺 | 30 tokens | yes |
| Virtual Whiskey Toast | 🥃 | 50 tokens | yes |
| Flowers | 🌷 | 80 tokens | yes |
| Celebration Cocktail | 🍸 | 80 tokens | yes |
| Virtual Champagne Bottle | 🍾 | 100 tokens | yes |

Unlike a combat artifact, an appreciation gift carries **no delivery fee** —
it is not an intervention in a running battle, so there is no right to buy.

**Key distinction from combat artifacts:**
- Do NOT go into battle inventory
- Do NOT affect combat in any way
- ARE permanently added to the chef's profile artifact showcase
- Appear as a gift notification in battle chat with donor's name
- Chef can display them on their public profile as audience appreciation

Chat notification: "💐 @username gifted Bouquet of Flowers to Chef X!"

More appreciation artifacts can be added over time (seasonal, special
events, etc.) — the category is open-ended.

## Open questions (TBD)

- **Can viewers gift to both chefs?** — probably yes, fans pick their side
- **Does the gifted artifact bypass the chef's normal inventory?** — yes,
  it's a direct add to battle inventory, not to permanent collection
- **Can a chef refuse a gift?** — probably not (drama is part of the fun)
- **Limits**: max gifts per viewer per battle? Anti-spam needed.

---

## Implementation notes (Phase 6+)

### Models
- `ArtifactGift`:
  - `battle` FK
  - `from_user` FK (viewer/donor)
  - `to_chef` FK (BattleProfile)
  - `artifact` FK (CombatItem)
  - `created_at`
  - `is_used` BooleanField

### Flow
- Gift purchase → payment confirmed → `ArtifactGift` created →
  artifact added to chef's active battle inventory →
  BattleChat notification posted automatically

### UI
- Gift button visible on battle page for all logged-in users
  (not just chefs)
- Small artifact shop panel (modal or sidebar drawer)
- Gifts shown in battle chat feed with gift icon 🎁
- Chef's combat panel shows gifted artifacts with special highlight

### Revenue
- Platform takes a cut of each gift transaction
- Gifting Legendary artifacts = higher price, higher platform revenue
- Creates incentive to make battles more spectacular (bigger audience =
  more gifts = more revenue)
