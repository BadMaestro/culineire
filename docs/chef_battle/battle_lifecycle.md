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

**Rewritten 2026-08-15 (T11) to describe what actually runs.** This section
carried two claims that were both wrong, and the second one had the phase
order backwards.

- Triggered automatically the moment combat ends, by `_resolve_round` — the
  same write that records the Stage 1 winner and loser.
- **The two blocks were already placed, before Stage 1.** Both chefs mark
  exactly two of their declared ingredients as key in the Changing Room
  (`declare_menu`, `BattleIngredient.is_key`, `KEY_COUNT = 2`). They are
  hidden from the opponent and cannot be changed once declared.
- **Only the Stage 1 winner shoots**, exactly three times, at the loser's
  declared list:
  - a shot at one of the loser's two blocks **bounces**, the block is revealed
    by that bounce, and the ingredient survives;
  - a shot at anything else **strikes the ingredient off** the menu the loser
    will cook from.
- **The loser never shoots.** His two blocks are the whole of his defence.
- **Fifteen minutes** (`INGREDIENT_PENALTY_WINDOW`), then
  `sweep_ingredient_penalty_deadlines()` advances the battle to Cooking with
  however many shots were actually fired. A winner who walks away cannot hold
  his opponent's battle open.

**On the phase order.** This section used to say the penalty runs *after*
voting, because the winner is decided by the audience. That is not what the
code does and never was: `_resolve_round` sets `winner`/`loser` from COMBAT
when the hit cap is reached, and moves the battle straight to
`ingredient_penalty`. The audience vote later decides the BATTLE's winner and
overwrites those same two fields. The real sequence is:

```
combat ends (Stage 1 winner known) → ingredient penalty → cooking →
presentation → voting → battle winner known
```

Superseded and named so nobody restores it: there is no post-result lock
placement, no sequential 48-hour loser-lock-then-winner-hit workflow, and no
72-hour recipe-replacement step. The Owner's ruling of 2026-08-15 replaced all
three; see `ingredient_combat.md`.

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
