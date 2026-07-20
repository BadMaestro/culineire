---
name: chef-battle-complete-spec
description: "Chef Battles полная спецификация: 7 фаз, архитектура, модели, сервисы, правила, бизнес-модель"
metadata: 
  node_type: memory
  type: project
  verified: 2026-07-10
  scope: Phase 0-7 complete blueprint
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

# CHEF BATTLES — ПОЛНАЯ СПЕЦИФИКАЦИЯ

## ИДЕНТИЧНОСТЬ ПРОДУКТА

**Публичное имя:** Chef's Battle  
**Внутреннее имя:** CHEF Combats Engine  
**Тип:** Retention engine (игровая система для удержания авторов)

### Суть (в одном предложении)
Система превращает публикацию рецептов и статей на CulinEire в живую соревновательную игру: авторы вызывают друг друга, готовят блюда по теме, зрители голосуют, лучшие получают корону, рейтинг и публичное признание.

---

## ФАЗОВАЯ КАРТА (7 фаз)

### PHASE 0: Foundation & Architecture (DONE)
- ✓ Django app `chef_battle` created
- ✓ Models specified (ChefBattleProfile, BattleChallenge, Battle, BattleEntry, BattleVote, BattleEvent)
- ✓ Service layer structure designed
- ✓ Admin interface prepared
- ✓ Test foundation created

### PHASE 1: MVP Battle Core (IN PRODUCTION)
**Status:** Deployed v2.5.171 with AMC compliance audit #1  
**Core loop:** Challenge → Accept/Refuse → Battle Room → Submit → Reveal → Vote → Result → Rating → Crown

**Features:**
- Chef can challenge another eligible author
- Opponent: accept, refuse, or ignore (expires)
- Accepted challenge creates Battle Room (public page)
- Both chefs submit existing approved recipe/article
- Entries hidden until reveal or deadline
- After reveal: public voting (authenticated users only, no self-voting)
- After voting deadline: winner calculated by vote totals
- Winner gets: +25 rating, loser gets -15 (floor 500)
- Winner gets 24h crown (time-limited prestige)
- Public BattleEvent created (visible in homepage feed)

**Models in production:**
- ChefBattleProfile (user PvP state)
- BattleChallenge (challenge request with status)
- Battle (main duel record)
- BattleEntry (recipe/article submission, hidden until reveal)
- BattleVote (authenticated votes only, 1 per user per battle)
- BattleEvent (activity log, public/private)
- OperatorActionIdempotencyKey (AMC audit trail dedup - v2.5.171)

**Ratings:** Simple v1 (no ELO complexity): +25 win, -15 loss, floor 500  
**Rank ladder:** Kitchen Porter → Prep Cook → Commis Chef → Chef de Partie → Sous Chef → Head Chef → Executive Chef → Culinary Master

**Anti-abuse (Phase 1):**
- Cooldown between same pair
- Daily battle limits per user
- Only approved content counts
- Self-voting blocked at DB level
- Duplicate votes blocked at DB level

### PHASE 2: Social Visibility (PLANNED)
- Homepage dynamic battle feed
- Chef profile battle history
- Real-time notifications (SSE or polling first, WebSocket later)
- Activity feed integration
- Crown holder announcements
- Rank promotion events

**Why separate phase:** Need Phase 1 stable first; visibility multiplies engagement.

### PHASE 3: Energy Economy (PLANNED)
**New model:** BattleMoveTransaction (append-only ledger)

**Earning rates:**
- Recipe published: +5 moves
- Article published: +3 moves
- Like received: +1 move
- Battle won: +10 moves
- Special seasonal events

**Rules:**
- Max ceiling: 100 unused moves
- Only approved content earns
- Anti-farming: same-source likes capped at 3/24h per author
- Balance mutations ONLY through append-only ledger (never direct update)

**Purpose:** Tie content creation to battle strength (active author = dangerous chef)

### PHASE 4: Combat Engine (PLANNED)
**Real mechanic (NOT fantasy combat):** Ingredient battle + biathlon

