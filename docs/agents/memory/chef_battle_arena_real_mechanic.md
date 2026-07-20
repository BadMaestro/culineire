---
name: chef-battle-arena-real-mechanic
description: "Arena Master Console текущий фокус: ингредиентный боевой движок, визуализация, механика 'Combat is NOT violence'"
metadata: 
  node_type: memory
  type: project
  verified: 2026-07-10
  source: Final Arena Prompt.yaml
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

# ARENA MASTER CONSOLE — REAL MECHANIC

## KEY PRINCIPLE: "COMBAT IS NOT VIOLENCE"

**This is CRITICAL to understand:**

The real mechanic of Chef's Battle is **NOT** generic fantasy combat. It's ingredient-based tactical competition.

### The Real Game
1. **Combat Phase:** Each chef locks 2 ingredients as "protected" from attack
2. **Biathlon Sub-Phase:** The round winner fires up to 3 blind shots at opponent's ingredient list
3. **Shot Mechanics:** 
   - Shot on locked ingredient = bounces back (no effect)
   - Shot on unlocked ingredient = eliminated from available pool
4. **Cooking Phase:** Whatever ingredients survive the combat must actually be cooked and photographed
5. **Moderator Verification:** Real cooking photos prove the dish was actually made
6. **Public Voting:** Audience votes for 2 days on final dishes
7. **Winner:** Hold crown 24h, gain rating points

### Why This Matters
- **NOT a metaphorical violence simulator** — it's ingredient strategy
- **"Combat artifacts" = kitchen tools** (knives, pans, protective gear) for ingredient battle, not weapons against people
- **Real culinary skill required** — if ingredients are eliminated, you must adapt and cook what's left
- **Photo evidence** — proves it's real cooking, not roleplay

---

## ARENA VISUALIZATION TASK (Current Focus)

### Goal
Make the arena page **visually communicate what this product actually is** — a real, original, live-streamed cooking competition with genuinely novel battle mechanic.

### Existing Assets Inventory

