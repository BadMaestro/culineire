---
name: Always work in main branch
description: User wants all changes made directly in the main branch, not in isolated worktrees
type: feedback
originSessionId: 3f235c3d-e519-407e-9152-52fd0ff86941
---
Always make changes directly in the `main` branch at `E:\CulinEire Project\CulinEire\CulinEire\`.

**Why:** User explicitly stated that changes should go into main, not into auto-created worktree branches.

**How to apply:** When Claude Code starts a session in a worktree (e.g. `claude/affectionate-agnesi-aa9e29`), edit files in the main project directory `E:\CulinEire Project\CulinEire\CulinEire\` instead of the worktree path. Never make changes only in the worktree without applying them to main.
