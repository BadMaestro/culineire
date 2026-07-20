# Chef Battles Arena — Interaction Parity: Implementation & Audit Report

**Date:** 2026-07-01
**Scope reference:** `Final Arena Prompt.yaml` — *MASTER BRIEF: CHEF BATTLES ARENA — SURFACE THE REAL MECHANIC* (7 numbered steps + constraints + verification list).
**Target surface:** `https://culineire.ie/chef-battle/arena/` and the shared battle-cursor / blast overlay used site-wide.
**Deployment model:** all changes are live on production. Flow: local edit → `git push` → server `git pull` + `collectstatic --no-input` + `systemctl restart unit`. Artifact renames additionally required `loaddata` (the fixture is a one-time DB seed, not read at runtime).

> **Note on brief premises.** Several of the brief's `dormant_or_partial_effects` assumptions turned out to be stale on inspection — the ripple, the online-dot presence wiring, and the real-avatar rendering were **already built and functioning**. Those steps were therefore *verified* rather than *implemented*. This is called out per-step below and is relevant to the audit: "no change needed" is a deliberate, checked conclusion, not an omission.

---

## 1. Per-step status (the 7 brief steps)

| # | Brief step | Status | Nature of work |
|---|-----------|--------|----------------|
| 1 | Port click-ripple to arena-cell | ✅ Done | Already existed; constants aligned for exact parity |
| 2 | Fix residual green in blast-ring | ✅ Done | Colour replaced; see caveat 6.2 |
| 3 | Surface real Crown holder at arena centre | ✅ Done | New backend branch + new render branch |
| 4 | Wire blast-ring to a real win event | ✅ Done (wired) | New; not yet observed firing from a genuine completion — see 6.3 |
| 5 | Connect arena-online-dot to real presence | ✅ Verified | Already fully wired; no change |
| 6 | Curate EPIC/LEGENDARY artifact names | ✅ Done | 13 items renamed + `loaddata` on prod |
| 7 | Verify chef avatar rendering in occupied cells | ✅ Verified | Already correct; no change |

