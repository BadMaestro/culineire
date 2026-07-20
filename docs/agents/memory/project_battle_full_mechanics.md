---
name: project_battle_full_mechanics
description: "Full Chef Battle mechanics — Move points, phases, ingredient locks/shots, biathlon, real kitchen, audience vote"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

## Move Points (earned from content)
- Published recipe (approved): **+2 Move** (docs/chef_battle/moves_economy.md)
- Published article (approved): **+2 Move**
- Published Pinch: **+2 Move** (user confirmed same)
- Battle win: **+5 Move**
- Battle participation: **+1 Move**
- Minimum 10 moves required to ISSUE a challenge
- NOTE: user described +5 per recipe/article — canonical value is +2 per docs. Clarify if needed.

## Battle Lifecycle (canonical from docs/chef_battle/battle_lifecycle.md)
```
declared → accepted → menu_locked → active (combat) → ingredient_penalty
→ cooking → presentation → voting → completed
```

## "Ready" Button — E3 (docs/chef_battle/battle_rules.md)
- Chef A presses "Ready" → signals preparation complete
- Chef B sees it, presses "Ready", proposes a specific combat time within 24h window
- Chef A confirms the proposed time → combat begins at that time
- Battle model fields: `challenger_ready`, `opponent_ready`, `proposed_combat_time`, `combat_time_confirmed`

## Pre-Battle Setup — Menu Declaration (menu_locked phase)
- Each chef declares their ingredient list
- BOTH lists must have EQUAL ingredient counts (5v5, 6v6, etc.) — system enforces
- Each chef marks exactly 2 ingredients as "locked" (hidden from opponent)
- Opponent sees padlock icon on their OWN ingredients only

## Round 1 — Combat (active phase)
- Chefs spend Move points to attack/defend
- Attacker selects 1–2 ingredients from opponent's visible list per move
- Hit on unlocked → ingredient ELIMINATED (opponent can't use it in dish)
- Hit on locked → BLOCKED; lock is revealed for that one ingredient
- Energy cost: 1 target = 1 move, 2 targets = 2 moves
- Combat items (attack/defense artifacts, 100 each, common→legendary)

## Cooking Phase
- Chefs cook using only surviving (non-eliminated) ingredients
- Two formats: **Webcam** (live/recorded stream) OR **Photo Series** (10 photos)
- Photos: from raw ingredients laid out → to final plated dish

## Presentation Phase
- Both entries revealed simultaneously
- Shows: dish photos/video, ingredient list, eliminated ingredients visible

## Voting Phase
- Audience votes on Presentation + Visual only (cannot taste)
- One vote per user; winner = most votes; draw if equal

## Post-Battle Ingredient Penalty (ingredient_penalty phase — AFTER voting)
- Winner gets 3 hits on loser's recipe
- Loser gets 2 locks (secret, same mechanic)
- Loser applies locks first → winner strikes 3 ingredients
- Banned ingredients must be replaced by loser within 72h

## Battle Page (D2)
- Dedicated URL per battle, created when active, archived when completed
- All game data stored → used for statistics + payment verification
- Visible to ALL in real time (chefs + spectators)
- Chefs see action controls; spectators read-only + vote/gift
- YouTube-style live chat at bottom
- Like naval battle (морской бой) — ingredient grid as target board

## Slot system
- 1 active battle slot per chef at a time
- Acceptance window: 12h from challenge issue
- Battle window: 24h from acceptance

## Rules Source
- Official rules: https://culineire.ie/chef-battle/rules/ (requires auth — 403 for bots)
- Canonical docs: docs/chef_battle/ in repo
- User confirmed 2026-07-02: app must 100% follow these rules
