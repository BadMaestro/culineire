# Handoff → CrestedTen: Arena Battle-Lifecycle Choreography

**From:** Bolt (handed off near usage limit, 2026-07-02)
**State at handoff:** working tree CLEAN, everything committed & deployed at `b6f0dc2c`. **No choreography code written yet** — only `drawCentre()` / `appendAvatarToCell()` were read. Nothing is half-finished.
**Owner instruction:** build the arena battle-lifecycle choreography. Go **one phase at a time**, verify each on prod, and **ask the owner when a decision is flagged**.

Companion doc (audit of everything already done this session): `docs/chef_battle/ARENA_INTERACTION_PARITY_AUDIT_REPORT.md` (may be uncommitted/untracked — owner had not decided whether to commit it; do not rely on it existing in a fresh checkout).

---

## The vision (owner's own words, paraphrased)

1. One chef challenges another → both still in their own ring cells.
2. Challenge **accepted by both** → the two chefs **leave their ring cells and move to two adjacent cells facing each other** (preparation).
3. **Battle time reached / battle starts** → both move to the **centre** and occupy **two full octagonal cells facing each other with `VS` between them** (Chef 1 vs Chef 2).
4. They stay centre-staged for the whole duel; on completion they **return to their original ring cells**.
5. While centre-staged, spectators **click a chef cell → popup** to watch/chat/support across all stages.
6. Spectators vote → results.
7. On result → the **site-wide Blast!** fires with the winner's name (ALREADY BUILT this session).
8. Winner gets notification + bonuses; both ratings & stats update (ALREADY BUILT — backend).

---

## Phase 1 — Two-cell VS centre  ← START HERE

**File:** `static/js/arena_puzzle.js`, function `drawCentre(g, center)`, branch `center.type === 'active_battle'`.

**Now:** draws ONE octagon (`fill #c8942a`) + a single `"<A> vs <B>"` text + `"BATTLE IN PROGRESS"`.

**Target:** replace with **TWO full octagonal cells facing each other**:
- left cell = `center.challenger`, right cell = `center.opponent`;
- each shows the chef's avatar (clipped into the octagon);
- `VS` text between them;
- optional small name label under each.

**Data is already provided** by the backend — `chef_battle/views.py` `_arena_center()` returns, for an active battle:
```
center = {type:'active_battle', battle_url, challenger:{name, avatar_url}, opponent:{name, avatar_url}}
```

**Geometry:** `CX = CY = 550`; centre zone radius `RING_RADII.centre = [0, 85]`. Suggested: two octagons radius ~46–50 at `(CX-44, CY)` and `(CX+44, CY)`, `VS` text at `(CX, CY)`. Tune visually with the owner (they iterate hard on spacing/centering).

**Reuse existing helpers:** `octagonPoints(cx,cy,R)` (returns a points string), `svgEl(tag, attrs)`, `pathFromPoints(points)`, and copy the `clipPath` + `<image preserveAspectRatio="xMidYMid slice">` avatar-clipping pattern from `appendAvatarToCell()` (approx lines 264–289). You will need octagon point PAIRS for the clip path — write a tiny local helper returning `[[x,y],…]` (mirror `octagonPoints` but return the array).

**Keep:** both cells `cursor:pointer`, click → `window.location.href = center.battle_url` (Phase 3 changes this); class `arena-cell arena-center--active`; `filter: url(#arena-cell-shadow)`; white stroke; gold `#c8942a` fill.

**MUST NOT (negative_prompt):** change ring geometry / ring count / cell count / shapes; change the `#arena-cell-shadow` filter; change per-rank fill-colour progression; introduce a new palette or typography.

### Verifying Phase 1 without a real battle
There is currently **no active battle on prod** (centre is crown/empty). **Do NOT create a fake battle in the prod DB** — it would fire the real site-wide Blast for live users and pollute stats. Verify with a **mock render in your own browser tab only**: temporarily expose the draw fn (`drawArena`/`drawCentre` live inside an IIFE, not global) e.g. `window.__arenaTest = drawArena;` during dev, then call it with a mock `center` payload (`type:'active_battle'`, real avatar URLs from `/static/images/` or `/media/`), screenshot, and **remove the throwaway hook before committing**. (This is how the Blast card was verified earlier — mock payload injected client-side, prod untouched.)

