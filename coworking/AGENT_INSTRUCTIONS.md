# Agent Coworking Protocol

Agents in this project run on **different machines and different accounts**.
The only channel they share is this git repository — there is no local
server or shared filesystem between them. `coworking/state.json` is
therefore tracked in git on purpose: it is how an agent on one machine sees
what an agent on another machine was doing.

## Critical rule: no autonomous git push from inside a script

`update_state.py` and `handoff.py` never run `git commit`/`push`. They only
edit `coworking/state.json` on disk. **Pushing** that file always goes
through the normal flow: show the human the diff, wait for an explicit
"yes", then commit/push. This file does not get a special exemption from
that rule.

**Pulling is different and is always safe to do on your own** — `git pull`
/ `git fetch` are read-only with respect to the working tree state other
than state.json itself, so do this freely without asking:

```
git pull
cat coworking/state.json
```

## On session start

```
git pull
python coworking/update_state.py --agent [your_id] --status active --log "Session started"
```

## Before every significant action

```
python coworking/update_state.py --agent [your_id] --log "Starting: [what]"
```

## After every significant action — do this every time, not "when you sense a limit"

```
python coworking/update_state.py --agent [your_id] --log "[what] done" --log-result ok --next "[literal next step]"
```

You cannot detect your own usage limit in advance — there is no internal
signal for that. The only defense is updating `next_step` after literally
every meaningful step, so whatever the last saved state is, it's good
enough for a colleague to pick up from, even if your session ends without
warning.

## Handing off deliberately (the human decides when, via the CLI)

The human watches for limits/availability and decides when to switch
agents. When they say "hand off to X":

```
python coworking/handoff.py handoff --from agent_a --to agent_b --note "why / what's next"
```

This only updates `coworking/state.json` locally (flips status on both
sides, logs the handoff). **Ask the human to commit + push** right after —
that push is the only way the receiving agent's machine can see it.

## Adding a new agent (no code change needed)

```
python coworking/handoff.py add-agent --label "Mac Mini / Code C"
```

Creates a new slot with an auto-generated id (or pass `--id` explicitly).
Push it the same way, so other machines know this agent exists.

## Viewing the board

```
python coworking/generate_dashboard.py
```

Writes a static, self-contained `coworking/dashboard.html` (open it
directly in a browser, `file://...`). It is a snapshot, not live — re-run
the script after a `git pull` for a fresh view. There is no Django view or
production page for this; it never touches the live site.

## Update frequency

Every 3-5 actions minimum, ideally after every meaningful step (see above —
this is not optional given we can't self-detect limits). The `--next` field
is the most important field — it must always be specific enough that a
fresh agent can start immediately with zero extra context (not "continue
work" but e.g. "Run audit.py and confirm noindex is fixed on /recipes/").

## Committing/pushing state.json

This file IS meant to be tracked in `main`'s history (unlike most working
files, it's not gitignored) — that's the whole point, it's how cross-machine
handoff works. But the push itself is still a normal, human-confirmed
commit: show the diff, get a "yes", push. Don't push on every single
`update_state.py` call — batch it up to the moments that matter (before a
handoff, before ending a session) so `main`'s history doesn't get noisy with
dozens of tiny state.json-only commits.