**Process:**
1. Each chef locks 2 ingredients as "protected"
2. Biathlon phase: round winner fires up to 3 blind shots at opponent's ingredient list
3. Shot on locked ingredient bounces back
4. Whatever ingredients survive must be actually cooked + photographed
5. Moderator verifies cooking phase photos
6. Public votes for 2 days
7. Winner holds Crown 24h

**Models needed:**
- CombatRound (turn-by-turn logs)
- CombatAction (attack/block/damage)
- IngredientLock (protected ingredients)

**Why separate phase:** MVP focuses on social loop first; combat adds depth later.

### PHASE 5: Artifacts & Cosmetics (PLANNED)
**Model:** KitchenArtifact (earned items)  
**Model:** ChefCosmetic (premium/earned cosmetics)

**Earning:**
- Loot drops at battle end (RNG based on rating)
- Seasonal achievements
- Tournaments wins
- Milestones

**Never buy:** Artifacts earned only (no direct purchase)  
**Can buy:** Cosmetics (profile frames, badges, banners) — NO pay-to-win

**Types:**
- Knives/uniforms (equipment with vote multipliers)
- Cosmetic frames/badges
- Profile prestige visuals

### PHASE 6: Seasons & Clans/Kitchens (PLANNED)
**Models:**
- Season (30-day competitive period)
- SeasonStanding (leaderboard positions)
- CulinaryKitchen (clan/guild for creators)
- KitchenMembership (chef membership)

**Features:**
- Monthly leaderboard resets
- Clan reputation pooling
- Regional leagues
- Hall of Fame
- Team identity layer

### PHASE 7: Sponsorship & Media (PLANNED)
**Sponsored battles** — brands can sponsor themed challenges  
**Automated recaps** — AI generates battle summaries  
**Creator subscriptions** — premium analytics, exclusive events  
**Newsletter integration** — weekly battle digest

---

## DATABASE SCHEMA (ALL MODELS)

### Phase 1 (Production)

```
ChefBattleProfile
├─ user (OneToOne)
├─ battle_rank (CharField, default="Kitchen Porter")
├─ battle_rating (Integer, default=1000)
├─ culinary_reputation (Integer, default=0)
├─ wins/losses/refused_battles/ignored_battles (Integers)
├─ win_streak / best_win_streak (Integers)
├─ crown_until (DateTime nullable) — active if > now
├─ crown_count (Integer)
├─ battle_moves (Integer, Phase 3)
├─ seasonal_score (Integer, Phase 6)
└─ timestamps

BattleChallenge
├─ challenger / opponent (ForeignKey(User))
├─ theme (CharField)
├─ message (TextField)
├─ battle_type (CharField: 'recipe' or 'article')
├─ status (pending|accepted|refused|expired|cancelled)
├─ is_sponsored / sponsor_brand / sponsor_prize_pool (Phase 7)
├─ expires_at (DateTime)
├─ accepted_at / refused_at / cancelled_at (DateTime nullable)
└─ timestamps

Battle
├─ challenge (OneToOne(BattleChallenge))
├─ challenger / opponent (ForeignKey(User), PROTECT)
├─ theme (CharField)
├─ status (scheduled|active|voting|completed|cancelled|disputed)
├─ start_time / submission_deadline / reveal_time / voting_deadline / end_time (DateTimes)
├─ winner / loser (ForeignKey(User), nullable)
├─ result_reason (public_vote|opponent_no_show|mutual_no_show|admin_decision)
├─ rating_delta_challenger / rating_delta_opponent (Integers)
├─ crown_awarded (Boolean)
└─ timestamps

BattleEntry
├─ battle (ForeignKey(Battle))
├─ author (ForeignKey(User))
├─ recipe / article (ForeignKey, nullable — one or other)
├─ battle_statement (TextField)
├─ submitted_at (DateTime nullable)
├─ is_revealed (Boolean)
├─ is_late (Boolean)
├─ moderation_status (pending|approved|rejected|flagged)
└─ timestamps

BattleVote
├─ battle (ForeignKey(Battle))
├─ voter_user (ForeignKey(User))
├─ voted_for (ForeignKey(User))
├─ ip_hash / user_agent_hash / session_key_hash (CharField 64)
├─ is_suspicious (Boolean)
├─ moderation_note (CharField)
└─ created_at

BattleEvent
├─ battle (ForeignKey(Battle), nullable)
├─ event_type (CharField: challenge_created|...|rank_promoted)
├─ actor / target (ForeignKey(User), nullable)
├─ message (TextField)
├─ payload_json (JSONField) — battle outcome, deltas, metadata
├─ is_public (Boolean) — feeds to homepage?
└─ created_at

OperatorActionIdempotencyKey (v2.5.171)
├─ correlation_id (CharField 64, unique)
├─ action (CharField 40)
├─ created_at (DateTimeField with index)
└─ purpose: Prevents replay attacks on broadcast actions via DB unique constraint
```

