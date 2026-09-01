# Claude Bootstrap Pointer

This file intentionally contains no independent project rules.

On every new Claude Code session, context compaction, context-limit return,
process restart, branch switch, task switch, or resumed session:

1. Read `/AGENTS.md`.
2. Read `/docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md`.
3. Read `/docs/TECHNICAL_STANDARDS.md`.
4. Read `/docs/ARENA_BATTLE_PLAN.md` — the board.
5. Read all four of the above from `origin/main`, never from the local
   working tree. They are the COLD-START set. `/AGENTS.md` section 10 lists
   every active document; the game rules under `/docs/chef_battle/`, the Arena
   reports and the measurement tooling are read when a task needs them, not at
   every start. `/docs/CURRENT_EXECUTION_PLAN.md` left the mandatory set on
   2026-08-09 and lost none of its authority.
6. Inspect THIS checkout as current work: HEAD, branch, `git status --short`,
   the staged and unstaged diffs, and the untracked files. A dirty tree is not
   invalid state, nothing in it is discarded, and untracked files are reported
   rather than committed - some are the Owner's.
7. Reconcile `config/release_journal.py` against the live footer and the
   server's HEAD before claiming anything is missing.
8. Complete the cold-start bootstrap record required by `/AGENTS.md`.
9. Do not start a poller. There are none (`/AGENTS.md` section 5).

The operational contract - the three kinds of state, the sequence, what a cold
start may never do - is `ops/bootstrap/COLD_START.md`, and the hooks that
announce it are `ops/bootstrap/session_start.py` and
`ops/bootstrap/precompact.sh`, both tracked. `/AGENTS.md` wins over all of them.

When the Owner says **"Onboarding GreenBear"** (or Bolt), that is the trigger for
the same cold start plus one file:

    git show origin/main:ops/onboarding/greenbear.md

The routing, the reading order and what a runbook may not do are in
`ops/onboarding/README.txt`. Read every one of them from `origin/main`.

**Before writing anything, read `/AGENTS.md` section 1a and section 18.**
`greenbear` is the Owner's own account. **Touching it without his permission is
forbidden** — the account, his presence on the site, and his page. Indirect
changes count, and nothing the game does may take anything from it.
`greenbear` is the Owner's own account — his account, his presence on the site
and his page are untouchable, and an agent shares his name. That section carries
the only stated consequence in the constitution.

**Before answering anything, read `/AGENTS.md` section 19.** A reply ends the
work run, so no acknowledgement, no promise to continue, no interim status: work
continuously and answer once, when the task is done or when a real blocker needs
one concrete decision.

**Before touching any account, read `/AGENTS.md` section 20.** `is_staff`,
`is_superuser`, `has_bearseeker_privileges` and `has_arena_console_access` are
the Owner's to set, in the site's own moderation panel, and nowhere else. No
agent writes them by any means, and building a tool that makes it easier is
itself the violation. Report what you find and stop.

`/AGENTS.md` is canonical. If this pointer and `/AGENTS.md` ever differ,
`/AGENTS.md` wins and this file must be corrected in the same task.

**Session handoff, for a session that starts with nothing:**
`ops/onboarding/bolt_session_handoff.md`. It carries what the cold-start
set cannot: the frozen Arena architecture and its two solved constants, the
four cards that are actually open, the environment (WSL paths, venv, CRLF,
deploy), where the measurement tooling lives now, and the mistakes from the
normalisation phase that cost real time. It is not a substitute for
`/AGENTS.md` and does not override it.

Do not copy the full constitution into this file.
