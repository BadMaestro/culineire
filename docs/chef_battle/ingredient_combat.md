# INGREDIENT COMBAT — Battle Mechanic

## Author note
Designed by project creator. The ingredient list IS the battlefield.
Chefs fight over ingredients before and during cooking — surviving
ingredients shape the final dish each chef must submit.

---

## Pre-battle: Menu Declaration

Before the battle becomes `active`, each chef must declare their menu:

- Select the recipe they will cook (required for submission)
- Provide their ingredient list for this battle
- **Both chefs must declare the same number of ingredients**: 5 vs 5,
  6 vs 6, 7 vs 7, etc. System enforces equality before activation.
- Each chef marks exactly **2 ingredients as "locked" (key)**
  - Locked ingredients are protected during combat — hits bounce off them
  - The lock is **hidden from the opponent** (they cannot see which 2 are locked)
  - Owner sees locks as a padlock icon 🔒 on their own list

---

## During Combat: Ingredient Hits

Each combat round the attacker targets ingredients from the opponent's visible list
(no lock indicators shown):

- **Hit on unlocked ingredient** → that ingredient is **removed** from the
  opponent's active list immediately. The opponent must cook without it.
- **Hit on locked ingredient** → **blocked**. Ingredient stays. After a block,
  the attacker learns that ingredient is protected (lock is revealed for that one).

Energy cost:
| Action | Energy cost |
|--------|-------------|
| Target 1 ingredient | 1 move |
| Target 2 ingredients | 2 moves |

---

## After Battle: Winner's Penalty

Once the battle is decided by **audience vote**, the post-battle ingredient
penalty is applied:

| Role | Privilege |
|------|-----------|
| **Winner** | Gets **3 hits** — can remove/replace 3 ingredients from the loser's recipe |
| **Loser** | Gets **2 locks** — can protect 2 ingredients from the winner's hits |

### How it works:

1. The **loser** first applies their 2 locks (secret, same as during combat)
2. The **winner** then selects 3 ingredients from the loser's recipe to hit
3. System reveals locks:
   - Hits on **unlocked** ingredients → those ingredients are **banned**:
     the loser must replace them in the submitted recipe
   - Hits on **locked** ingredients → blocked, ingredient survives
4. The loser receives a notification listing which ingredients were banned
   and must update their recipe accordingly before a deadline

### Key ingredient protection rule
A chef may always lock their most essential ingredient (e.g. the egg in a
fried egg dish). The winner cannot force a dish into something unrecognizable
as long as the loser uses their locks wisely.

---

## Example flow

**GreenBear (winner 3 hits) vs CrestedTen (loser 2 locks)**

CrestedTen's recipe: egg, butter, salt, pepper, chives, herbs

CrestedTen places locks on: egg 🔒, butter 🔒

GreenBear hits: [salt, chives, pepper]
- salt → no lock → **banned**
- chives → no lock → **banned**
- pepper → no lock → **banned**

Result: CrestedTen must resubmit recipe replacing salt, chives, and pepper.
egg and butter survive (locked).

---

## Implementation notes

### Models needed
- `BattleIngredient`:
  - `battle` FK
  - `chef` FK (BattleProfile)
  - `name` CharField
  - `is_key` BooleanField (combat lock, default False)
  - `is_eliminated` BooleanField (eliminated during combat, default False)
  - `eliminated_at` DateTimeField (null)
  - `eliminated_by` FK BattleProfile (null)

- `PostBattlePenalty`:
  - `battle` FK
  - `loser_lock_1`, `loser_lock_2` — ingredient names (chosen by loser)
  - `winner_hit_1`, `winner_hit_2`, `winner_hit_3` — ingredient names (chosen by winner)
  - `banned_ingredients` — JSONField (list of actually banned ingredient names)
  - `status`: `pending_locks` → `pending_hits` → `applied`
  - `apply_deadline` DateTimeField

### Constraints
- Ingredient count must be equal on both sides before battle goes `active`
- Post-battle penalty triggered only when battle `status == completed` and
  there is a winner (not a draw)
- Loser must apply locks before winner can make hits (sequential flow)
- Deadline: loser has 48h to lock, winner has 48h after that to hit,
  loser has 72h to update recipe after ban notification

### UI flow
- Loser sees: "The battle is over. Protect 2 ingredients before [deadline]."
- Winner sees: "Choose 3 ingredients to ban from [loser]'s recipe." (after loser locks)
- Loser sees result: "[salt, chives, pepper] have been banned from your recipe. Update it by [deadline]."