### Phase 3 (Planned)

```
BattleMoveTransaction (append-only ledger)
├─ profile (ForeignKey(ChefBattleProfile))
├─ amount (Integer: positive=earned, negative=spent)
├─ transaction_type (recipe_published|article_published|like_received|battle_won|combat_action_spent|admin_adjustment)
├─ reference_content_type / reference_object_id (generic FK)
└─ created_at
└─ Rule: NEVER update/delete; ChefBattleProfile.battle_moves updated atomically
```

### Phase 5 (Planned)

```
KitchenArtifact
├─ name (CharField 100)
├─ artifact_type (knife|uniform|ingredient_charm)
├─ rarity (common|rare|epic|legendary)
├─ vote_modifier (Decimal: 1.00 = +0%, 1.02 = +2%)
├─ energy_regeneration_bonus (Integer)
├─ owner (ForeignKey(User))
└─ acquired_at

ChefArtifact
├─ chef_profile (ForeignKey(ChefBattleProfile))
├─ artifact (ForeignKey(KitchenArtifact))
├─ equipped (Boolean)
├─ source_reason (battle_win|seasonal_reward|achievement)
└─ earned_at

CosmeticItem
├─ name / slug (CharField)
├─ type (CharField)
├─ price (Decimal, nullable — free if null)
├─ rarity (common|rare|epic|legendary)
├─ image (ImageField)
├─ is_active (Boolean)

ChefCosmetic
├─ chef_profile (ForeignKey)
├─ item (ForeignKey(CosmeticItem))
├─ purchased_at (DateTime)
└─ equipped (Boolean)
```

### Phase 6 (Planned)

```
Season
├─ name (CharField)
├─ starts_at / ends_at (DateTime)
├─ status (active|completed|archived)
├─ crown_rule (CharField)
└─ reward_rules_json (JSONField)

SeasonStanding
├─ season (ForeignKey(Season))
├─ chef_profile (ForeignKey(ChefBattleProfile))
├─ score (Integer)
├─ rank_position (Integer)
├─ wins / losses / streak (Integers)
└─ updated_at

CulinaryKitchen (Clan)
├─ name / slug (CharField, unique)
├─ leader (ForeignKey(User), PROTECT)
├─ reputation (Integer)
├─ tier (CharField: "Bronze Kitchen" default)
└─ created_at

KitchenMembership
├─ kitchen (ForeignKey(CulinaryKitchen))
├─ chef_profile (ForeignKey(ChefBattleProfile))
├─ joined_at (DateTime)
└─ role (member|officer|leader)
```

---

## SERVICE LAYER STRUCTURE

