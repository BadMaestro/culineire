# Arena — what the Owner must SEE. Scenario A.

**Status:** SCENARIO A dictated by the Owner on 2026-08-06 and being built.
Scenario B follows. Bolt records; the Owner dictates; nobody guesses.

## Why this file exists

On 2026-08-06 the Master Console got a Battle Cancellation Simulation built as
step cards — three columns of text per step. The Owner's answer, verbatim:

> «записывай шаги которые я хочу визуально видеть в эмуляции (не в сранном
> формате как на скриншоте), а в живую на арене, а вот эту вот хуйню удали и
> больше никогда мне подобную чушь не показывай»

The panel was deleted whole in v2.5.842. Nothing in it was factually wrong;
**being a description was the problem.** He checks the product by looking at the
arena. This file is a specification and is never rendered to him.

## Scenario A — the Owner's words, and what each one means in the build

### A1. Two chefs of the same rank stand in the same ring. CORRECT ALREADY.

> «два шефа одного ранга на арене в одинаковом кольце, это правильно, так как
> правила гласят +1 или -1 к рангу от кольца — они оба Kitchen Porter стоят
> правильно, если бы один из них был бы Prep Chef — они должны были бы появиться
> в разных кольцах — но пока всё правильно»

Nothing to build. The ±1 rule is enforced in `services.py`: a challenge whose
two ranks differ by more than one position in `RANK_ORDER` is refused. A ring is
a rank, so chefs of the same rank share a ring by construction.

**State: CONFIRMED, no work.**

### A2. A challenge draws the two chefs together.

> «они нашли друг-друга и один кинул вызов другому — а второй ответил — значит
> шефы сближаются внутри своего кольца, либо шеф который на 1 ранг выше занимает
> позицию рядом со вторым шефом, но всё ещё в своём кольце — получается что всё
> равно две соты стоят рядом друг с другом»

Two chefs bound by an accepted challenge stand in **adjacent cells**:

- same rank → neighbouring cells of the one ring;
- one rank apart → each stays in HIS OWN ring, and the pair is aligned so the
  two cells sit against each other across the ring boundary. A chef never
  leaves his rank's ring.

This replaces scattering for those two: the renderer currently spreads idle
chefs by a hash of their slug and deliberately avoids neighbours.

**State: LANDED v2.5.844.**

### A3. Twelve hours to accept, and before that nothing is pinned.

> «на то, чтоб принять вызов по правилам — 12 часов, и пока вызов не принял —
> шефы могут пропадать с арены»

The acceptance window is twelve hours (his X05 ruling, v2.5.837). While a
challenge is merely PENDING the two chefs are ordinary chefs: they scatter, and
they vanish when they go offline, like anyone else. Pairing begins at
acceptance, not at the challenge.

**State: CONFIRMED, no work.**

### A4. Once accepted, they are never apart again.

> «вызов принят — таймер 12 часов запущен — оба шефа снова вернулись на арену
> когда вернулись на сайт и теперь они уже не появляются в рандомных сотах или
> ячейках — а они всегда стоят друг с другом — пока идёт подготовка к баттлу»

From acceptance until the battle starts, the pair's placement is **stable**: the
same two adjacent cells every time either of them comes back online, not a fresh
random cell per visit. Leaving and returning must not move them.

**State: LANDED v2.5.844**, same mechanism as A2 - the seat is keyed to the
battle id and which chef takes which cell is fixed by slug, so leaving and
returning cannot move either of them.

### A5. An accepted challenge is announced at the top.

> «когда вызов принят — оба шефа уже рядом и теперь их предстоящий баттл
> анонсируется вверху где Next Battle:»

**State: ALREADY LANDED** (X01, v2.5.822→825, refined v2.5.834). An accepted
challenge is a SCHEDULED battle with a future start, which is exactly what the
board lists.

### A6. The board is a queue, ordered strictly by the clock, and READY jumps it.

> «когда предстоящих битв на арене будет несколько — они выстраиваются в поле
> Next Battle: один за одним, в два ряда — но строго по таймеру, чем меньше
> времени остаётся до боя — тем ближе к надписи Next Battle они передвигаются,
> если оба шефа нажимают кнопку "готов", а на таймере к примеру ещё было 10
> часов и они стояли в конце очереди, значит их пиля перемещается ближе в
> зависимости от очереди — оба готовы — таймер до матча 15 минут, если это
> ближайший матч — значит они в очереди первые — если есть меньше — значит
> вторые или третьи, итд.»

