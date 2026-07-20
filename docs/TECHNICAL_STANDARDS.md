# CulinEire Technical Standards

```yaml
document:
  id: "culineire-technical-standards"
  version: "1.0.0"
  status: "ACTIVE_AFTER_OWNER_MERGE"
  canonical_path: "/docs/TECHNICAL_STANDARDS.md"
  last_updated: "2026-07-20"
```

## 1. Stack and architecture

Current direction:

- Django monolith;
- Python 3.12;
- PostgreSQL;
- Django templates;
- existing HTML, CSS, and vanilla JavaScript;
- NGINX Unit / approved production stack;
- Git and GitHub;
- manual, owner-controlled production deployment.

Do not introduce:

- microservices;
- a separate battle backend;
- React, Vue, Angular, or a broad SPA rewrite;
- HTMX or Alpine merely because an archived prompt mentioned them;
- a second state machine;
- a second design token system;
- broad refactoring unrelated to the assigned task.

## 2. Repository bootstrap

Before work:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
git remote -v
```

Then complete the `/AGENTS.md` cold-start and CoWork readiness gate.

If unrelated modifications exist, stop. Do not stash, discard, reset, or absorb them without owner approval.

## 3. Work isolation

Required pattern:

```text
one agent
→ one work package
→ one branch
→ one isolated worktree
→ one owned file set
→ focused tests
→ clean commit
→ push
→ handoff
```

Cross-package interfaces must be agreed before parallel implementation.

A file cannot be simultaneously owned by two active work packages.

## 4. Discovery before modification

For each affected feature:

- find the URL entry point;
- find the view;
- find selectors and services;
- find model and migration dependencies;
- find template extension/include relationships;
- find CSS load order;
- find JavaScript imports, listeners, and DOM targets;
- find tests;
- find staff/admin consumers;
- find feature flags;
- find production/deployment dependencies.

Dynamic Django and JavaScript references may not appear in simple static grep.
Do not make deletion decisions from one search.

## 5. Django discipline

- Business state transitions belong in services.
- Read/query composition belongs in selectors where the project already uses them.
- Views remain thin.
- Models enforce durable integrity where technically appropriate.
- Migrations are explicit, reviewed, reversible where possible, and explained.
- Avoid data migrations without a production preflight.
- Financial, reward, vote, status, and crown operations must be atomic and idempotent.
- Permissions are server-side.
- Never depend on client-side hiding for access control.
- Do not expose unrevealed entries through template context, API payload, logs, cache, admin output, or error messages.

## 6. Frontend discipline

- Reuse existing components and contracts.
- Use semantic HTML and normal flow.
- Use CSS Grid/Flexbox for the 2D Arena.
- Use existing custom properties only.
- No raw colours.
- Avoid `!important` cascade warfare.
- Consolidate only after parity is proven.
- One interactive behaviour has one event owner.
- Do not duplicate listeners on polling updates.
- Prefer safe DOM APIs; review `innerHTML` usage.
- Modals and popups require focus entry, focus trap where appropriate, Escape, close controls, and focus return.
- All interactive controls require keyboard operation and visible focus.
- Honour `prefers-reduced-motion`.
- Test relevant viewport classes rather than one screenshot size.

## 7. Design tokens

Use only official site tokens.

Direction:

- warm parchment;
- natural ink;
- muted bronze;
- soft neutral surfaces;
- Playfair Display;
- Inter.

Legacy `--hall-*` compatibility variables do not become official 2D tokens merely because they exist globally.

Do not copy colours from old mockups, screenshots, historical specs, or dark Arena styles.

## 8. Security and integrity

Mandatory considerations:

- authentication;
- authorization;
- CSRF;
- rate limits;
- vote integrity;
- self-vote protection;
- duplicate protection;
- privacy-preserving fingerprints;
- secret rotation consequences;
- audit trail;
- moderation;
- hidden content;
- staff boundaries;
- payment webhooks;
- idempotency;
- data retention;
- safe error messages.

Never log secrets, raw payment data, private evidence, or unnecessary personal data.

## 9. Feature flags

Risky or unreleased functionality must be gated.

Feature flags do not constitute release approval.

Flags should default to the safest state for:

- public Chef Battle launch;
- voting expansion;
- rewards;
- Stripe Connect payouts;
- Live Video;
- external AI review providers;
- experimental UI.

The exact active setting names come from the repository, not an archived prompt.

## 10. Test strategy

### 10.1 Development loop

Run focused tests for the changed behaviour.

Do not run approximately 1,500 tests after every small edit.

Suggested sequence:

1. static and syntax checks;
2. focused unit tests;
3. focused integration tests;
4. affected app tests;
5. distributed full suite only at an integration/release gate.

### 10.2 Distributed full-suite gate

Follow `/AGENTS.md` section 9.

Before the run, create a machine-readable shard manifest, for example:

```json
{
  "test_run_id": "commit-hash-timestamp",
  "commit": "",
  "weights": {
    "primary_8_core": 8,
    "secondary_6_core": 6,
    "linode_1_core": 1
  },
  "shards": {
    "primary_8_core": [],
    "secondary_6_core": [],
    "linode_1_core": []
  }
}
```

Use historical durations if available. The goal is similar wall-clock completion, not equal test counts.

Each machine publishes:

```yaml
test_shard_result:
  test_run_id: ""
  machine: ""
  commit: ""
  workers: 1
  tests_collected: 0
  tests_passed: 0
  tests_failed: 0
  tests_skipped: 0
  duration_seconds: 0
  result: "PASS | FAIL | BLOCKED"
  failures: []