```
chef_battle/services/
├─ challenge_service.py
│  ├─ create_challenge(challenger, opponent, theme, message, battle_type)
│  ├─ accept_challenge(challenge_id, responder)
│  ├─ refuse_challenge(challenge_id, responder)
│  ├─ expire_challenge(challenge_id)
│  └─ cancel_challenge(challenge_id, canceller)
│
├─ battle_service.py
│  ├─ create_battle_from_challenge(challenge)
│  ├─ submit_entry(battle_id, author, recipe|article, statement)
│  ├─ reveal_battle(battle_id) — when both entries submitted or deadline
│  ├─ complete_battle(battle_id) — after voting deadline
│  ├─ resolve_no_show(battle_id) — handle missing submissions
│  └─ cancel_battle(battle_id)
│
├─ vote_service.py
│  ├─ cast_vote(battle_id, voter, voted_for)
│  ├─ validate_vote(battle_id, voter, voted_for) — checks all rules
│  ├─ get_vote_totals(battle_id)
│  └─ flag_suspicious_vote(vote_id, reason)
│
├─ rating_service.py
│  ├─ calculate_rating_delta(battle_id, winner_rating, loser_rating)
│  ├─ apply_battle_result(battle_id, winner_user, loser_user)
│  ├─ apply_refusal_penalty(challenge_id, refused_by)
│  ├─ update_rank(profile_id) — recompute rank from rating
│  └─ award_crown_if_applicable(profile_id) — set crown_until = now+24h
│
├─ event_service.py
│  ├─ create_battle_event(battle_id, event_type, actor, target, message, payload_json, is_public)
│  ├─ create_public_news_event(...) — explicit public flag
│  ├─ get_public_battle_events(filters) — for homepage feed
│  └─ get_profile_battle_events(user_id) — for chef profile
│
├─ energy_service.py (Phase 3)
│  ├─ add_move_transaction(profile_id, amount, transaction_type, reference)
│  ├─ deduct_moves(profile_id, amount) — atomic validation
│  ├─ get_balance(profile_id) — sum of all transactions
│  └─ apply_energy_cap(profile_id) — enforce 100 moves ceiling
│
├─ combat_service.py (Phase 4)
│  ├─ lock_ingredients(battle_id, chef_id, protected_ingredients)
│  ├─ fire_shot(round_id, actor_id, target_zone)
│  ├─ resolve_round(round_id) — hit/miss/block logic
│  └─ generate_combat_log_text(battle_id) — narrative descriptions
│
├─ artifact_service.py (Phase 5)
│  ├─ roll_loot_drop(battle_id, winner_rating)
│  ├─ mint_artifact(profile_id, artifact_name, rarity)
│  └─ equip_artifact(chef_artifact_id)
│
└─ clan_service.py (Phase 6)
   ├─ create_kitchen(name, slug, founder_id)
   ├─ join_kitchen(profile_id, kitchen_id)
   ├─ aggregate_seasonal_score(season_id)
   └─ execute_monthly_reset() — cron task for season wipe
```

---

## SELECTORS (Read-Only Queries)

```
chef_battle/selectors.py

get_user_battle_profile(user_id)
get_active_challenges(user_id) — incoming + outgoing pending
get_battle_public_data(battle_id) — safe subset, no hidden entries before reveal
get_leaderboard_top_n(n=100) — by rating
get_chef_battle_history(user_id, limit=20)
get_home_feed_events(limit=50, is_public=True) — for homepage
get_profile_battle_stats(user_id) — for profile card
is_crown_holder_now(user_id) — crown_until > now
can_user_challenge(challenger_id, opponent_id) — eligibility checks
get_battle_vote_totals(battle_id) — vote counts per participant
```

---

## BUSINESS RULES (HARD CONSTRAINTS)

### Challenge Rules
- ✗ Self-challenge blocked (ValidationError)
- ✗ Self-voting blocked (DB constraint)
- ✗ Duplicate voting blocked (unique constraint: battle+voter)
- ✓ Cooldown between same pair (24h or configurable)
- ✓ Active outgoing challenge limit (prevent spam)
- ✓ Only eligible (verified creator) authors can participate
- ✓ Challenge expires if not accepted within window (auto-expire via cron)

