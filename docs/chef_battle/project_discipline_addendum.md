## Final Project Discipline Addendum

These rules apply to every task, regardless of whether the work is assigned to Claude or Codex.

---

# Definition of Ready

Do not start coding until the task is ready.

A task is ready only when the following are clear:

```yaml
definition_of_ready:
  task_goal_clear: true
  target_branch_clear: true
  expected_scope_clear: true
  production_risk_understood: true
  files_or_apps_to_touch_identified: true
  tests_to_run_identified: true
  deployment_impact_understood: true
```

If any item is unclear, stop and ask clarifying questions before making changes.

---

# Definition of Done

A task is done only when:

```yaml
definition_of_done:
  scoped_change_completed: true
  unrelated_files_not_modified: true
  migrations_checked: true
  tests_run_or_failure_explained: true
  git_diff_checked: true
  committed: true
  pushed: true
  completion_report_provided: true
  deployment_command_provided: true
```

Do not describe unfinished work as complete.

---

# One Agent / One Branch / One Task Rule

Claude and Codex may both work on the project, but their work must remain isolated.

Required rule:

```yaml
parallel_work_rule:
  one_agent: "Claude or Codex"
  one_branch: "one feature branch per task"
  one_task_scope: "no unrelated work"
  one_commit_group: "only files related to the assigned task"
```

Never mix another agent’s unfinished work into your own commit.

If work depends on another branch, ask the user for the exact branch name or commit hash before continuing.

---

# Feature Flag Rule

Large or risky features should be controlled by a feature flag whenever practical.

Use feature flags for:

* Chef Battle public launch;
* new homepage blocks;
* live notifications;
* new voting systems;
* new payment-related logic;
* new moderation workflows;
* experimental UI.

Preferred setting style:

```python
CHEF_BATTLE_ENABLED = False
CHEF_BATTLE_PUBLIC_ENABLED = False
CHEF_BATTLE_VOTING_ENABLED = False
```

The default should be safe for production.

Do not expose unfinished features publicly unless explicitly instructed.

---

# Rollback Rule

Before completing any task, think about rollback.

Every completion report should include:

```yaml
rollback_plan:
  required: true
  method: "git revert / disable feature flag / rollback migration / restore backup"
  notes:
    - "Explain the safest rollback path."
```

For risky migrations or data changes, ask for explicit approval before proceeding.

---

# Phase Discipline Rule

Do not jump ahead in the Chef Battle roadmap.

The correct build order is:

```yaml
chef_battle_phase_order:
  phase_0: "Architecture, models, services, tests"
  phase_1: "Challenge, accept/refuse, battle room, submission, voting, result, rating, crown"
  phase_2: "Site-wide visibility, profile stats, activity feed, notifications"
  phase_3: "Battle moves and content-earned energy"
  phase_4: "Attack/block combat engine"
  phase_5: "Artifacts, cosmetics, monetisation"
  phase_6: "Seasons, clans/kitchens, tournaments"
```

Do not implement Phase 3, Phase 4 or monetisation mechanics before the core MVP is stable, tested and deployed.

---

# Event-First Architecture Rule

Chef Battle must be designed around events from the beginning.

Every important state transition should create a structured event.

Examples:

```yaml
battle_events:
  - challenge_created
  - challenge_accepted
  - challenge_refused
  - battle_started
  - entry_submitted
  - battle_revealed
  - voting_opened
  - vote_cast
  - battle_finished
  - chef_defeated
  - crown_awarded
  - rank_promoted
```

Reason:

The same event data should later power:

* battle room logs;
* homepage activity;
* chef profiles;
* notifications;
* admin audit views;
* weekly recaps;
* social media cards.

Do not hardcode battle news separately from battle events unless there is a clear reason.

---

# Public / Private Event Separation

Not every event should be public.

Use two levels:

```yaml
event_visibility:
  public:
    - battle_started
    - battle_revealed
    - battle_finished
    - chef_defeated
    - crown_awarded
    - rank_promoted
  private_or_admin:
    - vote_cast
    - suspicious_vote_flagged
    - moderation_note_added
    - admin_override
```

This prevents feed spam and protects moderation logic.

---

# Final Safety Reminder

When unsure, stop.

Ask the user.

Production safety is more important than speed.
Branch cleanliness is more important than clever shortcuts.
A small tested feature is better than a large unfinished system.
