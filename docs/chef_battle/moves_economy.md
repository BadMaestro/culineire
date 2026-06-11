# MOVES ECONOMY — Battle Energy Rules

## Author note
Defined by project creator. "Силы" (moves/energy) is the core resource
of Chef's Battle. It gates participation and rewards activity.

---

## Earning moves

| Source | Moves earned | Notes |
|--------|-------------|-------|
| Recipe published (approved) | +2 | Per approved recipe |
| Article published (approved) | +2 | Per approved article |
| Sponsorship slot purchase | varies | 5€ = 5 moves, see sponsorship mechanic below |
| Battle win | +5 | Existing rule |
| Battle participation | +1 | Existing rule |

## Sponsorship → Moves mechanic

Sponsors can earn battle moves by purchasing sponsorship slots.

| Slot price | Moves granted |
|-----------|--------------|
| €5 | 5 moves |
| €10 | 10 moves |
| €25 | 30 moves (bonus) |
| €50 | 65 moves (bonus) |

Exact tier structure TBD. Sponsorship is handled in the existing `/sponsors/`
system — moves are awarded when a sponsor payment is confirmed.

This mechanic is Phase 5+ and requires integration with sponsor payment flow.

---

## Spending moves

| Action | Cost |
|--------|------|
| Issuing a challenge | Requires minimum 10 moves in balance |
| Combat round investment | 1–3 moves per round (max_bonus per item) |

---

## Minimum balance to issue a challenge

**A chef must have at least 10 moves to issue a challenge.**

If balance < 10, the "Issue Challenge" button is hidden or disabled with a
message explaining how to earn more moves.

---

## Previous values (now changed)

| Field | Old value | New value |
|-------|-----------|-----------|
| MOVES_RECIPE_APPROVED | 3 | 2 |
| MOVES_ARTICLE_APPROVED | 2 | 2 (unchanged) |
