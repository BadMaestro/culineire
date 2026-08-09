#!/usr/bin/env bash
# PreCompact hook — canonical, tracked implementation.
#
# Same contract as ops/bootstrap/session_start.py, and deliberately the same
# words: a compaction is a cold start, and the two paths must not drift into
# telling an agent different things.
#
# It carries NO work state. Its predecessor committed and re-injected a private
# snapshot of a retired org chart on every compaction. A cache of the rules
# outlives the rules; origin/main does not.
#
# Never blocks: every failure path still exits 0.

set -uo pipefail

MSG='After compaction: COLD START. GOVERNANCE from origin/main - AGENTS.md, CHEF_BATTLE_PRODUCT_CONTRACT_2D.md, TECHNICAL_STANDARDS.md, ARENA_BATTLE_PLAN.md (the board). CURRENT WORK from this checkout - HEAD, branch, status, staged and unstaged diffs, untracked files; a dirty tree is not invalid state and untracked files are never auto-committed. PRODUCTION - reconcile release_journal.py with the live footer and the server HEAD. Task documents only after the card is known. Full contract: ops/bootstrap/COLD_START.md. No pollers, no roles. Do not read ops/director/ - it is retired history.'

printf '{"systemMessage":"%s"}\n' "$MSG"
exit 0