### Step 1 — Click-ripple parity
- **Found:** `fireCellRipple()` already existed in `static/js/arena_puzzle.js` and was already wired to cell and spectator clicks, using the identical JS `requestAnimationFrame` + SVG-circle mechanism as `static/js/sponsors_puzzle.js`. It differed only in constants (`MAX_R` 90 / `DURATION` 380 ms vs puzzle's 110 / 420).
- **Change:** aligned constants to `MAX_R = 110`, `DURATION = 420` for verified timing/easing parity.
- **Commit:** `dae0ebce`.

### Step 2 — Residual green in blast-ring
- **Found:** `.battle-blast` (the win-celebration overlay) lives as an **inline `<style>` block in `templates/base.html`**, which is why the earlier site-wide green-removal pass (which scanned `static/css/*.css`) missed it. The `blast-ring` keyframe and card border hardcoded `rgba(109, 206, 143, …)` / `#6dce8f` — legacy brand green.
- **Change:** replaced with the standardised gold accent `rgb(200, 148, 42)` / `#c8942a`.
- **Commit:** `dae0ebce`.
- **Caveat (6.2):** two *other* text colours inside the same overlay (badge, winner name) remain legacy green, and three unrelated semantic uses of `#6dce8f` persist elsewhere. Details in §6.

### Step 3 — Crown holder at arena centre
- **Backend:** extracted the duplicated centre-cell logic from `arena()` and `arena_state()` into a shared `_arena_center(active_battle)` helper (`chef_battle/views.py`) and added a third branch: when no battle is active but a real Crown holder exists (`ChefBattleProfile.crown_until > now` — the same query already used by the site-wide `hero_battle_panel` context processor), the centre returns `type: "crown"` with the holder's name, avatar, profile URL and crown expiry.
- **Frontend:** `drawCentre()` in `arena_puzzle.js` renders a 3-line stack — crown emoji above the name, `CROWN HOLDER` label below — on a gold cell that links to the holder's author profile.
- **Commits:** `7e599ef6`, `d4c985ce` (crown positioned above the name, not inline).
- **Verified live:** centre showed `👑 GreenBear / CROWN HOLDER`, matching the sidebar `CROWN HOLDER` widget.

### Step 4 — Blast-ring wired to a real site-wide win event
- **Found:** `.battle-blast` had **zero JS trigger anywhere** in the codebase — markup and CSS existed but nothing ever showed it.
- **Backend:** `_arena_latest_result()` (`chef_battle/views.py`) returns the most recently `COMPLETED` battle with a winner (`winner`, `loser`, `result_reason`, `theme` — all real, already-stored fields; `result_reason` is already a ready-made `"Public vote: 5-3"` string). Added to both `arena()` and `arena_state()` JSON as `latest_result`.
- **Frontend:** `initBattleBlast()` seeds `_lastSeenResultId` from the page's own initial data on load (so an already-finished battle does not retroactively celebrate on a fresh page view); each 20 s poll calls `maybeCelebrate()`, which fires the overlay **only if `battle_id` changed** since last seen. Populates `#blast-winner` / `#blast-score` and wires the previously-dead `#blast-dismiss` button.
- **Scope decision (owner):** fires for **any** arena visitor when **any** battle site-wide completes, not just participants.
- **Design decision:** uses the project's existing lightweight polling pattern (`pingArena` / `pollArenaState` / `notifications_poll`); the project has no WebSocket/Channels/ASGI infrastructure and a ~20 s-latency ambient celebration does not warrant introducing it.
- **Commit:** `67322444`.
- **Verification limitation (6.3):** confirmed end-to-end via a manual render + dismiss cycle (overlay displays correctly, dismiss clears it, zero console errors). **Not yet observed firing from a genuine battle completion**, because no battle has completed on prod since deploy.

### Step 5 — Online-dot presence
- **Found already fully wired**, contradicting the brief's premise ("0 instances rendered"). The path is: `profile.last_seen_at` (updated by the 60 s `pingArena` heartbeat) → `is_online` in the JSON payload → `appendOnlineDot()` in `arena_puzzle.js` → `arena-pulse` CSS animation. The "0 instances" the brief observed simply reflects nobody being online at that moment, not a broken wire.
- **Change:** none. Verified correct.

### Step 6 — EPIC/LEGENDARY artifact names
- **Found:** the true counts are **21 EPIC + 11 LEGENDARY** (32 total), not the 24 + 16 the brief stated. Several already matched the target Irish-myth / culinary-object pattern (`Cauldron of Lugh`, `The Irish Kitchen`, `Dagda's Cauldron`, `The Eternal Apron`, `Manannán's Cloak`).
- **Change:** rewrote the **13** items carrying generic Western-fantasy / Greek / Norse naming (full old→new table in §4). Only the `name` field changed — `description`, `effect_type`, `effect_value`, `token_cost`, `rarity` untouched.
- **Source of truth:** `chef_battle/fixtures/battle_artifacts.json`. Applied to the production DB via `loaddata` (verified in the DB and on the live gallery page).
- **Commit:** `b767097d`.

### Step 7 — Chef avatar rendering
- **Found correct.** `RecipeAuthor.display_avatar_url` (`recipes/models.py`) always returns either the uploaded photo or one of the illustrated `male` / `female` / `neutral` defaults — never a generic-initials placeholder. `appendAvatarToCell()` in `arena_puzzle.js` already renders it as a real clipped SVG `<image>`.
- **Change:** none. Verified.

---

## 2. Owner-requested extensions (beyond the 7 brief steps)

These were requested by the owner during the work and are **not** part of the original brief; listed for completeness.

### 2.1 Battle-cursor (knife + honing steel) reuse
The owner identified the pre-existing custom hover cursor (`static/js/battle_cursor.js` + `static/css/battle_cursor.css` + `static/images/battle_cursor.svg`) — a crossed carving-knife-and-steel that follows the pointer with a honing/spark animation — previously wired only to the header nav link and the wordmark "Issue a Challenge" CTA, and asked to reuse it.

- **`battle_cursor.js` rewritten** from direct per-element binding to **event delegation** on `document` (`pointerover` / `pointerout` / `pointermove`, which bubble — unlike `pointerenter`/`pointerleave`). This is required because arena cells are drawn by JS after load and **redrawn every 20 s**; static binding would never attach to them.
- **Applied to** combat/challenge CTAs: "Send Challenge", "Challenge This Chef", "Accept", "Make Move".
- **Applied to arena cells, then scoped** (owner refinement): the cursor now appears **only on chefs who are in an active battle** (`chef.in_battle`), not on every enrolled/online chef in the ring. `in_battle` becomes true the moment a challenge is accepted and a `Battle` is created, and clears on completion — i.e. it already tracks the "preparing for / in a duel" state.
- **Commits:** `fbcc99fc` (extension), `470d0631` (scope to `in_battle`).

### 2.2 Arena tooltip "View Profile" button centering
Found while testing the cursor: the tooltip's button carried two conflicting component classes (`arena-tooltip__link` + generic `btn-primary` from `base.css`'s `@layer base`, `min-height: 48px`), leaving the text near the top of an oversized box. Removed the redundant `btn-primary`, switched to `inline-flex` + `align-items: center`, and reduced `line-height` to minimise residual sub-pixel glyph-leading asymmetry.
- **Commits:** `9f7f1736`, `bd88de6f`, `39b3e190`.

