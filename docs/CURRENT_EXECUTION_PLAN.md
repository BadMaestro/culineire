# Current Execution Plan

```yaml
document:
  id: "current-execution-plan"
  version: "1.0.0"
  status: "ACTIVE_AFTER_OWNER_MERGE"
  phase: "Documentation Reset COMPLETE -- next stage is fresh-session bootstrap"
  owner: "CulinEire Product Owner"
  canonical_path: "/docs/CURRENT_EXECUTION_PLAN.md"
  last_updated: "2026-07-21"
```

**Documentation Reset and Coordination Reboot is complete** (integration
commit recorded in git history: `integration/documentation-reset` merged to
`main`). All three work packages (A: Ember, B: Bolt, C: GreenBear) reported
`COMPLETE` and were merged without conflict. See section 6 for the verified
gate values. The next stage is a fresh-session bootstrap by all three agents
against the new `main` -- no agent should continue planning or implementation
work from a pre-reset session's context; re-read the five active documents
and re-post the cold-start record per `AGENTS.md` section 3 before any
further work.

## 1. Immediate objective

Replace the accumulated Markdown instruction system with five active documents,
archive the previous project-owned Markdown corpus, preserve useful evidence,
reset active CoWork tasks without destroying agent identities or connections,
and establish a working distributed-test protocol.

No Arena implementation begins during this phase.

## 2. Active-document allowlist

After completion, the only active project instruction Markdown files are:

```text
/AGENTS.md
/CLAUDE.md
/docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md
/docs/TECHNICAL_STANDARDS.md
/docs/CURRENT_EXECUTION_PLAN.md
```

Every other project-owned Markdown file must be archived or presented to the
Product Owner as a documented technical exception.

Target archive:

```text
/docs/archive/pre-constitution-reset-2026-07-20/
```

Do not create additional active Markdown reports. Use JSON for inventories and machine-readable state.

## 3. Entry gate

Before any work package starts, all three agents must:

1. fetch the same approved base commit;
2. work in separate branches and worktrees;
3. read the five active documents;
4. complete the cold-start record;
5. connect CoWork pollers;
6. perform round-trip messages among Ember, GreenBear, and Bolt;
7. post branch, commit, machine, core count, task, and file ownership.

Required coordination record:

```yaml
coordination_reset:
  base_commit: ""
  agents:
    Ember:
      machine: ""
      logical_cores: 0
      branch: ""
      poller_connected: false
      round_trip_confirmed: false
    GreenBear:
      machine: ""
      logical_cores: 0
      branch: ""
      poller_connected: false
      round_trip_confirmed: false
    Bolt:
      machine: ""
      logical_cores: 0
      branch: ""
      poller_connected: false
      round_trip_confirmed: false
  old_active_tasks_closed_or_archived: false
  identities_preserved: true
  connections_preserved: true
  ready: false
```

No agent starts its work package until `ready: true`.

## 4. Parallel work packages

The agents are equal peers. The ownership below is task ownership only.

### Work package A — Active-document integration

**Recommended owner:** Ember  
**Branch:** `docs/constitution-active-set`

Owned files:

```text
/AGENTS.md
/CLAUDE.md
/docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md
/docs/TECHNICAL_STANDARDS.md
/docs/CURRENT_EXECUTION_PLAN.md
```

Tasks:

- install the five supplied canonical documents;
- verify internal paths;
- ensure tool-specific startup behaviour loads `AGENTS.md` through the `CLAUDE.md` pointer where relevant;
- verify no rule is duplicated independently in `CLAUDE.md`;
- add no sixth active Markdown document;
- commit and push only the five active documents.

Do not archive old files in this branch.

Output to CoWork:

```yaml
active_set_handoff:
  branch: ""
  commit: ""
  files_installed: []
  links_verified: true
  extra_active_markdown_created: false
  ready_for_archive_rebase: true
```

### Work package B — Markdown archive migration

**Recommended owner:** Bolt  
**Branch:** `docs/archive-legacy-markdown`

Owned paths:

