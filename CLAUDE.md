# Claude Bootstrap Pointer

This file intentionally contains no independent project rules.

On every new Claude Code session, context compaction, context-limit return,
process restart, branch switch, task switch, or resumed session:

1. Read `/AGENTS.md`.
2. Read `/docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md`.
3. Read `/docs/CURRENT_EXECUTION_PLAN.md`.
4. Read `/docs/TECHNICAL_STANDARDS.md`.
5. Read `/docs/ARENA_BATTLE_PLAN.md` — the board.
6. Read all five of the above from `origin/main`, never from the local
   working tree. They are the COLD-START set. `/AGENTS.md` section 10 lists
   every active document, including the game rules under `/docs/chef_battle/`,
   which are read when a task touches them rather than at every start.
7. Complete the cold-start bootstrap record required by `/AGENTS.md`.
8. Do not start a poller. There are none (`/AGENTS.md` section 5).

When the Owner says **"Onboarding GreenBear"** (or Bolt), that is the trigger for
the same cold start plus one file:

    git show origin/main:ops/onboarding/greenbear.txt

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
