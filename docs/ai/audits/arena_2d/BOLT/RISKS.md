# Risks — Backend and Domain Audit (BOLT)

## 1. Documentation conflict on the visual target (product decision required)

`docs/chef_battle/arena_mockup_spec.md` still states a 56-degree camera
perspective as the design target; AUDIT.txt states the opposite (simple 2D,
3D/cinematic abandoned). See `EVIDENCE.md` item 7. **This backend audit does
not resolve it — logged per `conflict_protocol` with
`user_decision_required: true`.** Until the owner decides, any 2D-rebuild
work risks being built against a document that no longer reflects the
target, or against no document at all.

## 2. The access.py fix is unit-tested but not yet E2E-verified with a real non-staff account

`chef_battle/access.py`'s new "any registered author" branch (this session,
commit `38c352a4`) is proven by 2 new tests plus the full suite, but
GreenBear reported (message id 1842, read during this session) that all 4
live test accounts are staff/superuser — none of them exercises the new
code path live. Risk: if the unit test's mental model of "authenticated
user with a RecipeAuthor and nothing else" differs subtly from how a real
account actually looks in production (e.g. an unexpected middleware or
session state), that gap would not be caught until a real user hits it.
**Recommended action:** either the owner performs one live click-through as
a genuinely non-staff author account, or a disposable test account is
created for exactly this check and nothing else (per GreenBear's stated
hard rule, he will not create or log into accounts himself).

## 3. Twelve backend files not traced to full evidence depth this pass

`chef_battle/arena_snapshot.py` and eleven adjacent-subsystem files (energy,
Stripe, observer, clan, faction, season, reaction, token_config, forms,
admin — see `FILE_INVENTORY.md`'s last row) were confirmed import-clean via
`manage.py check` but not individually traced for callers, dead-code status,
or duplication. Risk: a 2D-rebuild scoping decision that assumes "everything
outside the core arena path is safe to leave alone" could miss something
`arena_snapshot.py` specifically does, since its name suggests direct
overlap with the geometry/state contract this audit DID trace in
`selectors.py`. **Recommended action:** a follow-up pass specifically on
`arena_snapshot.py` before the 2D rebuild boundary is finalized, since it is
the one file in the unverified set whose name suggests direct relevance.

## 4. Notifications delivery mechanism unverified

`_notify_chef` is called from multiple places in `views.py` per this
session's earlier reading, but its actual delivery mechanism (email,
in-app, both) was not traced this pass. Risk: if a 2D rebuild changes any
page the notification links point to, an untraced notification template
could silently break. **Recommended action:** trace `_notify_chef`'s full
call graph before touching any URL a notification might reference.

## 5. Test-suite composition is not yet separated into "backend-asserting" vs "presentation-asserting"

697 tests currently pass, but this audit has not classified which of the
465 `chef_battle` tests assert pure backend behaviour (must survive a 2D
rebuild unchanged) versus which assert specific rendering/geometry outcomes
that a 2D layout might legitimately need to change (e.g. exact pixel/ring
counts tied to the current octagonal SVG). Risk: a future 2D
implementation phase could either (a) break backend contract tests without
realizing it, thinking they were "just visual," or (b) treat legitimate
backend regressions as acceptable rebuild fallout. This is the dependency
logged against CLAUDE_B (Ember) in `STATUS.yml` — flagged, not resolved,
by this lane.

## 6. Production risk from this audit's own artifacts: none identified

`git status --short` before this audit began showed the same 5 untracked
paths present since a prior session's work (`.env.backup-1111`,
`AI_EXPORT/`, three root-level report `.md` files) — none created by this
audit, none touched by this audit. This audit branch (`audit/arena-2d-bolt`)
contains only the 7 required audit files under
`docs/ai/audits/arena_2d/BOLT/`, confirmed by `git status` before the
initial commit. No production file has been modified, deleted, or renamed.
