#!/usr/bin/env python3
"""SessionStart hook — canonical, tracked implementation.

Owner, 2026-08-06: "всегда делай холодный старт а там уже всё подтянется и
конституция и твои права и обязанности."

THIS HOOK CARRIES NO WORK STATE, AND THAT IS THE POINT. Its predecessor pasted
a private snapshot of an org chart into the first turn of every session, ABOVE
the constitution, labelled "newer than any summary". The org chart had been
abolished four days after the snapshot was written, and the snapshot went on
being the first thing every window read for two weeks. A private cache of the
rules outlives the rules; origin/main does not.

So this says WHERE recovery begins and nothing else. No task state, no card, no
version number, no secret. Everything that could go stale is fetched from
origin/main by the agent, in the same breath.

It lived only in .claude/, which is gitignored, so it existed on exactly one
machine and a fresh clone could not reproduce it. It is tracked now; the local
Claude settings merely point at this file.

Fails silent and exits 0 on any problem: a broken hook must never block a
session.
"""
import json
import sys

REMINDER = (
    "COLD START, every time. Nothing is restored from a cache.\n"
    "\n"
    "GOVERNANCE - read from origin/main, never the working tree:\n"
    "  1. /AGENTS.md\n"
    "  2. /docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md\n"
    "  3. /docs/TECHNICAL_STANDARDS.md\n"
    "  4. /docs/ARENA_BATTLE_PLAN.md - the board, for the ready cards\n"
    "\n"
    "CURRENT WORK - inspect THIS checkout, including everything uncommitted:\n"
    "  HEAD, branch, git status --short, staged and unstaged diffs, untracked.\n"
    "  A dirty tree is not invalid state. Never discard it. Never auto-commit\n"
    "  untracked files - some are the Owner's.\n"
    "\n"
    "PRODUCTION - reconcile config/release_journal.py with the live footer and\n"
    "  the server's HEAD before claiming anything is missing.\n"
    "\n"
    "THEN the bootstrap record, to a FILE - the Owner gets one line.\n"
    "Task-specific documents are read AFTER the card is known, not before.\n"
    "\n"
    "The full contract: ops/bootstrap/COLD_START.md. AGENTS.md wins over it.\n"
    "No pollers (AGENTS.md 5). No roles - no Director, no gate holder (1)."
)

try:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": REMINDER,
        }
    }))
except Exception:
    sys.exit(0)
