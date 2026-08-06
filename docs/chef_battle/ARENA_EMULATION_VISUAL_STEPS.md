# Arena emulation — the steps the Owner wants to SEE

**Status:** OPEN and being filled. The Owner dictates; Bolt records here.
**Opened:** 2026-08-06, by the Owner's order.

## Why this file exists

On 2026-08-06 the Master Console got a Battle Cancellation Simulation built as
step cards: three columns of text saying what was on the screen, what the site
enforced and what changed. The Owner's answer, verbatim:

> «записывай шаги которые я хочу визуально видеть в эмуляции (не в сранном
> формате как на скриншоте), а в живую на арене, а вот эту вот хуйню удали и
> больше никогда мне подобную чушь не показывай»

The panel was deleted the same day (v2.5.842). What it described was not wrong;
being a description was the whole problem. **He checks the product by looking at
the arena.** Prose about behaviour proves nothing and costs him time — he wrote
the rules, he does not need them read back.

So this file is not a screen. Nothing here is ever rendered to him. It is the
specification of what must become **visible on the live arena** when an
emulation runs, and it is the acceptance list that emulation is measured
against.

## The rule this file works under

Every step below is shown by **doing it** — a real battle, real chefs, real
lifecycle transitions through the real services. `chef_battle/emulation.py`
already drives exactly that: `start_emulation()` creates the battle between the
two bots and `emulation_step()` advances precisely one lifecycle stage, without
short-circuiting a single service. The Owner presses a step and watches the
arena move.

Two facts already established and not to be re-litigated:

- The emulation bots (`EMU_CHEFS`) are exempt from the 180-second online window
  since v2.5.840, so they stand on the arena permanently. A test chef has no
  browser and would otherwise be invisible from birth.
- **Open, and it belongs to A09 (unassigned):** the two fighters of an ACTIVE
  battle vanish from the arena entirely when offline. The bout runs and nobody
  stands in the ring. Until A09 lands, several steps below cannot be seen at
  all, no matter how correct the backend is.

## The steps

Each row states the ONE thing the Owner must be able to see with his eyes.
Nothing here is accepted on a passing test; it is accepted when he sees it.

| # | Trigger | What must be visible ON THE ARENA | State |
|---|---|---|---|
| 1 | Emulation starts | Both bots standing in their own rank rings, named, not in the centre | LANDED v2.5.840 |
| 2 | Both press Ready | The pair leaves the rings and walks to the centre — the move itself, not a jump | TO SPEC (A09) |
| 3 | Battle opens | The centre pair reads as a confrontation: who against whom, the theme, the phase | TO SPEC |
| 4 | Phase advances | The lifecycle rail steps forward and the arena changes with it, every stage | TO SPEC |
| 5 | A withdrawal is asked for | Something on the arena says this battle is in question — the asking chef marked, the pair not simply gone | TO SPEC |
| 6 | The other chef answers | The arena shows the answer landing, still unsettled, awaiting the moderator | TO SPEC |
| 7 | The moderator rules | The verdict lands on the arena: the battle leaves the centre and the ring returns to the floor | TO SPEC |
| 8 | Penalty applied | The penalised chef's own numbers change where they are displayed, live, in the same poll | TO SPEC |
| 9 | Battle cancelled | The floor reads OPEN, the pair is back in the rings, nothing is left half-drawn | TO SPEC |

**TO SPEC** means the Owner has not yet said what it should look like. He fills
those in; nobody guesses on his behalf. What is on the screen, its colour and
its shape are his (AGENTS.md 17.13) — the one rule this whole episode came from.

## What is NOT allowed as an answer to any row above

- A text card, a table, a list of "what changes", or any panel that describes a
  step instead of performing it.
- A screenshot of a mockup.
- A passing test presented as the result. Tests are the floor, not the evidence.
