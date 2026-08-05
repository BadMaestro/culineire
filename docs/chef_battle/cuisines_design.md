# Chef Battle — Culinary Factions Design (Phase 6)

**Status:** DRAFT for owner approval. **No schema/migration is written until approved.**
**Supersedes:** `clans_design.md` (the clan/kitchen idea is dropped).
**Author:** GreenBear · **Parallel:** Bolt owns the Seasons engine — **shipped and live on origin** (`season_service` v2.5.189; `season_signals` hook v2.5.190; the post-commit `season_ended_committed` signal for faction rewards v2.5.192).
**Method:** synthesised from a 5-lens design pass (game-design, anti-abuse, legal/rewards, data-model, season-boundary) grounded in the live code, plus Bolt's confirmed season-hook contract.

---

## 1. Concept (owner-approved)

Players don't build clans — they **represent** two curated identities and compete for both, every season:

- **Cuisine** — culinary heritage ("where from"): Italian, French, Japanese, Chinese, Mexican, Indian, Greek, Thai, Korean, American.
- **Specialty** — mastery ("what you're master of"): Bakery, Pastry, BBQ, Grill, Seafood, Street Food, Fine Dining, Fusion, Molecular, Vegetarian, Vegan, Fermentation, Pizza, Pasta, Sushi, Desserts, Coffee, Cocktails.

Lore-facing: *"🇮🇹 Italian Cuisine · 🔥 BBQ Specialty"*, *"Japanese Cuisine is leading this season."* Every gameplay action earns **contribution points** that flow to **both** the chef's Cuisine and Specialty seasonal standings. At season end, rewards are distributed on individual contribution (scaled by placement) plus non-cash collective prestige.

## 2. Locked architecture decisions (owner delegated)

| # | Decision | Locked value | Why |
|---|----------|-------------|-----|
| A | **One unified model, not two stacks** | Generic `Faction(kind=cuisine\|specialty)` — both axes are rows of one table, one service, one leaderboard, one anti-abuse impl | Cuisine and Specialty are structurally identical; halves the code, a 3rd axis later = seed data, not new models |
| B | **Both axes at launch** | Ship Cuisine + Specialty together (shared machinery, marginal cost ≈ seed rows) | — |
| C | **Season-team, not permanent** | Switch only **between** seasons; hard-locked while a season is `ACTIVE` | Fresh restart each season; kills the bandwagon |
| D | **Event-sourced points** | Append-only `FactionContribution` ledger (mirrors `BattleMoveTransaction`); points credited to the faction **at the moment of the action** | Late-joining the leader earns nothing — past points don't transfer; auditable & reversible |
| E | **Ranking = normalised, not raw** | `normalized_score = total_points / √(active_member_count)`, ranked, **≥5 active-member floor** | Raw total = popularity contest; pure average = toxic exclusion of newbies. √N: a new member need only add ~½ the current per-capita average to be net-positive → recruiting always welcome, but size alone can't win |
| F | **Rewards via existing `RewardRecord`** | No parallel currency; individual CBR through `issue_reward()`; collective placement = **cosmetic/prestige only** | Keeps the anti-gambling/DAC7 posture (rules §15–18); a cash "faction prize pool" would be lottery-shaped |
| G | **Receiver is defensive + deferred** | `season_ended` receiver only finalises standings (cheap SUM); heavy reward issuance runs in a follow-up pass | Bolt's signals fire **inside** his season transaction — a raise would roll back the whole season transition |

## 3. Data model (proposed — not yet written)

```
Faction
  kind            cuisine | specialty          # discriminator — the whole trick
  name, slug (unique per kind), crest_icon, is_active
  # seeded/curated; NOT user-created → no name-moderation machinery needed

FactionMembership
  chef (FK RecipeAuthor), faction (FK), faction_kind (denormalised), season (FK Season, read-only)
  joined_at, left_at (nullable)
  -> UniqueConstraint(chef, faction_kind, season)   # one Cuisine + one Specialty per season

FactionContribution                                 # append-only, immutable
  chef (FK), faction (FK), faction_kind, season (FK, read-only)
  source_content_type + source_object_id            # generic FK -> the recipe/article/pinch/like/battle
  points (int), created_at
  index (season, faction), (chef, season)
  # standings are a SUM over this ledger — never a mutated counter

FactionSeasonStanding
  faction (FK), season (FK Season, READ-ONLY), total_points, active_member_count,
  normalized_score, rank_position, rewards_pending (bool)
  -> UniqueConstraint(faction, season)
  # written ONLY by the cuisine side (season_started opens, season_ended finalises)

SeasonReward                                        # thin audit bridge — NO monetary fields
  chef, faction, season, points_snapshot, placement,
  reward_record (FK -> RewardRecord, nullable)      # the money leg (individual CBR)
  cosmetic (FK -> ChefCosmetic/ChefArtifact, nullable)  # the collective non-cash leg
```

