# New Agent Onboarding: Connecting to the Coworking System

## Who you are

You are a Claude Code agent joining an active development team on
culineire.ie. One or more agents may already be registered. Coworking is a
real app on the live site backed by the production database — there is no
local file to read, no git pull needed for "state".

---

## Step 1 — See who's already there

```bash
python manage.py coworking_list
```

This shows every registered agent: status, last activity, and their
`next_step` — read this carefully if you're picking up from someone.

For the full picture (current task description, active prompt, memory,
recent log), open the dashboard: `https://culineire.ie/coworking/`
(moderator login required — same access as the rest of the internal tools).

---

## Step 2 — Choose your identity

Pick an id that doesn't already appear in `coworking_list` output. Keep the
label human-readable (e.g. "Bolt", "GreenBear", "Claude D").

---

## Step 3 — Register yourself

```bash
python manage.py coworking_update --agent <your_id> --label "<Your Label>" \
  --status active --log "Agent joined - reading project state" --log-result ok
```

If your id doesn't exist yet, this creates it automatically — no code
change, no migration, no separate "add agent" step needed (though the web
button works too if you'd rather a human click it).

---

## Step 4 — Read the full project context

```bash
cat CLAUDE.md
git log --oneline -20
```

---

## Step 5 — Introduce yourself in shared memory

```bash
python manage.py coworking_update --agent <your_id> --status active \
  --log "Orientation complete. Ready to take tasks." --log-result ok \
  --next "Waiting for task assignment or picking up from colleague" \
  --key-fact "Joined from <your machine/account description>"
```

---

## Step 6 — Check if a colleague needs pickup

```bash
python manage.py coworking_list
```

There's no reliable "I just hit my limit" signal an agent can set on
itself — usage limits aren't predictable from inside a session. So don't
look for a special status value. Instead: the human notices a colleague
stalled (or tells you directly) and clicks **"Передать эстафету"** on
`/coworking/`, which flips both agents' status and logs the handoff on
both sides. After that, run `coworking_list` again (or open the dashboard)
and read the outgoing agent's `task_description` / `task_next_step` /
`active_prompt` / memory to continue exactly where they left off.

---

## Step 7 — Begin working

```bash
python manage.py coworking_update --agent <your_id> \
  --task "Title of your task" --task-desc "What exactly you are doing and why" \
  --branch "branch-name-if-any" --next "First concrete action you will take" \
  --log "Starting task: [title]" --status active
```

Then follow `AGENT_INSTRUCTIONS.md` — update `--next` after every
meaningful step, not just when you think you're running low.

---

## Golden rules for this team

1. **`next_step` must always be specific.** A fresh agent must be able to
   start from it with zero extra context.
2. **Log before AND after** each significant action.
3. **Never overwrite a colleague's data.** `coworking_update` only touches
   your own agent row.
4. **Log blockers immediately** with `--blocker`.
5. **Handoffs are explicit and human-decided**, via the dashboard button —
   not something an agent decides on its own.
6. **No git operations from this app.** Code changes go through the normal
   diff-review-confirm-push flow, same as everything else in this repo.

---

## Quick reference

| Action | Command |
|--------|---------|
| List agents | `python manage.py coworking_list` |
| View full dashboard | `https://culineire.ie/coworking/` |
| Register / update yourself | `python manage.py coworking_update --agent X --log "..."` |
| Update next step | `... --next "..."` |
| Add key fact | `... --key-fact "..."` |
| Add to shared memory | `... --shared-memory "..."` |
| Mark task complete | `... --completed "task title"` |
| Hand off to a colleague | Click "Передать эстафету" on `/coworking/` (human-triggered) |
