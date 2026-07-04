# P01 Visual Report — Arena Master Console shell

Produced: 2026-07-04 · Phase: P01 (Desktop visual shell and information architecture)

## What was built

- **Access gate (DG-01):** `ARENA_MASTER_CONSOLE_ENABLED` setting (default **False**),
  `RecipeAuthor.has_arena_console_access` BooleanField (migration `recipes/0038`),
  `has_arena_console_access()` + `arena_console_guard` in `chef_battle/access.py`,
  view `master_console` (`chef_battle/views.py`), URL `/chef-battle/master/`
  (`chef_battle:master_console`). Failure mode: Http404, same as moderation tools.
- **Shell template:** `templates/chef_battle/arena_master_console.html` — topbar,
  arena overview (battle status / chef slots / ring placeholder / audience summary),
  7-step phase rail, eight-panel operator deck, system footer. `noindex, nofollow`.
- **CSS:** `static/css/arena_master_console.css` — dark operator surface scoped to
  `.amc-page` with local tokens; zero changes to shared stylesheets. The floating
  `#site-battle-widget` is hidden on the console page only (it overlapped panel 8).

## No fabricated data

Every panel renders explicit states only: "No active battle", "Not connected",
"Unavailable in this phase". A regression test asserts mockup example values
(1.6K, 2.4K, 1,240T, CB-2025-0714, Emerald Hall) never appear. All six shell
buttons (Start Phase, Lock Ingredients, Open Vote, Award Crown, Emergency Stop,
End Battle) are rendered `disabled`; a test enforces this.

## Verification pass 1

- **Tests:** `ArenaMasterConsoleAccessTests` — 12/12 pass. Cover: anonymous,
  regular chef, moderator-without-superuser, superuser-without-flag,
  flag-without-superuser (all 404); owner and superuser+flag (200); console flag
  off → 404 for everyone including owner; console independent of
  CHEF_BATTLE_ENABLED; no fabricated data; 8 panels present; buttons disabled;
  public arena unchanged.
- **Screenshots (local dev server, logged in as owner-linked operator):**
  - 1920×1080 — 8 deck panels in one row; no overlap after widget fix.
  - 1440×900 — deck 4×2; overview intact.
  - 1280×800 — deck 4×2, narrower overview columns.
  - 375×812 (mobile) — deliberate stacked fallback, ring placeholder first,
    full-width readable cards; no shrunken text.
- **DOM checks (all viewports):** no horizontal body overflow, no clipped panels
  (`scrollWidth <= clientWidth` on every card), no console errors/warnings.
- **Django:** `manage.py check` clean; migration `recipes/0038` applied.

## Verification pass 2

- **Scenario walk (live, via fetch credential switching):** anonymous console →
  404, anonymous arena → 200, operator console → 200. Public arena SVG renders
  760×760 with 200 cells for both anonymous and operator — behaviorally unchanged.
- **Keyboard traversal:** only 2 focusable elements in shell (both real links);
  disabled buttons are skipped natively. 16 aria-labelled landmarks;
  heading order H1 → H2×5 → H3×8.
- **Reduced motion:** shell has no animation; a `prefers-reduced-motion` guard
  disables any future transition inside `.amc-page`.
- **Diff review:** no shared file touched (base.css, header.css, chef_battle.css,
  arena.css, base.html all untouched). New CSS is page-scoped.
- **Regression suite:** `chef_battle` + `recipes` — 363 tests. All green except:
  1. Five access tests that require default flags; they fail only when local
     `.env` sets `CHEF_BATTLE_ENABLED=True` (dev-server convenience). Verified
     green with flags off. CI/server runs are unaffected (flags off by default).
  2. `recipes.GenerateRecipeCommandTests.test_generate_recipe_creates_draft_only_with_safety_fields`
     — **pre-existing failure on clean main** (verified via stash). Unrelated to
     P01; expected `image_rights_status=AI_GENERATED`, actual `not_applicable`.
     Reported to owner as follow-up.

## Reference comparison

Hierarchy matches the reference composition: top overview row (status | chef |
ring | chef | audience), phase rail beneath, eight-panel deck, system footer.
Deviations (intentional for P01): no live values anywhere, ring is an explicit
placeholder (public renderer embeds in P02), site header/footer retained (console
is a site page, not a separate app shell).

## Open items for P02

- Ring feed embed and all read models (single `/battle/master/state/` endpoint
  per P00_CONTRACTS.yaml).
- Server-time display currently uses render-time `{% now %}`; becomes live in P02.
- Baseline screenshots of the PUBLIC arena (P00 leftover) remain owner-waived.
