# Evidence — Backend and Domain Audit (BOLT)

Deep evidence chains for the conclusions in FEATURE_MAP.md and
FILE_INVENTORY.md that carry the most weight for the 2D rebuild decision.
Each entry follows the protocol's required fields.

## 1. The backend has no 3D-specific logic to begin with

- **File path:** `chef_battle/selectors.py`
- **Relevant symbol:** `get_arena_geometry()`, `SPECTATOR_RING_SEGMENTS = (40, 48, 56, 64, 72, 80, 88, 96)` (referenced this session at `selectors.py:1245`)
- **How the file is reached:** Imported by `chef_battle/views.py`, called inside `arena()` and `arena_state()` to build the JSON/context payload.
- **What depends on it:** `static/js/arena_render.js` (GreenBear's lane) reads the ring/segment counts to lay out the SVG; `recipes/views.py` `ARENA_BUILD_STAGES` references it as the origin of the geometry contract.
- **Classification:** REUSE_AS_IS
- **Confidence:** confirmed
- **Reasoning:** The geometry contract is a declarative data structure — ring counts, segment counts, rank-to-ring mapping — with no coordinates, angles, or projection math anywhere in this file. The projection/tilt/perspective math that made the arena LOOK 3D lived entirely in `static/js/arena_render.js` and `static/css/arena_render.css` (frontend), confirmed by this session's own earlier reading of those files' `projector()` function and CSS `perspective`/`rotateX` history. This means a 2D rebuild does not need to touch the backend contract at all — it needs a new frontend consumer of the same data. This is the single most important finding for scoping the 2D rebuild: **the backend was never the source of the cinematic complexity.**

## 2. The arena's centre-stage payload already carries what a "fighters" panel needs

- **File path:** `chef_battle/views.py`
- **Relevant symbol:** `_arena_center(active_battle)`, lines 783-824
- **How the file is reached:** Called from both `arena()` and `arena_state()` — the same function serves the initial page load and the poll refresh, so there is exactly one place this contract is defined, not two that could drift.
- **What depends on it:** Any frontend template/script rendering the centre of the arena (currently GreenBear's `arena_render.js`/`arena_command_deck.css`).
- **Classification:** REUSE_AS_IS
- **Confidence:** confirmed
- **Reasoning:** Read directly this session (prior to this audit) while investigating the "fighters" board stage: the function already returns `challenger.name` / `challenger.avatar_url` and `opponent.name` / `opponent.avatar_url` when an active battle exists (lines 799-806), and `name`/`avatar_url`/`crown_until` for the crown holder when no battle is active (lines 816-822). It was reported by GreenBear as "no backend data" for this stage, which was incorrect — the actual gap is that no `active_battle` exists in production right now to exercise the branch, not a missing capability. This was corrected on the live build board this session (`recipes/views.py`, `fighters` stage). Relevant for 2D scoping: a "fighters" panel in a 2D layout can be built against this exact payload shape without any backend change.

## 3. The access gate is now independent of chef enrollment (owner's rule, verified end-to-end)

- **File path:** `chef_battle/access.py`
- **Relevant symbol:** `is_battle_visible(request)`, lines 11-32
- **How the file is reached:** `chef_battle_guard` decorator, applied to every `chef_battle` view per its own docstring at `views.py` (decorator definition, `access.py:69-93`).
- **What depends on it:** Every gated view in `chef_battle/views.py` — confirmed via the decorator pattern, not individually enumerated for all 76 URL entries this pass.
- **Classification:** REUSE_AS_IS
- **Confidence:** confirmed
- **Reasoning:** Modified this session (commit `38c352a4`) to add: `author = getattr(user, "recipe_author_profile", None); return author is not None` as an independent branch, replacing a narrower `has_bearseeker_privileges` check that was strictly subsumed by it. Verified by 2 new tests plus the full 697-test suite passing. **Open item, not yet closed:** GreenBear reported this session (message id 1842, read during this session) that all 4 live test accounts are staff/superuser, so the new "plain author, not staff" branch is proven by unit tests but not yet exercised live/E2E by a real non-staff account. This is recorded here as unresolved pending either a genuine non-staff test account or an owner click-through.

## 4. Self-vote is now blocked at the database, not only in application code

- **File path:** `chef_battle/models.py`
- **Relevant symbol:** `CheckConstraint` named `chef_cannot_vote_for_themselves`, line 375 (per this session's earlier work); denormalised `voter_author` field on `BattleVote`
- **How the file is reached:** Enforced by PostgreSQL itself on every `INSERT`/`UPDATE` to `BattleVote`, independent of which code path writes the row.
- **What depends on it:** `chef_battle/views.py:battle_vote`, but also any future code path, management command, or migration data-fix that ever constructs a `BattleVote` directly.
- **Classification:** REUSE_AS_IS
- **Confidence:** confirmed
- **Reasoning:** Before this session, the only self-vote guard was `BattleVote.clean()`, which Django does not call from `.save()` — confirmed by a new test this session that writes a self-vote directly through `.save()` and asserts `IntegrityError`. Migration `0083` backfills `voter_author` from `RecipeAuthor.user` and aborts (with the offending row ids) if any historical self-vote would violate the new constraint — confirmed by reading the migration file directly. `voter_author` is nullable and denormalised specifically because `voter` is a `User` FK and `voted_for` is a `RecipeAuthor` FK on different tables; a `CheckConstraint` cannot join, so comparing the two ids directly would have been wrong (would catch coincidental id matches, not real self-votes) — this reasoning is preserved in the model's own code comment, confirmed read this session.

## 5. Request-fingerprint hashing was not real anonymisation before this session

- **File path:** `chef_battle/services.py`
- **Relevant symbol:** `hash_request_value`, line 84
- **How the file is reached:** Called from `chef_battle/views.py` (`battle_vote`) and `chef_battle/fraud.py` (duplicate-device/vote-rate gates).
- **What depends on it:** `BattleVote.ip_hash`/`user_agent_hash`/`session_key_hash`, `VoteIntegrityEvent`'s same three fields.
- **Classification:** REUSE_AS_IS (post-fix)
- **Confidence:** confirmed
- **Reasoning:** Before this session, `hash_request_value` was a bare `hashlib.sha256` of the input — an IPv4 address is a 4-billion-value space, rehashable in seconds, so the stored hash did not anonymise anything in practice. Rewritten this session to HMAC keyed on `SECRET_KEY`. A `hash_scheme` field distinguishes old (`v1`, unrecomputable, left alone) from new (`v2`) rows so the fraud gates never compare across schemes. Verified by a new test asserting the HMAC output does not equal the bare-SHA256 digest of the same input.

## 6. Vote/spectator eligibility does not require chef enrollment (matches the owner's golden rule)

- **File path:** `chef_battle/views.py`
- **Relevant symbol:** `battle_vote`, line 1559-1572 (authentication check, no enrollment check)
- **How the file is reached:** `chef_battle:battle_vote` URL, POST-only.
- **What depends on it:** `docs/agents/memory/golden_rule_author_can_visit_arena.md`'s stated rule.
- **Classification:** REUSE_AS_IS
- **Confidence:** confirmed
- **Reasoning:** The gate is `request.user.is_authenticated`, full stop — no check anywhere in this function for `ChefBattleProfile.enrolled_at` or any chef-specific flag. `voter_author = get_author_for_user(user)` is looked up and stored, but is nullable and does not block the vote if absent. This already satisfies the owner's rule that voting requires being a registered user, not being an enrolled chef, independent of the arena-visibility fix made elsewhere this session.

## 7. Documentation conflict: the design-target document still describes a 3D camera angle

- **File path:** `docs/chef_battle/arena_mockup_spec.md`
- **Relevant symbol:** Lines 20, 36, 40, 156 (quoted in BOOTSTRAP.yml)
- **How the file is reached:** Cited directly by 5 live code comments this session confirmed by grep: `recipes/views.py:2723`, `static/css/arena_command_deck.css:178`, `static/css/arena_hall.css:4`, `static/css/arena_render.css:340`, `static/js/arena_render.js:356`.
- **What depends on it:** The current (pre-2D-decision) frontend's stated design target.
- **Classification:** CONFLICT
- **Confidence:** confirmed (the conflict itself; not a judgment on which document should win)
- **Reasoning:** This document states the visual target IS a 56-degree camera perspective and explicitly frames the current flat rendering as a gap to close ("Our arena renders a strict plan view" is described as the thing still needing correction, not the goal). AUDIT.txt's `current_decision` states the opposite: the cinematic/3D direction is no longer the target, future direction is a simpler 2D interface. Per the protocol's `conflict_protocol`, this is logged as CONFLICT with `user_decision_required: true` — this backend audit does not resolve it, since the correct visual target is a product decision, not a backend fact.

## 8. Live CoWork evidence: 697/697 backend + related tests pass on this exact commit lineage

- **File path:** N/A (test run, not a file)
- **Relevant symbol:** `chef_battle`, `recipes`, `presence` test suites
- **How the file is reached:** `manage.py test chef_battle recipes presence --noinput --parallel 8`
- **What depends on it:** Confidence in every REUSE_AS_IS classification above.
- **Classification:** N/A (this is the evidence, not a classified item)
- **Confidence:** confirmed
- **Reasoning:** Run earlier this session against commit `2a28e4b2` (this audit's base commit) before this audit branch was created — 697 tests, 0 failures, 2 skipped (pre-existing skips, not investigated this pass). `manage.py check` (0 issues) and `manage.py makemigrations --check --dry-run` (no changes detected) were re-run during this audit itself, against the audit branch, confirming the base commit's state is exactly reproducible.
