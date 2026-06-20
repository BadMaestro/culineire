# Agent Coworking Protocol

Coworking is a real Django app on the live site (model `CoworkingAgent` +
`CoworkingLogEntry` + `CoworkingSharedMemory`, app `coworking/`). It is
**not** a local file anymore — `coworking/state.json` and the old
`update_state.py`/`handoff.py` CLI scripts were removed. The production
database is the shared state between agents on different machines/accounts;
there is no git-based sync step to remember.

Dashboard (moderator-only, same access pattern as the rest of the internal
tools — `is_moderator`, 404 for everyone else): `https://culineire.ie/coworking/`

## How an agent updates its own status

Run via SSH on the server where `manage.py` has access to the production
database (same way other ops commands in this project run):

```
python manage.py coworking_update --agent bolt --label Bolt --status active \
  --task "Fix sponsors N+1 query" --next "Run audit.py to verify fix" \
  --log "Modified sponsors/views.py" --log-result ok
```

Full flag list: `--agent`, `--label`, `--status` (active/idle/blocked),
`--task`, `--task-desc`, `--branch`, `--files` (comma-separated),
`--next`, `--prompt` (path to a file with the active prompt text), `--log`,
`--log-result`, `--log-note`, `--key-fact`, `--decision`, `--blocker`,
`--shared-memory`, `--open-question`, `--completed`. All of these merge
into the agent's own row — they never touch another agent's data.

## Checking who's registered

```
python manage.py coworking_list
```

Read-only. Shows every agent's status, last_seen and next_step.

## Update frequency

After every meaningful step, not just "when you sense a limit" — there is
no signal an agent can read to predict its own usage limit in advance. The
only defense is keeping `--next` current at all times, so whatever the
last saved state is, it's good enough for a colleague to pick up from even
if your session ends without warning.

## Handoffs are human-decided, via the web button

The human watches for limits/availability themselves and clicks
**"Передать эстафету"** on `/coworking/` to flip status on both agents and
log the handoff on both sides. There is no CLI handoff command — this is
intentionally a human-in-the-loop action, not something an agent triggers
on itself.

## Adding a new agent

Either click "Add agent" on the dashboard, or:

```
python manage.py coworking_update --agent <new_id> --label "<New Agent Label>" --status idle
```

No code change needed — agent count is not hardcoded anywhere.

## No autonomous git operations from this app

`coworking_update` and `coworking_list` only touch the database. Nothing in
this app runs `git`. Code changes elsewhere in the repo still go through
the normal flow: show the human the diff, wait for an explicit "yes", then
commit/push.
