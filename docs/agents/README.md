# How the agents on this project work

Read `GOLDEN_RULES.md` first — before any work, after every limit, after every
context compaction. Then `MASTER_WORKFLOW.md` for the commands.

These live in the repository on purpose. They used to exist only inside one
agent's private memory folder, which meant a lost folder or a new session took
the rules with it, and the other agent could not read them at all. Rules that
only one person can see are not rules.

| File | What it is |
|------|------------|
| `GOLDEN_RULES.md` | The analysis of what keeps going wrong and the rules against it. Read first. |
| `MASTER_WORKFLOW.md` | Who we are, the stack, the server, the exact deploy commands. |
| `CHEF_COMBATS_MANIFEST.md` | The owner's product/architecture manifest for Chef Combats. Written before most of `chef_battle` existed — read `MANIFEST_DELTA.md` alongside it, not instead of it. |
| `CLAUDE_RULES.md` | The owner's co-developer protocol: peer collaboration, design-token discipline, handoff format. Section 2 (equal engineers, no manager) is the current standing rule between Bolt and GB. |
| `MANIFEST_DELTA.md` | Where the two documents above disagree with the code as it actually stands, and what the owner ruled on each disagreement. Read this before halting work or refusing a file because of something either manifest says. |

Keeping them current is part of the work, not paperwork: every rule in
`GOLDEN_RULES.md` exists because something broke in production and cost the owner
time or money. When a new one is learned the same way, it goes in immediately —
and into the agent's memory folder too, so the copies do not drift.

The two copies:
- repository — `docs/agents/` (this folder), readable by everyone;
- Bolt's memory folder, loaded automatically at the start of a session.

## What else lives here

- `memory/` — the full memory folder, every rule and reference note, not just the
  two headline documents. It used to exist on one machine only.
- `claude-config/` — the agent settings and `PROJECT_STATE.md`: permission lists,
  dev-server launch config, and the operational context note. No secrets: the
  files name environment variables, they never carry values.

`.env` and its backups stay out of git and always will.
