AGENT ONBOARDING PACKAGE
========================
Package version: 1.5b
Against: AGENTS.md v2.1.0 on origin/main
Assembled: 2026-08-04, on the Owner's order

WHEN THE OWNER SAYS "ONBOARDING <NAME>"
---------------------------------------

That is the whole trigger. It means: stop, load the project, and come back
ready. The agent named goes to its own file and does what is written there.

    "Onboarding GreenBear"   ->  ops/onboarding/greenbear.txt
    "Onboarding Bolt"        ->  ops/onboarding/bolt.txt
    "Onboarding Ember"       ->  ops/onboarding/ember.txt

WHERE TO READ IT FROM — THIS IS THE PART THAT GETS SKIPPED
----------------------------------------------------------

NOT from the working tree. NOT from memory. NOT from a copy on somebody's
desktop. From origin/main, every time:

    git fetch origin
    git show origin/main:ops/onboarding/greenbear.txt

A local checkout can be behind, on another branch, or carrying an uncommitted
edit. `git show origin/main:` cannot be any of those. The same rule governs the
five canonical documents, and it exists because it has already failed the other
way: before 2026-07-29 these runbooks lived only as loose files on the Owner's
workstation, so an agent on any other machine could not read its own instructions
at all, and nothing could tell whether two copies had drifted.

The same trap bit the reference material on 2026-08-04: the Design Template was
being measured against while it existed only inside one zip on one desktop, and a
whole measurement matrix turned out to have been taken from a prototype the Owner
had rejected. If it is not in git, it cannot be checked. See
ops/reference/design_arena/README.md.

THE ORDER OF READING — DO NOT REORDER IT
-----------------------------------------

  1. AGENTS.md                                 the constitution, canonical
  2. AGENTS.md section 1a and section 18       the GreenBear law, read it early
  3. docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md   what the product is
  4. docs/CURRENT_EXECUTION_PLAN.md            the phase
  5. docs/TECHNICAL_STANDARDS.md               how code is written here
  6. docs/ARENA_BATTLE_PLAN.md                 the board: what is next, and whose
  7. ops/onboarding/<your name>.txt            your own cold-start procedure

All seven from origin/main. Then verify git, reconcile against production, write
the bootstrap record, and report ONE line to the Owner — not the record itself.

THE ONE THING EVERY AGENT MUST KNOW BEFORE TOUCHING ANYTHING
-------------------------------------------------------------

`greenbear` IS THE OWNER'S OWN ACCOUNT. Superuser id 1, author slug `greenbear`,
name GreenBear, Culinary Master, holder of the Arena crown. Verified on
production 2026-08-04.

His account, his privileges, his slug, his profile, his avatar and portrait
assets, his presence event, his personal page, the is_god_author branch and
god_mode.css are UNTOUCHABLE — including indirectly, through a shared hero
template or hero CSS. Code special-cased for him is deliberate design: do not
refactor "greenbear" into settings.OWNER_SLUG, do not abstract it, do not tidy
it. AGENTS.md section 18 has the full text and the Owner's own words. It carries
the only stated consequence in the constitution: the agents are replaced.

There is a NAMING COLLISION and it is nobody's fault but it is dangerous: an
agent is also called GreenBear. When a slug, a path, a fixture or an asset says
`greenbear`, default to THE OWNER, not to the agent. That mistake was made on
2026-08-04 — the agent nearly proposed deleting the Owner's own portrait because
it read his name as its own.

WHAT A RUNBOOK IS, AND WHAT IT IS NOT
--------------------------------------

A runbook is the cold-start procedure for one agent: load state, verify git,
reconcile against production, write the bootstrap record, report readiness. It is
operational, not authoritative.

It is NOT project instruction Markdown and does not fall under the five-document
allowlist in AGENTS.md section 10. It cannot define scope, architecture, design,
acceptance or release policy, and it never overrides the constitution.

If a runbook and AGENTS.md ever disagree, AGENTS.md wins and the runbook is
corrected in the same task.

THE ROSTER THIS PACKAGE COVERS
-------------------------------

AGENTS.md section 1 is the single authoritative roster. As of package 1.5b it is
Ember, Bolt, GreenBear — three equal peers, no roles, no director, no gate
holder. Any agent who knows how may deploy, one at a time, after proving every
check in section 8 on their own work.

See AGENT_PROFILES.txt beside this file for what is known about each agent, what
is not, and who said so. Anything an agent has not stated about itself is written
there as unstated rather than guessed.

KEEPING THEM IN SYNC
--------------------

When the Owner changes how the agents work, every runbook carrying the old rule
is corrected in the same change as the constitution. A runbook still describing a
repealed arrangement is worse than no runbook: an agent will follow it in good
faith and cite it afterwards.

Package 1.5b contents:
    README.txt            this file — the entry point and the routing
    AGENT_PROFILES.txt    who the three agents are, and what is not known
    greenbear.txt         cold-start runbook, v3.1
    bolt.txt              cold-start runbook, v3.1
    ember.txt             cold-start runbook, v3.1
