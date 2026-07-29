# Claude Bootstrap Pointer

This file intentionally contains no independent project rules.

On every new Claude Code session, context compaction, context-limit return,
process restart, branch switch, task switch, or resumed session:

1. Read `/AGENTS.md`.
2. Read `/docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md`.
3. Read `/docs/CURRENT_EXECUTION_PLAN.md`.
4. Read `/docs/TECHNICAL_STANDARDS.md`.
5. Read `/docs/ARENA_BATTLE_PLAN.md` — the board.
6. Read all five from `origin/main`, never from the local working tree.
7. Complete the cold-start bootstrap record required by `/AGENTS.md`.
8. Do not start a poller. There are none (`/AGENTS.md` section 5).

`/AGENTS.md` is canonical. If this pointer and `/AGENTS.md` ever differ,
`/AGENTS.md` wins and this file must be corrected in the same task.

Do not copy the full constitution into this file.
