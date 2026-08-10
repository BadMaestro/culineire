# MOVES ECONOMY — Battle Energy Rules

## Author note
Defined by project creator. "Силы" (moves/energy) is the core resource
of Chef's Battle. It gates participation and rewards activity.

> **SETTLED, X07, Owner 2026-08-10: THE DOCUMENT MATCHES THE CODE.** Earn
> values below were 2/2/5/1; `energy_service.py` has run 5/5/10/1 all along.
> No code changed; the table and the "previous values" note are corrected.
>
> **SETTLED, X08, Owner 2026-08-10: THE DOCUMENT MATCHES THE CODE.** Combat
> round investment was documented as 1–3; `COMBAT_MOVES_MAX` in
> `chef_battle/services.py` has run 1–5 all along. No code changed.

---

## Earning moves

| Source | Moves earned | Notes |
|--------|-------------|-------|
| Recipe published (approved) | +5 | Per approved recipe (`EARN_RECIPE_PUBLISHED`) |
| Article published (approved) | +5 | Per approved article (`EARN_ARTICLE_PUBLISHED`) |
| Sponsorship slot purchase | varies | 5€ = 5 moves, see sponsorship mechanic below |
| Battle win | +10 | `EARN_BATTLE_WON` |
| Battle participation | +1 | `EARN_BATTLE_PARTICIPATION` |
| Pinch published | +1 | `EARN_PINCH_PUBLISHED` |
| Like received | +1 | `EARN_LIKE_RECEIVED` |

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
| Combat round investment | 1–5 moves per round (`COMBAT_MOVES_MIN`/`COMBAT_MOVES_MAX`, max_bonus per item) |

---

## Minimum balance to issue a challenge

**A chef must have at least 10 moves to issue a challenge.**

If balance < 10, the "Issue Challenge" button is hidden or disabled with a
message explaining how to earn more moves.

---

## Previous values (now changed)

| Field | Old value | Value this doc used to claim | Actual running value (`energy_service.py`) |
|-------|-----------|-------------------------------|----------------------------------------------|
| EARN_RECIPE_PUBLISHED | 3 | 2 | 5 |
| EARN_ARTICLE_PUBLISHED | 2 | 2 | 5 |
| EARN_BATTLE_WON | — | 5 | 10 |
| EARN_BATTLE_PARTICIPATION | — | 1 | 1 (unchanged) |

This table itself drifted from the code (X07, Owner 2026-08-10) — kept for history, not as current spec. The "Earning moves" table above is the current spec.
