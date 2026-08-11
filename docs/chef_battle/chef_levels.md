# CHEF LEVELS — Progression System

## Author note
Defined by project creator.

> **THE OWNER'S STANDING RULE, 2026-08-10, in his own words:** «ТЗ писалось
> долго и несколько раз переписывалось — код уточнялся по факту и уточняющие
> вопросы задавались по факту — поэтому я склонен больше доверять коду — ТЗ и
> правки нужно адаптировать.»
>
> So where this file and the code disagree about a DECISION, the code is the
> decision and this file is adapted to it. That does not cover a rule the code
> never implemented at all: absence is not a decision, and those stay open
> questions for him. Both kinds are marked below.

---

## What actually runs: RANKS, not levels

**SETTLED — X09/X10, Owner 2026-08-05, and the standing rule above.** This file
describes five numbered levels plus a Hero tier on a `battle_level` field. None
of that exists. What ships is **eight named ranks** on
`ChefBattleProfile.Rank`, earned by WINS through `RANK_THRESHOLDS` /
`rank_for_wins()`, from Kitchen Porter to Culinary Master, and matchmaking is
limited to the same or an adjacent RANK by `check_rank_matchup()`. There is no
`battle_level` field and never was.

The level table below is kept as history, because it explains where the
thresholds came from. It is not the current spec.

---

## Level structure — HISTORICAL

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

**THERE IS NO HERO TIER — Owner, 2026-08-10: «у нас нет понятия Герой».**

This was buried by his own X09 ruling of 2026-08-05, and the board records it in
those words: *"The documented CulinEire Hero tier is buried with this — rank
does the progression and `is_hero` has meant the Owner's own account since it
was written."* Progression is eight ranks earned by wins; nothing is reached
"after 15 wins" and nothing is a tier above Culinary Master.

`is_hero` is **not** that tier. It is the Owner's own flag, set in exactly one
place — `get_or_create_battle_profile()`, only when the slug is `OWNER_SLUG` —
and true on exactly one account in production: `greenbear`. The branch in
`check_rank_matchup()` that skips the rank window when `is_hero` is set is
therefore not a game rule about heroes; it is the Owner standing outside the
matchmaking limit, which belongs with AGENTS.md §18 and not with progression.

- ~~A CulinEire Hero cannot challenge or be challenged by Level 1–5 chefs~~
- ~~If only one chef is CulinEire Hero, the challenge is blocked~~

**One thing genuinely remains, and it is cosmetic:** `changing_room.html:36`,
`rankings.html:66` and `hall_of_fame.html` still print the words "CulinEire
Hero" for `is_hero`. On the Owner's own row that reads correctly enough, but it
keeps a buried tier's name alive in the interface. Renaming that label is his
call and no agent's.

---

## Artifact rewards by cooking format — BUILT, v2.5.1001

> **OWNER, 2026-08-10: «этого ещё и вправду нет — будем строить».** Built on
> 2026-08-11. `BattleEntry.cooking_format` exists, the winner's pool follows
> it, and the tie-break below is implemented exactly as written: webcam counts
> only when BOTH chefs cooked on camera.

`battle_cooking_format()` and `drop_weights_for_battle()` in `services.py` are
the rule; `_DROP_WEIGHTS_BASIC` and `_DROP_WEIGHTS_PREMIUM` are the two pools,
carrying the same weights the single table always had — this splits WHICH
rarities can drop, it does not re-tune how likely each one is.

**The field was the only thing missing, and the answer was already being
collected:** `BattleEntryForm` has carried a photo/video radio since it was
written, declared on the form and absent from the model, so every chef's choice
was gathered at submission and thrown away. It is stored now.

An empty pool falls back to the full set rather than paying nothing: a rule
about tiers must not quietly become a rule about getting no prize at all.

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
