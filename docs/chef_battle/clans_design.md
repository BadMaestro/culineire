# Chef Battle — Clans & Alliances Design (Phase 6+)

**Status:** FINALISED by owner (session 2026-07-14). Supersedes the earlier pre-factions
clan draft entirely.
**Author:** GreenBear (design + UI). **Migrations:** Bolt owns ALL `chef_battle`
migrations — GreenBear sends model fields, Bolt writes model + migration + clan-scoring
selectors, then GreenBear builds UI on that API.
**Relationship to factions:** a `Clan` is a *player-created named group* (Fusion,
Cyber Chef). It is NOT a `Faction`. A `Faction` (cuisine/specialty axis, e.g. BBQ,
Italian) is curated. A clan *references* up to 3 factions as its "comfort categories".
The owner treats the words "clan" and "faction" as one concept colloquially — in code
they are two separate models and must not be merged.

---

## 1. Owner spec (verbatim intent)

### Clan
- **Clan = a name** (Fusion, Cyber Chef) with a **founder** (chef) + members. The name
  by itself is attached to nothing until categories are chosen.
- On creation the founder picks the **categories the clan is comfortable in**.
  **Max 3 categories. Selecting all is not allowed.**
- **Categories = existing `Faction` rows** (both `kind=cuisine` and `kind=specialty`,
  mixed freely). **No new category table** — the clan links to ≤3 `Faction`.
- The clan participates in / is displayed in **each** chosen category. Different clans
  **may overlap** on categories — allowed.
- A chef's **profession (specialty) stays at the chef level**, independent of the
  clan's categories. (Example: GreenBear founds clan *Fusion* with its own categories,
  but GreenBear's personal profession is still BBQ.)
- **SEASON WINNER = the single clan with the highest SUM of its members' season
  points** (cuisine/profession irrelevant to the total).

### Delegated to GreenBear (owner handed these off)
| Detail | Decision |
|--------|----------|
| Member limit | Soft cap **12** — keeps clans competitive, not mega-guilds |
| Join flow | **Request → founder approves** (membership request, founder accepts) |
| Points on leave | Points already earned **stay with the clan** (event-sourced ledger); the leaver simply stops accruing |

### Alliances (foundation in S1, full mechanic in S2 — MUST be written into the rules)
- Clans group into **alliances**. In a duel a clan can **call allied clans** to help.
- Then the fight is no longer about a specific recipe but about a **cuisine vs cuisine**
  (example: African BBQ vs Eastern-European dishes/plov) — a dispute over which cuisine
  is more popular this season.
- **S1:** minimal foundation only — `Alliance` model, clan↔alliance link, a
  "call an ally" hook. Full cuisine-vs-cuisine combat mechanic ships in **S2** when
  traffic justifies it.

---

## 2. Proposed models (GreenBear → Bolt; Bolt writes migration)

```
Clan
  founder        FK RecipeAuthor  (related_name="founded_clans")
  name           CharField(80)    (user-facing, moderated)
  slug           SlugField(80) unique
  crest_icon     CharField(8) blank      # emoji crest, mirrors Faction.crest_icon
  categories     M2M -> Faction   (related_name="clans")   # >=1, <=3 enforced in service, NOT DB
  moderation_status  CharField  (pending|approved|rejected, default pending)  # user-created name
  is_active      BooleanField default True
  created_at     DateTimeField auto_now_add

ClanMembership
  clan       FK Clan            (related_name="memberships")
  chef       FK RecipeAuthor    (related_name="clan_memberships")
  role       CharField (founder|member, default member)
  status     CharField (pending|active, default pending)   # request->approve flow
  joined_at  DateTimeField auto_now_add
  left_at    DateTimeField null blank
  -> partial UniqueConstraint(chef) WHERE left_at IS NULL AND status='active'
     # one active clan per chef

Alliance                        # S1 minimal foundation
  name        CharField(80)
  slug        SlugField(80) unique
  is_active   BooleanField default True
  created_at  DateTimeField auto_now_add

AllianceMembership              # through-model so "call ally" hook has a join row
  alliance   FK Alliance (related_name="memberships")
  clan       FK Clan     (related_name="alliance_memberships")
  joined_at  DateTimeField auto_now_add
  left_at    DateTimeField null blank
  -> partial UniqueConstraint(clan) WHERE left_at IS NULL   # one active alliance per clan
```

### Scoring source — Bolt's call (recommendation)
Season winner = highest sum of members' season points. Two ways to source
"member season points":
- **A. Aggregate existing `FactionContribution`** per chef per season, summed over the
  clan's current active members. Simple; but distorted by clan-hopping (a late joiner
  drags their whole season's points in).
- **B. Event-sourced `ClanContribution`** (mirrors `FactionContribution`): at battle
  resolution, credit points to the **winner's clan at that moment**. Hop-immune, matches
  the existing ledger pattern, and makes "points stay with the clan on leave" (owner
  decision) fall out naturally.

**Recommendation: B**, consistent with `FactionContribution`. If Bolt goes with B, add:
```
ClanContribution   (append-only)
  chef, clan (denormalised at write), season, source_content_type/object_id, points, created_at
ClanSeasonStanding
  clan, season, total_points, active_member_count, rank_position
  -> unique(clan, season)
```

### Selectors Bolt owns (for the Arena Observer prize + leaderboard)
- `get_season_winning_clan(season) -> Clan | None` — highest summed member points.
- `get_season_clan_champion(season, clan) -> RecipeAuthor | None` — top individual
  contributor inside the winning clan (this is who nominates the 2 Arena Observers).
- `get_clan_leaderboard(season) -> [rows]` — for GreenBear's clan board UI.

---

## 3. Anti-abuse (reuse existing gates, no new machinery)
| Threat | Mitigation |
|--------|------------|
| Clan-hopping to farm points | Event-sourced credit to clan-at-battle-time (scoring B); points stay with clan on leave |
| Offensive clan names | `moderation_status` on `Clan` (pending → approved), reuse existing moderation flow |
| One-man / smurf clans topping the board | Rank floor (recommend **≥3 active members** to appear on ranked clan board) |
| Suspended / fraud-flagged chefs | Excluded from clan aggregation (reuse `is_suspended` / fraud flags) |
| Collusion (same-clan farming) | Same-clan battles award zero clan points; layer on existing self-vote/device gates |

---

## 4. GreenBear UI scope (built after Bolt's API is live)
- Clan **create** flow: name + crest + pick ≤3 categories (Faction multiselect, mixed axes).
- Clan **membership**: request-to-join, founder approve/deny queue, member roster, leave.
- Clan **detail** page: crest, categories, roster, season standing.
- Clan **leaderboard** (season winner highlighted).
- **Alliance** UI (S1 foundation): create alliance, add/remove clans, "call ally" entry point.
- Season-winner display + tie-in to Arena Observer champion nomination (separate feature).

## 5. Boundaries
- GreenBear does NOT create `chef_battle` migrations. Sends model fields; Bolt migrates.
- Clan membership does NOT change a chef's individual rating/rank or their personal
  cuisine/specialty profession.
- Alliance combat (cuisine-vs-cuisine resolution) is S2 — S1 ships the model + link + hook only.
