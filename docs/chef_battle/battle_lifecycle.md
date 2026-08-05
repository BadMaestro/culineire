# BATTLE LIFECYCLE — Full Phase Flow

## Author note
Defined by project creator. This is the canonical sequence of every Chef's Battle.

---

## Phase sequence

```
declared → accepted → menu_locked → active (combat) → ingredient_penalty
→ cooking → presentation → voting → completed
```

---

## Phase 1 — Challenge Declared (`declared`)
- Challenger issues a challenge to opponent (requires ≥10 moves)
- Theme is set (e.g. "Fried Egg")
- Opponent notified by in-site message + email

## Phase 2 — Challenge Accepted (`accepted`)
- Opponent accepts (or refuses — battle cancelled)
- Both chefs are now committed

## Phase 3 — Menu Declaration (`menu_locked`)
- Each chef declares their ingredient list for the battle
- Both lists must have equal ingredient counts (5=5, 6=6, etc.)
- Each chef marks exactly 2 ingredients as locked 🔒 (hidden from opponent)
- System enforces equality before advancing
- Once both menus are submitted → battle moves to `active`

## Phase 4 — Combat (`active`)
- Chefs take turns making combat moves (uses energy/moves)
- Each move: attacker selects 1–2 ingredients from opponent's visible list
  - Hit on unlocked ingredient → ingredient eliminated from opponent's active list
  - Hit on locked ingredient → blocked (lock revealed for that ingredient)
- Eliminated ingredients: opponent cannot use them in their dish
- Combat continues for the declared number of rounds or until energy runs out

## Phase 5 — Ingredient Penalty (`ingredient_penalty`)
- Triggered automatically when combat ends
- Applies only when there is a winner (not a draw — winner determined later,
  so this phase runs after voting; see note below*)
- **Loser** places 2 locks on their recipe ingredients (48h deadline)
- **Winner** strikes 3 ingredients from loser's recipe (48h after loser locks)
  - Locked → blocked, ingredient survives
  - Unlocked → banned, loser must replace in submitted recipe
- **Loser** updates recipe with replacements (72h deadline)

*Note: winner is determined by audience vote in Phase 7. The ingredient
penalty phase therefore runs AFTER voting completes. Sequence:
combat ends → cooking → presentation → voting → winner known →
ingredient penalty applied.

## Phase 6 — Cooking (`cooking`)
- Each chef prepares their dish using only surviving (non-eliminated) ingredients
- Two formats — chef chooses at submission:
  - **Live webcam** — streams or records themselves cooking in real time
  - **Photo series** — uploads a sequence of preparation photos step by step
- Content is submitted through the battle entry form
- Deadline: `submission_deadline` field on Battle model

## Phase 7 — Presentation (`presentation`)
- Both entries revealed simultaneously (once both are submitted or deadline passes)
- Audience sees: dish photos/video, ingredient list, battle statement
- Eliminated ingredients shown visibly so voters understand what each chef
  overcame during combat

## Phase 8 — Voting (`voting`)
- Audience votes for the better dish
- Voting open until `voting_deadline`
- One vote per user
- Winner = most votes; draw if equal

## Phase 9 — Completed (`completed`)
- Winner announced
- Winner gets +5 moves, both participants get +1 moves
- Ingredient penalty phase begins (see Phase 5)
- If this is one of the first 10 battles → marked `is_historic = True`
- Participants may qualify for Board of Memory (first 20 unique chefs)

---

## Battle model status field values

| Value | Meaning |
|-------|---------|
| `declared` | Challenge issued, awaiting response |
| `accepted` | Accepted, awaiting menu declarations |
| `menu_locked` | Menus declared, combat not yet started |
| `active` | Combat in progress |
| `ingredient_penalty` | Post-vote penalty phase |
| `cooking` | Chefs are preparing dishes |
| `presentation` | Entries revealed, pre-vote |
| `voting` | Audience voting open |
| `completed` | Battle finished, winner known |
| `cancelled` | Challenge refused or expired |

---

## Cooking format options (BattleEntry)

```python
class CookingFormat(models.TextChoices):
    WEBCAM = "webcam", "Live / Recorded Webcam"
    PHOTOS = "photos", "Photo Series"
```

Entry fields for cooking content:
- `cooking_format` — webcam or photos
- `cooking_video_url` — link to stream/recording (webcam format)
- `cooking_photos` — multi-image upload (photos format)
- `recipe` — final submitted recipe (FK)
- `battle_statement` — chef's note to the audience
