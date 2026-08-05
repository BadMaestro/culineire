# CHEF LEVELS — Progression System

## Author note
Defined by project creator.

---

## Level structure

- Regular levels: **1 to 5** (3 wins per level)
- Top tier: **CulinEire Hero** (reached after 15 wins)
- Level stored on `ChefBattleProfile.battle_level` (integer 1–5, or "hero")

| Level | Wins required |
|-------|--------------|
| 1 | 0–2 |
| 2 | 3–5 |
| 3 | 6–8 |
| 4 | 9–11 |
| 5 | 12–14 |
| **CulinEire Hero** | **15+** |

Formula: `level = min(5, (wins // 3) + 1)` → CulinEire Hero if `wins >= 15`

---

## Matchmaking rules

**Regular levels**: maximum difference of 1 between opponents.

- Level 3 can challenge Level 2, 3, or 4
- Level 1 can challenge Level 1 or 2 only
- Level 5 can challenge Level 4 or 5 only (not CulinEire Hero)

**CulinEire Hero tier**: CulinEire Heroes can **only fight other CulinEire Heroes**.

- A CulinEire Hero cannot challenge or be challenged by Level 1–5 chefs
- If only one chef is CulinEire Hero, the challenge is blocked:
  "CulinEire Hero chefs can only battle other CulinEire Heroes."

---

## Artifact rewards by cooking format

| Cooking format | Artifact tier on win |
|----------------|----------------------|
| Photo series | Basic (Common / Uncommon) |
| Live webcam | Premium (Rare / Epic / Legendary) |

- Artifact is awarded to the **winner** at battle completion
- Format is set on `BattleEntry.cooking_format` (webcam / photos)
- If both entries use different formats, the **battle format** is determined
  by the lower tier (photos beats webcam for reward purposes — webcam only
  applies when BOTH chefs stream live)

---

## Implementation notes

### ChefBattleProfile fields to add
- `battle_level` IntegerField default=1 (computed from wins, or stored)
- `wins` IntegerField default=0 — counts toward level; **publicly visible**
- `losses` IntegerField default=0 — display only, no effect on level; **publicly visible**

### Level-up logic
- After each `completed` battle, recalculate level for both participants
- If level changes, create a BattleEvent: "Chef X reached Level Y!"

### Matchmaking enforcement
- In `challenge_create` view: check `abs(challenger_level - opponent_level) <= 1`
- If not: return error message, do not create challenge

### Artifact award
- After `completed` battle with a winner:
  - Determine `cooking_format` from winner's `BattleEntry`
  - If `webcam` → draw from Rare/Epic/Legendary artifact pool
  - If `photos` → draw from Common/Uncommon artifact pool
  - Award artifact via `ChefArtifact` (Phase 5 implementation)
