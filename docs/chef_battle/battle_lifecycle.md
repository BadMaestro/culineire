# BATTLE LIFECYCLE — Full Phase Flow

## Author note
Defined by project creator. This is the canonical sequence of every Chef's Battle.

> **THE OWNER'S STANDING RULE, 2026-08-10:** «ТЗ писалось долго и несколько раз
> переписывалось — код уточнялся по факту… поэтому я склонен больше доверять
> коду — ТЗ и правки нужно адаптировать.» Where this file and the code disagree
> about a decision, the code is the decision. Two corrections follow from it
> here, marked X15 and X17.

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
- ~~Winner gets +5 moves, both participants get +1 moves~~ — **corrected, X15,
  2026-08-10.** The winner gets **+10** (`EARN_BATTLE_WON`), participation is
  **+1** (`EARN_BATTLE_PARTICIPATION`), and second place is paid half the
  winner's share rather than nothing (`battle_rules.md`). This file was the
  last place still saying +5, contradicting `moves_economy.md`, which the
  Owner already settled against the code in X07.
- Ingredient penalty phase begins (see Phase 5)
- If this is one of the first 10 battles → marked `is_historic = True`
- Participants may qualify for Board of Memory (first 20 unique chefs)

---

## Battle model status field values

**Corrected, X17, 2026-08-10.** This list named ten statuses, two of which
(`declared`, `accepted`) are not battle statuses at all — they live on
`BattleChallenge`, because a challenge is not yet a battle. `Battle.Status`
has sixteen. The phase spine above is still right; this table is the code's.

| Value | Meaning |
|-------|---------|
| `scheduled` | Accepted, start time in the future |
| `menu_locked` | Menus being declared in the Changing Room |
| `active` | Combat in progress |
| `awaiting_submissions` | Combat done, dishes not yet in |
| `revealed` | Entries opened |
| `cooking` | Chefs are preparing dishes |
| `presentation` | Entries revealed, pre-vote |
| `voting` | Audience voting open |
| `completed` | Battle finished, winner known |
| `ingredient_penalty` | Post-vote penalty phase |
| `waiting` | Start timer expired with only one chef ready — grace period |
| `walkover` | Grace period expired; the chef who turned up takes the win |
| `void` | Neither chef turned up |
| `paused` | Emergency stop by an operator |
| `disputed` | Under moderation dispute |
| `cancelled` | Refused, expired, or withdrawn |

The two that moved: `declared` and `accepted` are `BattleChallenge.Status`
values (`pending`, `accepted`, `refused`, `expired`, `cancelled`).

---

## Cooking format options (BattleEntry) — NOT BUILT

**Open, not settled.** `CookingFormat`, `cooking_format`, `cooking_video_url`
and `cooking_photos` do not exist. What `BattleEntry` carries is a single
`cooked_photo` with `real_photo_confirmed` and a `photo_hash` for duplicate
detection, plus `recipe` and `battle_statement`. The photo-or-video choice
lives one level up, on the challenge, as `Battle.BattleType`.

This is absence, not a decision, so the standing rule does not settle it — and
`chef_levels.md`'s artifact-tier-by-format rule depends on the field that was
never added. **The Owner ruled on 2026-08-10: «этого ещё и вправду нет — будем
строить».** It is wanted, and it waits for his card.

```python
class CookingFormat(models.TextChoices):
    WEBCAM = "webcam", "Live / Recorded Webcam"
    PHOTOS = "photos", "Photo Series"
```

Entry fields for cooking content:
- ~~`cooking_format`~~ — not built; `Battle.battle_type` (photo/video) is the
  nearest thing that exists
- ~~`cooking_video_url`~~ — not built
- ~~`cooking_photos`~~ — not built; the entry carries one `cooked_photo`
- `recipe` — final submitted recipe (FK) ✔
- `battle_statement` — chef's note to the audience ✔
