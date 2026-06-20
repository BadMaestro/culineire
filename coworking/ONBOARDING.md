# New Agent Onboarding: Join the Coworking System

## Who you are

You are a Claude Code agent joining an active development team on
culineire.ie, on your own machine and account — possibly different from
any colleague already working on this project. The only thing you share
with them is this git repository, so the very first thing you do is pull.

---

## Step 1 — Orient yourself

```bash
cd "<repo root>"
git pull
git log --oneline -10
cat coworking/state.json 2>/dev/null || echo "No state.json yet — it will be created from state.example.json on first update."
cat coworking/AGENT_INSTRUCTIONS.md
```

`git pull` here is read-only with respect to anything except state.json
itself — safe to run without asking. Pushing is the step that always needs
the human's explicit "yes".

Read `state.json` (if it exists) carefully. You will find:
- What each active agent is currently doing
- What has been completed today
- Open blockers and questions
- Project memory (key facts about the codebase)
- The exact `next_step` each agent left, in case you need to pick up

---

## Step 2 — Choose your identity

```bash
python coworking/handoff.py list
```

Pick the next available slot, or register a brand-new one (no code change
needed — agent count is not hardcoded):

```bash
python coworking/handoff.py add-agent --label "[YourMachineName] / Code [Letter]"
```

Or keep an existing slot's label consistent with your machine if you're resuming.

---

## Step 3 — Register yourself

```bash
python coworking/update_state.py \
  --agent [your_id] \
  --status active \
  --log "Agent joined - reading project state" \
  --log-result ok
```

This edits `coworking/state.json` locally. Ask the human to review the diff
and push it — that's the only way a colleague on another machine learns you
exist.

---

## Step 4 — Read the full project context

```bash
cat CLAUDE.md
git log --oneline -20
```

---

## Step 5 — Introduce yourself in shared memory

```bash
python coworking/update_state.py \
  --agent agent_[YOUR_LETTER] \
  --status active \
  --log "Orientation complete. Ready to take tasks." \
  --log-result ok \
  --next "Waiting for task assignment or picking up from colleague" \
  --key-fact "Joined from [your machine description]"
```

---

## Step 6 — Check if a colleague needs pickup

```bash
python coworking/handoff.py list
```

No one can reliably self-report "I just hit my limit" — there's no signal
an agent can read to know that in advance. So don't rely on a special
status value for this. Instead look at `last_seen` (how long ago?) and
whether `current_task.next_step` looks unfinished. The human is usually the
one who notices a colleague stalled and decides to switch agents — if they
tell you to pick up from someone, or you see a stale `active` agent with an
unfinished `next_step`, that's your cue.

```bash
python coworking/generate_dashboard.py
```

Open the generated `coworking/dashboard.html` locally and click the
"Подхватить работу" button on their card — it copies a ready-made handoff
prompt (their task, next_step, prompt, memory) to your clipboard. Paste it
here and begin. This works straight from the static file, no server needed.

---

## Step 7 — Begin working

```bash
python coworking/update_state.py \
  --agent agent_[YOUR_LETTER] \
  --task "Title of your task" \
  --task-desc "What exactly you are doing and why" \
  --branch "branch-name-if-any" \
  --next "First concrete action you will take" \
  --log "Starting task: [title]" \
  --status active
```

Then follow `AGENT_INSTRUCTIONS.md` — log every 3-5 actions.

---

## Golden rules for this team

1. **`next_step` must always be specific.** A fresh agent must be able to
   start from it with zero extra context.
2. **Log before AND after** each significant action — every time, not just
   when you feel like you might be running low. You cannot detect your own
   limit in advance.
3. **Never overwrite a colleague's data.** `update_state.py` only merges
   your own slot.
4. **Log blockers immediately.**
5. **Handoffs are explicit and human-decided.** The human watches for
   limits/availability and tells an agent to run
   `python coworking/handoff.py handoff --from X --to Y`.
6. **Never run `git commit`/`push` from inside these scripts.** Pulling is
   always safe to do yourself. Pushing — including for `state.json` — is
   always a separate, human-confirmed step.

---

## Quick reference

| Action | Command |
|--------|---------|
| Pull latest state (safe, no confirmation needed) | `git pull` |
| Read full state | `cat coworking/state.json` |
| List agents | `python coworking/handoff.py list` |
| Register a new agent | `python coworking/handoff.py add-agent --label "..."` |
| Hand off to a colleague | `python coworking/handoff.py handoff --from X --to Y --note "..."` |
| View dashboard (local snapshot) | `python coworking/generate_dashboard.py` then open `coworking/dashboard.html` |
| Log an action | `python coworking/update_state.py --agent X --log "..."` |
| Update next step | `... --next "..."` |
| Add key fact | `... --key-fact "..."` |
| Add to shared memory | `... --shared-memory "..."` |
| Mark task complete | `... --completed "task title"` |
