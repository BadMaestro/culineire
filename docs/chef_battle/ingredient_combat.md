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

## Stage 1 result: winner's three shots

Owner ruling, 2026-08-15: the two locks are not placed after the result. Both
chefs place exactly two hidden locks during pre-battle menu declaration. Stage 1
then determines which chef attacks.

| Role | Privilege |
|------|-----------|
| **Stage 1 winner** | Gets exactly **3 hits** against the loser's declared ingredients |
| **Stage 1 loser** | Does not shoot; defends with the **2 locks placed before the battle** |

### How it works:

1. Before Stage 1, **both chefs** secretly lock exactly 2 ingredients in their own recipe.
2. Stage 1 determines the winner; the loser cannot shoot or change their locks.
3. The **Stage 1 winner** selects exactly 3 ingredients from the loser's recipe to hit.
4. System reveals targeted locks:
   - Hits on **unlocked** ingredients → those ingredients are **banned**:
     the loser must replace them in the submitted recipe
   - Hits on **locked** ingredients → blocked, ingredient survives
5. The loser receives a notification listing which ingredients were banned
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
- Both chefs must lock exactly 2 ingredients before Stage 1 starts
- Locks are immutable once Stage 1 starts and hidden from the opponent
- Only the Stage 1 winner may make exactly 3 hits; the loser never shoots
- There is no sequential 48-hour loser-lock then winner-hit workflow
- A draw and a missed pre-battle/action deadline require explicit deterministic outcomes

### UI flow
- Both chefs see before Stage 1: "Protect exactly 2 key ingredients before [deadline]."
- Stage 1 winner sees: "Choose 3 ingredients from [loser]'s recipe to hit."
- Stage 1 loser sees no firing control and cannot alter their locks
- Loser sees result: "[salt, chives, pepper] have been banned from your recipe. Update it by [deadline]."
