# HALL OF FAME — First Battles & Pioneer Chefs

## Author note
Defined by project creator. These are permanent historical records of the
Chef's Battle launch on CulinEire.

---

## Rule 1 — First 10 Battles Enter History

The first 10 battles ever completed on the site will be permanently marked as
**"Historic Battles"** and displayed in a dedicated section on the Chef's Battle
homepage. These battles are part of the site's founding story.

**Implementation:**
- `Battle` model gets a `is_historic` boolean field (auto-set when battle pk ≤ first 10 completed)
- Or a dedicated `HistoricBattle` marker set by service when `Battle.status = completed` and fewer than 10 historic battles exist
- Historic battles shown in a special "Hall of Fame" block on `/chef-battle/`
- Marked with a special badge/icon in battle listings

---

## Rule 2 — First 20 Chefs on the Board of Memory

The first 20 chefs (RecipeAuthors) who participate in any battle (as challenger
or opponent) will have their names permanently inscribed on the **Board of Memory**.

**Implementation:**
- `ChefBattleProfile` gets a `is_founding_chef` boolean field
- Set to `True` automatically when a chef's first battle is created and fewer than 20 founding chefs exist
- A "Board of Memory" section on `/chef-battle/` or a dedicated `/chef-battle/hall-of-fame/` page
- Founding chefs get a permanent badge on their profile and battle cards
- This cannot be revoked — it is a permanent historical record

---

## Display

Both features should be visible to all visitors (not gated behind CHEF_BATTLE_ENABLED)
once at least 1 historic battle or founding chef exists.

Suggested page sections:
- Homepage block: "The Founding Ten" (first 10 battles)
- Homepage block: "The Pioneer Chefs" (first 20 chefs)
- Or a single `/chef-battle/hall-of-fame/` page combining both
