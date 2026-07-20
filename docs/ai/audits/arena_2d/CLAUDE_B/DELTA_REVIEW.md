# CLAUDE_B Arena Audit Delta Review

## Exact target commit verified

- Worktree: `E:\CulinEire Project\CulinEire\delta-worktrees\CLAUDE_B`
- Branch: `audit/arena-2d-delta-claude-b`
- Verified `HEAD`: `2a28e4b2c3be0e1baad7340e06aa1f020931e025`
- Audited comparison only: `726e338076462982185e3caa7564cc37977a18c9..2a28e4b2c3be0e1baad7340e06aa1f020931e025`
- The worktree was clean before this report was created.

## Changed files in owned lane

Reviewed integration, regression-test, documentation, design-system, and legacy-classification consequences in these changed files:

- `chef_battle/access.py`
- `chef_battle/tests.py`
- `config/release_journal.py`
- `docs/agents/CHEF_COMBATS_MANIFEST.md`
- `docs/agents/CLAUDE_RULES.md`
- `docs/agents/GOLDEN_RULES.md`
- `docs/agents/MANIFEST_DELTA.md`
- `docs/agents/README.md`
- `docs/agents/memory/golden_rule_author_can_visit_arena.md`
- `recipes/tests.py`
- `recipes/views.py`
- `static/css/arena.css`
- `static/css/arena_command_deck.css`
- `static/css/arena_deck_polish.css`
- `static/css/arena_hall.css`
- `static/css/arena_master_console.css`
- `static/css/arena_render.css`
- `static/css/base.css`
- `templates/base.html`
- `templates/moderation/arena_build_plan.html`

No JavaScript file, public Arena template, renderer partial, URL configuration, selector, image asset, or documented prototype caller changed in the delta.

## Previous audit conclusions still valid

- The public Arena remains a frontend-reconstruction boundary around an existing server-owned system. The route, payload, polling/action delegation, lifecycle, scoring, gifts, presence, and operator-console dependency conclusions are not invalidated.
- The procedural ring/seat renderer and cinematic presentation remain legacy presentation. Removing CSS perspective and obsolete occupant `scaleY` compensation strengthens, rather than reverses, the conclusion that 3D camera behavior is not part of the future boundary.
- The six Arena stylesheets remain simultaneously active and overlapping. Token substitutions did not consolidate ownership or make any sheet deletion-safe.
- The Arena Master Console still shares the renderer partial; none of the delta decouples it.
- Browser accessibility, responsive interaction, cascade behavior, and visual acceptance remain unproven by server tests.
- No file now meets the standard for `CONFIRMED_DEAD_CODE`. The old hall assets remain candidates only, and the octant prototype still has its documented manual caller.
- Public and broadcast payloads remain distinct contracts; the delta provides no evidence that they became duplicates.
- The stale proto-gate test and the initial crown/gift/streak binding issue identified by the original audit were not changed.

## Previous audit conclusions requiring amendment

1. **Dark-launch visibility is broader.** At the intended baseline, any authenticated user with a `RecipeAuthor` can access guarded Arena endpoints while `CHEF_BATTLE_ENABLED=False`. Anonymous users and authenticated users without an author profile still receive 404, and the Master Console remains separately restricted. The old conclusion that dark-launch access was limited to staff/superuser/bearseeker must be replaced with this exact rule.
2. **The palette conflict is reduced but not resolved.** Many repeated raw colors were replaced by existing tokens, Arena-local aliases, or new `:root` `--hall-*` tokens. This improves consistency and reduces literal duplication, but it also promotes a dark hall palette into the global token namespace. It does not establish the future light, semantic, single-entry 2D design system and does not remove the six-sheet cascade risk.
3. **Flat-presentation evidence is newer.** `arena_render.css` no longer declares perspective and no longer stretches live occupants with breakpoint-specific `scaleY`. The future recommendation is unchanged, but the current legacy renderer is flatter than it was at the audited base.
4. **The internal build board is not implementation authority.** It now archives 13 stages, marks full-bleed and HUD complete, adds acceptance criteria, and freezes later stages. These records describe current work status; they do not supersede the audit's requirement for owner-approved 2D scope or browser evidence.

## Newly discovered reusable functionality

- A tested visibility path for ordinary registered authors to watch the Arena during dark launch, independent of chef enrollment.
- Shared `--hall-*` and bronze tokens that can reduce repeated literals while legacy Arena/console styles remain in service. They are compatibility aids, not a recommended foundation for the future 2D palette.
- Build-board archive/live/frozen grouping plus per-stage acceptance-criterion fields. This is reusable as internal project-status infrastructure, not as a public Arena component.

## Newly discovered risks

- Repository guidance is internally inconsistent: `docs/agents/memory/golden_rule_author_can_visit_arena.md` and the implementation allow any author during dark launch, while `docs/agents/GOLDEN_RULES.md` still states that the Arena is hidden from everyone except staff/superuser until release.
- `CHEF_COMBATS_MANIFEST.md` prescribes a dark premium/esports UI, while `MANIFEST_DELTA.md` says the owner overrode that direction with a light parchment floor. Reading the manifest without its delta can reintroduce the presentation direction the audit recommends abandoning.
- Global `--hall-*` tokens make legacy cinematic colors easier to consume outside the Arena. A future 2D implementation could accidentally treat them as canonical product tokens despite the owner decision recorded in `MANIFEST_DELTA.md`.
- The build board records full-bleed/HUD as complete using stated measurements, but the delta adds no automated browser or accessibility evidence. Those status claims must not be treated as regression proof.
- Broader visibility increases the number of users exposed to Arena state/poll/ping paths during dark launch. Focused access tests pass, but browser and load behavior were not exercised in this reconciliation.

## Contract changes

- `is_battle_visible(request)` now returns true when the feature is public, the authenticated user is staff/superuser, or the authenticated user has any `RecipeAuthor`; `has_bearseeker_privileges` is no longer part of this gate.
- The change applies transitively to endpoints wrapped by `chef_battle_guard`, not only the Arena page. The focused suite verifies the page and state endpoint for the privileged path and preserves anonymous denial.
- Console authorization remains unchanged and separate.
- No public Arena payload key, polling URL, JavaScript interface, public template selector, renderer-partial contract, or broadcast snapshot contract changed in the CLAUDE_B-owned delta.
- Design variables changed: repeated literals were redirected to global/site tokens and new global `--hall-dark-0/1/2`, `--hall-text`, `--hall-muted`, `--hall-border`, `--hall-green`, `--hall-red`, `--hall-gold`, and `--hall-gold-light` variables.

## Test evidence

- Command: `manage.py test chef_battle.tests.ArenaDarkLaunchTests recipes.tests.ArenaBuildPlanTests --verbosity=1` using the repository virtual environment, an isolated SQLite test database, development settings, and external notifications disabled.
- Result: **PASS — 17/17 tests**, Django system check reported no issues.
- The focused tests cover anonymous denial, superuser preview, ordinary-author access, denial without an author profile, and the revised build-board archive/frozen/start behavior.
- No browser, screenshot, assistive-technology, CSS-cascade, or deployment/static-request test was run; those original evidence gaps remain open.

## Final delta status

**MINOR_AMENDMENT**

The intended baseline does not invalidate the Arena audit. Amend the access conclusion to include all registered authors during dark launch, record the flatter/tokenized-but-still-legacy presentation state, and add the documentation/token-scope risks above. All principal integration boundaries, regression warnings, duplicate/dead-code classifications, and the requirement for owner approval before 2D implementation remain valid.