```text
/docs/archive/pre-constitution-reset-2026-07-20/**
/docs/archive/archive_manifest.json
```

Tasks:

1. inventory all tracked project-owned `*.md` files;
2. exclude the five active allowlisted files;
3. identify third-party, generated, submodule, or machine-required exceptions;
4. present genuine exceptions to the Product Owner rather than silently keeping them active;
5. use `git mv` where practical to preserve history;
6. preserve the original relative path inside the archive;
7. produce `/docs/archive/archive_manifest.json`;
8. mark every archived item `authority: historical`;
9. do not rewrite archived content;
10. do not delete legal, incident, accounting, or audit evidence;
11. commit and push only archive moves and the JSON manifest.

Manifest shape:

```json
{
  "archive_version": "2026-07-20",
  "base_commit": "",
  "active_markdown_allowlist": [],
  "archived": [
    {
      "original_path": "",
      "archive_path": "",
      "sha256": "",
      "authority": "historical",
      "retention_reason": ""
    }
  ],
  "exceptions_requiring_owner_decision": []
}
```

This branch must be rebased or recreated on top of Work Package A's accepted
commit before final merge so the five active files are not archived.

### Work package C — CoWork reset and distributed-test readiness

**Recommended owner:** GreenBear  
**Branch:** `ops/cowork-test-pool-reset`

This package must not modify the five canonical Markdown files.

Tasks:

- archive or close obsolete active CoWork tasks;
- preserve existing agent identities, connections, and required message history;
- confirm pollers for Ember, GreenBear, and Bolt;
- run round-trip message checks;
- prove that incoming messages are read and acknowledged before task completion;
- record the mapping between agents and the 8-core, 6-core, and 1-core machines;
- inventory the current test runner and test collection method;
- design a non-overlapping 8:6:1 timed-load shard manifest;
- do not run three duplicate full suites;
- run a small harmless shard-connectivity proof, not the entire 1,500-test suite, unless the Product Owner separately approves a full gate;
- report results to CoWork in YAML;
- place any machine-readable operational artifact in an owner-approved non-Markdown location.

Required output:

```yaml
cowork_and_test_pool_handoff:
  branch: ""
  commit: ""
  agents_connected:
    - "Ember"
    - "GreenBear"
    - "Bolt"
  round_trip_passed: true
  old_tasks_closed_or_archived: true
  identities_preserved: true
  connections_preserved: true
  machine_map:
    primary_8_core: ""
    secondary_6_core: ""
    linode_1_core: ""
  test_collection_count: 0
  shard_method: "historical-duration | deterministic"
  duplicate_test_execution: false
  full_suite_run: false
  blockers: []
```

## 5. Integration order

1. Product Owner reviews Work Package A.
2. Accept the active-set commit.
3. Work Package B rebases or recreates its archive moves on top of A.
4. Product Owner reviews the archive manifest and any exceptions.
5. Merge the archive migration only after approval.
6. Review Work Package C's CoWork and test-pool evidence.
7. Do not merge operational code changes unless separately authorised.
8. After all three handoffs, one temporary integration editor updates this plan in a scoped owner-approved commit. That role is not managerial.

No agent merges into the production branch without owner instruction.

## 6. Verification gate

The documentation reset is complete only when:

```yaml
documentation_reset_gate:
  five_active_markdown_files_present: true
  additional_active_project_instruction_markdown: 0
  legacy_markdown_archived: true
  archive_manifest_complete: true
  archive_exceptions_owner_resolved: true
  cowork_identities_preserved: true
  cowork_connections_preserved: true
  all_pollers_connected: true
  three_way_round_trip_confirmed: true
  highest_priority_message_rule_verified: true
  distributed_test_machine_map_confirmed: true
  non_overlapping_shard_method_confirmed: true
  production_code_modified: false
  arena_implementation_started: false
```

**Verified true, integration commit on `main` (2026-07-21):**

