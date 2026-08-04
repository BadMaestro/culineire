# Rescued from stale worktrees — 2026-08-04

Nine worktrees had accumulated on the workstation from sessions that ended
without closing them. The Owner asked for them cleared. Removing a worktree
loses only what is **not** in git: committed work lives on its branch and
survives untouched. So before any of them was removed, every untracked and
uncommitted file across all nine was inventoried, and everything that was
evidence rather than working scratch was copied here.

That distinction is the whole point of this directory. Four of the nine held
nothing at all; five held the files below, and none of it existed anywhere else.

## What is here, and why it was worth keeping

**`from-arena-slice-2/a06_measurement_matrix_2026-07-29.json`**
The machine-readable half of the A06 measurement matrix. The Markdown half is in
`ops/audits/arena/`; this JSON never reached the repository and sat in a Codex
worktree under `C:\Users\golov\Documents\`. It is the raw numbers behind a
matrix currently marked SUPERSEDED SOURCE, which makes it evidence of how the
wrong reference produced its figures — worth more now, not less.

**`from-bolt-sync/rescued-from-scratchpad/`**
Mockup crops, a hall wash asset, and four before/after screenshots (desktop and
mobile). Images of this kind are the Owner's approved or paid material, and
AGENTS.md 17.10 forbids deleting them. Their own directory name says they had
already been rescued once, from a scratchpad, by a previous session — and then
left in a worktree, one `git worktree remove --force` away from being lost for
the second and final time.

**`from-bolt-sync/bootstrap/`**
Bolt's cold-start records from 2026-07-27, plus the heartbeat file, inbox log
and poller script from the era when the constitution still required a poller.
Kept as audit history, not as anything to run: pollers were abolished on
2026-07-29 and `bolt_poller.py` is here as a record of what was removed.

**`from-bolt-sync/agent_chat_presence_backup.py`** and
**`from-bolt-sync/agent_chat.py.uncommitted.diff`**
The local chat on port 8799 is switched off but explicitly **not** retired — the
Owner said it will be wanted again, and section 5 forbids letting a cleanup pass
remove it. A seven-line uncommitted edit to `ops/agent_chat.py` was sitting in
that worktree with no commit and no explanation. It is preserved as a diff
rather than applied: nobody knows what it was for, and discarding an unexplained
edit is as wrong as merging one.

**`from-cursor-arenafront/arenafront_cold_start_2026-07-27.yaml`**
ArenaFront's cold-start record. ArenaFront was retired on 2026-07-27 and section
16 requires a retired agent's audit history to be preserved rather than
destroyed. This was the only copy.

## What was deliberately NOT rescued

`scratchpad/` directories, `.cursorignore`, and a zero-byte file named `v[^` in
the repository root — a shell accident from 2026-07-27, empty, created by a
redirect that misfired. Working scratch and typos are not evidence.

Also not rescued, because it was never at risk: every commit on every branch
those worktrees pointed at, including the six on `impl/arena-g2-camera` that
wired the 96 crowd faces. Branches are not worktrees. That worktree's working
copy showed the paid face assets as **deleted** — an uncommitted state nobody
had explained — and dropping the worktree discards that deletion rather than
performing it.

Checked afterwards rather than asserted, and the answer comes in two halves:

- The crowd faces are on `main` and untouched — 483 files under
  `static/images/crowd/`. Those are the paid ones, and they are safe.
- The hall backgrounds and the floor plate
  (`static/images/chef_battle/arena/`) are **not** on `main`, and that is
  deliberate rather than a loss: commit `ee88e451`, "emergency load purge — drop
  dead heavy assets", removed them, and the worktree simply predated the purge.

The first version of this note said "the assets are safe on main" with no such
split. That was true of the faces and misleading about the rest, which is
exactly the sort of sentence this directory exists to stop being written.
