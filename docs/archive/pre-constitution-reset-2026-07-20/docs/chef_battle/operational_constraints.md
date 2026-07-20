## Operational Constraints / Production Workflow Rules

These rules are mandatory for every development task.

The project is a real production website. Treat every change as production-sensitive, even when working locally or on a feature branch.

---

# 1. Branch isolation rules

Never mix unrelated work in the same branch or commit.

Before making any change, always check:

```bash
git status
git branch --show-current
git log --oneline -5
```

If the working tree contains unrelated changes, stop and report them clearly.

Do not continue until the user confirms what to do.

Required behaviour:

* Work only on the branch assigned for the current task.
* Do not include files from other tasks.
* Do not commit unrelated modifications.
* Do not silently fix unrelated issues.
* Do not switch branches if there are uncommitted changes.
* Do not merge branches unless explicitly instructed.
* Do not rebase production branches unless explicitly instructed.
* Do not rewrite history on shared branches.
* Do not use `git reset --hard`, `git clean -fd`, force push, or destructive Git commands without explicit approval.

If unrelated changes exist, respond with:

```yaml
status: "blocked"
reason: "Working tree contains unrelated changes."
current_branch: "<branch-name>"
unrelated_files:
  - "path/to/file"
required_user_decision:
  - "Confirm whether to commit, stash, discard, or move these changes before continuing."
```

---

# 2. Commit and push rules

The user does not want to repeatedly ask for commits and pushes.

When a task is complete and tests pass:

1. Commit the completed task.
2. Push the branch.
3. Report the commit hash.
4. Provide the deployment command immediately.

Do not leave finished work uncommitted unless the user explicitly asked for no commit.

Use clean, descriptive commit messages.

Example:

```bash
git add <changed-files>
git commit -m "Add Chef Battle challenge foundation"
git push origin <branch-name>
```

Never commit:

* debug prints;
* temporary files;
* local settings;
* secrets;
* `.env` files;
* database dumps;
* unrelated generated files;
* accidental IDE files;
* broken experimental work.

Before committing, run:

```bash
git diff --check
git status
```

---

# 3. Deployment responsibility

The user wants to perform deployment manually.

Do not deploy automatically unless explicitly instructed.

After every successful push, always finish with:

```text
Готово шеф — вот команда для деплоя:
```

Then provide the deployment command in a clean highlighted shell block:

```bash
cd /srv/culineire/current && bash /srv/culineire/current/deploy/update.sh
```

If the deployment command depends on a branch, migration, collectstatic, or special environment variable, state that clearly before the command.

Example final deployment note:

```yaml
deploy_ready: true
branch_pushed: "feature/chef-battle-phase-1"
commit: "abc1234 Add Chef Battle challenge foundation"
migrations_required: true
collectstatic_required: true
recommended_deploy_command: "cd /srv/culineire/current && bash /srv/culineire/current/deploy/update.sh"
```

Then show:

```bash
cd /srv/culineire/current && bash /srv/culineire/current/deploy/update.sh
```

---

# 4. Production safety rules

Always assume that the server is production.

Be extremely careful with:

* migrations;
* payment logic;
* Stripe;
* email sending;
* webhooks;
* user data;
* moderation states;
* file uploads;
* media files;
* permissions;
* legal pages;
* public URLs;
* SEO metadata;
* templates used across the whole site;
* shared CSS;
* database writes;
* management commands.

Before making risky changes, explain the risk and ask for confirmation.

High-risk actions require explicit approval:

* deleting data;
* changing existing migrations;
* editing production settings;
* changing Stripe/webhook/payment logic;
* changing authentication or permissions;
* changing email sending behaviour;
* running data migrations;
* running destructive SQL;
* modifying deployment scripts;
* changing NGINX Unit or server config;
* restarting services manually;
* applying large refactors;
* touching unrelated apps.

If unsure, stop and ask.

---

# 5. Clarifying question requirement

If the task is unclear, incomplete, ambiguous, contradictory, or risky, ask clarifying questions before coding.

Do not guess silently.

Ask questions especially when:

* the target branch is unclear;
* the feature scope is unclear;
* the requested behaviour affects production users;
* there are multiple valid implementation options;
* the change may require migrations;
* the change may affect payments, email, permissions or public content;
* existing code structure is unknown;
* the working tree is dirty;
* the user’s instruction conflicts with previous project rules.

Use this format:

```yaml
status: "clarification_required"
reason: "The task affects production behaviour and the expected rule is ambiguous."
questions:
  - "Should this apply to all users or only approved chefs?"
  - "Should this be visible publicly in Phase 1 or admin-only?"
  - "Should I create a new branch for this task?"
```

Do not proceed until the user answers.

---

# 6. Command visibility rule

Do not bury important commands inside long explanations.

The user does not want to search through a wall of text.

Every response that requires terminal action must include a separate section:

```markdown
# Commands to Run
```

Put only the required commands there.

Example:

```bash
cd /srv/culineire/current
git status
python manage.py check
python manage.py test chef_battle
```

For deployment, always include a separate final section:

```markdown
# Deploy Command
```

And show:

```bash
cd /srv/culineire/current && bash /srv/culineire/current/deploy/update.sh
```

---

# 7. Final response format after coding

After completing a coding task, use this exact structure:

````markdown
# Summary

Short explanation of what was completed.

# Changed Files

| File | Change |
|---|---|
| `path/to/file.py` | Description of change. |

# Tests Run

```yaml
tests_run:
  - command: "python manage.py check"
    result: "PASS"
  - command: "python manage.py test chef_battle"
    result: "PASS"
  - command: "git diff --check"
    result: "PASS"
````

# Git

```yaml
branch: "<branch-name>"
commit: "<commit-hash> <commit-message>"
pushed: true
working_tree_clean: true
```

# Deployment Notes

```yaml
migrations_required: true
collectstatic_required: true
production_risk: "low | medium | high"
manual_checks_after_deploy:
  - "Open /battle/"
  - "Create a test challenge."
  - "Check homepage battle news."
```

# Deploy Command

Готово шеф — вот команда для деплоя:

```bash
cd /srv/culineire/current && bash /srv/culineire/current/deploy/update.sh
```

````

---

# 8. If work is incomplete

If the task is not fully complete, do not pretend it is complete.

Use:

```yaml
status: "partial"
completed:
  - "What was done."
not_completed:
  - "What remains."
blocked_by:
  - "Reason or missing decision."
safe_to_deploy: false
next_steps:
  - "Concrete next action."
````

Do not provide a deploy command if the work is not safe to deploy.

Instead say:

```text
Не деплоить пока. Работа не готова к production.
```

---

# 9. If tests fail

If tests fail:

* do not commit unless explicitly asked;
* do not push unless explicitly asked;
* do not provide a deploy command;
* explain the failure clearly;
* provide the next fix step.

Use:

```yaml
status: "blocked"
reason: "Tests failed."
failed_tests:
  - command: "python manage.py test chef_battle"
    result: "FAIL"
failure_summary:
  - "Short explanation."
safe_to_deploy: false
next_steps:
  - "Fix failing test."
```

---

# 10. Final operating principle

Protect production first.

Then protect branch cleanliness.

Then protect user time.

The correct workflow is:

```text
understand task
→ check branch and working tree
→ ask questions if unclear
→ implement only scoped change
→ test
→ commit
→ push
→ give clean YAML report
→ give deploy command clearly
```

The user should never need to remind you to:

* be careful with production;
* keep branches isolated;
* avoid mixed commits;
* run tests;
* commit finished work;
* push finished work;
* provide the deployment command.
