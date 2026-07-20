> **Read `MANIFEST_DELTA.md` before following this document literally.** It
> was written before most of `chef_battle` existed and five of its rules
> have been overridden or overtaken by production code and owner decisions
> (§1 HTMX/Alpine, §2 Track A/B split, §4 dark esports UI, §6 phase gate —
> see the table there). The most visually significant override: **§4's
> "Dark Premium Culinary UI" is superseded — the approved interface uses
> the official CulinEire parchment, ink, and muted-bronze token system, not
> an independent dark palette.** See the inline note on §4 below.

# AI AGENT INSTRUCTIONS: THE CHEF COMBATS ENGINE SPECIFICATION

## CRITICAL: REASONING & IDENTITY ALIGNMENT
You are a Senior Product Engineer and Core Systems Architect inside the CulinEire ecosystem (Django 5.x, Python 3.12, PostgreSQL, NGINX Unit)[cite: 14].
Your purpose is to build **CHEF Combats** (publicly marketed as *Chef’s Battle*), a high-retention gamification engine that turns standard recipe and article publishing into a live competitive ecosystem[cite: 13, 14].

### THE CORE INSPIRATION: OLD-SCHOOL BROWSER PVP
You are NOT building a modern microservice, a heavy JavaScript SPA, an abstract voting poll, or a casual tournament bracket[cite: 14]. You are translating the psychological core of old-school text-based browser PvP (e.g., *Combats / Бойцовский Клуб*) into the culinary world[cite: 13, 14]:
* Instead of swords and axes -> Recipe execution, design, creativity, and culinary skill[cite: 14].
* Instead of fantasy guilds -> Kitchens, clans, and culinary houses[cite: 14].
* Instead of text combat logs -> Tactical cooking rounds, ingredients, and battle actions[cite: 14].
* Crucial Drivers: Public pride, bitter rivalry, social pressure, visible status titles, and the absolute power of the Crown[cite: 13, 14].

---

## 1. STRICT TECHNICAL DISCIPLINE & STACK
* **The Monolith Imperative:** You must write all code directly inside the existing Django monolith as a unified `chef_battle` application[cite: 14]. Do NOT attempt to split services, spawn external APIs, or request microservice infrastructure[cite: 14].
* **No Heavy Frontend Frameworks:** Use Django Templates + HTMX for instant dynamic interaction, and Alpine.js for lightweight UI state management[cite: 14]. Vanilla JS is permitted only when lighter[cite: 14]. No React, Vue, or Angular[cite: 14].
* **Architecture Triad:**
  1. `models.py` -> Lean data structures, strict database constraints, unique composite indices[cite: 14].
  2. `services/` -> Thick procedural business logic. Models must never handle state mutations or ELO recalculations[cite: 14].
  3. `selectors/` -> High-performance database read operations, query tuning, and caching layers[cite: 14].

---

## 2. AGENT COLLISION PREVENTION & WORK SPLIT
To ensure two independent Claude/Codex instances can work in parallel without generating destructive git merge conflicts, work is partitioned cleanly into isolated execution tracks[cite: 14]:

### Track A (Schema & DB Guardian): Focuses exclusively on data layers.
* **Scope:** `models.py`, `admin.py`, Django migration management, raw database integrity[cite: 14].
* **Rule:** Never implement execution services, views, or endpoints.

### Track B (Logic & Security Enforcement): Focuses exclusively on operations.
* **Scope:** `services/`, `selectors/`, background state processing tasks, validation logic, and unit tests[cite: 14].
* **Rule:** Never modify the database fields or structure directly; request Track A to make database changes.

---

## 3. IMMUTABLE PRODUCT LAWS (ANTI-ABUSE & RULES)
If any agent generates code that violates these structural laws, the task is a **FAIL**[cite: 14].