Two halves, and only the second is new:

- **The queue.** Three pills a row, at most two rows, soonest nearest the
  label. **ALREADY LANDED.**
- **READY PULLS THE MATCH IN TO FIFTEEN MINUTES.** When both chefs press Ready,
  the battle's start is brought forward to fifteen minutes from that press, and
  the pill re-sorts against every other battle on that new time. Ten hours at
  the back of the queue becomes fifteen minutes and near the front — unless
  somebody else is sooner still, and then they are second, or third.
  **TO BUILD.**

## How a run is watched — the Owner's pacing rule

> «перед началом эмуляции выводи на живую арену - 3 - 2 - 1 - и поехали, с шагом
> в 5 секунд»

    manage.py run_scenario_a          # the run
    manage.py run_scenario_a --clear  # remove what it left

Two things had to be solved together, and the second is why the first was not
enough on its own.

**The digits are counted by the browser, not sent by the server.** The arena
polls every ten seconds; three ticks inside three seconds cannot be delivered.
The server sends the MOMENT of the off, once, and the page counts down to it off
its own clock — so a watcher who arrives late sees the right number instead of a
stale one.

**The poll speeds up while a run is live.** A five-second step seen through a
ten-second poll is a step the Owner is TOLD about and never watches, which is
the complaint this whole file came from. During a run the arena polls every two
seconds and drops back to ten the moment the server stops sending a runway. The
window expires by itself: a crashed script cannot leave every open tab
hammering the site, and a test holds that.

Each step also puts one line on the arena saying what is happening WHILE it
happens, rather than the Owner being told afterwards what he should have seen.

## Facts the build stands on — measured, not assumed

- `expire_stale_battles` runs on production **every 15 minutes**, from the
  `deploy` user's crontab. That is what starts a battle whose clock has run out.
  Consequence to say out loud: a fifteen-minute countdown is resolved by a
  fifteen-minute sweep, so the actual start lands up to fifteen minutes after
  the countdown shows zero. If the Owner wants the start to be exact, the sweep
  has to run more often — his call, not a thing to change quietly.
- `resolve_start_rituals()` already says in its own docstring that the timer is
  a hard deadline and "pressing Ready only lets them start sooner", and it
  begins combat when both are ready at start time. A6 is the rule that docstring
  was written for; the Ready button had simply never implemented it.
- The emulation bots are exempt from the 180-second online window since
  v2.5.840, so a test pair stands on the arena permanently.

## What changed under this file since scenario A was dictated

**A09 is DONE** (GreenBear, v2.5.847), and it was the block on everything after
the off. A fighter is no longer filtered out of his own battle: the ring payload
used to keep only chefs inside the 180-second heartbeat, so a chef who closed
his tab vanished mid-bout and the ring ran empty.

**THE CENTRE RULE TIGHTENED** (v2.5.849), and this one changes scenario A's own
ending. The Owner ruled twice in a day; the second stands: **the pair reaches
the centre only when the battle BEGINS.** Pressing Ready is not the beginning -
since v2.5.844 it only pulls the start in to fifteen minutes, and those minutes
are spent standing in the rings. `facing_pair` is no longer produced at all.
The scenario runner narrated "the pair steps into the centre" on Ready and that
line was corrected the same day.

**Which is what made the empty pads load-bearing** (v2.5.848). With the centre
confined to a started battle, the two cells beside it are empty for the whole
life of a challenge rather than only between battles.

**A rehearsal takes nothing** (v2.5.848). A scenario battle left running was
picked up by the sweeper and cost both bots ten reputation for a dinner nobody
was going to cook. Penalties are exempt for a battle whose two participants are
both emulation bots, at the one gate inside penalise(); the rule is untouched
for every real chef, and two tests exist purely to prove that.

## Running it end to end

    manage.py run_scenario_a --to-the-off

Without the flag the run stops at Ready and the production sweeper starts the
battle in its own time, up to fifteen minutes later. With it, the clock is
brought to now and `resolve_start_rituals()` - the SAME function the cron calls,
not a shortcut around it - begins the battle while the Owner is looking at it.
That is the only way to watch the pair reach the centre without waiting a
quarter of an hour.

    manage.py run_scenario_a --clear

removes the battle a run leaves behind.

## Still to come

**Scenario B**, when the Owner dictates it. Rows for the withdrawal seen live -
the asking, the answer, the moderator's verdict and the numbers moving - are
still TO SPEC: what appears on the screen is his, and nobody guesses on his
behalf.