```yaml
documentation_reset_gate_actual:
  five_active_markdown_files_present: true          # AGENTS.md, CLAUDE.md, docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md, docs/CURRENT_EXECUTION_PLAN.md, docs/TECHNICAL_STANDARDS.md all present, confirmed on disk
  additional_active_project_instruction_markdown: 0  # content_prompts/README.md remains active but is a runtime existence-check dependency (recipes/views.py:164), not an instruction document -- owner classified it NON_AUTHORITATIVE_RUNTIME_EXCEPTION, may_define_project_rules: false
  legacy_markdown_archived: true                     # 185 of 191 tracked *.md files moved via git mv, 100% rename-detected (zero content change) into docs/archive/pre-constitution-reset-2026-07-20/
  archive_manifest_complete: true                    # docs/archive/archive_manifest.json: base_commit, five-file allowlist, 185 archived entries (sha256 + retention_reason each), one exception entry
  archive_exceptions_owner_resolved: true             # both flagged items resolved by direct owner instruction: content_prompts/README.md KEEP_AT_RUNTIME_PATH; root README.md KEEP_ARCHIVED (not restored)
  cowork_identities_preserved: true                   # per ops/test_pool/work_package_c_report.json: identities_preserved true, agents_connected [Ember, GreenBear, Bolt]
  cowork_connections_preserved: true                  # same source: connections_preserved true
  all_pollers_connected: true                         # Bolt's own poller confirmed active (cron job, 3-min interval) this session; WP C report confirms all three
  three_way_round_trip_confirmed: true                 # WP C report: round_trip_passed true; independently reproduced this session via direct ACK exchanges with both GreenBear and Ember on the bootstrap and Work Package B threads
  highest_priority_message_rule_verified: true         # demonstrated in practice this session: incoming GreenBear messages about an independent, concurrent audit-closure merge were read and acknowledged before proceeding with Work Package B
  distributed_test_machine_map_confirmed: true         # ops/test_pool/shard_manifest.json: weights 8:6:1, target_share/actual_share both recorded, machine_map owner-resolved with hostname evidence preserved (not silently overridden)
  non_overlapping_shard_method_confirmed: true          # shard_manifest.json: deterministic split by test-collection count (1429 tests, cross-checked two ways), explicit note to refine to historical-duration once real timings exist; zero duplicate/omitted tests
  production_code_modified: false                      # verified: git diff --name-only <previous main 7c2e1731>..<integration HEAD> -- '*.py' '*.html' '*.css' '*.js' returned empty; no migrations, no settings changed
  arena_implementation_started: false                   # no template, CSS, JS, or view code touched by any of the three work packages
```

Next stage: fresh-session bootstrap by all three agents against the new
`main` (section 7 below), not new 2D implementation work.

## 7. First technical gate after documentation reset

Before 2D implementation planning becomes code-ready:

1. verify actual production Arena visibility;
2. confirm it is staff/superuser only before release;
3. identify and separately approve any required access correction;
4. verify the current production base commit;
5. verify the confirmed `crown_streak`, `crown_ladder`, and `recent_gifts` context defect;
6. decide Battle Room navigation versus embedded presentation;
7. decide whether the privileged Live Arena visual preview remains;
8. approve the 2D information hierarchy;
9. approve responsive and accessibility acceptance criteria;
10. agree on Master Console compatibility strategy.

No broad audit is required. These are targeted gates.

## 8. Code-readiness status

```yaml
status:
  safe_to_archive_legacy_markdown: true
  safe_to_reset_cowork_tasks: true
  safe_to_plan_2d_after_reset: true
  safe_to_write_2d_code_now: false
  safe_to_delete_legacy_arena_code: false
  safe_to_release_arena: false
```

## 9. Completion report

Each work package reports:

```yaml
task_completion:
  agent: ""
  work_package: "A | B | C"
  status: "COMPLETE | PARTIAL | BLOCKED"
  branch: ""
  commit: ""
  pushed: false
  files_changed: []
  cowork_messages_processed: true
  tests_run: []
  production_code_modified: false
  implementation_started: false
  blockers: []
  owner_decisions_required: []
```