---

## 3. Files changed

| File | What changed |
|------|--------------|
| `chef_battle/views.py` | `_arena_center()` helper + `crown` branch (step 3); `_arena_latest_result()` + `latest_result` in both arena payloads (step 4); Roadmap "Phase FE-2" entry |
| `chef_battle/fixtures/battle_artifacts.json` | 13 EPIC/LEGENDARY `name` values rewritten (step 6) |
| `static/js/arena_puzzle.js` | Ripple constants (step 1); crown centre render (step 3); blast poll/dedup/trigger (step 4); battle-cursor classes on `in_battle` cells (ext 2.1) |
| `static/js/battle_cursor.js` | Rewritten to event delegation (ext 2.1) |
| `static/css/battle_cursor.css` | (unchanged logic; referenced by ext 2.1) |
| `static/css/arena.css` | Tooltip button centering (ext 2.2) |
| `templates/base.html` | Blast-ring green → gold (step 2) |
| `templates/chef_battle/arena.html` | Removed redundant `btn-primary` from tooltip link (ext 2.2) |
| `templates/chef_battle/battle_detail.html` | `battle-cursor-target` on "Make Move" (ext 2.1) |
| `templates/chef_battle/challenge_form.html` | `battle-cursor-target` on "Send Challenge" (ext 2.1) |
| `templates/chef_battle/challenge_list.html` | `battle-cursor-target` on "Accept" (ext 2.1) |
| `templates/chef_battle/chef_profile.html` | `battle-cursor-target` on "Challenge This Chef" (ext 2.1) |

---

## 4. Artifact renames (step 6) — old → new

| pk | Rarity | Effect | Old name | New name |
|----|--------|--------|----------|----------|
| 65 | Epic | attack | Dragon Wok | Cú Chulainn's Wok |
| 70 | Legendary | attack | Excalibur Cleaver | Claíomh Solais Cleaver |
| 71 | Legendary | attack | Prometheus Flame | Goibniu's Flame |
| 72 | Legendary | attack | Poseidon's Trident | Manannán's Trident |
| 73 | Legendary | attack | The CulinEire Sword | The CulinEire Carving Knife |
| 160 | Epic | defence | Mithril Oven Gloves | Newgrange Oven Gloves |
| 161 | Epic | defence | Dragon Scale Shield | Aoife's Chainmail Glove |
| 162 | Epic | defence | Aegis Stockpot | Tara's Stockpot |
| 163 | Epic | defence | Olympian Bain Marie | The Endless Bain Marie |
| 164 | Epic | defence | Phoenix Casserole | Brigid's Hearth Casserole |
| 165 | Epic | defence | Viking Stockpot | Fianna's Stockpot |
| 166 | Epic | defence | Titan Roaster | Balor's Roaster |
| 169 | Legendary | defence | Grail Chalice | The Ardagh Chalice |

Roster deliberately varied (Cú Chulainn, Aoife, Brigid, Balor, Goibniu, Manannán, the Fianna, Tara, Newgrange, the Ardagh Chalice, Claíomh Solais) rather than reusing one figure. All effect/cost/description values unchanged.

---

## 5. Verification performed (against the brief's `verification` list)

| Brief verification item | Result |
|-------------------------|--------|
| Click any arena-cell → same ripple timing/easing as puzzle-cell | ✅ Constants now identical (110 px / 420 ms); confirmed in code and via live click |
| Grep full codebase for `rgba(109, 206, 143` → zero matches | ✅ Zero live matches. (The only textual hit is a descriptive string inside the Roadmap detail in `views.py`, not a colour value.) |
| Crown holder at arena centre matches sidebar `CROWN HOLDER` | ✅ Live: centre `GreenBear` == sidebar `GreenBear` |
| No new console errors on `/chef-battle/arena/` | ✅ Zero errors across all test loads |
| Spot-check 5 rewritten names vs negative_prompt | ✅ All 13 checked; none use swords-as-weapons / dragons / Greek-Norse tropes |