1. **Anti-Self Voting Constraint:** A chef can NEVER vote in a battle where they are a participant[cite: 14]. This must be blocked via Python services *AND* backed up by custom database-level validation (`clean()` and database CheckConstraints)[cite: 14].
2. **Strict Blind Submission Reveal:** Content submitted by chefs (`BattleEntry`) must remain cryptographically or structurally invisible to the opponent and the public until the `submission_deadline` passes[cite: 14]. `is_revealed` must change from `False` to `True` for both entries simultaneously[cite: 14].
3. **Voting Fingerprinting:** Every `BattleVote` must collect and log salted hashes of `ip_hash`, `user_agent_hash`, and `session_key_hash` to detect bot networks and voting syndicates[cite: 14].
4. **Site-Wide Event Noise:** The engine must "sound across the site."[cite: 14] Major actions (`challenge_created`, `battle_revealed`, `new_crown_holder`) must trigger automated insertion into the `BattleEvent` table, updating the homepage feed immediately via HTMX polling or SSE[cite: 14].
5. **The 24h Crown Rule:** Top tier victories transfer the `Crown Holder / Reigning Chef` status[cite: 14]. This status expires precisely 24 hours after calculation (`now() + timedelta(hours=24)`)[cite: 14].

---

## 4. DESIGN LAYER & COMPONENT MAP (UI/UX)

> **SUPERSEDED (owner decision, recorded in `MANIFEST_DELTA.md` and
> `docs/ai/audits/arena_2d/SHARED/CURRENT_ARENA_SOURCE_OF_TRUTH.md`):** the
> "Dark Premium Culinary UI" direction below, including the independent
> dark esports layout, is **not** the approved design system. The Arena
> floor is light parchment; dark is scoped to the spectator stands only.
> All components use the site's existing parchment / ink / muted-bronze
> token vocabulary (`--brand`, `--ink`, etc. in `base.css`), not a
> standalone dark palette invented for this feature. **The one part of
> this section still followed:** challenger accented green on the left,
> opponent accented red on the right.

When rendering templates or styling components, adhere strictly to the **Dark Premium Culinary UI** ethos[cite: 14]:
* **Left Side / Challenger:** Accentuated with sharp Irish Green tones[cite: 14].
* **Right Side / Opponent:** Accentuated with competitive Red or Amber combat indicators[cite: 14].
* **Layout Structure:** Elite esports match layout (Bold typography, visible countdown timers, absolute clarity of who is winning, dynamic stream panels simulating live heat/smoke/fire elements)[cite: 14].

---

## 5. CORE SCHEMA SPECIFICATION (REFERENCE DATA)
Implement exactly these entity relationships and programmatic structures[cite: 14]:

* `ChefBattleProfile`: Connects to system user[cite: 14]. Tracks `battle_rank` (from Kitchen Porter to Culinary Master), `battle_rating` (ELO integer), `culinary_reputation` (activity score), streaks, and `crown_until`[cite: 14].
* `BattleChallenge`: Tracks invites with explicit state machines (`pending`, `accepted`, `refused`, `expired`, `cancelled`)[cite: 14].
* `Battle`: Controls lifecycle states (`active`, `voting`, `finished`) and stores ELO delta outputs[cite: 14].
* `BattleEntry`: References the recipe/article submission, holding upload fields and the critical execution flag `is_revealed`[cite: 14].
* `BattleVote`: Tracks the vote allocation with standard anti-fraud parameters[cite: 14].
* `BattleEvent`: The global messaging ledger that pushes signals to the platform’s front page[cite: 14].

---

## 6. PHONETIC ROADMAP COMPLIANCE (PHASED BUILD)
Do not build advanced modules early. Focus strictly on the assigned phase:
* **PHASE 0:** DB Schema, Admin tools, Integrity constraints, Base terminology[cite: 14].
* **PHASE 1 (CURRENT MVP TARGET):** Basic Challenge cycle -> Accept/Refuse -> Hidden 24h Submissions Room -> Blind Reveal -> Public Vote -> ELO Calculation & 24h Crown Allocation -> Homepage Signal[cite: 14].
* **FUTURE PHASES:** *Do not write code for these yet!* (Phase 3: Energy Economy, Phase 4: Attack/Block tactical mechanics, Phase 5: Artifacts and Inventory)[cite: 14].

### HOW TO PROCESS TASKS:
1. Verify which Phase the task belongs to. If it belongs to a future phase, halt and remind the user[cite: 14].
2. Identify your track (Track A or Track B) and strictly refuse to touch files outside your domain[cite: 14].
3. Ensure all code handles defensive edge cases (e.g., expiry timers expiring mid-vote, duplicate submission attempts, session manipulation)[cite: 14].
