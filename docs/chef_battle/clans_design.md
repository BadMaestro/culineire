# Chef Battle — Clans / Kitchens Design (Phase 6)

**Status:** DRAFT for owner approval. **No schema or migration will be written until this is approved.**
**Author:** GreenBear · **Parallel work:** Bolt owns the Seasons engine.
**Hard boundary:** this design *reads from* but **never modifies** `Season`, `SeasonStanding`, or `season_service` (Bolt's territory). Integration happens through a thin, agreed interface only.

---

## 0. Terminology decision (owner input needed)

The spec names the models `KitchenClan` / `KitchenMembership`, but the player-facing word is open. Candidates:

| Name | Pro | Con |
|------|-----|-----|
| **Kitchen** | On-theme | Collides with the **Kitchen Porter** rank and the live-video "kitchen area" wording — confusing |
| **Clan** | Clear, gaming-native | Less culinary |
| **House** | Elegant, evocative | Generic |
| **Brigade** | *Brigade de cuisine* is the real term for a kitchen team — perfect fit | Already used as a `prestige_title` value (migration 0017) — mild collision |

**Recommendation:** model stays `KitchenClan` (per spec); player-facing label **"House"** (clean, no collision). Final call is the owner's.

---

## The 5 architecture questions

### Q1 — Clan–battle model: how do clans actually compete?

| Option | Description | Cost |
|--------|-------------|------|
| **A. Passive aggregation** | Clans have no battles of their own; a clan's standing is derived from its members' individual battle results. | Low — reuses the existing battle flow untouched |
| **B. Clan-vs-clan team battles** | Dedicated battles between two clans (best-of-N member duels). | High — new battle type + lifecycle + combat changes |
| **C. Hybrid** | Ship A now; design the schema so clan-war *events* can be added later without a painful migration. | Low now, extensible |

**Recommendation: C (start passive).** Rationale: MVP discipline (`developer_role.md`), zero changes to the combat engine or `Battle` lifecycle, fastest path to the owner's "top pre-launch priority." Clan-war events become a clean Phase 6.5 add-on.

### Q2 — Membership

- **One active clan per chef** (enforced by a partial-unique constraint on `KitchenMembership` where `left_at IS NULL`).
- **Roles:** Founder/Leader, Officer (optional), Member.
- **Join policy (per-clan setting):** `open` / `request` / `invite`. Default **`request`**.
- **Size cap:** configurable, default **20** — bounds aggregation and abuse.
- **Leaving:** sets `left_at`; a **hop-cooldown** before joining another clan (see Q5).
- **Founding a clan:** gated (min rating/account age, or a token cost) to stop spam clans — see Q5.

### Q3 — Score aggregation

| Option | Description | Trade-off |
|--------|-------------|-----------|
| **A. Sum of members' `seasonal_score`** | Read each member's existing per-chef `seasonal_score` and sum. | Simple, but distorted by mid-season joins/leaves and touches shared field semantics |
| **B. Event-sourced clan points** | At **battle resolution**, credit points to the **winner's clan *at that moment*** into a per-season clan standing row. | Membership-time-aware, immune to later hopping, clean attribution |

**Recommendation: B (event-sourced).** Points are additive and can't be gamed by joining a strong clan after the fact. Stored in a new `ClanSeasonStanding` row (see models).

**Open sub-decision (owner):** rank clans by **total** score or **average per active member**? Total rewards big active clans but lets a single superstar carry a 1-member clan; average rewards efficiency but punishes size. **Recommendation:** *total*, but only clans with **≥3 active members** appear on the ranked leaderboard (kills one-man clans).

### Q4 — Season / rank interaction (without touching `Season*`)

- **Clans are season-scoped for competition** via a new `ClanSeasonStanding(clan, season, score, rank_position, active_member_count)` — this mirrors `SeasonStanding` but for clans and holds a **read-only FK to `Season`**. It does not modify `Season` or `SeasonStanding`.
- **Individual rank is untouched.** Clan membership does **not** change a chef's `rating` or `rank` — collective prestige and individual progression stay separate (this is also an anti-abuse property: no rating inflation via clans).
- **Integration with Bolt's engine:** when `season_service` transitions a season to `ended`, the clan side finalises `ClanSeasonStanding.rank_position`. **Proposed contract:** Bolt's season-finalisation emits a hook/signal (e.g. `season_ended`) that a `clan_service.finalise_clan_standings(season)` listens to. I own the clan listener; Bolt owns the emit. To be agreed in CoWork before either side codes the seam.

### Q5 — Anti-abuse

Reuses the existing `fraud.py` gate patterns rather than inventing new machinery.

| Threat | Mitigation |
|--------|------------|
| **Clan-hopping** to farm several clans | Membership-change **cooldown** (recommend 72h) + event-sourced points credited only to the clan-at-time-of-battle (Q3-B) |
| **Smurf / one-man clans** topping the board | **≥3 active members** required to rank (Q3) |
| **Collusion** (members battling each other to farm points) | Same-clan battles award **zero clan points**; layered on existing `gate_self_vote` / `gate_duplicate_device` |
| **Suspended / fraud-flagged chefs** | Excluded from clan score aggregation (reuse `is_suspended`, `fraud_flag`) |
| **Spam clan creation** | Founding gated by `gate_account_age` + min rating, or a token cost |
| **Offensive clan names/tags** | `moderation_status` on `KitchenClan` (pending → approved), reusing existing moderation flow |

---

## Proposed models (for approval — NOT yet written)

```
KitchenClan
  name, slug (unique), tag (2–5 chars), founder (FK RecipeAuthor),
  join_policy, description, crest_image, moderation_status,
  is_active, created_at

KitchenMembership
  clan (FK), chef (FK RecipeAuthor), role, joined_at, left_at (nullable)
  -> partial-unique(chef) WHERE left_at IS NULL   # one active clan per chef

ClanSeasonStanding
  clan (FK), season (FK Season = READ-ONLY reference), score,
  rank_position, active_member_count
  -> unique(clan, season)
```

`ChefBattleProfile` needs **no new field** (membership lives in `KitchenMembership`); an optional denormalised `current_clan` cache can be added later if read performance requires it.

---

## Open decisions blocking schema (owner)

1. Player-facing name: **House** (recommended) / Kitchen / Clan / Brigade?
2. Q1: passive aggregation now (recommended) vs clan-war battles now?
3. Q3: total-score + ≥3-member threshold (recommended) vs average-per-member?
4. Q2: default join policy (`request`), size cap (20), founding gate (rating/age vs token cost)?
5. Q5: same-clan battle points = **zero** (recommended) vs reduced; hop-cooldown length (72h)?

## Non-goals / boundaries

- Does **not** modify `Season`, `SeasonStanding`, or `season_service` (Bolt).
- Does **not** change individual rating/rank formulas.
- No new combat mechanics in the MVP.