```

No test is counted twice and no test is silently omitted.

### 10.3 Test safety

- Use isolated test databases.
- Do not point tests at production.
- Do not use production test-client rendering when it can write caches or files.
- Do not create production data for testing.
- Browser/visual acceptance uses the approved safe environment and real HTTP.
- Record pre-existing failures separately from task regressions.
- A failing full-suite shard blocks a full-suite pass.

## 11. CoWork protocol

The poller must remain running and connected.

Before work:

- close or archive obsolete active tasks without deleting audit history;
- preserve agent names and connections;
- confirm round-trip delivery for Ember, GreenBear, and Bolt;
- post the current branch, commit, task, and file ownership;
- read and acknowledge all pending messages.

During work:

- poll at safe checkpoints;
- poll after long commands;
- acknowledge every message;
- immediately obey owner stop/freeze/rollback instructions;
- communicate contract changes before committing;
- do not assume a message was delivered until acknowledged.

Git carries durable code state. CoWork carries immediate coordination. Important decisions must be reflected in Git documents or the task contract after owner approval.

## 12. Commit and handoff

Before commit:

```bash
git diff --check
git status --short
```

Run the task's required checks.

Commit only owned files.

Handoff:

```yaml
handoff:
  agent: ""
  task_id: ""
  branch: ""
  commit: ""
  base_commit: ""
  files_changed: []
  interfaces_changed: []
  tests:
    - command: ""
      result: ""
  cowork_messages_processed: true
  known_risks: []
  ready_for_integration: false
  safe_to_deploy: false
```

## 13. Deployment

Deployment is manual and owner-controlled unless explicitly delegated.

- Do not deploy automatically.
- Use the approved `deploy` account, never routine `root`.
- Use the current repository-approved deployment script.
- Do not invent a deployment command from an archived document.
- State migration, static, environment, worker, and rollback requirements.
- No deploy when tests fail or work is partial.
- After deploy, verify ownership, health, logs, access, and rollback readiness using approved non-destructive checks.

## 14. Rollback

Every production-affecting task includes:

```yaml
rollback:
  trigger_conditions: []
  code_method: "git revert or approved rollback branch"
  migration_method: ""
  feature_flag_method: ""
  data_risk: ""
  verification: []
```

Do not call a task deploy-ready without a credible rollback path.

## 15. Dead code and archival

`DEAD_CODE_CANDIDATE` is not `CONFIRMED_DEAD_CODE`.

Before removal, check:

- Python imports and dynamic discovery;
- URL reverse usage;
- templates;
- CSS and JS imports;
- event selectors;
- settings;
- admin;
- management commands;
- tests;
- migrations;
- deployment;
- Master Console;
- Git history and compatibility.

Legacy Arena deletion is a later task after the 2D replacement is stable.

## 16. Reporting style

Reports are concise, structured, and evidence-based.

Use valid YAML for status and handoff.

Do not call work complete when it is partial.

Do not bury blockers.

Do not send long explanations to the Product Owner unless requested.