**No new field on `ChefBattleProfile`** (membership lives in `FactionMembership`); an optional denormalised `current_cuisine`/`current_specialty` cache can be added later if leaderboard reads need it. `active_member_count` is **computed** (chefs past a contribution floor, excluding suspended/fraud/executive) — deliberately different from raw roster size.

### 3.1 Agreed build refinements (Bolt senior review)

- **`award_faction_contribution` placement in `award_moves`:** insert **after** the anti-farm / eligibility gates (so fake likes can't inflate a faction) but **before** the `ENERGY_CAP=100` early-`return 0`. Faction points are season-cumulative and **uncapped** — gating them behind the moves cap would silently stop a maxed-out chef from contributing and corrupt standings. (Bolt owns this insertion — sensitive core code.)
- **`normalized_score`:** compute **live** for the active leaderboard; **store** the frozen value only at `season_ended` finalisation. Do not recompute on every contribution write.
- **Two distinct thresholds, both named constants:** (a) *active-for-denominator* = **≥1 contribution in the season** (defines who counts in `√(active_member_count)`); (b) *rank floor* = **≥5 active members** for a faction to appear on the ranked board. They are different numbers and must not be conflated.
- **`FactionContribution` denormalised `faction`/`faction_kind` at write time** — confirmed correct: points belong to the faction *as of the earning moment* and survive a later switch.
- **`SeasonReward` money split:** collective leg → `ChefCosmetic` (non-cash); individual leg → `RewardRecord` (CBR). Matches anti-gambling §17.
- **Re-pick window (resolves the carryover ↔ lock tension):** carryover keeps a chef's prior-season pick by default, but a **7-day window** (`FACTION_REPICK_WINDOW_DAYS`) at the start of each season lets them freely change (or keep) it; after the window the pick locks until next season. First pick is allowed any time. Safe from bandwagoning because standings are still empty that early, and it doubles as the early-join reward-eligibility window (sec 8). Points already earned stay with the faction they were earned for (event-sourced), so a mid-window switch only redirects future contributions. Lives in `faction_selectors.set_faction_membership` (GreenBear's lane).

## 4. How points are earned

Reuse the existing `EARN_*` triggers as the point *sources* (no new economy): approved recipe/article/pinch, unique like received, battle win/participation. Each triggering action writes **two** `FactionContribution` rows — one to the chef's current Cuisine, one to their current Specialty — via a read-only hook, **decoupled from the capped `battle_moves` wallet** (that balance is capped at 100 and spent down, so it's not a valid cumulative-activity measure).

- **Same-faction battles award 0 faction points** (kills intra-team collusion) — new `gate_same_cuisine_battle` / `gate_same_specialty_battle`, hooked read-only after `calculate_battle_result`.
- **Per-opponent seasonal cap (3)** on battle-derived points + existing 24h cooldowns (`gate_post_battle_cooldown`, `gate_repeat_challenge_cooldown`) throttle cross-faction win-trading.
- **Like points** reuse the existing `LIKE_ANTI_FARM` dedup (3/source/24h, distinct likers). **Content points** count only `approved` objects.

## 5. Season integration — Bolt's shipped contract (`season_signals`, live on origin)

`chef_battle/season_signals.py` exposes **three** signals (Bolt built the third specifically to carry faction reward issuance safely):

- `season_started.send(sender=Season, season=…)` — inside `activate_season()`. **My receiver:** open `FactionSeasonStanding` rows for the season, carry membership over from the prior season, lift the season-lock.
- `season_ended.send(sender=Season, season=…, standings=<QuerySet[SeasonStanding] by rank_position>)` — inside `close_season()`, after the snapshot + `seasonal_score` reset. **My receiver:** cheap, non-raising finalisation of `FactionSeasonStanding.rank_position` from the frozen standings, set `rewards_pending=True`.
- `season_ended_committed.send(sender=Season, season=…)` — fires via `transaction.on_commit`, **after** `close_season` durably commits. **My receiver:** the heavy/fallible reward issuance (`SeasonReward` → `RewardRecord`). A failure here can **not** roll back the season close.