---

## Phase 2 — Movement / relocation (after owner sees Phase 1)

`drawArena()` currently draws `in_battle` chefs in their normal ring cells *and* fills the centre. Target behaviour:
- challenge accepted + `SCHEDULED` (start_time in future) → the two chefs **leave their ring cells** and render in **two adjacent cells facing each other** (prep);
- battle started (`status` in ACTIVE…VOTING, start_time passed) → they render **centre-staged** (Phase 1 two-cell VS);
- `COMPLETED` → back to their ring cells.

You will likely need the arena payload to tell the client **which battle each in_battle chef belongs to and its phase**, and `drawArena()` to **skip drawing those chefs in their ring positions** while centre-staged. Animating transitions between the 20 s redraws (`pollArenaState`) is non-trivial in SVG — **agree scope with the owner before over-building** (e.g. static relocation first, animation later).

Backend anchors: `Battle.status` (SCHEDULED, MENU_LOCKED, ACTIVE, AWAITING_SUBMISSIONS, REVEALED, COOKING, PRESENTATION, VOTING, COMPLETED, INGREDIENT_PENALTY, CANCELLED, DISPUTED), `Battle.start_time`. A chef is `in_battle` when challenger/opponent of a battle in `Battle.ACTIVE_STATUSES`.

---

## Phase 3 — Spectator popup (DECISION REQUIRED before building)

Clicking a battling chef's cell should open an in-arena popup to watch/chat/vote across all stages.

**Architectural fork — ask the owner first, do not guess:**
- **(A) Embed** the live battle inside an arena popup — new UI that must reuse the existing chat / vote / gift POST endpoints; **partially duplicates `battle_detail`**; touches 18+ / token / gift legally-sensitive flows.
- **(B) Link** — clicking a battling cell just navigates to the **existing `battle_detail` page** (full reuse, far less work).

---

## DO NOT REBUILD — already exists & deployed

- `battle_detail` page: live chat (8 s poll), voting, gifts/artifacts, all lifecycle stages.
- Winner determination, Elo rating (+25 / −15), stats, gift payouts, crown award.
- **Completion Blast overlay** — wired this session (`_arena_latest_result()` in `views.py` + `initBattleBlast`/`maybeCelebrate`/`fireBattleBlast` in `arena_puzzle.js`); fires site-wide for any arena visitor on any battle completing; dedup by `battle_id`.
- Crown-at-centre (`center.type==='crown'`), online-dot presence, real avatars, ripple parity.
- Notifications (`notifications_poll`).

Tracked in-app at `/chef-battle/roadmap/` under **Phase FE-2**.

---

## Open items inherited (from audit §6)

- **Green:** blast card badge (`.battle-blast__badge`) & winner (`.battle-blast__winner`) still legacy green `#1a6b3a`/`#d6f5e0` in the inline `<style>` of `templates/base.html`; plus 3 unrelated `#6dce8f` (`.battle-combat__turn--yours`, `.battle-pip__turn--yours` in `chef_battle.css`; `.mod-tool-link--done` in `moderation.css`). All await an owner call.
- Blast not yet observed firing from a **genuine** completed battle (only manual render+dismiss).
- Knife+steel cursor still on all 4 combat CTAs; owner may want it off the pre-battle ones (Send Challenge / Challenge This Chef / Accept), keeping only Make Move. Cursor on arena cells is already scoped to `chef.in_battle` only (`470d063`).

---

## Deploy & workflow reminders

- Flow: local edit → `git push` → SSH server `git pull` + `collectstatic --no-input` + `systemctl restart unit`. Fixtures (artifacts) also need `loaddata`.
- SSH: `wsl.exe -- bash -c "ssh -i ~/.ssh/culineire_linode -o StrictHostKeyChecking=no root@80.85.84.156 '…'"`; `.env` at `/srv/culineire/shared/.env`; settings module `config.settings`; project root `/srv/culineire/current`.
- **Owner tests on prod** and wants to approve before commits — respect that.
- **GreenBear pushes to `main` concurrently** — `git pull --no-edit` to merge before every push.
- No dev server / preview for this project; verify on prod (or client-side mock as in Phase 1).
