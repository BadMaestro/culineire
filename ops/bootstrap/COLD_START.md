# Cold start — the executable contract

`/AGENTS.md` section 3 is the law. This file is its operational detail: the
three kinds of state, the order they are read in, and what may never be read
from where. Where this file and `/AGENTS.md` differ, `/AGENTS.md` wins and this
file is corrected in the same task.

It is tracked, so a fresh clone on any machine has it.

---

## 1. Three kinds of state, and the one rule that matters

A recovering agent needs all three. They come from different places and
confusing them is how a session either obeys stale rules or throws away real
work.

### GOVERNANCE — the rules

**Source: `origin/main`, never the working tree.**

```bash
git fetch -q origin
git show origin/main:AGENTS.md
```

An uncommitted edit to `AGENTS.md` is a *proposal*, not the constitution. This
is the rule the hooks exist to enforce, and the reason is written in their own
comments: a private cache of the rules outlives the rules.

### CURRENT WORK — what is unfinished

**Source: this checkout, including everything uncommitted.**

```bash
git rev-parse --short HEAD
git branch --show-current
git status --short          # both sections
git diff --stat             # unstaged
git diff --cached --stat    # staged
git ls-remote origin refs/heads/main   # the REMOTE, not the tracking ref
```

**A dirty working tree is not invalid state.** After a compaction, a limit or a
process restart, uncommitted work is normal and may be the whole point of the
session. Read it. Never discard it, never `reset`, never `checkout --` it, and
never assume it is junk because the session that made it is gone.

**Untracked files are reported, never auto-committed.** Some belong to the
Owner — `scripts/` on the workstation does — and committing them is a decision
he makes, not an agent.

### PRODUCTION — what is actually live

**Source: the live site, reconciled against the journal.**

```bash
curl -s https://culineire.ie/ | grep -o 'v2\.5\.[0-9]*' | head -1
ssh -i ~/.ssh/culineire_linode root@80.85.84.156 \
  'cd /srv/culineire/current && git rev-parse --short HEAD'
```

`config/release_journal.py`'s newest entry must agree with both. A restart is
not proof that anything shipped: fetch the served file and read it.

### The rule, stated once

> Never take GOVERNANCE from an uncommitted working-tree modification.
> Always inspect the working tree as CURRENT WORK.

---

## 2. The mandatory set

Read at **every** cold start, from `origin/main`:

| # | File | Establishes |
|---|---|---|
| 1 | `/AGENTS.md` | the rules, the roster, the prohibitions |
| 2 | `/docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md` | what the product is; §14 the release gates |
| 3 | `/docs/TECHNICAL_STANDARDS.md` | how code is written and verified |
| 4 | `/docs/ARENA_BATTLE_PLAN.md` | the board — current work and what shipped |

Then the state checks of section 1, then the bootstrap record.

### Read AFTER the current card is known, not before

Loading these at every start costs a large part of the window before anything
is known about the task, and most sessions never touch them:

- `/docs/CURRENT_EXECUTION_PLAN.md` — a completed documentation-reset record
  from 2026-07-21. It governs nothing and dispatches nothing. **Preserved, and
  still an active document under `AGENTS.md` section 10** — read it when a task
  concerns the documentation programme.
- `/docs/chef_battle/*` — the game rules. Read when a task touches battle
  mechanics, ranks, moves, tokens or gifts, which by definition it announces.
- `ARENA_VISUAL_DEBT.md`, `ARENA_NORMALISATION_REPORT.md`,
  `ARENA_BOARD_SYNC_2026_08_09.md`, `ops/audits/arena/tools/` — Arena task
  material. The board names them when a card needs them.
- `ops/onboarding/*.txt` — the per-agent runbooks. Only on the Owner's explicit
  "Onboarding Bolt / GreenBear", which is a heavier operation than recovery.

Nothing here is deleted or downgraded. It is loaded on demand instead of by
ritual.

---

## 3. The sequence

```
SESSION START or COMPACTION
        |
        v
GOVERNANCE      AGENTS.md, product contract, technical standards   (origin/main)
        |
        v
BOARD           docs/ARENA_BATTLE_PLAN.md - which cards are ready   (origin/main)
        |
        v
CURRENT WORK    HEAD, branch, status, staged, unstaged, untracked   (this checkout)
        |
        v
PRODUCTION      live footer and server HEAD vs release_journal
        |
        v
TASK DOCS       only now, and only what the card needs
        |
        v
LOCAL AUDIT     write the bootstrap record to a file, not to the Owner's window
        |
        v
READY           one line to the Owner
```

---

## 4. Card scheduling

A card may start when **all of its declared prerequisites are satisfied** — the
`Depends on` column of the board's dispatch queue, and the matrix in
`docs/chef_battle/ARENA_BOARD_SYNC_2026_08_09.md`.

Card number and table position are **presentation and priority**, not a
dependency. Where the Owner has stated an explicit order, that order is the
dependency and it holds.

An agent still holds at most one card and never self-assigns. Do not invent
parallelism the board does not declare.

---

## 5. What a cold start may not do

- start a poller — there are none (`AGENTS.md` section 5)
- assume, claim or infer a role — there are none (section 1)
- read `ops/director/` — retired history
- read the governance documents from the working tree
- restore work state from any cache instead of from the repository and the
  working tree
- paste the bootstrap YAML into the Owner's window — he gets one line
- self-assign a card, or start a card whose prerequisites are unmet
- commit before `git config user.name` is the roster name and
  `core.hooksPath` is `.githooks`
- touch `greenbear`, or write `is_staff`, `is_superuser`,
  `has_bearseeker_privileges`, `has_arena_console_access` (sections 1a, 18, 20)

---

## 6. Recovery is complete when

- the mandatory set has been read from `origin/main`
- git identity, hooks path, HEAD and the remote are verified
- the working tree has been inspected and any unfinished work named
- production is reconciled with the journal
- the ready cards are known, or it is known that none is assigned
- the bootstrap record is written to a file
- the Owner has received **one line**

---

## 7. Sources that are NOT authoritative

| Thing | Status |
|---|---|
| `.claude/` (settings, hooks, any state file) | machine-local, gitignored, never authoritative |
| `.agent-chat/heartbeats/*.yaml` | local audit record. Losing it must cost nothing. |
| session scratchpad | disappears with the session; persist anything useful before it ends |
| `ops/onboarding/bolt_session_handoff.md` | a bridge and durable context, not a state database |
| any summary of this conversation | not a source |

If one of these disagrees with `origin/main`, `origin/main` is right and the
local copy is stale by definition.