### Battle Rules
- ✓ Two participants only in Phase 1
- ✓ Submission deadline mandatory (24h default after acceptance)
- ✓ Entries remain hidden until reveal or deadline
- ✓ Voting only after reveal
- ✓ Voting only during voting window
- ✓ Voting only by non-participants
- ✓ Winner only set after voting deadline

### Rating Rules
- ✓ Winner: +25 points
- ✓ Loser: -15 points
- ✓ Floor: 500 points (cannot go below)
- ✓ Repeated weak opponent: reduced gain
- ✓ Refusal: optional reputation penalty
- ✓ Win streak: optional small bonus

### Crown Rules
- ✓ Duration: exactly 24 hours (crown_until = now + 24h)
- ✓ Transfer: next winner may replace current holder
- ✓ Display: visible on profile, battle pages, leaderboard, homepage block

### Anti-Abuse Rules (MVP)
1. Cooldown between same pair (e.g., 7 days)
2. Daily battle limits per user (e.g., 3 active per user max outgoing)
3. Only approved/published content earns points
4. Self-voting blocked
5. Duplicate votes blocked
6. Challenge spam prevention
7. Eligible author verification only

---

## RETENTION MECHANICS (WHY IT WORKS)

### Author Loop
1. Author publishes recipe → earns battle moves (Phase 3)
2. Author sees new recipes in feed → challenges another author
3. Challenge creates public event (visible to audience) → social pressure
4. If accepted: enters battle room (public, visible to all) → brand new content opportunity
5. Submits dish → gets photographed/visible → builds portfolio
6. Wins: gets rating points, 24h crown, profile boost → status
7. Loss: rating penalty but engagement data → learns, comes back

**Result:** Author returns weekly to challenge, publish more recipes, build reputation

### Audience Loop
1. Viewer sees "Chef A challenged Chef B" event → curiosity
2. Visits battle page → votes for favorite → feels invested
3. Sees winner get crown → status visible → drama/anticipation
4. Returns to see who's crown holder now → drives recurring visits

### Platform Loop
1. More challenges = more UGC (recipes submitted for battles)
2. More voting = user engagement metric
3. More public events = SEO content + social shares
4. Brands sponsor battles = monetization

---

## MONETIZATION (NO PAY-TO-WIN)

### Allowed
- ✓ Premium cosmetics (frames, badges, banners)
- ✓ Featured chef promotion (paid placement on leaderboard)
- ✓ Sponsored battles (brand-themed challenges)
- ✓ Creator subscriptions (exclusive analytics, early access)
- ✓ Optional paid battle energy cap increase (minor, not game-breaking)

### Forbidden
- ✗ Direct purchase of artifacts
- ✗ Purchase of rating/crown
- ✗ Purchase of win streaks
- ✗ Anything that directly buys victory

**Principle:** Artifacts/energy earned through gameplay only. Cosmetics can be premium.

---

## PRODUCT PRINCIPLES (NON-NEGOTIABLE)

1. **"The battle must sound across the site"** — public visibility is core
2. **Low barrier to entry** — challenge form should be 3 clicks
3. **Public duels** — all battles visible by default
4. **Text logs** — combat/events stored as human-readable narratives
5. **Visible progression** — rating/rank always visible on profile
6. **Status matters** — crown, titles, streaks visible everywhere
7. **Community drama** — refusals, upsets, comebacks are social moments
8. **Career growth inside the world** — top chefs become micro-celebrities

---

## VERSION HISTORY

- **v2.5.171 (2026-07-10):** AMC Phase 1 complete - audit trail, idempotency keys, CSRF tests
- **v2.5.170:** Arena Master Console foundation
- Earlier: Phase 0 models, Phase 1 core battle system

---

## NEXT WORK (Remaining Compliance Audit Items)

**Completed:**
1. ✓ Audit rejected actions + idempotency key (v2.5.171)

**Remaining (3 of 4):**
2. Granular security checklist (instead of single boolean field on Recipe)
3. Bulk-load instead of N+1 queries (P02–P05)
4. Missing combat metrics (P04: misses/defended/surviving)
5. Update stale documentation (P01/P02 reports, public roadmap)
