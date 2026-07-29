AGENT ONBOARDING RUNBOOKS
=========================

One file per agent. The Owner points an agent here by name:

    "читай Onboarding GreenBear"   ->  ops/onboarding/greenbear.txt
    "читай Onboarding Bolt"        ->  ops/onboarding/bolt.txt
    "читай Onboarding Ember"       ->  ops/onboarding/ember.txt

WHY THESE LIVE IN GIT
---------------------

The agents are on different computers. Before 2026-07-29 these runbooks existed
only as loose files on the Owner's workstation, which meant an agent on any
other machine could not read its own instructions at all, and there was no way
to tell whether two copies had drifted apart.

Git is the one channel every agent already shares. A runbook here is readable
from any machine, carries its own history, and has exactly one current version:

    git fetch origin
    git show origin/main:ops/onboarding/greenbear.txt

READ FROM origin/main, NOT FROM THE WORKING TREE
------------------------------------------------

The same rule as the canonical documents. A local checkout can be behind, on
another branch, or carrying somebody's uncommitted edit. `git show origin/main:`
cannot.

WHAT THESE ARE, AND WHAT THEY ARE NOT
-------------------------------------

A runbook is the cold-start procedure for one agent: how to load the project
state, verify git, reconcile against production, write the bootstrap record, and
report readiness. It is operational, not authoritative.

It is NOT project instruction Markdown and does not fall under the five-document
allowlist in AGENTS.md section 10. It cannot define scope, architecture, design,
acceptance or release policy, and it never overrides the constitution.

If a runbook and AGENTS.md ever disagree, AGENTS.md wins and the runbook is
corrected in the same task.

KEEPING THEM IN SYNC
--------------------

When the Owner changes how the agents work, every runbook that carries the old
rule is corrected in the same change as the constitution. A runbook still
describing a repealed arrangement is worse than no runbook: an agent will follow
it, in good faith, and cite it afterwards.

Current: bolt.txt 3.1, greenbear.txt 3.1, ember.txt 3.1 — all three against
AGENTS.md v2.0.0. Every agent on the section-1 roster has one.
