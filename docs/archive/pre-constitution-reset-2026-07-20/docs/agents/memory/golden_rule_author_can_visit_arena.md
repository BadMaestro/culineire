---
name: golden-rule-author-can-visit-arena
description: "Owner's golden rule (2026-07-20): any registered author, not just an enrolled chef, may visit and watch the arena. Voting requires being a registered author. Anonymous visitors will be allowed to watch once the arena is public, but never to vote."
metadata:
  node_type: memory
  type: project
  originSessionId: unknown
---

# Golden rule: an author has the right to visit the arena

Stated by the owner on 2026-07-20, directed at all three agents (Bolt, GreenBear,
Ember) at once, explicitly asked to be written down so it does not need repeating.

**The rule, verbatim in substance:**

- To visit the arena as a spectator, a user does **not** need to be an enrolled
  chef (`ChefBattleProfile.enrolled_at` set). Being a plain registered
  **author** (has a `RecipeAuthor`) is enough.
- If that author later chooses to enroll as a chef, they keep arena access —
  nothing changes, it is a superset.
- Once the arena is opened to the public in the normal sense (not dark-launch
  preview), **even anonymous, non-registered visitors** will be able to open
  the arena page and watch battles.
- The **one thing anonymous/non-author visitors cannot do is vote**. Voting in
  a battle requires being a registered author. Being a registered author is
  sufficient to vote — chef enrollment is not required for that either.

## Why this matters, and what it contradicts

As read in code on 2026-07-20, `chef_battle/access.py` `is_battle_visible()`
currently gates the arena page behind:
```
CHEF_BATTLE_ENABLED (public launch, currently False) OR
user.is_staff OR user.is_superuser OR author.has_bearseeker_privileges
```
A plain registered author with **none** of those flags gets a 404 on
`/chef-battle/arena/` right now. This directly blocks the golden rule above —
an ordinary author cannot currently visit at all, let alone spectate. This was
discovered during testing when three test accounts had to be granted
`is_staff` just to reach the arena, which the owner then corrected: that
should never have been necessary for a plain author.

## How to apply

- **Backend** (`chef_battle/access.py`, Bolt's file): `is_battle_visible()`
  needs a path that lets any authenticated user with a `RecipeAuthor` through,
  independent of staff/superuser/bearseeker — those flags should only matter
  for privileged consoles (Arena Master Console etc.), not for spectating.
- **Anonymous visitors**: once `CHEF_BATTLE_ENABLED` goes public, the same view
  should render for them too (read-only, no vote controls) — this is a
  distinct, later step from letting registered authors in during dark launch.
- **Voting gate**: wherever `BattleVote` is created, the requirement is
  "authenticated user with a `RecipeAuthor`" — not enrollment, not staff.
- **Frontend implication (GreenBear's files)**: the spectator seating logic
  (`_get_spectators`, `buildAssignments` in `arena_render.js`) already treats
  "any non-enrolled author with a battle profile" as a spectator correctly —
  that part does not need to change. What was missing was the access gate
  upstream of it.

Do not re-litigate this rule or ask the owner to restate it — it is settled,
apply it wherever access/voting logic is touched next.