**Negative-prompt adherence (confirmed):** no changes to puzzle geometry / ring count / cell count / shapes; no changes to per-rank fill-colour progression; `#arena-cell-shadow` filter untouched; no new palette or typography; no fabricated business logic (crown, presence, win-events all read real data); `/sponsors/` and `puzzle-cell` untouched; COMMON/UNCOMMON/RARE names untouched; no Western-fantasy naming introduced.

---

## 6. Open items / remaining work

### 6.1 — Large unbuilt feature: battle-lifecycle choreography (owner vision)
The owner has described a full arena "live theatre" experience that is **not built**:
- Chefs visually **relocate** by battle state: challenge issued → both accept → move to adjacent cells **facing each other** (prep) → at battle time both move to the **centre** as **two octagonal cells facing each other with a `VS`** → on completion return to their ring cells.
- While a battle is live, clicking a battling chef's cell opens an **in-arena spectator popup** to watch/chat/vote/support across all stages, **without leaving the arena**.

**Important for scoping:** the *end* of this flow already exists and must not be rebuilt — the full battle experience (live chat, voting, gifts/artifacts, all lifecycle stages), winner determination, Elo rating (+25/−15), stats, gift payouts, crown award, the completion **Blast** (now wired), and notifications all already live in the backend and the `battle_detail` page. The genuinely new work is the **arena visualisation/choreography layer** and the decision of whether the spectator popup **embeds** the live battle (new, partially duplicates `battle_detail`) or **links to** the existing `battle_detail` page. Recommended: phase it, and confirm the popup approach before building, to avoid duplicating a legally-sensitive (18+, tokens, gifts) subsystem.

### 6.2 — Residual legacy green (colour), pending owner decision
- Inside the same blast overlay (`templates/base.html`), the **badge** (`.battle-blast__badge`, `#1a6b3a` on `#d6f5e0`) and **winner name** (`.battle-blast__winner`, `#1a6b3a`) text still use legacy green. Now visible for the first time because the overlay actually renders (step 4). Left untouched pending an explicit owner call — same class of decision as the intentionally-kept `.mon-card--green`.
- Three unrelated semantic uses of `#6dce8f` persist and are **outside the brief's named target** (the brief named only `rgba(109, 206, 143)`): `.battle-combat__turn--yours` and `.battle-pip__turn--yours` (`chef_battle.css:914, :1081`) and `.mod-tool-link--done` (`moderation.css:595`) — all "your turn / done" success indicators.

### 6.3 — Win-event blast not yet observed from a genuine completion
Step 4 is wired and verified via manual render + dismiss, but no real battle has completed on prod since deploy, so a live end-to-end firing from an actual `COMPLETED` battle has not been observed. Recommend confirming on the next genuine battle completion.

### 6.4 — Battle-cursor scope on CTAs (open question)
The knife+steel cursor is currently on all four combat CTAs ("Send Challenge", "Challenge This Chef", "Accept", "Make Move"). Only "Make Move" occurs during an active battle; the other three are pre-battle. Whether to scope the cursor off the pre-battle CTAs is an open owner decision.

---

## 7. Commit log (traceability)

Newest first. All merged to `main` and deployed.

| Commit | Subject |
|--------|---------|
| `470d0631` | fix: scope arena cutlery cursor to chefs in an active battle only |
| `31352ec2` | docs: mark Phase FE-2 roadmap items done (crown, blast-ring, artifacts) |
| `67322444` | feat: wire blast-ring to real site-wide battle completions (step 4) |
| `b767097d` | content: rewrite generic-fantasy EPIC/LEGENDARY artifact names to Irish myth pattern (step 6) |
| `d4c985ce` | fix: crown emoji sits above the name at arena centre |
| `7e599ef6` | feat: surface real Crown holder at arena centre (step 3) |
| `cdb1d4ff` | docs: add Phase FE-2 roadmap entry |
| `39b3e190` | fix: reduce arena tooltip button line-height |
| `bd88de6f` | fix: arena tooltip button text vertical centering — flex |
| `9f7f1736` | fix: arena tooltip View Profile button — conflicting component classes |
| `fbcc99fc` | feat: extend battle-cursor to arena cells and combat CTAs |
| `dae0ebce` | arena: align click-ripple constants with puzzle-cell, fix residual green in blast-ring (steps 1 + 2) |

*Tracked in-app at `/chef-battle/roadmap/` under "Phase FE-2 — Arena Mechanic Legibility (Interaction Parity)".*
