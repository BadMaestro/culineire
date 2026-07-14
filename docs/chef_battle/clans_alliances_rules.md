# CLANS, ALLIANCES & SEASON-WINNER PRIZE — Rules

## Author note
Defined by the project creator (owner) during the 2026-07-14 design session.
This file is the **canonical rules record**. Implementation/design detail lives
in `clans_design.md` (clan mechanics) and the observer-prize backend; those must
not contradict the rules below.

---

## 1. Clans

A **clan** is the real team unit of Chef's Battle (distinct from a *category*).

- A clan is a **name only** (e.g. `Fusion`, `Cyber Chef`) — the name itself is
  not tied to any cuisine or profession.
- Every clan has a **founder** (one chef) plus **members**.
- At creation the founder picks the **categories** the clan is comfortable
  working in. **Maximum 3 categories per clan.** A clan may not select every
  category.
- **Categories are the existing `Faction` taxonomy** — both cuisines
  (`kind=cuisine`, e.g. Italian, Molecular) and professions
  (`kind=specialty`, e.g. BBQ, Bakery, Dough work), mixed freely. A clan links
  to up to 3 `Faction` rows; no separate "category" table is introduced.
- A clan **appears / competes in each category it selected.** Different clans
  may select overlapping categories — this is allowed, not exclusive.

### Category vs. profession — they live on different levels

- A **category** is a clan-level choice (up to 3, set by the founder).
- A chef's **own profession/specialty stays at the chef level**, independent of
  the clan's categories.
- Worked example (owner's): chef **GreenBear** founds the clan **Fusion** and
  sets Fusion's own categories; but GreenBear's *personal* profession is **BBQ**,
  regardless of which categories Fusion picked.

### Season winner

- The **winning clan of a season** is the clan whose members scored the
  **highest total of seasonal points** — summed across all its members.
- Cuisine or profession is **irrelevant** to winning; only the members' combined
  seasonal score decides it.

### Open clan details (design lane — `clans_design.md`)

Left to the clan design pass, must not contradict the above: member cap, how the
founder admits members, and what happens to points when a member leaves.

---

## 2. Alliances

Alliances are **built as a foundation in Season 1** so the mechanic is not lost,
and **developed further in Season 2** once the site has traffic.

- **Clans may join into alliances.**
- In a battle, a clan may **call allied clans to help.**
- With allies involved the fight becomes a battle **of a cuisine**, not of a
  single recipe — e.g. *African BBQ* vs *Eastern European dishes (plov, etc.)*.
  The dispute is about **which cuisine is more popular this season**, not a
  single head-to-head recipe.

### Scope split

- **Season 1 (now):** minimal foundation only — the alliance entity, the
  clan↔alliance link, and the "call an ally into a battle" hook.
- **Season 2 (later):** the full cuisine-vs-cuisine popularity mechanic.

---

## 3. Season-winner prize — "Arena Observer"

A non-monetary prize awarded on top of the clan system.

- The **champion of the winning clan** (its top individual contributor) may
  **nominate 2 candidates from that same clan.**
- **No nomination → no role.** If the champion does not nominate within the
  window, the seats stay empty. There is **no fallback** to the next contributor.
- Each nominee receives a narrow **"Arena Observer"** role — **not** general site
  moderation (`has_bearseeker_privileges`). It grants a voice **only in Chef
  Battle disputes.**
- The observer's vote on a dispute is **advisory**: it is recorded and shown to
  the operator on the relevant `BattleReport`, but it does **not** block or
  weight the outcome. Final authority stays with the owner/operator.
- The role is **valid for the next season only** and **expires when that season
  ends.**

This prize applies to **every season's winning clan**, not only Season 1.