#### Shared Mosaic Component
- `.arena-cell` (arena page) and `.puzzle-cell` (/sponsors/ page) are **same underlying pattern**
- SVG mosaic of individually addressable cells in concentric rings
- Each cell has drop-shadow filter (#arena-cell-shadow) and pointer cursor
- **Structure is intentional and must NOT change**

#### Dormant/Partial Effects (Already in codebase, not wired)

```
.puzzle-ripple / puzzle-ripple-expand
├─ Status: Exists on puzzle-cell (sponsors)
├─ Missing on arena-cell
├─ Timing: 0.45s
└─ Purpose: Click animation

.battle-blast / blast-ring keyframe
├─ Status: Exists in DOM but is-active = false
├─ Not wired to any trigger on arena page
├─ Issue: Hardcodes rgba(109, 206, 143, ...) — green no longer in brand
└─ Fix: Use current live accent like rgb(248, 210, 138) from .battle-arena-news__item a:hover

.arena-online-dot / arena-pulse keyframe
├─ CSS exists
└─ 0 instances currently rendered on arena page

battle-crown-banner / hero-battle-panel__crown
├─ Exists elsewhere in codebase
└─ Not surfaced on arena centre cell (even though real Crown holder exists in sidebar)
```

#### Artifact Naming Pattern (212 items total)

**Tiers:** COMMON (76), UNCOMMON (56), RARE (40), EPIC (24), LEGENDARY (16)

**COMMON–RARE (fully disciplined):**
- Every item is real kitchen tool or equipment
- Examples: Apple Corer, Blowtorch, Aga Cooker, Blast Chiller, Cast Iron Casserole
- **DO NOT CHANGE** — this tier is perfect

**EPIC–LEGENDARY GOOD EXAMPLES (target tone):**
- "Dagda's Cauldron" (Irish mythology + cauldron)
- "Cauldron of Lugh" (Lugh = Irish god + cooking vessel)
- "The Irish Kitchen" (cultural identity)
- "The Eternal Apron" (culinary + timeless)
- "The Midnight Fridge" (vivid imagery + kitchen)
- **Pattern:** Irish mythology OR vivid culinary imagery fused with real/near-real kitchen object

**EPIC–LEGENDARY BAD EXAMPLES (DO NOT REPEAT):**
- "Dragon Scale Shield" (generic fantasy)
- "Excalibur Cleaver" (Western medieval, not Irish)
- "Poseidon's Trident" (Greek, not culinary)
- "Grail Chalice" (religious, out of scope)
- "Aegis Stockpot" (Greek mythology)
- "The CulinEire Sword" (weapon-like, wrong tone)
- "Boss Slayer's Ladle" (gaming combat metaphor, breaks "combat is ingredients" theme)
- **Pattern:** Generic Western fantasy / combat tropes with no Ireland/cooking tie

**Action:** Rewrite EPIC/LEGENDARY items matching bad patterns to good patterns (keep attack/defence/boost values, only rename)

#### Custom Art Assets
- Hand-drawn default avatars (male/female/neutral, 1254x1254 PNGs at `/static/images/`)
- These are original brand art
- Chef avatars on rankings page exist
- **Use these as visual reference** for how chef is represented — not generic initials placeholders

#### Crown Mechanic
- Winning battle grants Crown for 24h
- Shown on winner's public profile + sidebar ("CROWN HOLDER" widget)
- This is real, time-bound state (not decorative)
- Already tracked in DB: ChefBattleProfile.crown_until

---

## ARENA IMPLEMENTATION STEPS

### Step 1: Port Click-Ripple to Arena Cell
**What:** Apply same interaction `.puzzle-cell` has (`.puzzle-ripple`, `puzzle-ripple-expand`, 0.45s) to `.arena-cell`

**How:** Reuse existing class/keyframe if straightforward; duplicate only if reuse impractical

**File:** `static/css/hero_switcher.css` or relevant arena stylesheet

**Verification:** Click any arena-cell and confirm timing/easing matches puzzle-cell on `/sponsors/`

---

### Step 2: Fix Residual Green in Blast-Ring
**Problem:** `blast-ring` keyframe hardcodes rgba(109, 206, 143, ...) — green no longer in brand palette

**Solution:** Replace with current live accent color
- Example: `rgb(248, 210, 138)` from `.battle-arena-news__item a:hover`
- Or confirm newer standardized accent exists before assuming

**Verification:** Grep full codebase for `rgba(109, 206, 143` — should be 0 matches after

---

### Step 3: Surface Real Crown Holder in Arena Centre
**What:** Connect battle-crown-banner / hero-battle-panel__crown to `.arena-cell--centre`

**Goal:** Current Crown holder (real data from DB, already shown in sidebar) visible at arena centre with actual 24-hour framing

**Data flow:**
```
ChefBattleProfile.crown_until (DB)
  → Selector: is_crown_holder_now(user_id)
  → Template context: current_crown_holder
  → Render in .arena-cell--centre with crown_until countdown
```

**NOT:** Generic "champion" badge invented for this task  
**YES:** Real crown_until timestamp, real holder, real 24h urgency

**Verification:** Confirm Crown holder shown at arena centre matches sidebar "CROWN HOLDER" widget value

---

### Step 4: Wire Blast-Ring to Real Win Event
**What:** Trigger `blast-ring` animation when cell's chef just won and claimed crown

**Find:** Where blast-ring already fires elsewhere in app (likely on battle win)

**Wire:** If same event is observable on arena page (e.g., a cell's chef winning + crown claim), trigger it there

**NOT:** Fabricate fake win state to force this to run

**Verification:** Win a test battle, confirm blast-ring fires on corresponding arena cell

---

### Step 5: Connect Arena-Online-Dot to Real Presence Data
**Check:** Is spectator/online presence data already tracked in app?

**If YES:** Wire `arena-online-dot` to it on occupied or spectator cells

**If NO:** Report as gap — do NOT simulate fake online status

**Data possibility:**
- WebSocket presence (Phase 2+)
- SSE presence (future)
- Simple "viewed in last 5 min" flag

**Verification:** Confirm online dot appears only on cells with real spectators/viewers

---

### Step 6: Curate EPIC/LEGENDARY Artifact Names

**Task:** Rewrite entries in EPIC/LEGENDARY tiers matching bad-examples pattern to follow good-examples pattern

**Rules:**
- ✓ Irish mythology or vivid culinary imagery fused with real/near-real kitchen object
- ✓ Keep attack/defence/boost values unchanged
- ✗ Only naming changes (no stat changes)
- ✗ Do NOT touch COMMON, UNCOMMON, RARE (they're perfect)

**Example rewrites:**
- "Dragon Scale Shield" → "Lugh's Protective Apron" (mythology + cooking gear)
- "Excalibur Cleaver" → "Ancient Chef's Cleaver" (remove Arthurian, make culinary)
- "Boss Slayer's Ladle" → "Dagda's Sacred Ladle" (remove gaming, add Irish)

**Verification:** Spot-check 5 rewritten EPIC/LEGENDARY names against negative_prompt list

---

### Step 7: Verify Chef Representation in Occupied Cells
**Check:** What currently renders inside occupied (`.arena-cell--chef`) cells?

**If:** Generic initials placeholder → Fix to use real avatar system
**If:** Already real avatars → No change needed, just report verified

**Avatar system reference:**
- Uploaded chef photo, OR
- Male/female/neutral default from `/static/images/`

**Verification:** Load arena page, confirm occupied cells show real chef avatars, not initials

---

## NEGATIVE PROMPT (DO NOT DO THIS)

❌ Do not depict combat as physical violence against person
- In copy: no "strike down", "defeat enemy", "crush opponent"
- In iconography: no weapons, blood, death imagery
- In animation: no violent impact effects
- Correct framing: "ingredient battle", "tactical selection", "ingredient lock"

❌ Do not alter arena-puzzle-container geometry
- Ring count, cell count, path/polygon shapes are fixed

❌ Do not change per-rank fill color progression (ring-1 through ring-9)

❌ Do not replace #arena-cell-shadow filter or introduce different shadow technique

❌ Do not introduce new color palette, typography, or component not in codebase

❌ Do not invent business logic (online status, crown eligibility, battle state, win events) that doesn't exist
- Surface the gap instead of guessing

❌ Do not touch /sponsors/ or puzzle-cell itself — it's the reference, not the target

❌ Do not rewrite COMMON, UNCOMMON, RARE artifact names — they're correct

❌ Do not introduce generic Western-fantasy naming anywhere

---

## ARTIFACT RARITY SYSTEM (DO NOT CHANGE TIERS)

### COMMON (76 items) — Examples
Apple Corer, Apron, Baking Pan, Basting Brush, Bench Scraper, Blender, Bread Knife, Bottle Opener, Butter Dish, Cake Knife, Can Opener, Ceramic Knife, Cheese Grater, Chef's Knife, Cleaver, Colander, Cookie Sheet, Cooling Rack, Corkscrew, Cutting Board, Deck Scraper, Deli Knife, Digital Scale, Dish Brush, Dish Rack, Double Boiler, Dough Scraper, Egg Beater, Egg Separator, Fillet Knife, Fish Knife, Fondue Pot, Food Processor, Freezer Bag, Garlic Press, Glass Measuring Cup, Griddle, Grilling Pan, Grilling Tongs, Grill Pan, Grill Scraper, Grinder, Grindstone, Hammer, Handheld Mixer, Hand Whisk, Heat Diffuser, Honing Steel, Hot Pad, Ice Cream Maker, Ice Cream Scoop, Ice Pick, Ice Tongs, Infuser Basket, Instant-Read Thermometer, Iron Skillet, Juicer, Kettle, Knife, Knife Block, Knife Sharpener, Ladle, Lemon Squeezer, Meat Cleaver, Meat Mallet, Meat Thermometer, Measuring Cup, Measuring Spoon, Metal Colander, Metal Mixing Bowl, Microplane, Mixing Bowl, Mortar & Pestle, Mozzarella Fork, Muffin Tin, Mushroom Knife, Nesting Bowls, Nesting Spoon, Ovenproof Skillet, Paint Brush

### UNCOMMON (56 items) — Examples
Aga Cooker, Bain-Marie, Pasta Machine, Pressure Cooker, Rotisserie, Salamander, Sous Vide Precision Cooker, Stand Mixer, Steam Oven, Tagine, Tamagoyaki, Mandoline Slicer, Meat Saw, Microwave Oven, Milk Frother, Mini Chopper, Mortar Pestle (premium), Muddler, Nocciola Roller, Offset Spatula, Oyster Knife, Pasta Maker, Paring Knife, Pastry Bag, Pastry Wheel, Peeler, Pepper Grinder, Pizza Cutter, Pizza Peel, Plate Warmer, Poacher, Poaching Pan, Potato Ricer, Pound Cake Pan, Pressure Cooker, Quenelle, Range Hood, Ravioli Maker, Rolling Pin, Rotisserie Spit, Rustic Bread Knife, Salad Spinner, Salt Crock, Saucepan, Saute Pan, Scale (digital), Seafood Knife, Sealing Machine, Serrated Knife, Shears, Sheet Pan, Skewers (metal), Skimmer, Slotted Spoon, Smoker, Snips

### RARE (40 items) — Examples
Blast Chiller, Blowtorch, Brander, Broiler, Calphalon, Cast Iron Casserole, Ceramic Brazier, Chefs Torch, Chinois, Combi-Oven, Convection Oven, Copper Cookware Set, Crepe Maker, Cryogenic Chamber, Dehydrator, Dutch Oven, Earthenware Pot, Electric Grill, Electric Kettle, Emile Henry, Espresso Machine, Fermentation Crock, Fire Pit, Flat Top Griddle, French Press, Frying Basket, Frying Pan (premium), Grill Master Set, Halogen Oven, Heat Lamp, Hibachi, High-Speed Blender, Hobnail Cookware, Instant Pot, Japanese Knife Set, Kamado Grill, Knife Set (premium), La Cornue, Lava Stone Grill, Mandoline (premium), Marble Mortar

### EPIC (24 items) — MUST REWRITE if bad patterns

Current examples (some need rewrite):
- Dagda's Cauldron ✓
- Cauldron of Lugh ✓
- The Irish Kitchen ✓
- The Eternal Apron ✓
- The Midnight Fridge ✓
(+ others, some may have bad examples mixed in)

### LEGENDARY (16 items) — MUST REWRITE if bad patterns

Current examples (some need rewrite):
- Excalibur Cleaver ❌ → Rewrite to Irish mythology + kitchen
- Dragon Scale Shield ❌ → Rewrite to cooking-focused
- Poseidon's Trident ❌ → Rewrite
(+ others)

---

## VERIFICATION CHECKLIST

Before declaring arena visualization complete:

1. ✓ Click any arena-cell and confirm ripple timing matches puzzle-cell
2. ✓ Grep full codebase for `rgba(109, 206, 143` — result: 0 matches
3. ✓ Confirm Crown holder at arena centre = sidebar "CROWN HOLDER" value
4. ✓ Confirm no new console errors on `/chef-battle/arena/`
5. ✓ Spot-check 5 rewritten EPIC/LEGENDARY names against negative_prompt
6. ✓ Verify blast-ring fires on real win event only
7. ✓ Verify arena-online-dot reflects real presence data or report gap
8. ✓ Verify occupied cells show real chef avatars or report placeholder status

---

## CURRENT LIMITATIONS/GAPS

**As of v2.5.171:**

1. **Spectator/online presence data** — Not yet tracked
   - Gap: Can't wire arena-online-dot to real data
   - Dependency: Phase 2 requires real presence tracking (SSE/WebSocket)

2. **Combat logs not yet rendering** — Combat Phase 4 not implemented
   - Gap: blast-ring has no real combat event to wire to yet
   - Dependency: Phase 4 combat engine required for full implementation

3. **Artifact names audit** — EPIC/LEGENDARY cleanup needed
   - Task: Manual rewrite of bad-pattern names
   - Effort: Medium (identify 5-10 bad names, rewrite each)

**These are not blockers for Phase 1** — they're future work for Phase 2+ or cosmetic enhancement.
