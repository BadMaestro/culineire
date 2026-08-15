# GreenBear handoff — 2026-08-16, after the Arena audit day

Written to survive a context compaction. Production **v2.5.1071**,
`origin/main` = `d90ade9a`, tree clean, **deploy lock FREE**.

## Where the brief stands

Every card of the Owner's 2026-08-12 brief is DONE except **one**:

| Card | Owner on the board | State |
|---|---|---|
| T01–T16, T18–T21, AA1, AA2 | GreenBear / Bolt / Ember | **DONE** |
| **T17 — acceptance gate for the whole brief** | **GreenBear** | **PENDING — the last open card** |
| AA3–AA8 (my audit findings) | GreenBear | **DONE**, shipped 1062 / 1065 / 1068 |

**T17 HAS AN OWNERSHIP AMBIGUITY AND IT MUST NOT BE GUESSED AT.** The card has
said `"owner": "GreenBear"` since I created it on 2026-08-12 (`7dcc4faa`), and
nobody has changed it. But on the Carpet (message **#3515**) I told Bolt *"T17
runs after 1068, over both of us, and it is yours — you finish last now"*, and
he did finish last (his T15/T11 release, v2.5.1071, landed after my v2.5.1068).
He has not answered that message. **So the board and the conversation disagree.**
Ask the Owner or Bolt before starting it; do not just take it because the card
carries my name, and do not assume Bolt has it because I offered.

What T17 requires, from its own card: focused tests per ticket, real barrier
tests for every concurrency claim, the security and money suites, the state
matrix, `manage.py check`, `makemigrations --check`, `git diff --check`, then
**the full suite once** on PostgreSQL across eight workers, recording engine,
worker count, totals, duration and any pre-existing failures separately — plus
a browser smoke over battle detail, combat log, readiness, cooked upload, clan
create, the progress pages and the console reconciliation display. Forbidden:
production writes for a demonstration, weakened assertions, captured SQL
standing in for an interleaving test.

## What I shipped today, and the one thing each release is about

- **v2.5.1062** — the emulation-bot switch was applied at two reads and missing
  at six: the centre stage's crown holder AND its active-battle occupants, the
  crown streak, Recent Battle Gifts, and both blast paths. The blasts matter
  most: `arena_blast()` feeds `sitewide_blast.js` on **every page of the site**,
  and battle #14 (emu-chef-alpha over emu-chef-beta, 2026-08-05) was the most
  recent completed battle on the whole site, so a bot's rehearsal win was firing
  a site-wide celebration. Also AA4: the broadcast page (B01–B03/R01–R02, five
  DONE cards) had no entrance — the centre click opened the popup and the
  popup's own "full-screen Battle Room" link went to the antechamber.
- **v2.5.1065** — three endpoints: `arena_take_seat` carried
  `@ratelimit(block=False)` and never read `request.limited`, so it *looked*
  limited and was not; `arena_ping` and `arena_battle_popup` had none.
- **v2.5.1068** — AA6 removed the popup surface my own AA4 had orphaned (view,
  route, template, payload key, DOM, `open()/close()`; the blast in the same
  file survives); AA7 made chef potential an indicative band (`"40–60"`) so the
  exact aggregate never leaves the server; AA8 released a spectator seat on
  enrolment.

## Rulings and corrections from today that must not be re-litigated

- **The Owner cut AA8 down to size and was right.** I had reported "a spectator
  seat is not released when they enrol" beside two real findings. Enrolment is a
  **separate procedure** — `/chef-battle/enroll/` is linked from the Chef
  Battles home, the profile form and the author page, and **not from the arena**
  — so the sequence is narrow and the seat lapses on its own in 180 s. It is
  tidiness, not a defect; the card and journal say so, and it ships with **one**
  test, not the three I first wrote.
- **Bolt corrected me on `arena_battle_popup` and was right**: it carried no
  `@login_required` but it did carry `chef_battle_guard`, so an anonymous caller
  got a 404 during the dark launch. I verified it against production before
  accepting. (Moot now — AA6 deleted the endpoint.)
- **The timer collision, resolved his way.** My centre click used a 150 ms
  `setTimeout` so the ripple is seen before the browser leaves. Two guards
  (`ArenaLifecycleMechanismCountTests`, `ArenaRendererReadsBeforeItWritesTests`)
  **counted** the renderer's timers, so my flourish read as a first-paint
  readiness gate. My full-suite run went red and I deleted the flourish; Bolt had
  already pushed the better fix inside T11 — the guards now **name** the two
  timers they allow and still fail on a third. I restored the 150 ms and kept his
  tests. **The renderer must have exactly two `setTimeout`s: the 900 ms ripple
  cleanup and this 150 ms navigation.**

## Working rules this day proved the hard way

- **ONE LOCK, and it is the tracked in-repo `.agent-chat/deploy.lock`.** We spent
  hours claiming two different files — mine in the repo, Bolt's one level up,
  outside it — so AGENTS.md section 8 protected nothing and neither of us could
  see the other. Claim it, push it, release it, and read it before every deploy.
- **Version rotation is +3, not +2** (AGENTS.md amended 2026-08-14 for three
  agents): GreenBear 1029, 1032, …; Bolt 1030, 1033, …; Ember 1031, 1034, ….
  **My last was 1068. Live is 1071. My next is 1074** — and the rule that matters
  more than the rotation is *never below what is already live*, which I got wrong
  once today (claimed 1044 against a live 1057).
- **The board's baseline string is guarded.** `recipes/views.py`
  `ARENA_RELEASE_STAGES` (`"commit": "… / production vX"`) and
  `docs/ARENA_BATTLE_PLAN.md`'s `Production baseline:` must both match the footer
  in `templates/base.html`, or `recipes.tests.ModerationPanelRoleTests`
  `test_the_arena_boards_baseline_matches_the_footer_too` goes red.
- **A deploy that changes JS needs `deploy.sh`**, not a bare restart —
  collectstatic must re-run or the old hashed file keeps being served.
- **Production had root-owned files today.** My first 1062 deploy died on
  `insufficient permission for adding an object to repository database`: 111
  working-tree files and 179 git objects under `/srv/culineire/current` were
  owned by `root:root`. Fixed with `sudo chown -R deploy:deploy`. If a deploy
  dies that way again, that is why — and something is running git as root there.

## The Carpet (how the agents actually talk)

Messages live on the **production** database. Last message: **#3515** (mine to
Bolt). Read one:

```bash
ssh deploy@80.85.84.156 "cd /srv/culineire/current && set -a && . /srv/culineire/shared/.env && set +a \
  && /srv/culineire/venv/bin/python -c \"import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();\
from coworking.models import CoworkingMessage;print(CoworkingMessage.objects.get(id=3515).body)\""
```

To send, `scp` a small script into `/srv/culineire/current/` (NOT `/tmp` — the
Django settings module will not import from there), run it with the venv python,
then delete it. `CoworkingMessage.send(from_agent="greenbear", to_agent="bolt",
subject=…, body=…)`. Bodies are ASCII, English between agents.

Today's thread: **3510** Bolt on the lock collision → **3511** mine → **3512**
his popup correction, handing me the rate limits → **3513** mine → **3514** his
sync before T11/T15/T17 → **3515** mine (lock free, my last package, T17 to him).

## Still open, and deliberately not mine to start

- **A18's two accessibility gaps**, deferred by the Owner to Stage 3 on
  2026-08-10: focus rings on four of the first six deck controls, and 9.2 px
  rank chips.
- **VD1**, the overflow at the Owner's own viewport, which he froze as visual
  debt — not to be "fixed" quietly.
- The full audit act is `docs/chef_battle/ARENA_ACCEPTANCE_AUDIT_2026-08-15.md`;
  its four conditions are all now closed except what T17 certifies.
