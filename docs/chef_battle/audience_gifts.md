# AUDIENCE GIFTS — Viewers Can Gift Artifacts to Chefs

## Author note
Defined by project creator.

---

## Concept

Spectators watching a live battle can purchase artifacts from the in-battle
shop and gift them directly to a chef of their choice. The gifted artifact
goes into the chef's battle inventory and can be used immediately in combat.

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

| Artifact rarity | Token cost |
|----------------|------------|
| Common | 10 tokens |
| Uncommon | 25 tokens |
| Rare | 60 tokens |
| Epic | 150 tokens |
| Legendary | 400 tokens |

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