The first two fire **inside Bolt's transaction** (a raise rolls back the season transition), so those receivers stay minimal and non-raising. The heavy reward work hangs on the **post-commit** signal — no need for my own deferred management command. I read `Season`/`SeasonStanding` read-only and never write rating, rank, or `seasonal_score`.

## 6. Rewards & legal posture

**Owner decision (final): faction/season rewards are NON-CASH recognition only — no CBR, no `RewardRecord`, no payout path at all.** This removes the entire money/legal surface for factions. Winning and top factions and their chefs receive:

- **Legendary combat artifacts** — grant a `Rarity.LEGENDARY` `Artifact` as a `ChefArtifact` (reuse the existing artifact-grant path, cf. `drop_battle_artifacts`).
- **A place in the Hall of Fame** — extend the existing `hall_of_fame` view / selectors to induct season faction champions.
- **Permanent season medals** — awarded as a `ChefCosmetic` (or a `michelin_stars`-style permanent marker) that stays on the account forever.

**No cash-convertible reward is tied to faction results.** The only path to a monetary reward is an **optional external sponsor's own initiative**, handled separately, out of scope for the core arena — treated as an occasional incentive, not a feature.

Because there is no payout leg, the earlier CBR/placement-multiplier/DAC7 machinery for factions is dropped. `SeasonReward` becomes a thin audit record of the non-cash grants (artifact / hall-of-fame entry / medal cosmetic), with no monetary fields — consistent with its model definition. Anti-gambling §17 holds trivially: nothing of cash value is ever awarded for a faction outcome.

Rules surface: **§20 "Culinary Factions"** states rewards are non-cash recognition (legendary artifacts, Hall of Fame, permanent medals) and that any monetary reward would only ever come from an optional external sponsor; §15–18 are **not edited** (locked legal work).

## 7. Keeping it fun & fair (game-design)

- **Losing-faction engagement:** per-faction internal leaderboards ("#3 in the Japanese Cuisine") and MVP callouts — big-fish-in-small-pond status independent of overall placement.
- **Niche viability:** an **underdog multiplier** for under-subscribed factions + rotating "spotlight" events + exclusive faction cosmetics, so picking Greek over Italian has a real draw.
- **Renewal:** team standings reset each season (event-sourced, season-scoped); individual rating/rank/cosmetics persist. Bookend with a ceremony ("Japanese Cuisine won Season 3") + a re-pick window.
- **Future events** ride this cleanly: Battle of Cuisines, Discipline/Specialty Championship, Bakery Cup, BBQ Masters, Fusion Festival, Molecular Challenge.

## 8. Anti-abuse summary (all on existing `fraud.py` patterns)

| Threat | Mitigation |
|--------|-----------|
| Same-faction self-feeding | Same-faction battles = 0 points |
| End-of-season bandwagon | In-season lock + event-sourced points + placement reward requires early membership & personal contribution |
| Niche capture by 2–3 grinders | ≥5 active-member floor; active = past contribution threshold, suspended/fraud/executive excluded; per-member contribution cap |
| Cross-faction win-trading | Per-opponent cap 3/season + existing cooldowns |
| Smurf/multi-account stuffing | `gate_account_age(7d)`, enrolled + age_verified required, device/IP fingerprint clustering → staff review (log-only, no auto-suspend) |
| Cheap-action farming | Approved-content-only, like anti-farm dedup, per-action daily caps |

## 9. Open items for the owner

Most decisions are locked above (per your delegation). Genuinely owner-preference tunables:

1. **Seed lists** — confirm the 10 cuisines / 18 specialties above (add/remove any?).
2. **Reward magnitudes** — placement multiplier curve (proposed 1.5/1.3/…/0.9) and the token conversion for the individual CBR leg.
3. **Specialty timing** — ship simultaneously with Cuisine (recommended, shared code) vs Cuisine-first fast-follow.
4. Confirm the **collective leg stays strictly non-cash** for launch (strongly recommended by legal lens).

## 10. Boundaries

- Never modifies `Season`, `SeasonStanding`, `season_service` (Bolt) — read-only + the agreed signals.
- Never changes individual `rating`, `rank`, `reputation`, or `seasonal_score`.
- No new combat mechanics.
