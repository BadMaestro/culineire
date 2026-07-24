RELEASE_JOURNAL = [
    {
        "version": "2.5.480",
        "date": "2026-07-24",
        "commit": "a72fe18a",
        "title": "Merge af14 wall-wash refresh with r10c+af5–af13",
        "section": "Chef Battles / Deployment",
        "summary": "Merge ArenaFront af14 (82f8728e: regenerated hall-wall-wash-v1.png for darker cinematic depth; single image regen; cache-bust af14). Load order: polish r10c → atmosphere af14. SVG centre mask held. Journal+board updated. Not a public Arena release. Rollback: revert merge and redeploy.",
    },
    {
        "version": "2.5.479",
        "date": "2026-07-24",
        "commit": "324a2ef4",
        "title": "Merge af13 corner vignettes with r10c+af5–af12",
        "section": "Chef Battles / Deployment",
        "summary": "Merge ArenaFront af13 (b849492e: cinematic corner vignettes; SVG centre mask held) onto live polish r10c + af5–af12. Load order: polish r10c → atmosphere af13. Journal+board updated. Owner no-idle auto-merge continues unless Owner says HOLD. Not a public Arena release. Rollback: revert merge and redeploy.",
    },
    {
        "version": "2.5.478",
        "date": "2026-07-24",
        "commit": "2a90d400",
        "title": "Merge af11–af12 side washes + bottom depth with r10c stack",
        "section": "Chef Battles / Deployment",
        "summary": "Merge ArenaFront af11 (5b5b7421: green/red side washes) and af12 (c7940285: bottom hall depth vignette) onto live polish r10c + af5–af10. Load order: polish r10c → atmosphere af12. SVG centre mask held. Journal+board updated. Not a public Arena release. Rollback: revert merge and redeploy.",
    },
    {
        "version": "2.5.477",
        "date": "2026-07-24",
        "commit": "848660d9",
        "title": "Merge af9–af10 outer haze + ceiling vignette with r10c stack",
        "section": "Chef Battles / Deployment",
        "summary": "Merge ArenaFront af9 (85a32a20: outer stand haze) and af10 (e706aad6: ceiling vignette + wall-wash lift) onto live polish r10c + af5–af8. Load order: polish r10c → atmosphere af10. SVG centre mask held. Journal+board updated. Not a public Arena release. Rollback: revert merge and redeploy.",
    },
    {
        "version": "2.5.476",
        "date": "2026-07-24",
        "commit": "5c499093",
        "title": "Merge af8 side gold dust with r10c+af5–af7",
        "section": "Chef Battles / Deployment",
        "summary": "Merge ArenaFront af8 (a2e97a39: denser side gold dust + stand gold lines; af6 SVG centre mask held) onto live polish r10c + af5–af7 stack. Load order: polish r10c → atmosphere af8. Journal+board updated. Not a public Arena release. Rollback: revert merge and redeploy.",
    },
    {
        "version": "2.5.475",
        "date": "2026-07-24",
        "commit": "e706aad6",
        "title": "ArenaFront af10: ceiling vignette + wall-wash lift",
        "section": "Chef Battles / Deployment",
        "summary": "Owner no-idle: cinematic top vignette and stronger upper gold bloom; lift hall-wall-wash toward ceiling. SVG centre mask from af6 held. Cache-bust af10. Fence: polish untouched. Rollback: revert and redeploy. [Authored by ArenaFront.]",
    },
    {
        "version": "2.5.474",
        "date": "2026-07-24",
        "commit": "85a32a20",
        "title": "ArenaFront af9: outer stand haze + journal renumber",
        "section": "Chef Battles / Deployment",
        "summary": "Softens outer stand crowd-haze rings only (centre mask still clear). Journal renumber note for branch alignment. Cache-bust af9. Fence: polish untouched. Rollback: revert and redeploy. [Authored by ArenaFront.]",
    },
    {
        "version": "2.5.473",
        "date": "2026-07-24",
        "commit": "f6eeb715",
        "title": "Merge af7 token hall deepen with r10c+af5+af6",
        "section": "Chef Battles / Deployment",
        "summary": "Merge ArenaFront af7 (dab856e0: token-only hall deepen, drop raw HEX fallback, stronger gold/side washes; af6 SVG centre mask kept) onto live r10c+af5+af6 stack. Load order: polish r10c → atmosphere af7. Journal+board updated. Not a public Arena release. Rollback: revert merge and redeploy.",
    },
    {
        "version": "2.5.472",
        "date": "2026-07-24",
        "commit": "a2e97a39",
        "title": "ArenaFront af8: denser side gold dust + stand gold lines",
        "section": "Chef Battles / Deployment",
        "summary": "Owner no-idle: denser cinematic gold dust on left/right stands and brighter stand gold lines using official --hall-gold tokens only. SVG centre mask held. Fence: polish untouched. Rollback: revert and redeploy. [Authored by ArenaFront.]",
    },
    {
        "version": "2.5.471",
        "date": "2026-07-24",
        "commit": "b68da937",
        "title": "Merge af6 SVG-clear floor-sheen with r10c+af5",
        "section": "Chef Battles / Deployment",
        "summary": "Merge ArenaFront af6 (7a2e1d9d: dial down centre floor-sheen + mask so live SVG seats read) onto Cursor r10c + af5 dark hall cascade. Load order: polish r10c → atmosphere af6. Journal+board updated. Not a public Arena release. Rollback: revert merge and redeploy.",
    },
    {
        "version": "2.5.472",
        "date": "2026-07-24",
        "commit": "dab856e0",
        "title": "ArenaFront af7: token-only hall deepen + no raw HEX (Cursor #2214)",
        "section": "Chef Battles / Deployment",
        "summary": "Follow-up to af5 deploy note (#2214): drop raw HEX fallback on .page--arena background-color; use var(--hall-dark-0, var(--ink)) only. Deepen upper gold bloom and green/red side washes with official --hall-* tokens; SVG centre mask from af6 unchanged. Cache-bust af7. Files: arena_atmosphere.css, arena.html, release_journal, 3G board. Fence: polish untouched. Rollback: revert and redeploy. [Authored by ArenaFront.]",
    },
    {
        "version": "2.5.471",
        "date": "2026-07-24",
        "commit": "c090665e",
        "title": "Merge af5 dark hall after polish with r10c SVG/confrontation fix",
        "section": "Chef Battles / Deployment",
        "summary": "Merge ArenaFront af5 (48b03481: atmosphere AFTER polish; dark .page--arena hall fill for Owner Capture10) with Cursor r10c (547fa05a: transparent confrontation, live SVG ring contrast). Load order: hall → polish r10c → atmosphere af5. Also retains af4 crowd-haze rings. Journal+board updated. Not a public Arena release. Rollback: revert merge and redeploy.",
    },
    {
        "version": "2.5.470",
        "date": "2026-07-24",
        "commit": "7a2e1d9d",
        "title": "ArenaFront af6: dial down floor-sheen so live SVG seats read (Owner #2207)",
        "section": "Chef Battles / Deployment",
        "summary": "Owner live screenshot + CoWork #2207: painted floor-sheen dominated the hall centre and obscured interactive SVG seat rings. af6 lowers .page--arena::after opacity (~0.28–0.32), masks out the centre so SVG octagon stays clear, keeps wall wash / gold dust / dark hall page fill from af5. Cache-bust af6. Files: arena_atmosphere.css, arena.html link, release_journal, 3G board. Fence: polish untouched. Rollback: revert and redeploy. [Authored by ArenaFront.]",
    },
    {
        "version": "2.5.469",
        "date": "2026-07-24",
        "commit": "547fa05a",
        "title": "3G polish r10c: kill white crown card; restore live SVG floor readability",
        "section": "Chef Battles / Deployment",
        "summary": "Owner screenshot feedback: cream confrontation plate covered the hall and atmosphere art read as the floor while seat rings disappeared. Cursor r10c (arena_deck_polish.css ?v=20260724-r10c): confrontation band background/border/shadow removed (transparent — floating chef+centre only); live SVG z-index/opacity forced; stronger ring strokes and rank/spectator fills so the interactive octagon reads over atmosphere; translucent spine steps; removed leftover polish rotateX(32deg) on render. fitScene camera preserved. Journal+board same commit. Not a public Arena release. Rollback: revert this commit and redeploy.",
    },
    {
        "version": "2.5.468",
        "date": "2026-07-24",
        "commit": "48b03481",
        "title": "ArenaFront af5: dark hall page fill after polish (Owner live Capture10)",
        "section": "Chef Battles / Deployment",
        "summary": "Owner live screenshot showed parchment floor but missing mockup dark hall — root cause: polish loaded after atmosphere and filled .page--arena with a light wash. af5 loads arena_atmosphere.css AFTER polish, reclaims page-level hall fill with official --hall-dark-* + wall wash, keeps crowd-haze rings, does not restyle polish deck chrome/seats/confrontation. Files: static/css/arena_atmosphere.css, templates/chef_battle/arena.html (cascade order + af5 cache-bust), config/release_journal.py, recipes/views.py (3G). Fence held on arena_deck_polish.css contents. Not a public release. Rollback: revert and redeploy. [Authored by ArenaFront.]",
    },
    {
        "version": "2.5.467",
        "date": "2026-07-24",
        "commit": "706c5b42",
        "title": "3G polish r10b: spine ladder, LIVE ribbon, chef portrait rings",
        "section": "Chef Battles / Deployment",
        "summary": "Owner no-idle continuous composition. Cursor polish r10b (arena_deck_polish.css ?v=20260724-r10b): rank spine denser gold ladder over centre; broadcast ribbon LIVE weight + active phase gold fill; circular chef portrait rings with hall-green/hall-red rims; lower Join CTA bronze weight. Official tokens only; fitScene unchanged. Journal+board same commit. Not a public Arena release. Rollback: revert this commit and redeploy.",
    },
    {
        "version": "2.5.466",
        "date": "2026-07-24",
        "commit": "c03f9593",
        "title": "ArenaFront af4: mockup crowd-haze rings under live floor (non-interactive)",
        "section": "Chef Battles / Deployment",
        "summary": "Owner no-idle order: continuous atmosphere shipping. ArenaFront slice af4 adds concentric crowd-haze / stand underlay rings on .page--arena::after using official --hall-gold/--ink tokens only — atmospheric art matching the approved mockup stands, not fake interactive seats (D2). Cache-bust arena_atmosphere.css?v=20260724-af4. Files: static/css/arena_atmosphere.css, templates/chef_battle/arena.html (link only), config/release_journal.py, recipes/views.py (3G evidence). Fence held vs arena_deck_polish.css. Linode paced; work on local 8-core. Stage 3 remains IN PROGRESS; not a public Arena release. Rollback: revert this commit and redeploy. [Authored by ArenaFront.]",
    },
    {
        "version": "2.5.467",
        "date": "2026-07-24",
        "commit": "7d4a6573",
        "title": "3G polish r10a: gold hex centre, bright parchment plate, ring hierarchy",
        "section": "Chef Battles / Deployment",
        "summary": "Owner no-idle continuous composition. Cursor-only polish slice (arena_deck_polish.css ?v=20260724-r10a): confrontation VS/crown centre as gold hex badge with bronze bloom; brighter flat parchment floor plate (light-floor rule, no rotateX); inner rings 1–3 brighter parchment strokes, outer 6–8 darker bowl; side show panels night-glass lift; amplify existing floor-stage glow without redefining ::after geometry. fitScene camera unchanged. Journal+board updated same commit. Not a public Arena release. Rollback: revert this commit and redeploy.",
    },
    {
        "version": "2.5.466",
        "date": "2026-07-24",
        "commit": "8cb3d854",
        "title": "3G composition catch-up: unsquash rings + atmosphere mockup-align under polish",
        "section": "Chef Battles / Deployment",
        "summary": "Catch-up journal entry after Owner required Arena Build Plan visibility for both agents. Live tip 8cb3d854 (v2.5.469): merge of ArenaFront atmosphere mockup-align (af3 / 23542486) under Cursor polish-last load order; prior slice 369965be removed polish rotateX(32deg) that overrode fitScene()/arena_render transform — restored translate(-50%,-50%) scale(var(--arena-fit)) so octagon rings and spectator stands are no longer squashed. Cursor owns arena_deck_polish.css; ArenaFront owns arena_atmosphere.css + static/img/arena/**; shared arena.html coordinated (polish link last). Board 3G updated same commit. Not a public Arena release — staff/superuser gate unchanged. Rollback: revert 8cb3d854 then 369965be and redeploy.",
    },
    {
        "version": "2.5.396",
        "date": "2026-07-24",
        "commit": "template hygiene fix on origin/main (rebased on 3G R1)",
        "title": "Fix multi-line {# #} comments in arena.html (caught by the distributed gate)",
        "section": "Chef Battles / Deployment",
        "summary": "The distributed 8:6:1 gate (Cursor 8-core + GreenBear 6-core + Linode 1-core, run_id arena-stage3-close-b9b3e411) surfaced one real regression: config.tests.TemplateCommentHygieneTests.test_no_multiline_short_comments_in_templates failed because the Stage 3E edit added two multi-line {# ... #} comments to templates/chef_battle/arena.html. In this Django a {# #} comment must open and close on the same line; a multi-line one renders as visible page text. Both were converted to {% comment %}...{% endcomment %}. Verified: TemplateCommentHygieneTests + ArenaRankColumnTests 8/8 pass. Separately triaged the gate's other observation, a '200 != 404' seen under --parallel on Windows: NOT a regression — ArenaDarkLaunchTests + ArenaPreviewShareLinkTests + ValidShareTokenTests pass 23/23 serially and live prod confirms /chef-battle/arena/ is 404 for anonymous; it is a --parallel test-isolation artifact (CHEF_BATTLE_ENABLED override interleaving), and the Windows parallel runner additionally crashes on any failing test with 'cannot pickle traceback object', so shards are being re-run serially. This fix rebased cleanly on top of Cursor's 3G R1 (0fafb338); arena.html auto-merged (different regions). Changed file: templates/chef_battle/arena.html (+ this journal). No behaviour change beyond removing the stray comment text. Rollback: git revert this commit and redeploy.",
    },
    {
        "version": "2.5.395",
        "date": "2026-07-24",
        "commit": "pending",
        "title": "Stage 3G R1: Arena Hall tokens — challenger/opponent use official hall green/red",
        "section": "Chef Battles / Deployment",
        "summary": "Owner-approved 3G R0 map; R1 applies site-palette side accents on the live Arena (dark launch, staff/superuser only). (1) Challenger/opponent glows and --ad-green/--ad-red now point at official --hall-green/--hall-red from base.css instead of --brand/--brand-dark (both bronze), restoring green-vs-red identity without inventing a parallel palette. (2) --arena-gold points at --accent-bronze. (3) H1 Emerald Hall renamed Arena Hall (mockup/prototype copy). (4) Rank column unchanged (Owner Option A). Files: arena_deck_polish.css, arena_effects.css, arena_command_deck.css, arena.html, tests, ops/audits maps. No migrations. Prototype branch not merged. Focused ArenaRankColumnTests + new R1 token/title tests; distributed 8:6:1 not claimed. Rollback: git revert; no migrations. [Authored by Cursor.]",
    },
    {
        "version": "2.5.394",
        "date": "2026-07-23",
        "commit": "consolidation on origin/main 5f497d3b",
        "title": "Close loose ends: constitution v1.3.0, Cursor onboarded, CF5 recovered, 3E verification-pending, pool re-mapped",
        "section": "Governance / Chef Battles / Deployment",
        "summary": "Tracking, governance, and coordination consolidation — no Arena runtime code, CSS, JS, template, model, migration, or test behaviour changed. Brings to production the doc-only commits already on origin/main plus this tidy-up. (1) CONSTITUTION v1.3.0: agent Cursor was added to the section 1 roster by Owner instruction; section 15 Command Integrity and section 16 New Agent Onboarding are now canonical; section 1/3/5 wording is count-neutral. (2) CURSOR ONBOARDED: connectivity gate GREEN (round-trip + bootstrap), full project handoff committed at ops/handoff/greenbear_to_cursor.json. With Bolt and Ember on weekly limits and GreenBear near limit, Cursor (8-core) is the carrying agent. (3) CF5 DEFINITION RECOVERED: it was undefined in the repo; found in the Stage 2 audit synthesis (CoWork #1950) as 'battle_detail.html a11y coverage 4 vs arena.html 20' — a LOW-severity accessibility gap on the Battle Room detail template, needs no Owner decision, now assigned to GreenBear+Cursor. Recorded on the board. Sibling CF4 (popup a11y) was already fixed in 3B; CF0-CF3/CF6 were fixed in 3A — CF5 is the last open CF and it is small. (4) 3E BOARD CARD CORRECTED: it was stale ('contrast artifact not recorded, hidden on mobile'). Those gaps are CLOSED and DEPLOYED (v2.5.392, commit 2fd70161): ordered <ol>, contrast 14.30:1/12.62:1 recorded in ops/audits/stage_3e_rank_column.json, mobile no longer display:none, ArenaRankColumnTests 7/7. Status is now CODE DEPLOYED — VERIFICATION PENDING; the remaining distributed gate + live QA (Ember's suspended VERIFY_AND_CLOSE_STAGE_3E) are now carried by GreenBear+Cursor. (5) DISTRIBUTED POOL RE-MAPPED (Owner ruling, D4): do NOT wait for Bolt/Ember; when they return they catch up to us. The 8:6:1 gate stays runnable — Cursor primary 8-core, GreenBear secondary 6-core, and the production Linode (1-core) still takes the lightest proportional shard, run by either active agent over SSH (test DB separate, locmem cache under IS_TESTING, no file-cache risk). ops/test_pool/shard_manifest.json updated. (6) UNFINISHED WORK CAPTURED: Bolt entered IDLE cleanly with nothing in flight; Ember left only the suspended 3E close (now ours). Changed tracking files this entry: recipes/views.py (ARENA_RELEASE_STAGES only), ops/test_pool/shard_manifest.json, config/release_journal.py. Validation: JSON parse, py_compile, git diff --check; no test suite run (the distributed gate is the next step, per Owner: close tails first). Rollback: revert this consolidation commit and redeploy; the constitution and handoff docs on origin/main are independent and need no runtime rollback.",
    },
    {
        "version": "2.5.393",
        "date": "2026-07-23",
        "commit": "7e2e2a1b",
        "title": "Two token-gated Arena preview links: the current Arena and the prototype",
        "section": "Chef Battles / Deployment",
        "summary": "Two read-only share links added on the same principle as the build-board link, deployed by fast-forwarding production from dfa9b293 (v2.5.392) to 7e2e2a1b. Both are gated by one new secret ARENA_PREVIEW_SHARE_TOKEN (separate from the build-plan token), the URL segment is the credential, an unset token 404s both, and both responses carry X-Robots-Tag noindex/nofollow/noarchive. (1) /chef-battle/preview/arena/<token>/ renders the REAL current Arena from real data. To avoid duplicating logic, arena()'s read-only context assembly was extracted into _arena_page_context(); the live view keeps its presence writes, the preview does none (a test asserts a GET writes no BattleViewerPresence and creates no ChefBattleProfile). The arena draws itself entirely from the embedded arena-data-json on load, so an anonymous holder gets a faithful snapshot while the live pollers 404 harmlessly (renderer swallows them). (2) /chef-battle/preview/prototype/<token>/ serves Ember's isolated visual-shell prototype, its CSS inlined and the site's Google Fonts injected. Only the two self-contained reference files (index.html, prototype.css) were vendored under ops/prototypes/arena_visual_shell/ — the prototype BRANCH design/arena-visual-shell-prototype was NOT merged and remains a composition reference per the 3G plan. A constant-time valid_share_token() helper (empty-guard) in chef_battle/access.py now backs the gate. Files: chef_battle/views.py (refactor + two views), chef_battle/access.py, chef_battle/urls.py, config/settings.py, chef_battle/tests.py, and the two vendored prototype files. Deploy: deploy.sh fast-forwarded main, check clean, makemigrations --check found no changes, no migrations, collectstatic 0 copied; the script's bare `systemctl restart unit` again failed with 'Interactive authentication required' and was completed with `sudo /bin/systemctl restart unit` (Unit active). The ARENA_PREVIEW_SHARE_TOKEN was set in /srv/culineire/shared/.env (backup .env.bak-preview-links taken). LIVE VERIFICATION (real HTTP + in-app browser): both links = 200; the arena preview draws a full scene — 1411 SVG floor polygons, 546 occupant nodes, 17 rings, zero console errors; the prototype shows its 'Isolated visual prototype' masthead with no external prototype.css request; wrong token = 404; the real /chef-battle/arena/ stays 404 for anonymous (dark launch NOT widened); the earlier build-board link still 200. Tests: 12 new (ArenaPreviewShareLinkTests, ValidShareTokenTests) plus 25 arena regression tests (rank column, geometry, dark launch, initial-render context) green; the arena() refactor changed no behaviour. NOT run, recorded plainly: the distributed 8:6:1 gate (AGENTS.md section 9) and any authenticated browser QA beyond this anonymous preview check. Stage 3 remains IN PROGRESS, completed stages remains 2, release readiness remains NOT READY; 3C, 3D, 3E, CF5 unchanged; no Arena access was widened. Rollback: on main, git revert 7e2e2a1b (the merge) — no migrations to unwind, the vendored prototype files go with it; remove ARENA_PREVIEW_SHARE_TOKEN from shared/.env (or restore .env.bak-preview-links); rerun deploy.sh; sudo /bin/systemctl restart unit; verify both preview links 404.",
    },
    {
        "version": "2.5.392",
        "date": "2026-07-23",
        "commit": "dfa9b293",
        "title": "Stage 3E rank column, workstream 3G plan, and the build-board share link go to production",
        "section": "Chef Battles / Deployment / Governance",
        "summary": "One deploy carrying three merged pieces, fast-forwarded onto production from 816213764 to dfa9b293. (1) Stage 3E, the rank floor column: all eight ranks from ChefBattleProfile.Rank render as an ordered <ol>, the column stays present below 768px instead of being display:none, and contrast is recorded from the shipped tokens (--ink #1f2c25 on --surface #fffdf9 = 14.30:1 label, 12.62:1 count, both clearing the 7:1 bar) in ops/audits/stage_3e_rank_column.json. Files: templates/chef_battle/arena.html, static/css/arena_command_deck.css, static/js/arena_render.js, chef_battle/tests.py. (2) Workstream 3G, the visual integration plan: ops/audits/arena_visual_integration_plan.json records which composition ideas are carried from the isolated prototype (design/arena-visual-shell-prototype, commit 8ec421c0, reference only, never to be merged) and which are rejected (its private palette, invented logo/icons, round floor, deleted stands); the Arena Build Plan board in recipes/views.py gains a 3G entry, PLANNED — NOT STARTED. No implementation. (3) The build-board share link: /recipes/arena-build-plan/<token>/ serves the same read-only board to any holder of an unguessable path segment taken from ARENA_BUILD_PLAN_SHARE_TOKEN (config/settings.py, recipes/urls.py, recipes/views.py, recipes/tests.py). Unset token means the route 404s; the comparison is constant-time; the response carries X-Robots-Tag noindex/nofollow/noarchive. The token was set in /srv/culineire/shared/.env this deploy (a .env.bak-greenbear-3g backup was taken first). Deploy: /srv/culineire/scripts/deploy.sh fast-forwarded main, manage.py check clean, makemigrations --check found no changes, no migrations to apply, collectstatic copied 2 and post-processed 164. The script's bare `systemctl restart unit` failed with 'Interactive authentication required' (it omits sudo); the restart was completed with `sudo /bin/systemctl restart unit` (deploy user NOPASSWD) and Unit is active. LIVE VERIFICATION (real HTTP, following the www->apex 301): https://culineire.ie/recipes/arena-build-plan/<token>/ = 200 titled 'Arena Release Plan'; wrong token, empty token, and the bare path = 404; the Arena itself stays 404 for anonymous — dark launch was not widened; X-Robots-Tag present; home and /recipes/ = 200. NOT VERIFIED, recorded rather than smoothed over: the distributed 8:6:1 gate (AGENTS.md section 9) was NOT run before this integration — only targeted tests were (ArenaRankColumnTests 7/7 and ArenaBuildPlanShareLinkTests 9/9 locally, plus check/migration/py_compile); Stage 3E had NO live authenticated browser QA — its mobile behaviour is asserted by a CSS-parsing test, not seen on a device. Stage 3 remains IN PROGRESS, completed stages remains 2, release readiness remains NOT READY; 3C, 3D, CF5 remain OPEN; 3E's board status is unchanged by this deploy. Rollback: on main, git revert dfa9b293 (the merge) — no migrations to unwind; remove the ARENA_BUILD_PLAN_SHARE_TOKEN line from shared/.env (or restore .env.bak-greenbear-3g); rerun deploy.sh; sudo /bin/systemctl restart unit; verify Unit active and the share link 404s.",
    },
    {
        "version": "2.5.391",
        "date": "2026-07-23",
        "commit": "db98ea52",
        "title": "Remaining Arena governance documents follow the settled mockup direction",
        "section": "Governance / Chef Battles / Deployment",
        "summary": "Arena governance-document synchronization only; no product code, Arena runtime code, CSS, JavaScript, template, model, view, test, authentication, data, migration, or Stage 3 board state changed. GreenBear's read-only verification at deployed head a7952922 found the remaining direct contradictions in AGENTS.md section 11 and docs/TECHNICAL_STANDARDS.md sections 6-7, recorded in CoWork message 2052. Those clauses now match the Product Owner's settled direction: the approved Arena mockup is the visual target; responsive 2D may use static perspective, depth, rotateX, layered CSS/SVG composition, images, and the fixed cinematic angle without introducing a true 3D engine or interactive 3D camera. Centrally defined official named Arena tokens may derive from the approved mockup and remain part of the CulinEire design system; scattered raw colour literals and a detached parallel visual system remain prohibited. The approved Arena palette is a dark hall, gold accents, light parchment floor, green challenger accent, and red opponent accent, while the general site palette remains unchanged. The constitution also distinguishes permitted non-impersonating atmospheric crowd presentation from the eight interactive rings / 544 real-viewer-only seats, filled front rows first with logged-in self-seating and no synthetic occupants. Accessibility, semantic markup, responsive behaviour, keyboard operation, reduced motion, readable contrast, security, and code-quality requirements remain intact. No Stage 3 implementation workstream was completed: Stage 3 remains IN PROGRESS, completed stages remains 2, release readiness remains NOT READY, 3C, 3D, and 3E remain OPEN, and CF5 remains OPEN and UNASSIGNED. Changed authorized files: AGENTS.md, docs/TECHNICAL_STANDARDS.md, and config/release_journal.py. Validation: complete diff review, stale-phrase search, governance consistency assertions, authorized-file check, and git diff --check; tests were not run. Rollback: revert the governance-document commits, push the revert, rerun /srv/culineire/scripts/deploy.sh, and verify the restricted Unit service is active.",
    },
    {
        "version": "2.5.390",
        "date": "2026-07-23",
        "commit": "2c222ca9",
        "title": "Arena contract and Stage 3 tracking follow the settled owner-approved mockup",
        "section": "Chef Battles / Moderation / Deployment",
        "summary": "Product-contract and tracking synchronization only; no Arena product code, CSS, JavaScript, template, model, data model, authentication, migration, or test state changed. The Product Owner ruled that the previously approved 2D Arena mockup is the settled visual target: 2D excludes a true 3D engine, but permits responsive perspective and depth simulation, the fixed angled cinematic composition, photographic or painted hall atmosphere, dark setting, gold accents, light parchment floor, and the mockup hierarchy through official named Arena tokens. The contract now separates atmospheric crowd presentation from the eight interactive rings / 544 real-viewer seats: atmospheric figures may match the mockup but must not impersonate registered or online users; interactive seats remain real-viewer-only, front rows first, with self-seating. It preserves challenger-left / opponent-right green-red composition, real photo and name requirements, flags only after an approved country-data source, and the KITCHEN PORTER through CULINARY MASTER rank column with recorded >=7:1 contrast evidence. The Arena Build Plan no longer presents the approved mockup direction as unresolved. Workstreams 3C, 3D, and 3E remain OPEN and now record their source-supported partial deployed implementation and exact remaining gaps; 3D remains blocked specifically on the Product Owner's country/flag data-source decision. No Stage 3 implementation workstream was completed by this synchronization. Stage 3 remains IN PROGRESS, completed stages remains 2, release readiness remains NOT READY, and CF5 remains OPEN and UNASSIGNED. GreenBear supplied the line-level review specification in CoWork message 2048. Changed authorized files: docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md, recipes/views.py (ARENA_RELEASE_STAGES only), and config/release_journal.py. Validation: complete diff review, Python syntax/static state assertions, authorized-file check, and git diff --check; no test suite or browser QA was run. Rollback: revert the documentation/tracking commits, push the revert, rerun /srv/culineire/scripts/deploy.sh, and verify the restricted Unit service is active.",
    },
    {
        "version": "2.5.389",
        "date": "2026-07-22",
        "commit": "34de9eba",
        "title": "Stage 3B authoritative tracking synchronization",
        "section": "Moderation / Deployment",
        "summary": "Documentation/state synchronization only; no product behaviour, authentication, data, migration, or test state changed. The Arena Build Plan now records Stage 3B exactly as DEPLOYED — AUTHENTICATED PRODUCTION RE-QA PASSED 19/19. Ember remediation source db017dad1ced81925be4f125d3639a6c20fb8eeb was deployed as 388f7776b433929902476f12891834eebb36f1c1, with CoWork evidence 2029/2030/2031. GreenBear's authenticated production re-QA reported 19/19 PASS, with synthesis in CoWork 2035/2036/2037. The verified-scope limitation remains explicit: production had no active battle, the popup was opened programmatically, and creating a demo battle was prohibited, so the live-battle tile click path itself was not exercised. This does not claim Stage 3 completion: Stage 3 remains IN PROGRESS, completed stages remains 2, release readiness remains NOT READY, and 3C, 3D, and 3E remain OPEN. CF5 remains OPEN and UNASSIGNED and is neither closed nor reinterpreted. GreenBear is unavailable because its limit is exhausted; Bolt remains IDLE as emergency reserve. This v2.5.389 correction follows the already-published v2.5.388 entry and supersedes only its stale Stage 3B tracking wording. Changed tracking files: recipes/views.py and config/release_journal.py. Validation: static syntax checks, tracking-state assertions, and git diff --check; no test suite or browser QA was run. Rollback: revert the documentation commits, push the revert, rerun /srv/culineire/scripts/deploy.sh, and verify the restricted Unit service is active.",
    },
    {
        "version": "2.5.388",
        "date": "2026-07-22",
        "commit": "fef2c1cc",
        "title": "Stage 3B passes authenticated QA; site made survivable when the cache breaks",
        "section": "Moderation / Deployment",
        "summary": "Six deploys since v2.5.387, recorded together. STAGE 3B RE-QA: Ember remediated the two defects GreenBear found in authenticated QA and GreenBear re-verified them live under an ephemeral session, 19 checks and 19 PASS. The photographic hall backdrop is gone and the 544 illustrated crowd figures it was suppressing are back; the popup close control is clickable, where elementFromPoint previously returned the site header link and a real click timed out. Ember found the true cause: the popup sat inside a container with isolation isolate, so no local z-index could clear a sticky header, and it is now mounted under BODY. Stage 3B is therefore DEPLOYED, AUTHENTICATED QA PASSED, DISTRIBUTED VERIFIED. Stage 3 stays IN PROGRESS regardless, because 3C, 3D and 3E remain open; completed stages stays 2 and readiness stays NOT READY. Two qualifications are recorded on the board rather than smoothed over: the popup was opened programmatically because production has no active battle and no demo battle was created to force one, since AGENTS.md section 8 forbids data-writing production diagnostics to prove a visual result; and the 6px overflow at 390 is the site header, not the arena. WHOLE-SITE CACHE FIX, the most important change here: monitoring middleware and the three context processors reached the cache with no error handling, and they run on every request and every render respectively, so one unwritable cache file returned 500 for the entire site rather than one page. That was not hypothetical; it happened, caused by a diagnostic run as root leaving a root-owned cache file the deploy worker could not write. All call sites are now guarded: a dead cache costs an extra query, which is not comparable to losing the site. The context processors were found by writing the regression test, not by reading the code. WAF ACCEPTANCE: new ops/waf/waf_acceptance.sh checks real HTTP through nginx and ModSecurity, which the Django test client never touches, and returned 11 of 11 with nothing blocked. It needs no credentials because ModSecurity runs before Django, and it carries a POST control probe so a 403 on a real endpoint can be told apart from Django CSRF; the arena react 403 was proven to be CSRF. CRS is 3.3.5-2, already the newest packaged version; CRS 4.x exists upstream but is unpackaged and was not attempted. SERVER HEALTH PAGE rebuilt in the site's own design language: the standard hero, mon-section and mon-cards, with card colour driven by the same disk thresholds watchdog.sh uses so the page and the alarm cannot disagree. Its inline style block moved into monitoring.css, charts are fixed-height with a faint filled area, and the new CSS contains zero raw colours. LOG ROTATION, server-side: /var/log went from 605 MB to 343 MB. The growth was our own cron, since every scheduled run opens a PAM session and systemd raises a user slice, about 26,000 lines a day, and not attacks. Size caps were added. Separately, application logs had not rotated since 2 July: the logrotate config declared user unit while every file is owned by deploy, so it failed with Permission denied and gave up silently, and import_blocked.log had reached 28 MB. Fixed. LINODE MIRROR is live: a read-only API token now feeds the panel CPU, disk I/O, swap and network series at 287 samples each. Changed release files: recipes/views.py, config/release_journal.py, config/context_processors.py, monitoring/server_metrics.py, monitoring/views.py, monitoring/urls.py, monitoring/tests.py, monitoring/middleware.py, templates/monitoring/server_metrics.html, templates/monitoring/dashboard.html, static/css/monitoring.css, ops/waf/waf_acceptance.sh. No migrations. Tests: 45 in monitoring, 66 with config, all passing. Honest note: the redesign was pushed with one test red, an assertion looking for the old lowercase heading, and fixed in a follow-up commit rather than quietly amended. Rollback: revert this commit on main, push the revert, rerun /srv/culineire/scripts/deploy.sh and then the restricted Unit restart.",
    },
    {
        "version": "2.5.387",
        "date": "2026-07-22",
        "commit": "pending",
        "title": "Server health mirror, and the protection layer behind it",
        "section": "Moderation / Deployment",
        "summary": "Context first, because the feature only makes sense with it: at 03:20 UTC the daily backup wrote its 1.6 GB into the last free space on the 25 GB disk, PostgreSQL PANICked four minutes later with no space left on device, and every page returned HTTP 500 until 11:09 -- seven hours and forty-five minutes. The same fault had already occurred on 07-19 and self-healed unnoticed. Nothing was watching, so nothing was known; the outage was found by accident while checking preconditions for an unrelated task. sar confirms the machine sat at 100% CPU (user 43 / sys 43 / iowait 11) for the whole window and fell to 5% the moment space was freed. Recovery needed only a journald vacuum and an apt cache clean; no backup, database file or product file was touched. This release adds the missing eyes. New moderator-only page at /monitoring/server/ mirrors the Linode panel (CPU, disk I/O, swap rate, network in and out over 24h) and adds the readings Linode does not show at all: disk, memory, swap and load average, which are the numbers that actually predicted the failure. Three deliberate omissions, each a decision rather than an oversight: no database table, because Linode already retains 24h and copying it would add write load to a 1 GB single-core box that is already using swap, so the data is cached for five minutes instead; no charting library, because the project has none and adding one for four sparklines would introduce a second design language, so the charts are server-rendered SVG polylines that work without JavaScript; and no emergency controls, because an endpoint that restarts production services needs its own review of authorisation, CSRF, rate limiting and audit logging rather than being attached to a dashboard. The page degrades honestly: without LINODE_API_TOKEN the host readings still render and the page states what is missing, and API failures are caught, because a health page that returns 500 during an incident is worse than none. Both behaviours are covered by tests. Disk thresholds (85% warning, 92% critical) are copied from watchdog.sh so the page and the alarm cannot disagree, and every colour is an existing base.css token per the design constitution. Alongside this, server-side only and outside the repository: backup.sh gained a preflight space guard that aborts without writing when the result would not fit, verified against the historical 320 MB condition where it would have prevented the outage entirely; retention was split by cost and rate of change (database 30 days, env 7 days, media 1 copy), cutting the backup directory from 15 GB to 1.7 GB; a watchdog runs every five minutes checking disk, PostgreSQL, HTTP and sustained CPU, alerting to the owner private Telegram with ten repeats for critical faults and a thirty-minute re-nag while unresolved; a 1 GB ballast file can be released automatically to keep PostgreSQL writable; journald is capped at 200 MB. The unused mediamtx streaming service was stopped and disabled (zero sessions in seven days, no references in application code, Live Video disabled by contract), freeing about 20 MB of RAM. Changed release files: monitoring/server_metrics.py (new), monitoring/views.py, monitoring/urls.py, monitoring/tests.py, templates/monitoring/server_metrics.html. No migrations. Tests: 9 new, 39 in the monitoring app, all passing. Note on numbering: this entry was renumbered from 2.5.386 to 2.5.387 because a concurrent deploy claimed 386 while this work was in progress -- the collision was caught before push, not after. Rollback: revert this commit on main, push the revert, rerun /srv/culineire/scripts/deploy.sh and the restricted Unit restart.",
    },
    {
        "version": "2.5.386",
        "date": "2026-07-22",
        "commit": "ac311379",
        "title": "Completed Arena Build Plan stages collapse and turn green",
        "section": "Moderation / Deployment",
        "summary": "Owner request. On /recipes/moderation/arena-build-plan/ every release stage now renders as a native disclosure element instead of a plain article: stages with status DONE start collapsed so finished work stops crowding the board, and every other stage stays open. No JavaScript is involved, so the header stays keyboard operable for free; a CSS chevron shows open/closed state, the summary carries a visible focus ring, and the rotation is disabled under prefers-reduced-motion. Completed stages are now green rather than the brand bronze: the border and the header tint use the existing :root token --hall-green, while the status badge and the number bubble mix that token toward --ink because --hall-green is a mid-tone and small text on it would fall to roughly 2.2:1 contrast. No raw colour was introduced and no new token was invented. Changed file: templates/moderation/arena_build_plan.html. Static evidence: Django template render check confirmed 8 stage disclosures, 8 summary headers, both DONE stages collapsed and the other six open, no leftover article stage markup, and the green plus reduced-motion rules present; Python compilation and manage.py check passed; application and project suites were not run. Stage statuses, counts, readiness and all Stage 3A/3B evidence are untouched — this is presentation only. Rollback: revert this commit on main, push, rerun /srv/culineire/scripts/deploy.sh, then the restricted Unit restart.",
    },
    {
        "version": "2.5.385",
        "date": "2026-07-22",
        "commit": "a6b3781e",
        "title": "Arena Stage 3 distributed verification: 154/154 passed, staff QA still blocked",
        "section": "Moderation / Deployment",
        "summary": "Documentation-only deploy by GreenBear acting as distributed-verification coordinator; no product file was modified in this release. One run, run_id arena-stage3-20260721-2213-d8f08f22, against commit d8f08f224a11dab4ce3ba5051cead32029d5a604, verified before the run to equal both origin/main and the production HEAD with a clean production checkout and Unit active, and confirmed by ancestry to contain both packages under test (Stage 3A backend f3edd724 and Stage 3B frontend 6a2b5f52). The manifest selected 154 tests across 13 whole test classes -- Stage 3A access gates, initial-render context, and adjacent Arena regressions -- and deliberately not the application or project suite; every label was verified to exist at that exact commit by parsing chef_battle/tests.py there rather than trusting a remembered name. The split was two disjoint shards: GreenBear 6-core took ArenaDarkLaunchTests, ArenaInitialRenderContextTests, ArenaMasterConsoleAccessTests, ChefBattleAccessTests, BattleChatSecurityTests, ArenaMasterStateTests and ArenaMasterGovernanceTests (64 tests, 6 workers, 110.5s, 64 passed, 0 failed, 0 errors, 0 skipped); Bolt 8-core took ArenaMasterActionTests, ArenaMasterModerationTests, ArenaMasterActionSecurityTests, ArenaMasterMonitorTests, ArenaMasterVotingAnalyticsTests and ArenaMasterEconomyTests (90 tests, 113.9s, 90 passed, 0 failed, 0 errors, 0 skipped). Non-overlap is arithmetic, not assertion: 7 plus 6 equals the 13 selected classes, 64 plus 90 equals the 154 selected tests, the label sets intersect in nothing, and no test method was split across machines. Combined result 154/154 passed, zero failures, zero errors, zero skips. Two things are recorded here precisely because they weaken the result rather than support it. First, the shards ran on different database backends -- GreenBear on PostgreSQL and Bolt on SQLite by its own report -- so PostgreSQL-specific constraint behaviour was exercised on one side only. Second, and more important, a green test run is NOT the interactive staff QA: Ember reported BLOCKED at this exact commit because the only available browser session receives the staff-gated 404 and, correctly, entered no credentials, so every interactive check (popup focus entry, Tab and Shift+Tab trap, Escape, visible close, focus return, popup-preview-only, full-page Battle Room, Master Console regression, desktop 1920 and mobile 390) stands as BLOCKED and not as passed. Classification: Stage 3A becomes DEPLOYED AND DISTRIBUTED VERIFIED; Stage 3B becomes DEPLOYED, SERVED ASSETS VERIFIED, INTERACTIVE STAFF QA PENDING, DISTRIBUTED VERIFIED. Stage 5 keeps its stale claim removed -- the GreenBear 6-core environment is no longer rate-limited -- and now records the run, both shard results and the first real per-shard durations, while deliberately remaining neither active nor DONE because it stays sequentially dependent on Stages 3 and 4. Stage 3 stays IN PROGRESS, completed delivery stages stays 2, and release readiness stays NOT READY. Two adjacent findings remain open with no owner invented for either: the photographic hall backdrop is still live in production (the deployed arena_render.css still applies hall-bg-v3-final.webp as a live rule and the image is still served, so the new light HUD renders over the dark photograph and the drawn crowd stays suppressed through the .has-arena-backdrop path, against AGENTS.md section 11 and product contract section 12), and CF5, where templates/chef_battle/battle_detail.html is unchanged since d852fff5 with 4 aria/role attributes against roughly 20 on the Arena Hall. Neither was fixed in this assignment. Changed release files: recipes/views.py and config/release_journal.py, both project-status data only. CoWork: manifest 1993/1994/1995, BOLT_SHARD_RESULT 1996/1997/1998, EMBER QA BLOCKED 1999/2000/2001. Rollback: revert this commit on main, push the revert, rerun /srv/culineire/scripts/deploy.sh and then the restricted Unit restart if required.",
    },
    {
        "version": "2.5.384",
        "date": "2026-07-21",
        "commit": "4eed7a53",
        "title": "Arena backend access + initial-render package deployed (Stage 3A)",
        "section": "Chef Battles / Deployment",
        "summary": "Agent Bolt integrated and deployed Stage 3A. Source branch impl/arena-access-and-context, source commit ce43242b65fc3d0ca8a259544ab4d1ffb9f7eaf8, cherry-picked cleanly onto main (the 3 backend files were unchanged since base d852fff5) to resulting and deployed commit f3edd72453f904a8f1cadd539a3a2e36dfb97029. Changed files: chef_battle/access.py, chef_battle/views.py, chef_battle/tests.py. It removes the registered-author dark-launch access branch so Arena visibility is staff/superuser-only, keeps Arena Hall and Battle Room gated through @chef_battle_guard and is_battle_visible(), gates arena_react and battle_chat_poll through is_battle_visible(), preserves the existing battle_chat_send @chef_battle_guard, and exposes crown_streak, crown_ladder, and recent_gifts at the top level of the initial-render context; regression tests updated and the stale proto-gate test renamed. Static checks: py_compile, manage.py check clean, git diff --check clean. Deploy ran /srv/culineire/scripts/deploy.sh as the deploy user; manage.py check clean; no migrations; collectstatic 0 copied / 164 post-processed; Unit restarted via the deploy user's restricted sudo (NOPASSWD /bin/systemctl restart unit) and is active; production checkout clean at f3edd724. Server-side production verification (deployed code, RequestFactory): anonymous Arena route 404 (gate intact, no access widening); is_battle_visible False for anonymous and for a plain non-staff author, True for staff and superuser; author branch absent from is_battle_visible; arena_react and battle_chat_poll gated; battle_chat_send guard preserved; top-level crown_streak/crown_ladder/recent_gifts present; no new server errors. Authenticated browser QA of the initial render is delegated to Ember; distributed test verification is delegated to GreenBear (run_id and shard manifest), and the Bolt 8-core shard will run only against that manifest. This commit also updates Arena Build Plan Stage 3A to DEPLOYED — SERVER-SIDE VERIFIED — DISTRIBUTED VERIFICATION PENDING. Stage 3 stays IN PROGRESS, completed delivery stages stays 2, readiness NOT READY; Stage 3B frontend evidence and journals v2.5.382/v2.5.383 preserved. Related CoWork: 1960-1962, 1977-1979. Rollback: revert f3edd724 and this journal commit on main, push, rerun /srv/culineire/scripts/deploy.sh, then the restricted Unit restart.",
    },
    {
        "version": "2.5.383",
        "date": "2026-07-21",
        "commit": "c67f00e6",
        "title": "Arena frontend accessibility and light-token package deployed (Stage 3B)",
        "section": "Chef Battles / Deployment",
        "summary": "Ownership takeover: original owner GreenBear, implementation agent Ember, integration and deployment owner Bolt (Ember closed its session at its weekly limit). Two ordered production commits. First, the frontend package: source branch impl/arena-frontend-a11y-tokens-ember at 0dbac5e99c1c1071da966d1ede36926e489600ed was cherry-picked cleanly onto main (the 11 files were unchanged since base d852fff5) to resulting and deployed commit 6a2b5f52536f5b7de9aea706b1fbb1b26d8f8e11. Changed files: static/css/arena.css, arena_command_deck.css, arena_deck_polish.css, arena_effects.css, arena_hall.css, arena_master_console.css, arena_master_console_plan.css, arena_render.css; static/js/arena_battle_room.js, arena_octant_prototype.js; templates/chef_battle/arena_battle_popup.html. It adds popup focus entry, Tab and Shift+Tab focus trap, Escape close, a visible close control, and focus return, keeps the popup preview and navigation only with a link to the separate full-page Battle Room, removes the independent dark palette in favour of official light/parchment tokens, and removes all raw colours (0 hex/rgb/hsl across the owned files). Static validation: node --check on both scripts, CSS brace balance, Django template parse, raw-colour scan 0, git diff --check clean. Deploy ran /srv/culineire/scripts/deploy.sh as the deploy user; manage.py check clean, no migrations; collectstatic copied 10 files and post-processed 164; Unit restarted via the deploy user's restricted sudo (NOPASSWD /bin/systemctl restart unit) and is active. Served-asset verification: home and /recipes/ 200; Arena gate intact (anonymous 404 during dark launch, access not widened); served hashed arena_hall.css carries design tokens with 0 raw hex and served hashed arena_battle_room.js carries the focus-management code; no server errors. Second, this build-plan and journal commit updates Arena Build Plan Stage 3B to DEPLOYED — SERVED ASSETS VERIFIED — INTERACTIVE STAFF QA PENDING and records this entry. INTERACTIVE STAFF QA PENDING (not performed by the agent because the Arena is staff/superuser-only and the agent cannot authenticate): authenticated popup, focus entry, Tab and Shift+Tab focus trap, Escape close, visible-close click, focus return, popup-preview-only, full-page Battle Room, Master Console, and desktop 1920 and mobile 390 visual and overflow checks. Distributed verification remains pending (Stage 5); application and project suites not run. Stage 3 stays IN PROGRESS, completed delivery stages stays 2, readiness NOT READY; Stage 3A backend evidence and journal v2.5.382 preserved. Related CoWork: takeover 1967/1968/1969. Rollback: revert 6a2b5f52 and this journal commit on main, push, rerun /srv/culineire/scripts/deploy.sh, then the restricted Unit restart.",
    },
    {
        "version": "2.5.382",
        "date": "2026-07-21",
        "commit": "7bb59786",
        "title": "Arena Build Plan records the backend access workstream (Stage 3A)",
        "section": "Moderation / Deployment",
        "summary": "Documentation-only deploy: Stage 3 workstream 3A (Backend access and initial-render context, owner Bolt) is now recorded on the Arena Build Plan as IMPLEMENTATION COMPLETE — UNVERIFIED AND NOT DEPLOYED. It captures source branch impl/arena-access-and-context at ce43242b65fc3d0ca8a259544ab4d1ffb9f7eaf8 (pushed; not merged to main; not deployed): the registered-author dark-launch access branch is removed so Arena Hall and Battle Room are staff/superuser-only via @chef_battle_guard and is_battle_visible(); arena_react and battle_chat_poll now check is_battle_visible(); battle_chat_send is unchanged and keeps its existing @chef_battle_guard; and top-level crown_streak, crown_ladder, and recent_gifts are supplied in the initial-render context. Tests run: zero by owner policy; static verification was owned-file scope plus git diff --check. IMPORTANT: the backend commit ce43242b was NOT integrated or deployed in this step — only the Arena Build Plan page status data was changed. Changed release file: recipes/views.py. Static evidence: Python compilation, Django system check, and build-plan context assertions (8 stages, 2 complete, Stage 3 the sole active stage, readiness NOT READY, 3A status and evidence visible) passed; application and project suites were not run. Result: successful. Rollback: revert this commit on main, push the revert, and rerun /srv/culineire/scripts/deploy.sh followed by the restricted Unit restart if required.",
    },
    {
        "version": "2.5.381",
        "date": "2026-07-21",
        "commit": "e7520529",
        "title": "Arena Build Plan becomes a sequential release pipeline",
        "section": "Moderation / Deployment",
        "summary": "Source ops/arena-build-plan-sequential-rewrite at e752052909a86da6c7a07975e365bb75ed29cfb1 fast-forwarded origin/main from d852fff53b8de0f7fcd46897c4ce287c6abe8a0d without conflicts or history rewriting. The production deploy used /srv/culineire/scripts/deploy.sh; Django check, migrations and collectstatic completed, then Unit was restarted separately with the deploy user's restricted sudo. Production checkout and deployed commit were e752052909a86da6c7a07975e365bb75ed29cfb1 and clean. Changed release files: recipes/views.py and templates/moderation/arena_build_plan.html. Static evidence: Python compilation, Django template syntax, sequential-stage assertions and git diff --check passed; application/project suites were not run. Authenticated live verification confirmed 8 current stages, 2 complete, Stage 3 active, readiness NOT READY, deferred mobile scope, and collapsed Legacy Arena Milestones; the old 3/7 board is gone. Result: successful. Rollback: revert e752052909a86da6c7a07975e365bb75ed29cfb1 on main, push the revert, and rerun /srv/culineire/scripts/deploy.sh followed by the restricted Unit restart if required.",
    },
    {
        "version": "2.5.380",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "Any registered author can visit the arena",
        "section": "Chef Battles",
        "summary": "is_battle_visible() required staff, superuser, or bearseeker privileges during dark launch, so a plain author got 404 -- exactly why three test accounts needed a staff grant just to be seen in the stands. Owner's rule: any registered author may visit and watch, chef enrollment is never a condition for visibility, only for participation. has_bearseeker_privileges is itself a RecipeAuthor field and added nothing once 'any author' is the rule, so it was dropped rather than kept as a no-op check.",
    },
    {
        "version": "2.5.379",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "Real spectators stop being stretched into ghosts",
        "section": "Chef Battles",
        "summary": "The 3D camera was retired days ago, but a leftover scaleY(1.79/1.27/1.11) billboard rule kept stretching every real occupant photo vertically. Caught live: three real test spectators (julija-golovina, culin-eire, denis-golovin) rendered as tall thin rectangles instead of square portraits. Rule removed entirely -- a flat camera needs no un-squashing.",
    },
    {
        "version": "2.5.378",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "Self-vote blocked at the database, arena tokens, manifest in the repo",
        "section": "Chef Battles",
        "summary": "BattleVote.clean() blocked a chef voting for themselves, but Django never calls clean() from save() - a CheckConstraint now enforces it directly, backed by a denormalised voter_author field (the constraint cannot join voter's User row to voted_for's RecipeAuthor row). Request fingerprint hashes moved from bare SHA-256 to HMAC keyed on SECRET_KEY. The arena build board is rewritten: 13 finished stages collapse into one archive line, the 7 live stages each carry a written acceptance criterion instead of none, and two of them (fullbleed, hud) turned out to already be built and working once measured rather than eyeballed. 89 live raw hex colours across the arena stylesheets (183 minus comment-only matches) are down to 35, mostly documented exceptions where no green/red/blue token exists anywhere in the scheme. The owner's product manifest and co-developer protocol now live in docs/agents/, with a delta document recording where they're stale against shipped code.",
    },
    {
        "version": "2.5.377",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "Full-bleed reaches the phone too",
        "section": "Chef Battles",
        "summary": "The arena filling the screen was gated at 901px, so a phone kept the old boxed floor with a border and a light card background while desktop was already edge to edge. Floor sizing and the hall's colour now apply at every width; only the panel overlay stays desktop-only, since below 900px there is no room beside the floor to float them over it.",
    },
    {
        "version": "2.5.376",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The last of the 3D leaves the arena",
        "section": "Chef Battles",
        "summary": "The camera was retired days ago and the projection already draws flat, but the 3D context it needed was still declared - costing nothing to look at while quietly inviting the next person to turn depth back on.",
    },
    {
        "version": "2.5.375",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "Everything the agents work from is in the repository",
        "section": "Site",
        "summary": "The rules, the reference notes, the session history and the agent settings lived on one machine, in one private folder. Losing that folder lost the project's working memory, and the other agent could not read any of it. All 108 notes are in docs/agents/memory now, the settings in docs/agents/claude-config, and the local test panel is tracked. Secrets stay out: the copied files name environment variables, they never carry values, and .env and its backups remain untracked.",
    },
    {
        "version": "2.5.374",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The rules the agents work by now live in the repository",
        "section": "Site",
        "summary": "The working rules existed only inside one agent's private memory folder: a lost folder or a new session would have taken them, and the other agent could not read them at all. They are in docs/agents/ now. GOLDEN_RULES.md carries the three-week analysis behind them - 727 commits in main of which one in three undoes the last, 39 collided version numbers - and the rules written against each pattern.",
    },
    {
        "version": "2.5.372",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The demo battle becomes a command instead of a script on the server",
        "section": "Chef Battles",
        "summary": "Every HUD panel in the reference carries battle content - phase, countdown, two chefs, votes, gifts - and with nothing running the layout was being positioned against empty boxes. demo_battle creates one through the real path, a challenge then accept_challenge, so what appears is a battle the site itself would have made. It ships through git rather than being copied onto the server as a throwaway. Dry run by default, --run to create, --end to close it, and it refuses to start a second while one is live.",
    },
    {
        "version": "2.5.371",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The floor takes the room it was promised",
        "section": "Chef Battles",
        "summary": "The arena was being sized by the whole seating disc rather than the floor, so the floor came out less than half the size it was set to and the hall behind it stopped short of the screen edges. The rank pills go dark on the pale floor, the way the mockup has them, instead of pale on pale.",
    },
    {
        "version": "2.5.370",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The rank ladder lies on the floor it describes",
        "section": "Chef Battles",
        "summary": "The list of kitchen ranks floated above the arena as a separate column, reading bottom rank last. It now lies on the floor between its near edge and the crown, in the order the mockup shows, and it is described in one stylesheet instead of three.",
    },
    {
        "version": "2.5.369",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The board admits the hall is finished, and the session table is swept",
        "section": "Moderation",
        "summary": "The backdrop stage was still open on the board while the hall has been live in production for hours, with our octagon landing within 2% of the painted one. It is closed, and its note now records what the frames actually cost: 4 of the 12 the owner allowed, of which two were drawn under a camera tilt he later retired. Separately, 63 rows left the session table - 43 expired and 20 belonging to accounts that no longer exist. Live sessions of real people were left alone; signing the owner out of his own tabs to tidy a table would be the worse outcome.",
    },
    {
        "version": "2.5.368",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The arrival announcement belongs to GreenBear again",
        "section": "Site",
        "summary": "Announcing an arrival to the whole site is the owner's own privilege and always has been. It had been widened to fire for staff, superusers and bearseekers as well, so a bearseeker signing in raised the same popup - from the outside indistinguishable from someone signing in as the owner, which is exactly how he read it. Only the owner fires it now. The module had no tests at all, which is how the rule drifted unnoticed; it has six.",
    },
    {
        "version": "2.5.368",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The arena sits in the window it was given",
        "section": "Chef Battles",
        "summary": "The arena was told to be as tall as the window, but it starts below a sticky header - so it ran that far past the bottom, the floor sat low and the supporter ticker fell off the screen. It now takes the window minus the header, and the page stopped scrolling sideways.",
    },
    {
        "version": "2.5.367",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "One arena, described in one place",
        "section": "Chef Battles",
        "summary": "Two stylesheets had been setting the same widths and padding for the same arena, each unaware of the other, and whichever loaded last decided what you saw - which is how the octagon ended up off the side of the screen. Layout now lives in one file and the other paints.",
    },
    {
        "version": "2.5.366",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The bronze funnel on the floor goes back out",
        "section": "Chef Battles",
        "summary": "A widened bronze gradient had been added to the floor, running from almost-black at the centre out to parchment at the rim. It came from the first arena, which the owner had shown while asking about colour - not from the reference being built to, where the floor is even cream and rank is read from the pills. It was drift, and it goes out the same evening it went in. The walkway is kept: the reference has it, and its colour is the coolest token the scheme holds.",
    },
    {
        "version": "2.5.365",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The panels move onto the hall",
        "section": "Chef Battles",
        "summary": "The arena had panels standing beside it in a grid, on a page of light parchment - a dashboard about an arena. They now float on the hall itself as dark glass with a bronze edge, placed where the mockup puts them. Phones keep the stacked layout.",
    },
    {
        "version": "2.5.364",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "An address can be freed for good",
        "section": "Accounts",
        "summary": "Registering an address that had been deleted was refused as already taken: the login row survived while its author profile was gone, so nothing on the site could see the account, and the only thing it still did was block its own address. purge_account removes both halves and the author's content in one transaction, by address or as a sweep of every profile-less login row. It prints what it will remove and refuses a superuser without --force, so clearing a stale signup is not one typo away from deleting the owner.",
    },
    {
        "version": "2.5.363",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "Rank becomes readable again",
        "section": "Chef Battles",
        "summary": "The first arena said rank without a word: the floor ran from deep bronze at the centre out to almost-white at the rim. Painting the hall dark took that contrast with it - the eight steps survived but sat between 0.90 and 0.65 in brightness, which is nothing on a lit floor, so rank stopped being visible. The steps are widened, not re-hued, and the floor stays light. The walkway between the floor and the crowd is pushed to the coolest colour the scheme actually has rather than the blue it once was: the scheme has no blue, and inventing one is how the arena grew its own palette last time.",
    },
    {
        "version": "2.5.362",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "A black square stops lying across the hall",
        "section": "Chef Battles",
        "summary": "Going full-bleed exposed the scene's old dark plate - a flat fill and a floor texture, drawn to give the arena a surface back when the page around it was light parchment. Inside the old 960px card its edges were never visible; across a full-screen hall it read as a black square over the middle of the room, which is how the owner photographed it on a phone. The hall image is the surface now, so the plate is cleared on this page and kept for the Master Console, which has no backdrop behind it.",
    },
    {
        "version": "2.5.361",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The arena stops being a box on a page",
        "section": "Chef Battles",
        "summary": "The widest gap to the reference was never the camera or the palette. The hall was a 1520px card with rounded corners holding a 960px picture in the middle of an ordinary page, while the reference is a room you stand in. The deck is released from its width and the scene from the 960px cap and its card treatment. Nothing is restructured - the grid columns are what put the side panels around the floor. Height is 100svh rather than 100vh so a phone does not gain a scrollbar when the browser chrome slides away.",
    },
    {
        "version": "2.5.361",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The arena stops being a box on a page",
        "section": "Chef Battles",
        "summary": "The widest gap to the reference was never the camera or the palette. The hall was a 1520px card with rounded corners holding a 960px picture, sitting in the middle of an ordinary page, while the reference is a room you stand in. The deck is released from its width and the scene from its 960px cap and its card treatment; nothing is restructured, because the grid columns are what put the panels around the floor. Height is 100svh rather than 100vh so a phone does not gain a scrollbar when the browser chrome slides away.",
    },
    {
        "version": "2.5.360",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "Two releases were both called 2.5.356",
        "section": "Site",
        "summary": "A rebase took a version number the other agent had already used, so the journal carried the same release twice and listed the one after it out of order. The superseded entry described a deploy that was stopped and redone, and is gone; the recent block is back in order. Only the recent block was touched - older entries carry historical version strings that are not numbers, and sorting the whole list would have scrambled them.",
    },
    {
        "version": "2.5.359",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "A real viewer can be seen in the stands again",
        "section": "Chef Battles",
        "summary": "Hiding the painted-over seats hid live people with them: an avatar is cut to the shape of its seat, and a hidden seat has no shape, so anyone watching rendered at nothing at all. Seats are now clear rather than absent, and a live viewer carries a bronze edge against the painted crowd.",
    },
    {
        "version": "2.5.358",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The board stops issuing orders against numbers that no longer exist",
        "section": "Moderation",
        "summary": "Pressing START on the spectator stage sent both agents a brief describing 208 seats across four rings - a contract that had been replaced three days earlier by 544 across eight. The stage now describes what is actually there, and carries the hole that pressing START exposed: switching the SVG stands off under the backdrop took the real viewers with them, so a logged-in visitor currently cannot see themselves in the arena at all.",
    },
    {
        "version": "2.5.357",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The camera steps back and the hall comes into view",
        "section": "Chef Battles",
        "summary": "The floor was pressed against the edges of its frame and the hall behind it survived as thin strips - it read as looking down a hatch. The floor now takes about two thirds of the width, which leaves the hall visible and room beside it for the panels.",
    },
    {
        "version": "2.5.356",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The panels become glass, and the last raw colours leave the arena",
        "section": "Chef Battles",
        "summary": "The deck's panels were flat cards on a hall. They are dark glass now, with a bronze edge lit along the top and shadowed along the bottom, and the crown medallion throws a glow behind itself. The edge is stacked inset shadows, not a gradient border-image, which would have looked identical and silently switched border-radius off. The scheme's accent bronze was only declared inside the About component, so the arena kept its own copy of the hex; it is a root token now and the copy is gone, and shadows are mixed from the ink instead of plain black, which read cold against a warm scheme.",
    },
    {
        "version": "2.5.355",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The crown holder stops being a white card in a dark hall",
        "section": "Chef Battles",
        "summary": "The owner's own name sat in near-invisible light type on a white panel - the one place on the arena that shows his avatar. The card was not the bug: the deck's polish layer declares a second palette and paints a dozen components from it, while the hall only re-pointed the first, so every one of those panels was a white block waiting to be noticed. Re-pointing that palette fixes them together instead of one at a time.",
    },
    {
        "version": "2.5.354",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The hall is drawn properly now",
        "section": "Chef Battles",
        "summary": "The backdrop was a cheap draft standing in for the real thing. Redrawn at full quality from the same description: the crowd reads as people rather than dots, and the floor came out a truer octagon - its eight edges spread 6.9% where the draft spread 23.2%.",
    },
    {
        "version": "2.5.353",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "A hall drawn from the same place the arena is looked at",
        "section": "Chef Battles",
        "summary": "The backdrop is redrawn from directly overhead, so its floor is a regular octagon like ours instead of a shape no projection could match. Measured at 0.409 mean edge against the ideal 0.414, and square to within 0.4%.",
    },
    {
        "version": "2.5.352",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The arena is looked at from straight above",
        "section": "Chef Battles",
        "summary": "The owner settled the camera: no tilt at all. The floor is a plan view again, which makes the grid and any top-down artwork line up exactly and puts every click where the tile is drawn. The projection stays in the code, switched off by a single number.",
    },
    {
        "version": "2.5.351",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The floor lands on the hall it is standing in",
        "section": "Chef Battles",
        "summary": "The projection was solved against the two measurements taken off the backdrop at once - how far the octagon narrows into the distance and how tall it stands - because fixing either one alone kept pushing the other out.",
    },
    {
        "version": "2.5.350",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The build board catches up with the change of approach",
        "section": "Moderation",
        "summary": "The board still described an arena drawn entirely in code, which stopped being the plan when the owner ruled that the hall becomes a picture. Three stages are added: the backdrop and the switching-off of the SVG stands under it, the floor's true perspective (it never had any - both edges were the same length while the mockup converges to 0.51), and the mobile arena as its own scene, where tapping a ring opens that rank's chefs. The mobile stage carries the number that forced it: at 390px an outer tile is about 34px wide and 8px tall, which no finger can hit.",
    },
    {
        "version": "2.5.349",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The floor gets a camera instead of a tilt",
        "section": "Chef Battles",
        "summary": "The arena was a flat octagon leaned back, which shortens it but leaves the far edge as wide as the near one. Measured against the hall photograph: ours 1.000, the picture 0.51. The floor is now drawn through a real projection with the convergence as its one number.",
    },
    {
        "version": "2.5.348",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The hall becomes a photograph, the floor stays code",
        "section": "Chef Battles",
        "summary": "Eight releases went into drawing a bowl, tiers and a crowd that never change. They are now one still image behind the arena, and the floor - where every tile is a chef with a state and a click - stays as the SVG on top of it. Alignment test, measured on production.",
    },
    {
        "version": "2.5.347",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "A developer note stops printing itself under the footer",
        "section": "Site",
        "summary": "Three lines about the battle-start banner were rendering as visible text at the bottom of every page that could see Chef Battles - the owner found it browsing on a phone. Django's short comment {# #} closes at the end of its own line, so a multi-line one is not a comment at all and every line reaches the page. Two more were leaking the same way, in the recipe generator and the Pinch card. All three are now {% comment %} blocks, and a test walks the template tree so the next one fails in CI instead of on the site.",
    },
    {
        "version": "2.5.346",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "The crowd got its faces back",
        "section": "Chef Battles",
        "summary": "Cutting the studio background away ate the heads with it — hair and shoulders went, leaving pale scraps in the seats — and because the cut was taken from the dark originals it silently undid an earlier brightening. The cut is now tight enough to keep the head, and the lift is applied after it rather than before.",
    },
    {
        "version": "2.5.345",
        "date": "2026-07-20",
        "commit": "pending",
        "title": "A walkway and a bronze rim between the floor and the crowd",
        "section": "Chef Battles",
        "summary": "The parchment ran straight into the stands with nothing between them, so the arena read as one slab. The mockup's grey walkway now circles the floor with a bronze rim light along each edge, and the seats fade into the dark on the same curve as the faces sitting in them.",
    },
    {
        "version": "2.5.344",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The rank ladder stops sitting on the crown holder",
        "section": "Chef Battles",
        "summary": "The eight rank pills ran straight across the centre of the arena. Measured on the live page: the stage begins 32.2% down the floor container and the ladder ran from 8.5% to 44.8%, so it covered the crown holder. It was not merely anchored too low - at 36.3% tall it did not fit in the space above the stage at all. The steps are compacted and the anchor raised, in proportions of the container rather than pixels, so the clearance survives the scene being refitted. Verified at 1280 and 1920: no overlap.",
    },
    {
        "version": "2.5.343",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The crowd stopped sitting like eggs in a carton",
        "section": "Chef Battles",
        "summary": "Every stand-in face carried the studio background it was photographed on and landed dead centre of its seat, on a fixed stride that repeated the same head every third chair. The backgrounds are cut away and the hall is dealt by a hash, so no row repeats.",
    },
    {
        "version": "2.5.342",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The arena scene loses its invented green",
        "section": "Chef Battles",
        "summary": "The bowl, its rim and the spotlight were still #0e1a12 / #05100a / #d9a441 - an emerald-and-yellow-gold pair that appears nowhere in the CulinEire scheme, whose brand core is parchment, ink and muted bronze. They now derive from the hall tokens. The per-ring brightness list in CSS is gone too: it was written for four spectator rings, silently covered none of the four added when the stands went eight deep, and is replaced by the row/rows_total fall-off the faces already use.",
    },
    {
        "version": "2.5.341",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The back rows step back into the dark",
        "section": "Chef Battles",
        "summary": "Every face in the stands burned at the same brightness, so the far rows shone as hard as the front and the perspective read flat. Brightness and colour now fall away row by row, using the row number the server already publishes.",
    },
    {
        "version": "2.5.340",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The stand-in crowd can be seen in the dark",
        "section": "Chef Battles",
        "summary": "The three default faces filling empty seats were made for a light page and sank into the dark stands. They are regenerated brighter and more contrasted, so a face six pixels wide still reads as a person.",
    },
    {
        "version": "2.5.339",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The arena hall is painted in the site's own colours",
        "section": "Chef Battles",
        "summary": "The hall had been painted in an invented emerald-and-gold pair (#0d1a12, #16241a, #d9a441) that appears nowhere in the CulinEire scheme, whose brand core is warm parchment, ink and muted bronze. Every colour now derives from the design tokens: the room is mixed down from --ink, the accents are the site's own bronze, and the text is --surface-soft. Text contrast measured at 14:1.",
    },
    {
        "version": "2.5.338",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The crowd became faces instead of cropped slices",
        "section": "Chef Battles",
        "summary": "Every spectator portrait was scaled to its seat and cut to the seat's shape, so the stands read as a mosaic of half-heads. Portraits are now round, sized to the measured mockup, and each one is straightened by its own measurement rather than a single constant.",
    },
    {
        "version": "2.5.337",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "Moderators can open the arena build board, and the stands gained depth",
        "section": "Moderation",
        "summary": "The build board is a moderation tool, but it was gated on the privilege-granting check, which only superusers pass — every bearseeker moderator got a 404 on a page built for them. It now uses the same moderator gate as the rest of the moderation panel; the Master Console stays where it was. Separately the arena's seating went from four rings to eight, so the stands have real depth behind the front row, and the spectator query limit is derived from that instead of a hardcoded 208.",
    },
    {
        "version": "2.5.336",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The arena stopped cutting its own floor off",
        "section": "Chef Battles",
        "summary": "The tilted arena was sized off the container's height alone, so on a wide screen it ran 202px past each side and 216px past the bottom and the frame cut the floor off. It is now sized off whichever axis runs out first, and the octagon fits whole at every width.",
    },
    {
        "version": "2.5.335",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The Arena Build board is reachable from the moderation panel",
        "section": "Moderation",
        "summary": "The build board shipped without a way in: it had a page but no link. It now sits in the moderation panel next to Arena Console Plan.",
    },
    {
        "version": "2.5.334",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "Arena Build board: mark the camera stage green, un-pin the version",
        "section": "Moderation",
        "summary": "The camera/perspective stage is live on production, so it now shows green on the Arena Build board (7 of 11 stages complete). The board's production-version label was hard-coded and had gone stale several releases behind; it now reads the latest release automatically so it can never drift again.",
    },
    {
        "version": "2.5.333",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The arena page becomes the hall",
        "section": "Chef Battles / Arena",
        "summary": "The arena was a tilted picture squeezed inside a white card on a light page - nothing like the design, which is a dark broadcast hall with the arena filling the room. The whole arena page is now that hall: deep green-black room with warm gold light, every panel around the arena turned to dark glass, and the arena itself sized to fill the scene instead of sitting in a square box with dead bands above and below. Faces in the crowd now stand upright and round instead of lying flattened on the tilted floor - people in a hall look at the camera. The Master Console keeps its flat overhead view on purpose: it is an operations tool, and a map is the right view for operating on seats.",
    },
    {
        "version": "2.5.332",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "Arena Build board + coworking card fix",
        "section": "Moderation",
        "summary": "A new owner-only Arena Build board at /recipes/moderation/arena-build-plan/ lays every arena stage oldest-first in two lanes -- backend (Bolt) on the left, frontend (GB) on the right -- with each stage's dependency and a green done/100% badge once it is in production. Each unfinished stage carries a big red START button that fires a live coworking message to both agents to get to work; pressing it again re-sends. Also fixes the coworking dashboard, where an agent card that stored a plain string in a list field rendered one letter per line -- the model now coerces such a value into a list.",
    },
    {
        "version": "2.5.331",
        "date": "2026-07-19",
        "commit": "pending",
        "title": "The arena is seen from the stands, not from above",
        "section": "Chef Battles / Arena",
        "summary": "The arena was drawn straight down onto a flat plan, which is why it never looked like the hall in the design. It is now seen from a raised seat looking across the floor, the way the design shows it, so the arena reads as a room with depth: the far side sits back, the near side comes forward, and the crowd wraps around a lit floor. Nothing about the seating changed - the same rings, the same seats, the same places - only the point of view. On phones the view stands up closer to overhead, so seats in the far rows stay large enough to tap.",
    },
    {
        "version": "2.5.330",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "The arena stands fill with faces",
        "section": "Chef Battles / Arena",
        "summary": "Seats nobody has taken yet are filled with the site's own default avatars - the same faces a member has before uploading their own photo - so the arena reads as a full house instead of empty stone. They sit in shadow, dimmed and warmed by the stage light, so a real spectator appears as a lit face among the crowd. This is a preview of a full hall: as members arrive they replace these seats with their own avatars.",
    },
    {
        "version": "2.5.329",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "Remove the placeholder crowd from the arena stands",
        "section": "Chef Battles / Arena",
        "summary": "The figures used to fill the empty spectator seats were crude shapes that spilled past their seats and looked nothing like a crowd. They are removed while a properly drawn crowd is prepared using the site's own illustration pipeline.",
    },
    {
        "version": "2.5.327",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "Arena tiles get dark mortar, so the floor stops reading as white brickwork",
        "section": "Chef Battles / Arena",
        "summary": "On a phone the arena floor looked like flat white brickwork no matter how the rank colours were set. The outline around each tile was almost white and kept a fixed thickness however far the arena was scaled down, so on a small screen it covered much of every tile and drowned out the colour underneath. The seams are now dark mortar and thinner, which lets each ring show its own depth again - the rank ladder had been correct all along and simply could not be seen.",
    },
    {
        "version": "2.5.326",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "The arena crowd becomes the dark stands around the floor",
        "section": "Chef Battles / Arena",
        "summary": "The first pass at the darkened hall put the dark behind the arena, which left it visible only in the corners around the eight-sided floor - a black box rather than an amphitheatre. The dark now belongs to the crowd itself: the four spectator rings are the stands, deepening ring by ring as they fall away from the stage, with a taken seat lit like a face catching the stage light. The floor keeps its warm parchment, and its rank steps were deepened so the ranks read clearly instead of washing out to white.",
    },
    {
        "version": "2.5.325",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "The arena now sits in a dark bowl, lit from above",
        "section": "Chef Battles / Arena",
        "summary": "The arena floor keeps its warm parchment, and the darkness moves where it belongs: the hall around the floor. The playing floor now sits inside a deep green-black bowl with a gold rim, with a warm spotlight pooling over the centre and the outer edge falling into shadow, so the arena reads as a lit stage in an amphitheatre rather than a flat panel. Nothing about the floor palette changed - ranks still read as depth from the innermost ring outward.",
    },
    {
        "version": "2.5.324",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "Revert the dark arena floor - the floor stays light parchment",
        "section": "Chef Battles / Arena",
        "summary": "The previous skin pass darkened the arena floor, but the owner's decision is that the floor is a light warm parchment - the dark belongs to the amphitheatre around it, not the playing floor. This reverts the floor to its light palette. The darker surround treatment is being built separately as part of the arena visual work.",
    },
    {
        "version": "2.5.323",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "A published recipe is rewarded once, not once per re-approval",
        "section": "Chef Battles",
        "summary": "Publishing a recipe, article or pinch grants battle-move energy and a season contribution to the author's faction and clan. Because editing an approved recipe sends it back for moderation, a chef could edit and have the same recipe re-approved repeatedly, and each re-approval paid the reward again - including the uncapped clan/faction season points, a way to farm a clan's standing. The reward is now paid once per object; likes are unaffected, keeping their own separate per-source daily limit.",
    },
    {
        "version": "2.5.322",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "Arena gets its dark amphitheatre skin (phase A of the mockup pass)",
        "section": "Chef Battles / Arena",
        "summary": "First visual pass toward the design mockup, still fully procedural. The arena floor was a flat warm parchment; it now reads as a lit, dark-stone amphitheatre. The change is a palette swap scoped to the arena container (the site-wide brand tokens are untouched) plus a warm gold spotlight over the stage, an edge vignette that sinks the floor into a bowl, and a bloom on the crown. No sprites, no images: colour, SVG gradients and a filter only.",
    },
    {
        "version": "2.5.321",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "One arena: the procedural build is now the only one, plus a challenge button on recipes",
        "section": "Chef Battles / Arena",
        "summary": "The arena no longer forks. The procedural, code-drawn arena is now what everyone sees at /chef-battle/arena/ - the old ?proto=1 switch is gone, and a plain visit no longer shows the previous build. The Master Console renders the same procedural arena, so its data now carries the full arena payload it needs. The retired renderer and its unreachable prototype sandbox have been removed. Recipe pages also gain an Issue a Challenge button that starts a battle from that recipe, shown only where the challenge would actually work.",
    },
    {
        "version": "2.5.320",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "Battle integrity hardening: frozen recipes, single scoring, artifacts returned",
        "section": "Chef Battles",
        "summary": "Three integrity fixes found in a battle-engine sweep. A recipe entered in a live battle is now locked from editing until the battle is over, so its ingredient lines cannot be reshuffled out from under the biathlon and it cannot be flipped out of published mid-vote. Scoring a battle now runs under a row lock and re-checks the status, so an overlapping cron run and operator click can no longer both award the same win and double a chef's rating and crown. And a decisive win now returns each chef's unused reserved artifacts to their chest, the same way a draw already did, instead of leaving them pinned to the finished battle forever.",
    },
    {
        "version": "2.5.319",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "Agent message subjects can be longer",
        "section": "Coworking",
        "summary": "The subject line on an agent-to-agent coworking message was capped at 200 characters, which truncated or rejected the longer, more descriptive subjects the agents use to summarise a handoff at a glance. The cap is now 1000 characters.",
    },
    {
        "version": "2.5.318",
        "date": "2026-07-18",
        "commit": "pending",
        "title": "Staff reach the arena they can already see, and battle buttons match the gate",
        "section": "Chef Battles / Arena",
        "summary": "During dark launch, staff were shown the arena panels but the battle views themselves turned them away with a not-found page, because the view gate omitted staff while the panel-preview flag included them. The view gate now lets staff in too, matching what they already see; the Arena Master Console stays superuser-only, so this does not open the console to staff. Templates also gain a battle_visible flag computed from that same view gate, so any button linking into a battle view is shown exactly when the view will accept it. Also clarifies the challenge recipe help text, which described only what the field is not.",
    },
    {
        "version": "2.5.317",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "Only a published recipe can carry a battle, and a recipe can now start one",
        "section": "Chef Battles",
        "summary": "A chef could issue a challenge with a recipe that was still a draft, or one moderation had already rejected, and accepting that challenge turned it into a battle entry anyway. The audience would then have been asked to vote on a recipe it could not open. Every recipe chooser in a battle now offers approved recipes only, and the status is checked again at the moment the battle is created, because a challenge stands for forty-eight hours and moderation can withdraw a recipe inside that window. A challenge can also now be started from a published recipe: that recipe names the chef being challenged and suggests the theme, while the challenger still brings a dish of their own.",
    },
    {
        "version": "2.5.316",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "Moderation headings get the brand typeface back",
        "section": "Moderation",
        "summary": "Headings on the automation and sponsor review screens were quietly rendering in the body typeface instead of the brand serif. They referenced a font variable that was never declared anywhere, so the rule was discarded and the heading simply inherited the surrounding text. They now use the same brand serif as the rest of the site, which is what they were always meant to be.",
    },
    {
        "version": "2.5.315",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "A battle about to start calls the whole site to its seats",
        "section": "Chef Battles / Arena",
        "summary": "Five minutes before a scheduled battle begins, every page of the site now carries a small corner banner naming the theme, both chefs and the real countdown, inviting members to take their seat and guests to register for one. It never blocks the page, so nobody is held hostage mid-recipe, and it dismisses per battle rather than forever: the next battle calls again. The teleport flash on the arena floor was also fixed — it had been firing every twenty seconds at nobody.",
    },
    {
        "version": "2.5.314",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "The countdown says what it is ending",
        "section": "Chef Battles / Arena",
        "summary": "The arena countdown now names the thing it is counting down to — dish submission, public voting, or the battle itself — instead of the generic 'Live deadline'. The wording is re-read on every refresh, because the phase can change while the clock is running.",
    },
    {
        "version": "2.5.313",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "The battle start ritual",
        "section": "Chef Battles / Arena",
        "summary": "A scheduled battle now resolves on its own start timer, which is a hard deadline: both chefs ready starts it early, and when the clock runs out the arena acts on who actually turned up. One chef present means a short wait for the other, then a walkover to the chef who came — the absentee forfeits. If neither appears the battle is void and both are penalised. The sitewide blast now also carries the battle about to start, so visitors on any page are invited to take a seat with the real countdown.",
    },
    {
        "version": "2.5.312",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "Cancel Battle erases a test battle and returns its artifacts",
        "section": "Chef Battles / Arena",
        "summary": "While Chef Battles is in test mode, the operator Cancel Battle control now erases an unscored battle completely — the battle, its linked challenge and every related record — leaving no trace anywhere, and returns every artifact the battle reserved, consumed or locked back to the owning chef's chest. A scored battle, or any battle once Chef Battles is public, still follows the safe mark-cancelled path.",
    },
    {
        "version": "2.5.311",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "Voting is for registered members only",
        "section": "Chef Battles / Voting",
        "summary": "Anonymous visitors can no longer vote in a battle: a passer-by is invited to sign in instead, and only a signed-in account can cast a ballot. The per-device anonymous constraint is retired while the connection fingerprints are kept, so duplicate-account abuse from one device is still caught. Historical anonymous ballots are removed by migration.",
    },
    {
        "version": "2.5.310",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "Align the purchases & VAT page with real chef payouts",
        "section": "Legal",
        "summary": "The purchases and VAT page now matches what the platform actually does: purchased tokens stay closed-loop and are never bought back, while a Chef may request a discretionary real-money buy-back of approved reward tokens. A new Chef Payouts section covers the Chef Reward Agreement, a rate locked at request time, Stripe Connect with identity verification, DAC7 reporting under EU Directive 2021/514, and the Chef's own tax responsibility.",
    },
    {
        "version": "2.5.309",
        "date": "2026-07-17",
        "commit": "pending",
        "title": "Offer a free arena seat on hover",
        "section": "Chef Battles / Arena",
        "summary": "Hovering a free arena cell now offers a single \"Sit here\" label that follows the cursor, shown only where the viewer could actually sit (a chef over their own rank ring, a spectator over the stands). The static cache version was also bumped so returning visitors receive the current renderer instead of a stale cached copy.",
    },
    {
        "version": "2.5.308",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Arena spectators are the people actually watching",
        "section": "Chef Battles / Arena",
        "summary": "Any logged-in visitor now takes a seat in the arena: enrolled chefs sit in their rank ring and every other signed-in author sits in a spectator ring, shown with their own avatar while their presence is fresh. The spectator list is drawn from live arena presence rather than token balance, so the outer rings fill with the real audience.",
    },
    {
        "version": "2.5.307",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Restore the free-seat plus on the Arena floor",
        "section": "Chef Battles / Arena",
        "summary": "The procedural arena preview again marks every free seat with a plus, drawn once with the grid and toggled in place by the live poll, so an open floor reads as an invitation rather than a dead grid. Owner-requested; matches the legacy floor behaviour.",
    },
    {
        "version": "2.5.306",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Arena occupants fall back to an initial",
        "section": "Chef Battles / Arena",
        "summary": "In the procedural arena preview an occupied tile whose chef has no avatar now renders the chef's initial instead of appearing empty, so a taken seat never reads as free.",
    },
    {
        "version": "2.5.305",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Unified procedural Arena renderer behind ?proto=1",
        "section": "Chef Battles / Arena",
        "summary": "The ?proto=1 preview now runs a unified renderer that draws the procedural octagon and fills each tile with its chef, clipped to the cell outline, alongside the ported live command deck, battle-room popup, blast and ripple, and the effects layer on the unified floor. The default arena is unchanged.",
    },
    {
        "version": "2.5.304",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Dark-launch the procedural Arena preview",
        "section": "Chef Battles / Arena",
        "summary": "The Arena page now carries a gated procedural preview: with ?proto=1 the polar-geometry renderer draws the full octagonal grid from the live read-model and refreshes the roster on a ten-second poll, while the default page remains exactly as before. Also hardened agent discovery: the identity endpoint is read-only and markdown negotiation now varies caches by Accept header.",
    },
    {
        "version": "2.5.303",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Keep internal traffic out of visitor statistics",
        "section": "Monitoring",
        "summary": "Monitoring no longer records the team's own traffic: any machine seen with a staff login is remembered for a week and its page views, including anonymous fetches such as manifest requests and diagnostic curls, stay out of the statistics. Fixed internal addresses (the production host itself) can be listed via a new setting. Genuinely suspicious probes are still recorded regardless of source.",
    },
    {
        "version": "2.5.302",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Add seat capacity to the Arena geometry contract",
        "section": "Chef Battles / Arena",
        "summary": "Each ring in the declarative Arena geometry now carries its seat capacity, derived from the live arena's existing ring counts and aligned to the eight-sided symmetry so every octant holds a whole number of cells. The procedural renderer reads cell density from the contract instead of hardcoding it.",
    },
    {
        "version": "2.5.301",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Add declarative Arena geometry read-model",
        "section": "Chef Battles / Arena",
        "summary": "The public Arena read-model now publishes the arena's structural geometry: an eight-sided radial grid of thirteen rings (centre stage, eight chef-rank rings from Culinary Master innermost to Kitchen Porter outermost, and four spectator rings) derived from the real rank model. The procedural renderer draws the polar grid from this single source of truth instead of hardcoding ring or rank counts.",
    },
    {
        "version": "2.5.299",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Add the Arena floor environment plate",
        "section": "Chef Battles / Arena",
        "summary": "Introduced the first production Arena environment plate: a clean cinematic octagonal kitchen floor behind the existing live SVG cells. Real chefs, ranks, tooltip, popup and interaction layers remain above the image and unchanged.",
    },
    {
        "version": "2.5.298",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Label the Arena deadline countdown",
        "section": "Chef Battles / Arena",
        "summary": "The public Arena deadline contract now carries a kind and human label derived from the same real per-phase deadline source, so the command deck can say what the countdown means (dish submission closes, public voting closes, or battle closes) instead of a generic deadline. It stays null when no deadline is set.",
    },
    {
        "version": "2.5.296",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Anchor the Arena deadline to server time",
        "section": "Chef Battles / Arena",
        "summary": "The live Arena deadline now ticks smoothly between state polls using the authoritative deadline and server_time pair supplied by the public read-model. Each poll resynchronises the display; it stops cleanly when no active deadline exists.",
    },
    {
        "version": "2.5.295",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Add authoritative Arena server time",
        "section": "Chef Battles / Arena",
        "summary": "The public Arena read-model now stamps an authoritative server_time ISO timestamp at payload build alongside the deadline and phase, so clients can reconcile their own clock drift against the countdown. It rides the same Arena poll payload and is always present.",
    },
    {
        "version": "2.5.294",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Format the Arena Crown holding window reliably",
        "section": "Chef Battles / Arena",
        "summary": "Corrected Crown expiry formatting: the public ISO timestamp is now formatted by the existing Arena read-model on initial load and poll refresh, avoiding an empty server-side date while preserving the no-expiry fallback.",
    },
    {
        "version": "2.5.293",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Show the real Crown holding window",
        "section": "Chef Battles / Arena",
        "summary": "The Arena centre now states the Crown holding window when the public crown expiry exists, both on first render and after a centre refresh. When no expiry is supplied it retains the existing honest awaiting-challenge message.",
    },
    {
        "version": "2.5.292",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Correct the Arena phase rail",
        "section": "Chef Battles / Arena",
        "summary": "Removed a duplicate Biathlon step from the public Arena lifecycle rail, restoring the intended seven distinct real phases.",
    },
    {
        "version": "2.5.291",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Show the real Arena battle deadline",
        "section": "Chef Battles / Arena",
        "summary": "The Current phase card now shows a compact, tabular countdown sourced only from the public Arena deadline contract. It updates with the existing state poll and shows an honest no-deadline state when there is no current battle deadline; no client-side clock is invented.",
    },
    {
        "version": "2.5.290",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Add Arena deadline countdown read-model",
        "section": "Chef Battles / Arena",
        "summary": "The public Arena read-model now surfaces the active battle's real countdown as {deadline_iso, seconds_remaining}, reusing the existing per-phase deadline logic and clamping remaining seconds at zero. It rides the same Arena poll payload as the metrics and phase rail and returns nothing when no battle is live, so no timer is invented.",
    },
    {
        "version": "2.5.289",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Bind the public Arena phase rail",
        "section": "Chef Battles / Arena",
        "summary": "The Arena phase rail and its current-phase card now render the public key, label and step supplied by the battle read-model, then clear safely to the real open-floor state when no battle is present. Existing polling updates the same elements in place without inventing a timer or phase.",
    },
    {
        "version": "2.5.288",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Add Arena phase rail read-model",
        "section": "Chef Battles / Arena",
        "summary": "The public Arena read-model now exposes a phase rail entry (key, label, step 1..7) mapping the live battle state across Challenge, Combat, Biathlon, Cooking, Mod Review, Voting and Crown. It rides the same Arena poll payload as the top-bar metrics, resolves a paused battle to the phase it was paused from, and returns nothing when no battle is live.",
    },
    {
        "version": "2.5.286",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Make the Arena centre stage live",
        "section": "Chef Battles / Arena",
        "summary": "The centre-stage context now presents only the real current state: a live challenger/opponent pair, the actual Crown Holder, or an explicit open-centre state. It refreshes when the centre occupant changes during the existing Arena poll while retaining the active battle link and the SVG arena as source of truth.",
    },
    {
        "version": "2.5.285",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Add Arena rank spine and action rail",
        "section": "Chef Battles / Arena",
        "summary": "Added a compact desktop rank spine drawn from the existing rank groups and a responsive action rail that presents the live kitchen state alongside genuine Rankings, enrolment, challenge or sign-in routes. Both components retain the site button interactions and hide safely on narrow screens where the floor needs priority.",
    },
    {
        "version": "2.5.284",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Connect live Arena crown and gift panels",
        "section": "Chef Battles / Arena",
        "summary": "The public Arena now renders its crown streak, today's crown ladder and recent battle gifts from the real read-model, with profile links, honest empty states and safe in-place refreshes on the existing Arena polling cycle.",
    },
    {
        "version": "2.5.282",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Integrate Arena command-deck icon sprite",
        "section": "Chef Battles / Arena",
        "summary": "Integrated the coordinated CulinEire-owned Arena SVG sprite into the public command deck, starting with clear viewers and rank-tier metric icons while preserving existing interactions and the SVG battle floor.",
    },
    {
        "version": "2.5.280",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Add live Arena chef focus stage",
        "section": "Chef Battles / Arena",
        "summary": "When a real battle is active, the Arena now presents its challenger and opponent in a compact central VS stage with the true theme and status, while retaining the existing SVG centre and battle-room entry point.",
    },
    {
        "version": "2.5.279",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Bind Arena phase rail and spectator generator",
        "section": "Chef Battles / Arena",
        "summary": "The Arena lifecycle rail now reflects the real Battle.status, and spectator cells are generated by a pure polar-coordinate slot generator that distributes real presence records over rings 9–12 without creating fake identities or counts.",
    },
    {
        "version": "2.5.278",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Correct Arena command-deck density",
        "section": "Chef Battles / Arena",
        "summary": "Corrected the first Arena command-deck responsive pass: metrics now remain readable in the side rail and the complete rank legend wraps inside its allocated floor header instead of clipping.",
    },
    {
        "version": "2.5.277",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Start the Arena mosaic rebuild",
        "section": "Chef Battles / Arena",
        "summary": "Introduced the first responsive command-deck layer around the existing live SVG arena: lifecycle rail, real-data metrics, phase, ladder and gift panels, while retaining arena polling, chef cells, battle popup and legal gift controls. Added the reference mosaic and incremental assembly plan for the complete rebuild.",
    },
    {
        "version": "2.5.276",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Align the four arena action buttons",
        "section": "Chef Battles / Navigation",
        "summary": "All four lower widget actions now share a left-aligned one-centimetre inset and identical vertical rhythm. Enter Arena uses the established Issue a Challenge CTA treatment and matching cutlery artwork.",
    },
    {
        "version": "2.5.275",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Tighten arena menu spacing",
        "section": "Chef Battles / Navigation",
        "summary": "Centred Arena Menu and standardised its internal gaps to one compact spacing unit, further reducing the widget width and row density.",
    },
    {
        "version": "2.5.274",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Fix arena widget disclosure marker",
        "section": "Chef Battles / Navigation",
        "summary": "The header now uses an explicit up triangle while open and down triangle while closed, instead of relying on a CSS rotation state.",
    },
    {
        "version": "2.5.273",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Compact Chef Battles widget rhythm",
        "section": "Chef Battles / Navigation",
        "summary": "Reduced widget width, internal spacing, icon scale and row heights while preserving the two-column menu and comfortable clickable targets.",
    },
    {
        "version": "2.5.272",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Use the CulinEire mark in arena widget",
        "section": "Chef Battles / Navigation",
        "summary": "Replaced the generic crossed-tools glyph beside Chef Battles Arena with the existing compact CulinEire logo mark.",
    },
    {
        "version": "2.5.271",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Correct Enter Arena interaction states",
        "section": "Chef Battles / Navigation",
        "summary": "Enter Arena now brightens from a muted surface on hover, while its separate click ripple uses a visible dark-bronze wave.",
    },
    {
        "version": "2.5.270",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Wire widget buttons to existing click effects",
        "section": "Chef Battles / Navigation",
        "summary": "Widget menu and toggle now use the existing header floating ripple, while its large action buttons use the existing internal Hero-button ripple. The widget title now has dark bronze contrast on its light header.",
    },
    {
        "version": "2.5.269",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Match arena widget interaction standards",
        "section": "Chef Battles / Navigation",
        "summary": "Arena-menu links now use the primary-header interaction timing, while its large action buttons use the Hero pill transition; no new animation language was introduced.",
    },
    {
        "version": "2.5.268",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Generated Chef Battles navigation assets",
        "section": "Chef Battles / Navigation",
        "summary": "Replaced line-art widget symbols with nine generated culinary game icon assets, cropped to transparent PNGs and applied the site parchment, cappuccino, bronze and culinary-green palette to the navigation shell.",
    },
    {
        "version": "2.5.267",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Align recipe Hero with homepage standard",
        "section": "Recipes / Hero",
        "summary": "Recipe Hero now uses the homepage height, type scale, spacing, action gap, and photo-control offset while keeping staff actions on one desktop row.",
    },
    {
        "version": "2.5.266",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles widget icon system",
        "section": "Chef Battles / Navigation",
        "summary": "Replaced generic widget icons with purpose-drawn kitchen and battle SVGs using only CulinEire brand colours.",
    },
    {
        "version": "2.5.265",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Keep recipe hero actions on one desktop row",
        "section": "Recipes / Hero",
        "summary": "Expanded the recipe hero action measure to the approved 900px desktop width so staff and navigation actions stay on one row.",
    },
    {
        "version": "2.5.264",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Standardise recipe detail presentation",
        "section": "Recipes / Detail page",
        "summary": "Recipe pages now reuse the canonical hero-actions include and present their content in the site-standard warm document frame.",
    },
    {
        "version": "2.5.263",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Move recipe staff actions into hero",
        "section": "Recipe details / Hero",
        "summary": "Removed the standalone staff toolbar and placed its edit, delete, and Pinch actions inside the recipe hero.",
    },
    {
        "version": "2.5.262",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Restore staff action contrast",
        "section": "Recipe details / Staff tools",
        "summary": "Made edit, delete, and Pinch actions readable against the dark staff toolbar on recipe detail pages.",
    },
    {
        "version": "2.5.261",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Remove leaked Pinch template comment",
        "section": "Pinch / Mobile navigation",
        "summary": "Removed a multiline template comment that was rendered as visible text on the Pinch page.",
    },
    {
        "version": "2.5.260",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Unified list filter backgrounds",
        "section": "Recipes / Articles / Pinch",
        "summary": "Category filters on all three collection pages now use the surrounding page background instead of a white card surface.",
    },
    {
        "version": "2.5.259",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Compact recipe category filter",
        "section": "Recipes / Navigation",
        "summary": "Removed an oversized page-section gap between the recipe category row and its View All control.",
    },
    {
        "version": "2.5.258",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Challenges command label",
        "section": "Chef Battles / Navigation",
        "summary": "Simplified the command deck label from My Challenges to Challenges.",
    },
    {
        "version": "2.5.257",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles command deck hover correction",
        "section": "Chef Battles / Navigation",
        "summary": "Removed a stale dark hover state from the command deck controls; hover states now remain within the CulinEire cappuccino, blue, green, and bronze palette.",
    },
    {
        "version": "2.5.256",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "CulinEire palette arena command deck",
        "section": "Chef Battles / Navigation",
        "summary": "The command deck now follows the CulinEire colour and font scheme: cappuccino surfaces, warm bronze, restrained blue and green accents, and no decorative layer outside its boundary.",
    },
    {
        "version": "2.5.255",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Compact, closed arena command deck",
        "section": "Chef Battles / Navigation",
        "summary": "The command deck is now compact and visually closed with a dedicated lower metal cap; controls retain their touch-safe interactive size.",
    },
    {
        "version": "2.5.254",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Generated arena command deck frame",
        "section": "Chef Battles / Navigation",
        "summary": "A CulinEire-generated metallic cyan-and-amber frame now powers the Chef Battles command deck while the controls remain real, accessible HTML links.",
    },
    {
        "version": "2.5.253",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles command deck visual reference",
        "section": "Chef Battles / Navigation",
        "summary": "The command deck adopts the approved metallic kitchen-battle reference: cyan and amber energy rails, illustrated control hierarchy, and a prominent arena launch control.",
    },
    {
        "version": "2.5.252",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Live Arena token alignment",
        "section": "Chef Battles / Navigation",
        "summary": "The Chef Battles command deck now directly uses the Live Arena broadcast colour tokens, surfaces, borders, and green primary action treatment.",
    },
    {
        "version": "2.5.251",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles arena command deck",
        "section": "Chef Battles / Navigation",
        "summary": "The floating arena widget now uses an opaque dark broadcast command-deck design with structured controls, strong hierarchy, and owned SVG icons.",
    },
    {
        "version": "2.5.250",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Header sign-in popover",
        "section": "Accounts / Navigation",
        "summary": "Desktop visitors can sign in from a compact form beside the Sign In link, without leaving the page they are reading.",
    },
    {
        "version": "2.5.249",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles: Knife Roll widget label",
        "section": "Chef Battles / Navigation",
        "summary": "The Chef Battles widget now calls the chef's artifact collection Knife Roll.",
    },
    {
        "version": "2.5.247",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles: interactive knife and tool roll",
        "section": "Chef Battles / Knife and tool roll",
        "summary": (
            "Knife roll summary cards now work as filters, pagination keeps the selected "
            "filter, and every artifact card opens a dedicated reference page with its "
            "Move effect, rarity, description, and catalogue price."
        ),
    },
    {
        "version": "2.5.246",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles: knife roll follows CulinEire page standards",
        "section": "Chef Battles / Knife and tool roll",
        "summary": (
            "The knife and tool roll now uses the shared homepage Hero action include "
            "and the Company Information document layout, with a clear summary and "
            "24 artifacts per page instead of one unmanageable collection wall."
        ),
    },
    {
        "version": "2.5.245",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles: visible artifact Move effects",
        "section": "Chef Battles / Knife and tool roll",
        "summary": (
            "Every artifact card in a chef's knife and tool roll now displays "
            "its actual combat effect, such as Attack +5 Move or Defence +10 Move."
        ),
    },
    {
        "version": "2.5.244",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles: named spectator artifact delivery",
        "section": "Chef Battles / Live gifts",
        "summary": (
            "Spectators now choose the exact non-legendary artifact for a chef, "
            "with the item price and matching delivery fee shown before purchase. "
            "Legendary artifacts remain prize-only; chefs carry artifacts in a knife and tool roll."
        ),
    },
    {
        "version": "2.5.243",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles: finite attack and defence loadouts",
        "section": "Chef Battles / Combat",
        "summary": (
            "Each chef can bring at most three attack artifacts and three "
            "defence artifacts into a battle. The server enforces the limit "
            "and returns unused loadout items to inventory after the battle."
        ),
    },
    {
        "version": "2.5.242",
        "date": "2026-07-16",
        "commit": "pending",
        "title": "Chef Battles: artifact power decides every combat round",
        "section": "Chef Battles / Combat",
        "summary": (
            "Combat now compares each chef's committed Move power plus the "
            "matching attack or defence artifact bonus. A stronger defender "
            "wins the round and receives the point; tied totals are bonus "
            "rounds until a chef leads after reaching three wins."
        ),
    },
    {
        "version": "2.5.241",
        "date": "2026-07-15",
        "commit": "pending",
        "title": "Chef Road: combat-to-biathlon and draw payout continuity",
        "section": "Chef Battles / Core journey",
        "summary": (
            "A decisive combat round now records winner and loser and opens "
            "the ingredient biathlon directly. A completed draw now also runs "
            "Next Battle Unlock, allowing eligible pending CBR/LSR records to "
            "enter payout review."
        ),
    },
    {
        "version": "2.5.239",
        "date": "2026-07-15",
        "commit": "pending",
        "title": "Chef Road: recipe lifecycle and source-index biathlon",
        "section": "Chef Battles / Core journey",
        "summary": (
            "A challenger recipe is attached when the challenge is accepted, "
            "without counting as a dish submission. Attached recipes remain "
            "stable through dish submission. Biathlon locks and shots now use "
            "the original recipe line indices, so blank lines cannot retarget "
            "ingredient actions."
        ),
    },
    {
        "version": "2.5.235",
        "date": "2026-07-15",
        "commit": "pending",
        "title": "Chef Road: block dish submit in pre-combat phases (lifecycle guard)",
        "section": "Chef Battles / Lifecycle",
        "summary": (
            "battle_entry_submit had no status check, so a chef could submit the "
            "dish entry during scheduled/menu_locked, skipping combat. Added a "
            "lifecycle guard rejecting submission in the pre-combat phases so the "
            "UI hiding the button and the server agree. Confirms the menu_locked "
            "next-step is the Changing Room only. Test added."
        ),
    },
    {
        "version": "2.5.233",
        "date": "2026-07-15",
        "commit": "pending",
        "title": "Fix battle_set_ready 500 (Chef's Road lifecycle blocker #1)",
        "section": "Chef Battles / Lifecycle",
        "summary": (
            "First backend blocker on the end-to-end Chef's Road: pressing Ready "
            "500'd because battle_set_ready called create_battle_event with a "
            "positional battle arg (the signature is keyword-only) and the wrong "
            "kwargs (note= / author= instead of message= / actor=), plus an "
            "invalid event_type string. Fixed the call and added a MENU_LOCKED "
            "BattleEvent.EventType (migration 0077). Both chefs ready now advances "
            "SCHEDULED -> MENU_LOCKED cleanly. Test added."
        ),
    },
    {
        "version": "2.5.232",
        "date": "2026-07-15",
        "commit": "pending",
        "title": "Master Console: safely delete unscored test battles",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Added an owner-only Delete Test Battle control for the dark-launch "
            "console. It permanently removes an unscored test battle, its "
            "dependent events, reactions and linked challenge. The action is "
            "disabled when Chef Battles is public and refuses scored battles, "
            "protecting chef ratings, crowns and move ledgers."
        ),
    },
    {
        "version": "2.5.230",
        "date": "2026-07-15",
        "commit": "pending",
        "title": "Live arena: add CSP nonce to inline script (fixes video/polling/reactions)",
        "section": "Chef Battles / Live Arena",
        "summary": (
            "The live-arena preview inline <script> (HLS attach, snapshot polling, "
            "heart reactions, tabs) had no nonce, so the site CSP (script-src "
            "'self' 'nonce-...') blocked the whole block and none of the arena JS "
            "ran - video panels stayed on fallback. Added "
            "nonce=request.csp_nonce to the inline script, matching the rest of "
            "the site. HLS video now attaches and plays."
        ),
    },
    {
        "version": "2.5.229",
        "date": "2026-07-15",
        "commit": "pending",
        "title": "Live arena preview: fix leaked comment + collapsed video stage",
        "section": "Chef Battles / Live Arena",
        "summary": (
            "Two visible preview bugs fixed while GreenBear was rate-limited. "
            "(1) The SVG sprite include used a multi-line {# #} comment, which "
            "Django only supports single-line, so it rendered as literal text at "
            "the top of the arena; switched to {% comment %}{% endcomment %}. "
            "(2) The fit-to-screen media query let the dual video stage collapse "
            "to near-zero height because the tall matchup portraits ate the "
            "vertical space; capped portrait height to 132px and gave the stage a "
            "40vh minimum so the video panels stay the dominant broadcast block."
        ),
    },
    {
        "version": "2.5.227",
        "date": "2026-07-15",
        "commit": "pending",
        "title": "Live arena: fix video playback (self-host hls.js + CSP media blob)",
        "section": "Chef Battles / Live Arena",
        "summary": (
            "Live HLS video was not playing because hls.js loaded from the "
            "jsdelivr CDN, which the site CSP script-src does not allow, so Hls "
            "was undefined. Self-hosted hls.min.js (1.5.13) as a static asset "
            "(static/js/vendor/) referenced via {% static %}, and added "
            "media-src 'self' blob: to the CSP so the MSE video blob URL is "
            "permitted. Video now plays end-to-end from the self-hosted MediaMTX "
            "HLS."
        ),
    },
    {
        "version": "2.5.223",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "Live Arena Phase 1: snapshot envelope + polling endpoint",
        "section": "Chef Battles / Live Arena",
        "summary": (
            "Server-authoritative arena snapshot (arena_snapshot.py) with a "
            "transport envelope (server_timestamp, sequence, full-state-on-"
            "reconnect) and the exact frontend field shape agreed with GreenBear: "
            "per-side chef {num, name, rank, clan, country=Ireland, avatar_url, "
            "playback_url, viewers, likes=reaction_count, comments, supporters, "
            "role}, theme, remaining_seconds, chat. Owner-gated polling endpoint "
            "chef_battle:live_arena_snapshot; the preview page now renders real "
            "battle data when a battle exists and falls back to dev fixtures "
            "otherwise. Unblocks the frontend to bind real reactions + live "
            "polling. 3 tests."
        ),
    },
    {
        "version": "2.5.222",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "Live Arena Phase 1: heart reactions backend",
        "section": "Chef Battles / Live Arena",
        "summary": (
            "First Phase-1 data increment for the live arena. BattleReaction "
            "(migration 0076) records append-only 'heart' taps per battle side; "
            "reaction_service.record_battle_reaction aggregates the per-side count "
            "with a per-source rolling rate limit (anti-farm). New endpoint "
            "chef_battle:arena_react (POST battle_id + side) returns the new count "
            "for the arena heart button. Preview fixture country corrected to "
            "Ireland (owner decision). Next: arena_state snapshot envelope feeding "
            "the preview with real data. 5 tests."
        ),
    },
    {
        "version": "2.5.218",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "Live Arena broadcast preview page (owner build canvas)",
        "section": "Chef Battles / Live Arena",
        "summary": (
            "Owner-visible live preview of the new broadcast arena at "
            "/chef-battle/master/live-arena/preview/ so the owner can watch the "
            "arena take shape as it is built, rather than only a status matrix. "
            "Renders the reference composition (green-left / gold VS / red-right "
            "matchup header, dual live stage with fallback and overlays, central "
            "timer plate, live chat) with dev fixtures, swapped for the real "
            "arena_state snapshot and MediaMTX HLS video as Phase 1/2 land. "
            "Owner-gated; linked prominently from the Master Console."
        ),
    },
    {
        "version": "2.5.217",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "Live Arena build tracker in the Master Console",
        "section": "Chef Battles / Live Arena",
        "summary": (
            "Owner-visible progress tracker for the Live Arena implementation "
            "(migration 0074/0075). LiveArenaStage seeds 16 dependency-ordered "
            "stages (foundation -> frame -> live modules -> cross-cutting), each "
            "tracked on two axes: backend presence (Bolt) and frontend presence "
            "(GreenBear). Page at /chef-battle/master/live-arena/ (owner-gated, "
            "linked from the Master Console) shows the backend x frontend matrix "
            "with progress bars; statuses and notes update live from the console "
            "with no deploy, each agent writing only its own column. Part of the "
            "paired Phase 0 audit of the Live Arena master brief. 4 tests."
        ),
    },
    {
        "version": "2.5.215",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "Arena Observer prize backend (Season Champion Recognition)",
        "section": "Chef Battles / Clans",
        "summary": (
            "Backend for the non-cash season-champion prize (migration 0073). New "
            "models SeasonArenaObserver + ObserverDisputeVote and observer_service: "
            "the winning clan's champion (top contributor) seats up to 2 clan "
            "members as Arena Observers for the following season. can_nominate_"
            "observers / nominate_arena_observers validate champion, clan "
            "membership, distinct pair and open window; is_active_arena_observer / "
            "get_active_arena_observers derive the active window from won_season "
            "(active only while the current season is its immediate successor, so "
            "the seat auto-expires with no stored flag to drift). cast_observer_vote "
            "records an ADVISORY, non-binding vote on a BattleReport (one per "
            "observer per report, updatable); get_observer_votes lists them for the "
            "operator. Dark-launched, no UI yet; GreenBear builds the nomination / "
            "badge / dispute-vote UI on this API. 6 new tests."
        ),
    },
    {
        "version": "2.5.213",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "CoWork owner paste-box: route any-length text to an agent",
        "section": "Coworking",
        "summary": (
            "Added a 'Paste & deliver' box to the coworking dashboard so the owner "
            "can paste text of ANY length (e.g. a full agent transcript that would "
            "be split across several Telegram messages) and route it to a chosen "
            "agent's inbox as a single CoworkingMessage. The agent picks it up via "
            "its 15s inbox poller. No character cap (TextField, no form truncation); "
            "moderator-gated like the rest of the dashboard. 4 new tests."
        ),
    },
    {
        "version": "2.5.212",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "Chef Battle 'almost here' announcement image + newsfeed post",
        "section": "Newsfeed / Chef Battles",
        "summary": (
            "Added the Chef Battle 'coming soon' promotional banner "
            "(static/images/chef_battle/chef_battle_coming_soon.png) and published "
            "a battle_event newsfeed entry announcing that Chef Battle is ~90% "
            "complete with launch days away. The entry carries the themed banner "
            "as its image_url so the Telegram channel post shows the on-topic "
            "artwork rather than a generic image."
        ),
    },
    {
        "version": "2.5.209",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "Clans backend: models, ledger scoring, winner/champion selectors",
        "section": "Chef Battles / Clans",
        "summary": (
            "Backend foundation for Clans & Alliances (Phase 6), built on "
            "GreenBear's model spec. New models (migration 0072): Clan (founder, "
            "name/slug, up to 3 Faction categories, moderation status), "
            "ClanMembership (request/approve, one active clan per chef via a "
            "partial unique constraint), Alliance + AllianceMembership (S1 "
            "foundation, one active alliance per clan), and an event-sourced "
            "ClanContribution ledger + ClanSeasonStanding board. Scoring "
            "(clan_service.py) decides the season winner by the RAW SUM of a "
            "clan's members' seasonal points (owner's rule), with a >=3 "
            "active-member floor; selectors get_clan_leaderboard, "
            "get_season_winning_clan and get_season_clan_champion feed the UI and "
            "the Arena Observer prize. Earning is wired into award_moves alongside "
            "faction contribution (same events, savepoint-isolated); a season-end "
            "receiver freezes ClanSeasonStanding. Dark-launched (no UI yet); "
            "GreenBear builds the clan UI on these selectors next. 6 new tests."
        ),
    },
    {
        "version": "2.5.208",
        "date": "2026-07-14",
        "commit": "pending",
        "title": "Arena rules: Clans, Alliances & Season Champion Reward sections",
        "section": "Chef Battles / Rules",
        "summary": (
            "Added three new sections to the public arena rules page "
            "(/chef-battle/rules/), recording the owner's Clans design so the "
            "mechanic is locked into the official rules: "
            "(21) Clans: a named team with a founder and members; the founder "
            "picks up to 3 categories from the existing Cuisines and Specialties; "
            "a Chef's own Specialty stays personal; the winning clan of a season "
            "is the one whose members earned the highest combined seasonal "
            "contribution. "
            "(22) Alliances: clans may ally and call each other into battles, "
            "turning a recipe duel into a cuisine-versus-cuisine contest; "
            "introduced in stages, expanding over future seasons. "
            "(23) Season Champion Reward: the winning clan's champion may "
            "nominate 2 clan members as Arena Observers for the following season; "
            "no nomination means empty seats with no fallback; the role is an "
            "advisory voice in Chef Battle disputes only (not site moderation), "
            "recorded for the operator but non-binding, expiring when that season "
            "ends. All three are non-cash, skill-based and not gambling. "
            "TOC, mobile jump and section count updated (23 sections). "
            "Canonical rules also recorded in docs/chef_battle/clans_alliances_rules.md."
        ),
    },
    {
        "version": "2.5.153",
        "date": "2026-07-08",
        "commit": "pending",
        "title": "Chef Battles UI overhaul: nav merge, hero cleanup, widget links",
        "section": "Chef Battles / UI",
        "summary": (
            "Nine simultaneous improvements across the Chef Battles UI. "
            "(1) /chef-battle/notifications/ merged into /messages/ inbox: "
            "pending challenges and recent battle events now appear in the Messages "
            "inbox under a 'Battle Notifications' section. "
            "(2) Dropdown: 'My Notifications' removed; 'Chef Battle' renamed "
            "'Chef Battles' and linked to /chef-battle/ instead of /challenges/; "
            "Messages moved to first position for regular users. "
            "(3) /chef-battle/ hero: 'Challenges' button added after 'Rules'; "
            "'Rankings' and 'Enter Arena' buttons removed; 'Payout' button added "
            "after 'Issue a Challenge'. "
            "(4) Hero 'More' burger button and hidden nav list removed entirely. "
            "(5-6) Widget: 'Battle Chest' and 'Changing Room' console-style buttons "
            "added (same styling as Master Console)."
        ),
    },
    {
        "version": "2.5.152",
        "date": "2026-07-08",
        "commit": "7973dfe",
        "title": "Fix empty-state spacing: gap between text and button",
        "section": "UI",
        "summary": (
            "Added margin-block-start: 1.25rem to links and buttons inside "
            ".empty-state so the action button is not jammed against the "
            "explanatory paragraph above it. Visible on /chef-battle/notifications/ "
            "empty state and any other page using .empty-state."
        ),
    },
    {
        "version": "2.5.151",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Remove Moderation panel link from messages inbox side nav",
        "section": "UI",
        "summary": (
            "Dropped the 'Moderation panel' link from the messages inbox "
            "legal-toc side panel added in v2.5.150. The moderator-only side "
            "nav now shows just 'Archived messages' alongside the shared 'Your "
            "inbox' and 'Start a new message' links."
        ),
    },
    {
        "version": "2.5.150",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Messages inbox rebuilt on the legal-hub shell layout",
        "section": "UI",
        "summary": (
            "Rebuilt everything below the /messages/ hero to follow the "
            "/legal/ hub principle, reusing the existing legal-shell classes "
            "from base.css (no new CSS). Added an intro block (eyebrow + H2 + "
            "paragraph), a four-tile summary panel (Conversations / Unread / "
            "Kept together / Reach us, with live counts from the view), and the "
            "two-column legal-document-layout: a sticky legal-toc side panel "
            "(Your inbox / Archived / Moderation panel / Start a new message + "
            "helper text) beside the legal-hub-main column that holds the "
            "existing thread list. The inbox view now passes total_count and "
            "unread_count. Moderator and member copy variants preserved."
        ),
    },
    {
        "version": "2.5.149",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Messages inbox H1 reworded to a single warm two-line title",
        "section": "UI",
        "summary": (
            "Replaced the two per-role inbox H1s with one unified, on-brand "
            "two-line title, 'Your Conversations Around The CulinEire Kitchen "
            "Table' (kitchen-table motif, works for both the moderator and "
            "member views). The moderator/member split now lives only in the "
            "three-line subtitle. Verified live at two rendered lines via Range "
            "client-rect counting."
        ),
    },
    {
        "version": "2.5.148",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Messages inbox hero standardised to the golden standard",
        "section": "UI",
        "summary": (
            "The /messages/ inbox hero was the last messaging page still using a "
            "custom four-button action row (Recipes / Pinch / Articles / "
            "Contact); its sibling archive page already used the shared include. "
            "Swapped it for {% include 'includes/hero_actions.html' %} (the "
            "canonical golden-standard nav row) since the inbox has no page-"
            "specific technical buttons. Also expanded the copy to the golden "
            "proportion: a title-case H1 that wraps to two lines and a "
            "three-line descriptive subtitle (moderator and member variants), "
            "verified live via Range client-rect line counting. No em dashes "
            "per the UI copy rule."
        ),
    },
    {
        "version": "2.5.147",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Arena presence: appear immediately, refresh every 10s",
        "section": "Chef Battles / UI",
        "summary": (
            "Made an enrolled chef show up in the arena promptly. (1) arena() "
            "now updates the viewer's last_seen_at BEFORE building the ring, so "
            "a chef appears in their own arena on first page load instead of "
            "waiting for the first poll. (2) arena_state (the poll) now also "
            "refreshes the polling chef's last_seen_at, so presence no longer "
            "depends solely on the slower 60s ping heartbeat. (3) Dropped the "
            "ring refresh interval from 20s to 10s (arena_puzzle.js POLL_"
            "INTERVAL). Note: a chef only registers as present if their browser "
            "actually hits the arena while authenticated - if the page was "
            "opened before logging in, the heartbeat runs anonymously (401) and "
            "they must reload after login."
        ),
    },
    {
        "version": "2.5.146",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Arena ring cells show only online chefs",
        "section": "Chef Battles / UI",
        "summary": (
            "The arena ring now places only currently-online chefs in its "
            "sector cells; offline chefs disappear from the ring entirely and "
            "reappear automatically once they return to the arena. Done by "
            "filtering the `rings` payload in _build_arena_payload to chefs "
            "with is_online (last_seen_at within the 180s window) - the existing "
            "60s arena heartbeat + 20s state poll already refresh presence, so "
            "no JS change was needed. chefs_by_rank stays complete so the "
            "rank legend/roster counts still reflect every enrolled chef, and "
            "the centre (crown holder / active battle) is unaffected. Applies "
            "to the public arena, the 20s poll and the Master Console ring."
        ),
    },
    {
        "version": "2.5.145",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Master Console link in the sitewide Chef Battles widget",
        "section": "Chef Battles / UI",
        "summary": (
            "Added a gold-accented 'Master Console' link inside the floating "
            "Chef Battles Arena widget (above Enter Arena), shown only to users "
            "who can actually open the Arena Master Console. Gating reuses "
            "chef_battle.access.has_arena_console_access(request) exactly - the "
            "owner (GreenBear) always sees it; other superusers see it only when "
            "ARENA_MASTER_CONSOLE_ENABLED is on AND they have "
            "RecipeAuthor.has_arena_console_access - so the link never leads to "
            "a 404. The flag is injected via the battle_widget_context "
            "processor. Links to chef_battle:master_console (/chef-battle/master/)."
        ),
    },
    {
        "version": "2.5.144",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Fix stuck drag on the sitewide Chef Battles widget",
        "section": "Chef Battles / UI",
        "summary": (
            "The floating Chef Battles Arena widget could get stuck mid-drag: "
            "the grabbing cursor stayed clenched and the card followed the "
            "pointer with no mouse button held and no new click. Root cause in "
            "battle_widget.js: setPointerCapture was called late (only after the "
            "12px drag threshold), so a pointerup that landed off the handle "
            "(once the card slid out from under the cursor) was missed - endDrag "
            "never ran, leaving pointerId set (constant for a mouse) and "
            "data-dragging=true, so later hover moves re-dragged the widget. "
            "Fixes: capture the pointer at pointerdown so every move/up/cancel "
            "reaches the handle; add a lostpointercapture end path; bail out of "
            "pointermove when e.buttons === 0; fully reset state "
            "(releasePointerCapture + pointerId=null + data-dragging=false) on "
            "every end; ignore non-primary mouse buttons; clear stale gestures "
            "on a new pointerdown. Reproduced then verified fixed live in Chrome."
        ),
    },
    {
        "version": "2.5.143",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Revert v2.5.142 sweep — restore functional page hero buttons",
        "section": "UI",
        "summary": (
            "v2.5.142 wrongly replaced the hero action rows on functional and "
            "content pages with the generic shared nav, wiping page-specific "
            "buttons (Generate AI Recipe, Recipe Studio, create/tool flows, "
            "and the contextual legal/messaging navigation). Restored all 26 "
            "of those templates to their previous state so their own buttons "
            "come back. The shared includes/hero_actions.html stays only on "
            "the genuinely empty-hero pages (auth status/reset, messaging "
            "archive/detail, reports, moderation panel, pinch detail, profile "
            "edit) from v2.5.141. GreenBear's author_detail.html was never "
            "touched."
        ),
    },
    {
        "version": "2.5.142",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Roll the shared hero action row across all non-battle pages",
        "section": "UI",
        "summary": (
            "Switched every remaining non-Chef-Battle page that still had a "
            "bespoke hero action row to the shared includes/hero_actions.html "
            "(26 templates: all legal pages, about, privacy, collection, "
            "messaging inbox/contact, monitoring, newsfeed add, authoring "
            "forms, pinch form, recipe detail, screenshot/generate flows, "
            "sponsors annual contract, offline). Pages already on the "
            "homepage burger + actions-list pattern were left untouched, and "
            "recipes/author_detail.html was deliberately excluded (GreenBear "
            "page, plus author management CTAs) pending owner approval."
        ),
    },
    {
        "version": "2.5.141",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Hero action rows use the homepage's exact class set (golden standard)",
        "section": "UI",
        "summary": (
            "Golden standard = every non-Chef-Battle hero uses the same classes "
            "as the homepage hero, including hero__actions > hero__burger + "
            "hero__actions-list with the standard site nav. Earlier edits had "
            "used a bare hero__actions with ad-hoc buttons. Extracted the "
            "canonical block into includes/hero_actions.html and switched the "
            "14 edited pages (profile edit, 7 auth status/reset, messaging "
            "archive + detail, legal reports list + detail, pinch detail, "
            "moderation panel) to include it, so they carry the identical "
            "burger + actions-list + Pinch/Explore/Read/Sponsors set as home."
        ),
    },
    {
        "version": "2.5.140",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Last two non-Chef-Battle heroes standardised",
        "section": "UI",
        "summary": (
            "Final sweep: the moderation panel and the pinch detail page were "
            "the only remaining non-Chef-Battle heroes with a pill but no "
            "actions row. Added a hero__actions button row to both (moderator "
            "nav on the panel; Pinch Feed / Explore Recipes / Read Articles / "
            "Sponsors on pinch detail, matching the recipe detail pattern). "
            "Every non-Chef-Battle hero page now carries the pill + actions "
            "golden pattern."
        ),
    },
    {
        "version": "2.5.139",
        "date": "2026-07-07",
        "commit": "pending",
        "title": "Non-Chef-Battle pages brought to the golden hero standard",
        "section": "UI",
        "summary": (
            "Audited every non-Chef-Battle page and standardised the heroes "
            "that lacked the pill/actions pattern. Added the pill to login "
            "and signup; added pill + a compact actions row to the seven auth "
            "status/password-reset pages (signup_success, activation_pending, "
            "activation_invalid, password_reset form/confirm/done/complete); "
            "added pill + actions to messaging archive and message_detail "
            "(matching inbox); and added an actions row to the moderator "
            "reports_list and report_detail pages. The listed legal pages and "
            "profile/edit were already handled earlier."
        ),
    },
    {
        "version": "2.5.138",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Move Delete Profile from the author dashboard to the profile edit page",
        "section": "Chef Battles / UI",
        "summary": (
            "The 'Profile Settings / Delete Profile' block was removed from the "
            "author dashboard (author_detail.html) and rebuilt at the bottom of "
            "the profile edit page (/recipes/profile/edit/), below the Your Data "
            "& Privacy block, as a standard .auth-admin-section with a title, an "
            "explanatory note and a red Delete Profile button (confirm dialog, "
            "recipes:author_delete). Shown only in self-edit mode for non-owner "
            "authors (new can_delete_own_profile context flag mirrors the old "
            "not-is_god_author guard, so the owner never sees it). The "
            "moderator's separate 'Delete Author Profile' action is untouched."
        ),
    },
    {
        "version": "2.5.137",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Author profile edit hero brought to the Author Studio standard",
        "section": "UI",
        "summary": (
            "The Edit Profile page (profile/edit) was the only Author Studio "
            "form whose hero lacked the standard pattern used by the recipe, "
            "article and pinch forms. Added the 'Author Studio' pill and the "
            "hero__actions button row (Back to dashboard, Explore Recipes, "
            "Read Articles, Sponsors), and upgraded the hero background to a "
            "<picture> with the webp source. All other listed legal pages "
            "already match the golden standard and were left untouched."
        ),
    },
    {
        "version": "2.5.136",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Halve the collapsed Content Dashboard box height",
        "section": "Chef Battles / UI",
        "summary": (
            "With the group headers hidden and all sections collapsed by "
            "default, the Content Dashboard box was ~138px tall but showed only "
            "its title and filter row - the rest was empty space from the box "
            "padding, the filter row's bottom margin, and the collapsed "
            "sections' own top margins (which still applied at zero height). "
            "Trimmed box padding-block 1rem->0.7rem, dropped the filter row's "
            "1.25rem bottom margin, and zeroed the margin of collapsed "
            "card-controlled sections (they regain it when opened). Box is now "
            "~72px collapsed, about half. Verified live in Chrome as GreenBear."
        ),
    },
    {
        "version": "2.5.135",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Updated author hero background image",
        "section": "UI",
        "summary": (
            "Owner supplied a new hero-profile.png (coastal sunset with the "
            "Irish cookery books and tablet). Regenerated hero-profile.webp "
            "from the new PNG so the <picture> webp source matches (the hero "
            "serves the webp first to modern browsers, so a stale webp would "
            "silently keep showing the old image)."
        ),
    },
    {
        "version": "2.5.134",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Drop redundant dashboard group headers (cards are the toggle now)",
        "section": "Chef Battles / UI",
        "summary": (
            "The Content Dashboard group headers (RECIPES / ARTICLES / PINCH / "
            "My Collection) duplicated the count cards that now toggle those "
            "sections, so they were visual noise. The wiring script now tags "
            "each card-controlled section with .is-card-controlled and CSS "
            "hides that section's own <summary> header - leaving just the "
            "content the card reveals. Gated on the JS-added class so the no-JS "
            "fallback keeps the summaries usable. Nested My Collection "
            "sub-sections (Saved Recipes/Articles/Pinch) are not card-controlled "
            "and keep their own clickable headers. Verified live in Chrome as "
            "GreenBear."
        ),
    },
    {
        "version": "2.5.133",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "My Collection card expands inline with nested saved sub-sections",
        "section": "Chef Battles / UI",
        "summary": (
            "The My Collection count card now toggles an inline dash-collection "
            "section like the other three cards, instead of only linking to "
            "/collection/. The section expands into three independently "
            "collapsible nested <details> sub-sections - Saved Recipes, Saved "
            "Articles, Saved Pinch - each listing the saved items with a View "
            "link, so the owner can browse saved content without leaving the "
            "page. The author view now builds dashboard_saved_recipes / "
            "_articles / _pinch (mirroring the /collection/ view querysets; "
            "collection_count is derived from their lengths) and only on the "
            "owner's own private dashboard. The card keeps its /collection/ "
            "href as a no-JS fallback. Verified live in Chrome as GreenBear."
        ),
    },
    {
        "version": "2.5.132",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Hotfix: stray template comment rendered as text on author page",
        "section": "Chef Battles / UI",
        "summary": (
            "The v2.5.131 explainer comment above the card-toggle script used a "
            "multi-line {# ... #} block. Django's {# #} comment syntax is "
            "single-line only, so the multi-line version was NOT stripped and "
            "rendered as visible text below the Content Dashboard - and the "
            "'<details>' substring inside it even became a stray collapsible "
            "'Details' element. Replaced it with {% comment %}...{% endcomment %} "
            "(multi-line safe). Verified live in Chrome as GreenBear."
        ),
    },
    {
        "version": "2.5.131",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Author dashboard: count cards toggle their content section",
        "section": "Chef Battles / UI",
        "summary": (
            "The count cards (145 Recipes, 5 Articles, 30 Pinch) now act as the "
            "toggle for their matching Content Dashboard section, mirroring the "
            "group-header chevron added in v2.5.130. Clicking a card expands or "
            "collapses its <details> section in place; the card's corner chevron "
            "points right when collapsed and rotates down when open. Wired as "
            "progressive enhancement (a small nonce'd inline script maps each "
            "card's data-dash-toggle to the section id and mirrors the open "
            "state) - if JS is off or the section is absent, the card stays a "
            "normal navigation link. The label (Recipes/Articles/Pinch) is now "
            "centred in the card. My Collection has no dashboard section so it "
            "stays a plain link. All sections collapsed by default to keep the "
            "page tidy. Verified live in Chrome logged in as GreenBear."
        ),
    },
    {
        "version": "2.5.130",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Author dashboard: centre Battle History, spacing, collapsible content groups",
        "section": "Chef Battles / UI",
        "summary": (
            "Three author-page tweaks. (1) Centred the 'Battle History' "
            "sub-heading to match the centred 'Chef Battles Arena' header. "
            "(2) Added 1.5rem breathing room between the 'No battles yet' "
            "empty-state and the actions row (My Moves / Enter Arena / "
            "Rankings), which were touching. (3) Made the Content Dashboard "
            "content groups (Recipes / Articles / Pinch) collapsible using "
            "native <details>/<summary> - no JS, so no CSP-nonce concern. All "
            "collapsed by default; the chevron points right when closed and "
            "rotates down when open; each group toggles independently. The "
            "count cards (145 Recipes etc.) stay as navigation links and My "
            "Collection stays a plain link, per owner decision. Verified live "
            "in Chrome logged in as GreenBear."
        ),
    },
    {
        "version": "2.5.129",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Fix cramped spacing above Chef Battles Arena section on author page",
        "section": "Chef Battles / UI",
        "summary": (
            "On the logged-in author page (enrolled chef, e.g. GreenBear), the "
            "'Chef Battles Arena' section header was jammed directly against the "
            "bottom of the hero with zero gap. Cause: chef_battle.css set "
            ".chef-arena-section { padding-block-start: 0 } - a leftover from when "
            "the Arena block lived at the page bottom. Since v2.5.127 the block "
            "sits directly under the hero, so it needs the standard 2rem section "
            "top padding. Changed the value from 0 to 2rem; verified live in "
            "Chrome logged in as GreenBear (hero->header gap now 32px, matching "
            "the site's section rhythm; the gap below the section was already "
            "correct via the following profile section's own top padding)."
        ),
    },
    {
        "version": "2.5.128",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Restore centered GreenBear/author hero (drop stale hero--has-battle)",
        "section": "Chef Battles / UI",
        "summary": (
            "The author hero carried the hero--has-battle class whenever "
            "chef_battle_enabled was true (staff / superuser / bearseeker, i.e. "
            "GreenBear viewing his own page while logged in). That class applies "
            "the LOCKED two-column, left-anchored battle layout "
            "(text-align:left; align-items:flex-start), which jammed the pill, "
            "H1 and action buttons to the left edge while the avatar stayed "
            "centered - a visibly broken hero. Anonymous visitors never got the "
            "class, so the public page still looked correct. Since the Arena "
            "panel was moved out of the hero in v2.5.127, hero--has-battle no "
            "longer serves any purpose on this hero and only broke centering. "
            "Removed the class from author_detail.html so the hero uses its "
            "designed centered .hero--author-profile layout in every view, "
            "matching the golden GreenBear standard. No LOCKED hero CSS was "
            "touched; template-only change verified live in Chrome (centered "
            "without the class, broken with it)."
        ),
    },
    {
        "version": "2.5.127",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Chef Battles Arena block moved directly under the hero",
        "section": "Chef Battles / UI",
        "summary": (
            "The merged Chef Battles Arena section (stat cards, crown banner, "
            "gifts, battle history, actions) was rendered at the very bottom "
            "of the author page. Moved the _author_battle_section.html include "
            "to sit directly under the hero, above the author profile content, "
            "on every author page (shown when the flag is on and the author is "
            "an enrolled chef)."
        ),
    },
    {
        "version": "2.5.126",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "GreenBear hero H1 shows his name in every view (golden standard)",
        "section": "Chef Battles / UI",
        "summary": (
            "On GreenBear's own profile the hero H1 showed 'Author Dashboard' "
            "(the private-dashboard label) instead of the golden 'GreenBear' "
            "name when viewed in a manage/dashboard context. Reordered the H1 "
            "so the is_god_author branch takes priority: GreenBear's page now "
            "always renders his name in the gold treatment, matching the "
            "golden-standard profile. Isolated to is_god_author only - every "
            "other author keeps the unchanged 'Author Dashboard' / 'Author's "
            "Profile' logic."
        ),
    },
    {
        "version": "2.5.125",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Revert author-hero name experiment; GreenBear page untouched",
        "section": "Chef Battles / UI",
        "summary": (
            "Reverted the v2.5.122/124 author-hero name changes: GreenBear's "
            "personal profile page and god_mode.css must never be modified, "
            "and other author pages should follow GreenBear's page as a "
            "reference standard, not become clones of it. Restored "
            "author_detail.html, base.css, recipes/views.py and god_mode.css "
            "to their pre-change state. The floating widget's mouse drag "
            "(v2.5.123), the Arena Menu centring and the merged-profile "
            "section-title alignment are kept."
        ),
    },
    {
        "version": "2.5.123",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Floating battle widget draggable with the mouse too",
        "section": "Chef Battles / UI",
        "summary": (
            "The sitewide floating Chef Battles widget could be dragged up and "
            "down only with a finger on touch devices; on desktop the drag was "
            "gated off. Removed the coarse-pointer / narrow-viewport gate so "
            "the pointer-event drag now works identically with the mouse: "
            "press-and-hold the header row and slide the card up or down, "
            "position remembered per device. A short click still toggles the "
            "card open/closed (drag threshold unchanged). The grab/grabbing "
            "cursor and touch-action:none now apply on every device."
        ),
    },
    {
        "version": "2.5.122",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Floating widget Arena Menu centred; merged section titles aligned",
        "section": "Chef Battles / UI",
        "summary": (
            "Centred the floating Chef Battles widget's Arena Menu title and "
            "link list, and left-aligned the merged-profile section titles "
            "(Gifts, Battle History) for even spacing against the full-width "
            "stat cards. (The author-hero name change originally shipped here "
            "was reverted in v2.5.125.)"
        ),
    },
    {
        "version": "2.5.121",
        "date": "2026-07-06",
        "commit": "pending",
        "title": "Chef profile merged into author page; hero battle panel removed",
        "section": "Chef Battles / UI",
        "summary": (
            "Full profile merge: the standalone chef battle profile is gone - "
            "chef_battle:chef_battle_profile now redirects to the author "
            "detail page anchored at #chef-arena. The chef's arena stats, "
            "crown banner, gifts and battle history render on the author page "
            "via the new chef_battle-owned partial _author_battle_section.html "
            "(shown only when the flag is on and the author is enrolled). The "
            "big _hero_battle_panel.html include was removed from all 37 hero "
            "templates and the partial deleted; its functions now live in the "
            "floating corner widget (Arena Menu section). Two pre-existing "
            "bugs fixed: get_author_for_user crashed on AnonymousUser, and "
            "token_shop used a namespaced 'accounts:login' that does not "
            "reverse. Added 10 ProfileMergeTests. Full suite green: 1177 OK."
        ),
    },
    {
        "version": "2.5.120",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Chef profile page rebuilt on the canonical corporate hero",
        "section": "Chef Battles / UI",
        "summary": (
            "The chef profile still used the legacy battle-room-hero. Rebuilt "
            "it on the site's canonical hero - the same hero hero--home "
            "hero--author-profile structure used by the recipe author page "
            "and every legal page (e.g. company-information): hero__background "
            "+ hero__overlay + container hero__inner > hero-copy with pill, "
            "hero-author-avatar-wrap, hero-title, hero-subtitle and a "
            "hero__actions button row, plus the shared _hero_battle_panel "
            "include and hero--has-battle when the flag is on. All primary "
            "actions moved into hero__actions (uniform, even, aligned); the "
            "one-off btn-ghost Report button was dropped in favour of the "
            "standard text-link. Verified live: pill sits at the locked 49px "
            "golden anchor, hero buttons all 36px on one line, mobile hero "
            "centred and battle panel correctly hidden, no body overflow, no "
            "inline styles and no legacy classes remain."
        ),
        "checklist": [
            "chef_profile.html: canonical hero hero--home hero--author-profile",
            "actions in hero__actions; Report -> text-link (no btn-ghost)",
            "reuse hero-author-avatar-wrap + _hero_battle_panel include",
            "removed dead .chef-profile-identity CSS",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.119",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Chef profile page brought to the classic template look",
        "section": "Chef Battles / UI",
        "summary": (
            "The chef profile page was a wall of ad-hoc inline styles with a "
            "left-aligned, uneven action row (the Report ghost button had a "
            "different padding and corner radius than the pill buttons next "
            "to it) and an Enter Arena link floating faintly over the hero "
            "photo. Rebuilt to the site's classic pattern used by every "
            "other Chef Battles page: battle-room-hero with a centred "
            "identity block and Enter Arena inside a proper battle-actions "
            "row; page-section + container battle-page body; all layout "
            "moved from inline styles to named component classes "
            "(chef-profile-stats, chef-profile-gifts, chef-profile-history, "
            "etc.). The three main actions now sit in a centred battle-"
            "actions row, all identical pills; Report drops to its own "
            "centred line so it never breaks the even row. Fixed the mobile "
            "history overflow (the reused battle-table row carries a 42rem "
            "min-width meant for a horizontal-scroll wrapper this list does "
            "not use). Zero inline styles remain in the page body. Verified "
            "live at desktop and 375px."
        ),
        "checklist": [
            "chef_profile.html: classic hero + page-section, no inline styles",
            "chef_battle.css: chef-profile-* component classes",
            "action row centred, buttons even; Report on its own line",
            "mobile history overflow fixed (min-width reset)",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.118",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "One-click full battle emulation",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "New Run Full Emulation button in console panel 1: one click "
            "creates the bot battle and walks it through every stage to the "
            "crown automatically, pausing five seconds per stage so the "
            "owner can watch the panels, the ring and the battle room "
            "update live. A progress line narrates each stage (combat, "
            "biathlon, cooking, voting, winner). If an emulation battle is "
            "already mid-flight the button simply continues it. Start Only "
            "and Step Manually remain for stage-by-stage inspection. "
            "Live-verified: full autonomous run finished with a crowned "
            "winner and no console errors."
        ),
        "checklist": [
            "console: Run Full Emulation button + live progress line",
            "arena_master_console.js: auto-runner over the existing endpoints",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.117",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Battle emulation: full lifecycle test battles from the console",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "New owner-only emulation mechanics (chef_battle/emulation.py): "
            "Start Emulation creates a battle between two dedicated bot "
            "chefs (EMU Chef Alpha/Beta, isolated accounts with infinite "
            "energy), and each Emulation Step click advances it exactly one "
            "lifecycle stage THROUGH THE REAL DOMAIN SERVICES - readiness, "
            "menu entries with bot recipes, combat rounds until the win "
            "condition, biathlon locks and shots, cooking-photo submission "
            "and owner approval, voting with synthetic voters, and the real "
            "result calculation. Seven clicks = a complete battle visible "
            "live in the console, the arena ring and the public battle "
            "room. Only one emulation can run at a time; the step action "
            "refuses non-emulation battles; everything is audited. Fixed "
            "in passing: submit_combat_action ignored infinite_moves (hero "
            "rank chefs with zero balance could not declare actions even "
            "though the energy service allows them). 4 new tests incl. a "
            "full-lifecycle assertion; chef_battle suite 258 green."
        ),
        "checklist": [
            "chef_battle/emulation.py: start_emulation + emulation_step",
            "master_action: start_emulation / emulation_step verbs (owner-only)",
            "console panel 1: Emulation section with two buttons",
            "services: infinite_moves honored in submit_combat_action",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.116",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Chef Battles corner widget: site design language + finger drag",
        "section": "Chef Battles / UI",
        "summary": (
            "The floating corner widget was visually orphaned: an ad-hoc "
            "flat panel whose Enter Arena used btn-primary's dark ink on a "
            "dark background and was unreadable. Per the site principle "
            "(reuse existing design, never invent), the card now speaks the "
            "same language as the mobile nav drawer / hero widget: dark "
            "gradient + 16px blur, cream border, 14px radius, and the "
            "Enter Arena button gets the drawer's light-on-dark button "
            "treatment. New battle_widget.js: on touch devices (and narrow "
            "viewports) the header row is a vertical drag handle - slide "
            "the widget up/down with a finger, position clamped to the "
            "viewport and remembered per device; a short tap still toggles "
            "the card, a finished drag never toggles it. Desktop mouse "
            "behaviour unchanged. Verified live at 375px: readable button, "
            "drawer-style card, synthetic drag moved 642 -> 442px and "
            "persisted."
        ),
        "checklist": [
            "chef_battle.css: widget card on drawer tokens; light Enter Arena; grab cursor",
            "static/js/battle_widget.js: pointer drag + localStorage position",
            "_widget.html: script include",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.115",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Drawer: Sign Out back at the bottom",
        "section": "UI / Mobile",
        "summary": (
            "Per owner correction: only the profile block belongs at the top "
            "of the drawer; Sign Out returns to the bottom, below the nav "
            "links, with its own separator. Verified order live at 375px: "
            "profile -> nav -> Sign Out, single centred button."
        ),
        "checklist": [
            "base.html: drawer logout form moved out of the auth block",
            "header.css: bottom separator on the drawer logout",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.114",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Mobile drawer layout per owner annotations; hero battle panel hidden on mobile",
        "section": "UI / Mobile",
        "summary": (
            "Three changes from the owner's annotated mobile screenshots. "
            "(1) The hero Chef Battles Menu panel is hidden on mobile "
            "(<=640px) - the floating corner widget covers battles/arena "
            "entry there and was overlapping the panel; desktop and tablet "
            "keep it. (2) The drawer profile block moved to the top of the "
            "drawer (above the nav links), separator flipped accordingly. "
            "(3) The drawer Sign Out label is centred. Verified live at "
            "375px (profile above nav, one centred Sign Out, hero panel "
            "gone) and 1920px (hero panel visible, locked hero anchors "
            "49/119px intact)."
        ),
        "checklist": [
            "chef_battle.css: .hero-battle-panel hidden at <=640px",
            "header.css: drawer auth block order -1 + flipped separator; Sign Out centred",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.113",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Drawer: exactly one Sign Out button",
        "section": "UI / Mobile",
        "summary": (
            "Follow-up to v2.5.112: the author-panel dropdown's own Sign Out "
            "was rendering as a detached, misaligned duplicate below the "
            "drawer (its popup is absolutely positioned on mobile), so two "
            "buttons appeared. The dropdown copy is now hidden while the "
            "drawer is open; the drawer keeps its single centred Sign Out "
            "(13px/13px gaps, verified live in both collapsed and expanded "
            "profile states). Desktop dropdown unchanged."
        ),
        "checklist": [
            "header.css: .ce-nav--open .ce-author-panel .ce-nav__logout hidden",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.112",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Mobile fixes: drawer author block, Sign Out, GreenBear bubble clamped",
        "section": "UI / Mobile",
        "summary": (
            "Three mobile issues from the owner's live iPhone review. (1) The "
            "author block in the nav drawer used the desktop dark ink on the "
            "dark drawer card - name and greeting were near-invisible; the "
            "drawer now overrides them with light tones. (2) Sign Out was "
            "buried inside the collapsed author dropdown; the drawer now "
            "shows a dedicated Sign Out button directly under the profile "
            "block (drawer-only, desktop unchanged). (3) GreenBear speech "
            "bubbles overflowed the viewport edge: min-width:max-content was "
            "overriding the 180px cap so long phrases never wrapped, and the "
            "bubble is centred on a bear that roams up to 88 percent of the "
            "hero width. Now the bubble wraps at min(180px, 100vw-16px) and "
            "hero_chef.js measures each phrase and shifts the bubble back "
            "inside the horizon while the tail stays anchored on the bear. "
            "Golden bear positions and animations untouched."
        ),
        "checklist": [
            "header.css: drawer author colors + .ce-nav__logout--drawer",
            "base.html: drawer Sign Out form",
            "hero_chef.css: width:max-content + viewport-aware max-width + --speech-shift",
            "hero_chef.js: per-phrase viewport clamp",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.111",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Hero battle panel deduplicated against the corner widget",
        "section": "Chef Battles",
        "summary": (
            "The hero 'Chef Battles Menu' panel and the sitewide corner "
            "widget were showing overlapping live data. Per owner decision "
            "the overlaps were removed from the hero side: the Crown Holder "
            "card (the corner widget marks the crown holder in Top Chefs) "
            "and the Live Now battle display (the corner widget lists "
            "active battles) are gone. The hero panel is now a pure menu - "
            "Season, Arena (My Challenges), Treasury, Gift Shop - while all "
            "live battle data lives only in the corner widget. Locked hero "
            "anchors verified untouched (kicker 49px, H1 119px)."
        ),
        "checklist": [
            "templates/_hero_battle_panel.html: Crown Holder + Live Now removed",
            "hero golden anchors re-verified live (49/119px)",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.110",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Master Console button on the challenges page",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "The challenges page action row now includes a Master Console "
            "button, rendered only for accounts that pass the console access "
            "gate (the owner and flagged operators). Regular chefs see no "
            "trace of it (test-enforced)."
        ),
        "checklist": [
            "challenge_list: can_see_console via has_arena_console_access",
            "OwnerBriefingTests extended (button visible/hidden per role)",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.109",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Owner briefing on the challenges page: AMC report, manual, test-battle guide",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "The challenges page now shows an owner-only briefing block "
            "(rendered exclusively for the greenbear account, test-enforced) "
            "with four collapsible sections: (1) the completion report of "
            "the 10-phase Arena Master Console plan - every phase at 100%, "
            "versions v2.5.96-v2.5.108, with evidence document references; "
            "(2) honest bug and deviation analysis - the seven real defects "
            "found and fixed along the way (latent arena crash, Emergency "
            "Stop timer freeze, report counter, photo lifecycle, vote-series "
            "timezone, CSP nonces, stale tests) plus every deliberate "
            "deviation from the reference (Award Crown disabled by the "
            "audience-decides principle, read-only economy, no fabricated "
            "risk scores, honest provider-termination flag); (3) a "
            "step-by-step console manual covering every panel and control; "
            "(4) a full walkthrough for running a test battle from challenge "
            "to crown, including the Emergency Stop drill."
        ),
        "checklist": [
            "templates/chef_battle/_amc_owner_briefing.html (owner-only include)",
            "challenge_list view passes is_owner",
            "OwnerBriefingTests (2): owner sees, regular chef does not",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.108",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Real viewer presence for the Arena Master Console (DG-04 resolved)",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "The last open console gap is closed: active-viewer counts are "
            "now real. New BattleViewerPresence model (migration 0059) "
            "records pseudonymised device heartbeats (sha256 of IP+UA, the "
            "same technique as vote dedup - no raw IP/UA, no account "
            "linkage) on the existing public surfaces: the battle room page "
            "and its logged-in 20s poll count per battle; the arena page "
            "and its poll count the lobby separately. A viewer is active if "
            "seen within 180 seconds (the same window as the chef "
            "heartbeat); idle rows are purged after an hour. The console "
            "Audience card now shows real 'Battle viewers' and 'Arena "
            "lobby' counts instead of Unavailable. Heartbeats are fail-safe "
            "(they can never break a public poll - test-enforced) and the "
            "public arena JSON contract is unchanged. 7 new tests; "
            "chef_battle suite 252 green."
        ),
        "checklist": [
            "chef_battle/0059: BattleViewerPresence",
            "services: record_viewer_presence (fail-safe heartbeat + 1h purge)",
            "hooks: battle_detail, battle_state_poll, arena page, arena_state",
            "console Audience card: real per-battle + lobby counts",
            "docs: DG-04 resolution in P00_DECISIONS + P02_DATA_DICTIONARY",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.107",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Arena Master Console P09: final hardening and release readiness",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Final phase of the 10-phase console plan. Hardening: a "
            "monotonic poll sequence so a slow response can never overwrite "
            "newer state; the ledger hash-chain verification is cached for "
            "60 seconds (it was scanning the full table on every 20-second "
            "poll); visible keyboard-focus outlines on all console controls "
            "and a polite live region on the system-status line. "
            "Verification: 96 focused console tests across 8 suites plus "
            "the complete project test run; JS syntax, Django checks and "
            "migration drift clean; viewports 1920/1440/1280/mobile with no "
            "overflow or clipping; public arena regression clean; "
            "performance measured at 37 queries / 4.0 KB / 24 ms per poll "
            "with one battle. Release evidence: acceptance report, "
            "performance report, security review, and rollout/rollback/"
            "incident procedures in docs/chef_battle/arena_master_console/. "
            "CHEF_BATTLE_ENABLED stays OFF; the console remains visible "
            "only to the owner on production."
        ),
        "checklist": [
            "JS: stale-poll guard; selectors: verify_chain 60s cache",
            "CSS: :focus-visible outlines; template: aria-live status",
            "docs: P09_ACCEPTANCE_REPORT.md, P09_PERFORMANCE_REPORT.md, P09_SECURITY_REVIEW.md, P09_ROLLOUT_ROLLBACK.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.106",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Arena Master Console P08: rewards governance, payouts and battle reports",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Panel 7 is live per DG-06: CBR/LSR status matrix across the "
            "full reward lifecycle, recent reward rows, and the payout "
            "request queue. Owner-only approve/reject buttons delegate to "
            "the pre-existing owning services (approve_payout_request / "
            "reject_payout_request) - the console never touches payout "
            "status, reward records, ledger rows or Stripe directly; the "
            "approve dialog states the real Stripe Connect consequence. New "
            "BattleReport model (migration 0058) implements the DG-06 "
            "workflow: any console operator submits a structured post-battle "
            "report (summary, flags, recommendation), the owner is notified "
            "and decides. The panel shows a live LedgerEvent hash-chain "
            "verification result; tests assert the chain stays intact after "
            "an owner payout approval. Rewards are presented as "
            "discretionary platform rewards - never funds or earnings "
            "(test-asserted wording). 9 new tests; full suite green."
        ),
        "checklist": [
            "chef_battle/0058: BattleReport",
            "services: operator_submit_battle_report + operator_review_payout",
            "selectors: get_master_governance_detail() -> governance section",
            "console panel 7: matrix, payouts, reports, ledger chain status",
            "docs: P08_AUTHORITY_MATRIX.yaml, P08_LEDGER_AUDIT.md, P08_HANDOFF.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.105",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Arena Master Console P07: economy, gifts and artifacts panel (read-only)",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Panel 6 upgraded to a full read-only economy view: token flows "
            "grouped by transaction type over an explicit 24h window (signed "
            "sums exactly as stored in the immutable ledger), appreciation "
            "gift catalogue from the source-of-truth constants with live "
            "delivery counts, per-chef gift totals, artifact inventory by "
            "lifecycle status plus catalogue rarity distribution, and token "
            "orders by status with disputed/refunded ids flagged for "
            "attention. No operator economy write was approved, so none "
            "exists: a test posts five invented mutation verbs to the action "
            "endpoint and asserts each is rejected. Reconciliation tests "
            "prove displayed totals equal ledger sums and wallet balances "
            "equal transaction sums. Closed-loop wording (virtual items, "
            "never cash or earnings) is asserted on the rendered page. "
            "8 new tests; full suite green."
        ),
        "checklist": [
            "selectors: get_master_economy_detail() -> economy.detail",
            "console panel 6: flows/gifts/artifacts/orders lists + wording hint",
            "tests: reconciliation, wallet invariant, no-write-path, wording",
            "docs: P07_LEDGER_DEFINITIONS.yaml, P07_RECONCILIATION_REPORT.md, P07_HANDOFF.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.104",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Arena Master Console P06: voting integrity and audience analytics",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Panel 5 upgraded from raw counts to a full integrity view: vote "
            "percentages with honest NULL at zero votes, a 24-hour hourly "
            "vote series bucketed in UTC (found and fixed: default bucketing "
            "silently used the site timezone while labelled UTC), one-vote "
            "enforcement evidence (the two DB unique constraints plus "
            "aggregate counts of rejected attempts from private "
            "VoteIntegrityEvent records, grouped by gate code), a "
            "privacy-safe suspicious-vote queue (vote id, target, timestamp "
            "- no voter identity, no request hashes, test-asserted), tie "
            "state with completion readiness including the blocked-by-tie "
            "case, and community pulse (visible chat volume, support tokens "
            "aggregated per chef). Read-only phase; no automated risk "
            "scoring exists and none is claimed. 9 new tests; full suite "
            "green."
        ),
        "checklist": [
            "selectors: _voting_analytics_for_battle() replaces P02 voting loop",
            "console panel 5: percentages, badges, evidence counts, pulse",
            "TruncHour tzinfo=UTC fix (was site-TZ while labelled UTC)",
            "docs: P06_METRIC_DEFINITIONS.yaml, P06_PRIVACY_REPORT.md (extended), P06_HANDOFF.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.103",
        "date": "2026-07-05",
        "commit": "pending",
        "title": "Arena Master Console: post-audit corrections for P03-P05",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Independent compliance audit of P00-P05 found and fixed real "
            "defects in the completed phases. Emergency Stop now truly "
            "freezes battle time: on resume the submission/voting/end "
            "deadlines are shifted forward by the measured pause duration "
            "inside the locked transaction (with clock-skew protection), and "
            "the resume audit records the shift. Stream report counts now "
            "aggregate the authoritative LiveBroadcastReport rows instead of "
            "the unsynchronised legacy counter. Cooked-photo moderation "
            "follows the real lifecycle: uploads stay in COOKING with "
            "PENDING review, approve requires a photo plus real-photo "
            "confirmation, and PRESENTATION starts only after both entries "
            "are approved. Malformed action IDs return JSON 400 instead of "
            "500; cancelling a paused battle clears all pause fields; "
            "rejected vote-integrity evidence handling fixed. Remaining "
            "audit items are recorded per item as deferred-to-phase or "
            "accepted risk in the phase documents."
        ),
        "checklist": [
            "operator_resume: deadlines shifted by pause duration (clock-skew safe)",
            "console streams: report_count from LiveBroadcastReport aggregate",
            "cooked-photo lifecycle: COOKING+PENDING -> owner approve -> PRESENTATION",
            "master_action: malformed IDs -> JSON 400; cancel clears pause fields",
            "audit trail: P03_AUDIT_REPORT.md / P05_SAFETY_REPORT.md post-audit sections",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.102",
        "date": "2026-07-04",
        "commit": "pending",
        "title": "Arena Master Console P05: moderation, safety and live-stream panel",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Panel 4 is live: cooking moderation queue with per-entry state "
            "(status, photo presence, real-photo confirmation, lateness), "
            "pending DSA content reports, and live-stream sessions with real "
            "broadcast safety data (checklist confirmation, safety delay, "
            "agreement presence, viewer report count). Owner-only actions via "
            "the audited master_action endpoint: moderate_entry (adverse "
            "outcomes require a reason and notify the chef), review_report "
            "(note mandatory), end_stream (terminates the platform record and "
            "honestly reports provider_side_terminated: false - no provider "
            "integration exists and none is simulated). No fake automated "
            "detection is claimed anywhere. Moderation notes verified absent "
            "from public endpoints. 10 new tests; suite 212 green."
        ),
        "checklist": [
            "selectors: get_master_moderation_detail() in moderation.detail",
            "services: operator_moderate_entry/review_report/end_stream",
            "console panel 4: queue/reports/streams + owner row actions",
            "docs: P05_ACTION_MATRIX.yaml, P05_SAFETY_REPORT.md, P05_HANDOFF.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.101",
        "date": "2026-07-04",
        "commit": "pending",
        "title": "Arena Master Console P04: live battle monitor + combat engine panels",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Read-only monitor section added to the console state payload "
            "(same endpoint, same 20 s poll): battle and challenge counts with "
            "documented definitions, an append-only live event log including "
            "operator audit entries, per-round combat detail (outcomes, hit "
            "totals, current-round declared actions), biathlon lock/shot "
            "state, and artifacts-in-use. Polling is proven side-effect free "
            "by test (three polls create zero rounds/actions/events/"
            "transactions). Hidden combat information is served only behind "
            "the console gate; public arena JSON is verified unchanged. "
            "9 new tests; full chef_battle suite green."
        ),
        "checklist": [
            "selectors: get_master_monitor() merged into master_state",
            "console panels 2/3: counts, event log, combat detail, artifacts",
            "docs: P04_VISIBILITY_MATRIX.yaml, P04_COMBAT_REPORT.md, P04_HANDOFF.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.100",
        "date": "2026-07-04",
        "commit": "pending",
        "title": "Arena Master Console P03: owner battle-flow controls + Emergency Stop",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "First operator write surface, reachable only by the owner: force "
            "phase transitions (transitions with an owning domain service call "
            "that service - approve_cooking_phase, calculate_battle_result; "
            "direct assignment only where DG-02 authorizes the owner override), "
            "Emergency Stop per DG-03 (battle -> PAUSED with paused_at/reason/"
            "from_status via migration 0056, live streams TERMINATED, timers "
            "frozen in the console, both chefs notified in-site + email), "
            "Resume, Cancel and public Broadcast. Every action is POST+CSRF, "
            "transactional with row locking, idempotency-guarded via "
            "expected_status (stale clicks get 409), and audited as a "
            "BattleEvent OPERATOR_ACTION with correlation id and before/after "
            "state. Award Crown stays permanently disabled - the crown is "
            "decided only by audience voting. Non-owner console operators see "
            "an explicit read-only panel. Fixed in passing: missing CSP nonce "
            "on console/ring inline scripts. 22 new tests; chef_battle suite "
            "193/193."
        ),
        "checklist": [
            "chef_battle/0056: Battle.paused_at/paused_reason/paused_from_status",
            "services: operator_force_status/emergency_stop/resume/cancel/broadcast",
            "POST /chef-battle/master/action/ (owner-only, CSRF, audited)",
            "console panel 1: owner controls with consequence confirms",
            "docs: P03_TRANSITION_MATRIX.yaml, P03_AUDIT_REPORT.md, P03_HANDOFF.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.99",
        "date": "2026-07-04",
        "commit": "pending",
        "title": "Arena Master Console P02: live read-only data + embedded arena ring",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "The console now shows real data: battle status card, chef cards, "
            "7-step phase rail, and live counts in the moderation, voting, "
            "economy and ranks panels, all sourced from the new read-only "
            "get_master_state() selector via POST /chef-battle/master/state/ "
            "(20 s poll, 12 queries / 1.9 KB with one battle; every field "
            "documented in P02_DATA_DICTIONARY.yaml). The public arena ring "
            "renderer is embedded through a new shared partial "
            "_arena_ring.html; arena() and arena_state() were deduplicated "
            "into _build_arena_payload() with the public JSON contract "
            "verified unchanged. Active-viewer count is honestly reported as "
            "unavailable: the presence source DG-04 assumed does not exist. "
            "Fixed in passing: a latent public-arena 500 (.value on a "
            "DB-loaded battle status) and a multi-line template comment "
            "rendering as text. 17 new tests; full chef_battle suite 171/171."
        ),
        "checklist": [
            "chef_battle/selectors.py: get_master_state() + rail/next-status maps",
            "chef_battle/views.py: _build_arena_payload() dedup + master_state endpoint",
            "templates/chef_battle/_arena_ring.html shared partial (arena.html refactored)",
            "arena_master_console.html + .js + .css: live data, 20s poll, countdown",
            "tests: ArenaMasterStateTests (17), query budget, public-leak checks",
            "docs: P02_DATA_DICTIONARY.yaml, P02_QUERY_REPORT.md, P02_HANDOFF.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.98",
        "date": "2026-07-04",
        "commit": "pending",
        "title": "Arena Master Console: owner always sees the console (flag = operator kill switch)",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Owner decision: the whole site is always visible to the owner — "
            "feature flags never hide anything from GreenBear. The console "
            "access gate now grants the owner (superuser + owner slug) access "
            "unconditionally; ARENA_MASTER_CONSOLE_ENABLED remains a kill "
            "switch for NON-owner operators only (superuser + "
            "has_arena_console_access, 404 otherwise). Tests and P00/P01 "
            "contract docs updated to record the override."
        ),
        "checklist": [
            "chef_battle/access.py: owner bypasses ARENA_MASTER_CONSOLE_ENABLED",
            "tests: flag-off case now expects 200 for owner, 404 for others",
            "P00_CONTRACTS.yaml + P01_HANDOFF.yaml: owner override recorded",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.97",
        "date": "2026-07-04",
        "commit": "pending",
        "title": "Arena Master Console P01: visual shell + DG-01 access gate (dark)",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Console shell shipped at /chef-battle/master/ behind the new "
            "ARENA_MASTER_CONSOLE_ENABLED flag (default False — the URL 404s for "
            "everyone on production until the owner enables it). Access per DG-01: "
            "superuser AND (owner slug OR the new "
            "RecipeAuthor.has_arena_console_access flag, migration recipes/0038); "
            "everyone else receives 404. Shell renders the reference information "
            "architecture — overview row (battle status, chef slots, ring "
            "placeholder, audience), 7-step phase rail, eight-panel operator "
            "deck, system footer — with explicit empty states only ('No active "
            "battle', 'Not connected'); a test asserts no mockup example values "
            "render and all six control buttons stay disabled. New page-scoped "
            "arena_master_console.css; zero shared-style changes; public arena "
            "verified byte-identical in behavior. 12 focused access tests. "
            "Verified at 1920/1440/1280 and mobile with no overflow or overlap."
        ),
        "checklist": [
            "config/settings.py: ARENA_MASTER_CONSOLE_ENABLED flag (default False)",
            "recipes: has_arena_console_access field + migration 0038",
            "chef_battle/access.py: arena_console_guard (Http404)",
            "chef_battle: master_console view + /chef-battle/master/ URL",
            "templates/chef_battle/arena_master_console.html + static/css/arena_master_console.css",
            "chef_battle/tests.py: ArenaMasterConsoleAccessTests (12 tests)",
            "docs: P01_VISUAL_REPORT.md + P01_HANDOFF.yaml",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.96",
        "date": "2026-07-04",
        "commit": "pending",
        "title": "Arena Master Console P00 complete: discovery, baselines, frozen contracts",
        "section": "Chef Battles / Arena Master Console",
        "summary": (
            "Phase P00 of the 10-phase Arena Master Console plan "
            "(docs/chef_battle/arena_master_console/) executed and documented. "
            "All 8 reference-mockup panels mapped against existing code in "
            "P00_REUSE_MATRIX.yaml with verified line references; public arena "
            "contract (arena, arena_state, arena_ping, arena_battle_popup) frozen "
            "and the smallest operator read-model contract proposed in "
            "P00_CONTRACTS.yaml; query/payload baselines measured on an isolated "
            "test DB: arena() 15 queries/47KB anonymous, 21/51KB authenticated, "
            "arena_state() 7 queries/4.5KB. All six decision gates (DG-01..DG-06) "
            "resolved in P00_DECISIONS.yaml. Stale assumption recorded: "
            "battle_lifecycle.md status table is outdated vs the real 13-value "
            "Battle.Status. No production behavior changed; roadmap updated with "
            "the AMC phase block."
        ),
        "checklist": [
            "docs: P00_REUSE_MATRIX.yaml, P00_CONTRACTS.yaml, P00_BASELINE_REPORT.md added",
            "chef_battle/views.py: Phase AMC block added to battlefield roadmap",
            "No migrations, no public URL or behavior changes",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.87",
        "date": "2026-07-03",
        "commit": "14f29c7",
        "title": "Pinch 8b: increase base clearance so MORE/caption visually clear footer handle",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Cross-device audit finding: at desktop Chrome (lvh=dvh, toolbar delta=0) "
            "the 8b safe-zone base values were too small — MORE button sat 22px "
            "inside the footer handle's vertical zone (809–826 vs handle 804–844), "
            "and the caption had only 8px gap above the handle arch. Fixed by "
            "increasing open-btn/sheet__close base from 1.1rem→3rem (48px clears "
            "40px handle + 8px gap) and overlay padding-bottom base from 3rem→3.5rem "
            "(caption now 16px above handle). On real mobile Chrome (56px toolbar "
            "delta) MORE gets 104px clearance. Layout verified in Chrome 390×844 "
            "post-deploy: moreBottomCSS=48px, moreGapAboveHandle=+8px, "
            "captionGapAboveHandle=+16px. CSS hashed to pinch.8db9574bbaee.css."
        ),
        "checklist": [
            "pinch.css: 8b open-btn/close bottom: 1.1rem → 3rem",
            "pinch.css: 8b overlay padding-bottom: 3rem → 3.5rem",
            "pinch.css: 8b actions bottom: 0.9rem → 1rem (minor tidy)",
            "Verified post-deploy: moreGap=+8px, captionGap=+16px at 390×844",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.86",
        "date": "2026-07-03",
        "commit": "18f16ff",
        "title": "Pinch: remove broken Django multi-line comment in More sheet",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Django template comment syntax {# #} does not support multi-line "
            "content — the second line was rendered as literal HTML in the page. "
            "Removed the malformed comment from item_card.html. No functional change."
        ),
        "checklist": [
            "templates/pinch/item_card.html: removed broken multi-line comment",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.85",
        "date": "2026-07-03",
        "commit": "included in 2.5.83–86 range",
        "title": "Pinch: More sheet — remove Full Recipe and Open Page buttons",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Owner request: 'Full Recipe' and 'Open Page' pills removed from the "
            "More sheet. The cover photo has linked directly to the recipe since "
            "v2.5.74, making these redundant. Remaining sheet rows: description "
            "text, 'Read the story' (if linked_article), Edit/Delete (author/ "
            "moderator only)."
        ),
        "checklist": [
            "templates/pinch/item_card.html: Full Recipe row removed",
            "templates/pinch/item_card.html: Open Page row removed",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.84",
        "date": "2026-07-03",
        "commit": "included in 2.5.83–86 range",
        "title": "Pinch 8b: bottom safe zone — lift card furniture above toolbar",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Cards are 100lvh tall but the visual viewport is 100dvh (smaller when "
            "Chrome/Safari toolbar is visible). The delta (up to ~175px on iPhone) "
            "hid the caption and MORE button below the fold. Fix: bottom-anchored "
            "card furniture (overlay, open-btn, close, actions, sheet) lifted by "
            "calc(100lvh - 100dvh + Xrem). The card box stays 100lvh so snap "
            "geometry never changes. Dead CSS for .ab-card .ab-card__sheet "
            ".ab-sheet__open-btn (21 lines) removed."
        ),
        "checklist": [
            "pinch.css: section 8b added — overlay, open-btn, close, actions, sheet lifted by lvh-dvh delta",
            "pinch.css: dead .ab-sheet__open-btn CSS block removed",
            "Verified post-deploy in Chrome 390×844",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.83",
        "date": "2026-07-03",
        "commit": "included in 2.5.83–86 range",
        "title": "Pinch: tricolour shimmer on header handle + swipe gesture fix + speed match",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Three owner-requested fixes: (1) Tricolour shimmer added to header "
            "handle (pinch-tricolour 7s animation, 3s delay, paused when open) to "
            "match the footer handle. (2) Swipe-to-open gesture fixed: pointermove "
            "listeners on both handles changed to passive:false with e.preventDefault() "
            "on confirmed drag >8px — iOS snap scroller was claiming the gesture. "
            "(3) Header drawer speed matched to footer: transition duration 0.38s→0.28s, "
            "max-height targets tightened (ce-header__inner 140px→80px, category-nav "
            "80px→52px); kick() delay updated to 320ms. Also: stale-fetch guard and "
            "transitionend race guard added to comments panel JS."
        ),
        "checklist": [
            "pinch.css: pinch-tricolour animation on .pinch-header-handle",
            "pinch.css: header drawer transition 0.38s→0.28s, max-heights tightened",
            "main.js: pointermove passive:false on both handles",
            "main.js: kick() delay 420ms→320ms",
            "main.js: comments stale-fetch guard (fetchSlug vs activeSlug)",
            "main.js: transitionend race guard (once:true, check is-open)",
            "main.js: mutual exclusion — opening footer closes header and vice versa",
        ],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.82",
        "date": "2026-07-03",
        "commit": "pending",
        "title": "Pinch: collapsible header drawer — full-screen cards by default",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Owner request: mirror the footer drawer at the top. On mobile "
            "Pinch the logo row (.ce-header__inner) and the filter carousel "
            "are now collapsed by default (max-height 0), leaving only the "
            "social/support strip — cards grow from ~680px to ~810px at "
            "390x844 (+130px of air, measured live). An arch handle under "
            "the strip (arch pointing down, same tricolour-family styling "
            "as the footer handle, ~136x60 hit area) opens the drawer by "
            "tap or swipe-down and closes it by tap or swipe-up; scrim "
            "(z-index 45, below filter z-50 and header z-120) click-closes; "
            "Escape closes. body.pinch-header-open is the single source of "
            "truth. Geometry follows automatically: setHeaderH's rect "
            "measurements shrink --sticky-offset to the strip height, and "
            "card height + scroll-padding-top consume the same variable, so "
            "snap tiling stays exact in both states (verified live: closed "
            "snap 810/810, card2 top == strip bottom 34; open snap 701/701, "
            "card2 top == filter bottom 143). New resilience: setHeaderH is "
            "now also hooked to window resize — RO callbacks ride the "
            "render pipeline and freeze in occluded windows (v2.5.70 rAF "
            "lesson), so the drawer dispatches a synthetic resize 420ms "
            "after each toggle as a deterministic backstop, which also "
            "re-runs the filter carousel's update(true)."
        ),
        "checklist": [
            "feed.html: #pinch-header-handle + #pinch-header-scrim added",
            "pinch.css: section 6b — collapse rules, handle at top:var(--sticky-offset), scrim z-45",
            "main.js: header drawer IIFE (tap + pointer swipe, kick() resize dispatch)",
            "main.js: setHeaderH hooked to window resize (occluded-RO backstop)",
            "Verified pre-deploy in Chrome 390px via injection: both states pixel-exact",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.78",
        "date": "2026-07-03",
        "commit": "pending",
        "title": "Pinch: root snap scroller (real Safari address-bar collapse) + filter self-heal",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Proper rework of v2.5.74's two broken fixes, designed via "
            "multi-agent diagnosis. (1) Root scroller: iOS Safari only "
            "collapses its address bar on DOCUMENT scroll, never on an inner "
            "div — and overscroll-behavior:contain on the old inner scroller "
            "blocked chaining entirely, so the 1px body hack was dead on "
            "arrival (deleted along with its scrollTo(0,0) snapback IIFE, "
            "which would have pinned the refactored feed to card 1). Now "
            "html:has(.hero--pinch) carries scroll-snap-type:y mandatory + "
            "scroll-padding-top:var(--sticky-offset); the wrappers are "
            "overflow:visible/height:auto so cards flow in the document; "
            "cards are 100lvh minus sticky offset (static geometry — no "
            "re-snap jumps on toolbar transitions; the first swipe collapses "
            "the bar and each card then exactly fills the screen) with "
            "scroll-snap-stop:always. unlockScroll now restores scrollY "
            "unconditionally (document scroll IS the feed position). "
            "Comments panel locks html overflow too (iOS ignores body-only). "
            "Scrims get touch-action:none; footer/comments get "
            "overscroll-behavior:contain so overlays never scroll the feed. "
            "(2) Filter carousel self-heal: on iOS the whole-item "
            "visibility/centering module could freeze with stale state "
            "(bfcache restores move scrollLeft without firing scroll/resize "
            "events) leaving categories half-clipped under the arrows. Added "
            "a pageshow handler plus a 600ms idle watchdog that re-runs the "
            "idempotent update(true) — any missed state repairs itself "
            "within a second. (3) Bottom sheet: keeps Bolt's v2.5.76/77 "
            "Pointer Events handle drag (unchanged); the crude v2.5.74 "
            "document-wide bottom-80px swipe trigger is gone with the IIFE "
            "merge; handle gains a ~136x60px invisible hit area."
        ),
        "checklist": [
            "pinch.css: html:has(.hero--pinch) snap root; wrappers overflow:visible; cards 100lvh + scroll-snap-stop",
            "pinch.css: 1px body hack deleted; footer overscroll contain; scrim touch-action none; handle hit-area",
            "main.js: snapback IIFE deleted; unlockScroll unconditional restore; html overflow lock in comments panel",
            "main.js: filter module gains pageshow + 600ms idle watchdog (self-heal, idempotent)",
            "Verified pre-deploy in Chrome 390px: doc snap 680px/card exact, sticky pinned, watchdog heals corrupted state",
            "Safari address-bar collapse needs on-device check by owner",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.77",
        "date": "2026-07-03",
        "commit": "pending",
        "title": "Pinch footer — shimmer on arrow colour, lower swipe threshold",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "(Bolt) Follow-up tuning of the v2.5.76 drag: tricolour shimmer "
            "moved to the SVG arrow colour, swipe threshold lowered "
            "(SWIPE_MIN 28px, VELOCITY 0.25px/ms)."
        ),
        "checklist": ["main.js + pinch.css tuning; deployed by Bolt"],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.76",
        "date": "2026-07-03",
        "commit": "pending",
        "title": "Pinch footer — Pointer Events drag + tricolour shimmer",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "(Bolt) Footer drawer handle became a Pointer Events drag target "
            "with pointer capture, finger-follow transform, momentum-aware "
            "snap and ghost-click guard; footer body swipe-down closes when "
            "its inner scroll is at top. Irish tricolour shimmer animation "
            "on the handle."
        ),
        "checklist": ["main.js: pointerdown/move/up/cancel drag; deployed by Bolt"],
        "deployment_status": "deployed",
    },
    {
        "version": "2.5.74",
        "date": "2026-07-03",
        "commit": "pending",
        "title": "Pinch: swipe footer gesture, Safari address-bar collapse, card → recipe link",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Three mobile UX improvements: (1) Footer drawer now responds to "
            "touch swipe — swipe up from the bottom 80px to open, swipe down "
            "when at the top of the sheet to close (in addition to the existing "
            "tap-the-handle behaviour). (2) Safari address-bar auto-hide now "
            "works on the Pinch page: body gets 1px extra height so Safari "
            "treats the document as scrollable and collapses its chrome on "
            "upward swipe; a passive scroll listener immediately snaps scrollY "
            "back to 0 so the layout never shifts. (3) Tapping a Pinch card "
            "image now navigates directly to the linked recipe if one exists, "
            "falling back to the Pinch detail page only when there is no "
            "linked recipe."
        ),
        "checklist": [
            "main.js: touchstart/touchend swipe listeners in footer drawer IIFE",
            "main.js: Safari address-bar snapback IIFE (scroll → scrollTo(0,0))",
            "pinch.css: body:has(.hero--pinch) overflow-y:scroll + min-height:calc(100dvh+1px)",
            "item_card.html: cover link href uses linked_recipe.get_absolute_url when available",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.73",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Arena Stage E3 — Ready button + readiness gate",
        "section": "Chef Battles / Arena (Phase FE-3)",
        "summary": (
            "Stage E3: chefs press 'I'm Ready' in the antechamber (battle_detail, SCHEDULED status). "
            "Added challenger_ready + opponent_ready + proposed_combat_time + combat_time_confirmed "
            "fields to Battle model (migration 0052). When both chefs press Ready the battle "
            "advances from SCHEDULED to MENU_LOCKED (ingredient declaration phase). "
            "Antechamber shows live ready indicators (green chip when ready, grey waiting). "
            "battle_set_ready() view: login_required, require_POST, participant-only, "
            "idempotent (second press returns info message). create_battle_event() logged on advance. "
            "battle_detail context: viewer_is_challenger + can_set_ready added. "
            "CSS: .antechamber-ready, .antechamber-ready__indicators, .antechamber-ready__chip, "
            ".antechamber-ready__chip--on, .antechamber-ready__waiting added to chef_battle.css."
        ),
        "checklist": [
            "models.py: challenger_ready, opponent_ready, proposed_combat_time, combat_time_confirmed added",
            "migrations/0052_battle_ready_fields.py: created",
            "views.py: battle_set_ready() added; battle_detail context: viewer_is_challenger, can_set_ready",
            "urls.py: battles/<int:pk>/ready/ → battle_set_ready",
            "battle_detail.html: antechamber-ready block with chips + form button",
            "chef_battle.css: .antechamber-ready* styles added",
            "base.html: v2.5.73",
            "manage.py check: 0 issues (pending verify on server)",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.72",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Pinch filter centering hotfix — transform race in visibility math",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "v2.5.71's whole-item module subtracted the TARGET translateX from "
            "getBoundingClientRect() values, but during the 0.25s transform "
            "transition rects contain the INTERPOLATED transform — updates "
            "landing mid-animation miscomputed edge items by up to the full "
            "shift (e.g. 'All' wrongly hidden at scroll start). Rewritten in "
            "content coordinates: each item's position is taken relative to the "
            "nav's own rect (both move by the same transform, so it cancels "
            "exactly) and compared against [scrollLeft, scrollLeft + "
            "clientWidth], which are transform-free by definition. No stored "
            "shift state needed for visibility; the transform is only written, "
            "never read back."
        ),
        "checklist": [
            "main.js: whole-item visibility computed as itemRect - navRect vs scrollLeft window",
            "main.js: stored shift variable dropped from visibility math",
            "Verified live: symmetric blanks at start AND end of list, 'All' stays visible",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.71",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Pinch filter — resting centering + tighter dot separators",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Owner request: the filter row looked uneven (whole-item hiding left "
            "all blank space piled on one side) and spacing between categories "
            "was too generous. (1) The whole-item module now centers the group "
            "of fully visible categories between the arrows once scrolling "
            "settles: it computes the leftover blank on each side in "
            "untransformed coordinates and applies translateX((blankRight - "
            "blankLeft) / 2) to .category-nav with a 0.25s ease transition. "
            "justify-content stays flex-start (center breaks scrollability — "
            "see v2.5.70); centering is purely visual via transform, so scroll "
            "math and the arrows' enable/disable logic are unaffected. Debounced "
            "scroll (120ms) substitutes for scrollend on iOS Safari. (2) The "
            "mobile dot separators are CSS-generated (.category-nav__item::after "
            "with 0.6em side margins) — tightened to 0.3em and nav side padding "
            "0.5rem -> 0.4rem. Result at 430px: 6 categories fit fully instead "
            "of 5, content width 783px -> 733px, resting blanks split 19px/19px."
        ),
        "checklist": [
            "main.js: whole-item module gains recenter-at-rest (shift-aware visibility math)",
            "pinch.css: .category-nav__item::after margin-inline 0.3em (mobile Pinch only)",
            "pinch.css: .category-nav transition transform 0.25s; padding-inline 0.4rem",
            "Verified live at start of list: 6 items fully visible, blanks 19/19 symmetric",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.70",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Pinch filter — whole-item visibility + unreachable-left scroll fix",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Owner request: a category must never show half-clipped under the "
            "carousel arrows — it is either fully inside the visible track or "
            "hidden entirely until the arrows scroll it fully into view. New "
            "main.js module toggles visibility per item on scroll/resize/font-load "
            "(rAF-free: occluded Chrome windows freeze rAF and one pending frame "
            "was permanently blocking the generic carousel's scheduleUpdate). "
            "Two root-cause bugs found live: (1) .category-nav kept "
            "justify-content: center — with overflowing content the left half "
            "of the list spilled LEFT of the scroll origin and was physically "
            "unreachable (scrollLeft cannot go negative); ~421px of categories "
            "('All', 'Mini Recipe', 'Snack'…) could never be scrolled to. Now "
            "flex-start in mobile snap mode. (2) The carousel ResizeObserver "
            "watched only the track (flex: 1, width-stable) so late font loads "
            "never re-enabled the arrows — it now also observes the content, "
            "plus scrollend/fonts.ready call updateControls directly."
        ),
        "checklist": [
            "pinch.css: .category-nav justify-content: flex-start (mobile Pinch only)",
            "main.js: whole-item visibility module for .pinch-filter-carousel (scroll/resize/RO/fonts.ready, no rAF)",
            "main.js carousels: scrollend + fonts.ready direct updateControls; RO also observes track.firstElementChild",
            "Verified live: at start 'All…Cocktail' fully visible, 'Quick Tip' hidden entirely; arrows enable/disable correctly",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.69",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Pinch mobile snap — filter row, true full-bleed, handle rides the sheet",
        "section": "Pinch / Mobile TikTok feed",
        "summary": (
            "Live-debugged on production in Chrome device emulation. Three root causes "
            "fixed: (1) base .category-nav-block rule stacks the block as flex COLUMN "
            "with a 20px gap, so the inline filter arrows landed on separate rows — "
            "overridden with flex-direction: row / gap: 0 in the mobile Pinch block; "
            "(2) .container kept width: calc(100% - 20px) + auto margins and "
            ".recipe-vscroll (.ab-grid-scroll) carried ~19px inset padding plus 1px "
            "borders on .recipe-vscroll-wrap/.ab-card, so cards never reached the "
            "viewport edges — all zeroed, cards are now pixel-exact full-bleed "
            "(verified: card rect 0..430 wide, wrap bottom == viewport bottom, "
            "body scrollHeight == viewport height, no page scroll); (3) footer drawer "
            "handle stayed parked at the bottom when the sheet opened — main.js open() "
            "now publishes --pinch-footer-h and CSS moves the handle to the sheet's "
            "top edge (bottom: calc(var(--pinch-footer-h) - 40px)) with the arch "
            "flipped down, replacing the drag-pip. Drawer toggle state now derives "
            "from the footer class instead of a private variable. --sticky-offset "
            "ResizeObserver additionally observes .ce-header and the filter block "
            "so late layout shifts recompute the snap card height."
        ),
        "checklist": [
            "pinch.css: .category-nav-block gets flex-direction: row + gap: 0 (mobile Pinch only)",
            "pinch.css: .container width 100% / margin-inline 0; .ab-grid-scroll padding 0",
            "pinch.css: borders/shadow/radius off .recipe-vscroll-wrap and .ab-card in snap mode",
            "pinch.css: handle rides to sheet top when open; drag-pip hidden while open",
            "main.js: open() sets --pinch-footer-h; aria-label swaps open/close",
            "main.js: drawer state read from footer class (no desync)",
            "main.js: ResizeObserver also observes .ce-header + .category-nav-block",
            "Verified live: snap lands exactly per card (200px flick -> 665px card), arrows scroll/disable correctly",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.68",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Arena Stage D1 — Battle Room page becomes the antechamber",
        "section": "Chef Battles / Arena (Phase FE-3)",
        "summary": (
            "Stage D1: battle_detail hero redesigned as an antechamber (прихожая). "
            "The old VS/combat-hits block is replaced by two side-by-side chef comparison "
            "cards showing avatar, name, rank (from ChefBattleProfile), rating, W/L, "
            "and win streak. A 'Watch Live in Arena →' CTA button appears for active "
            "battles, linking to the arena page. The kicker text changes from "
            "'X Chef Battles' to 'Chef Battle · Status'. All existing combat panels, "
            "entries, chat, gifts, and log remain unchanged (D2 — where chefs perform "
            "combat actions — is an open owner decision). challenger_profile and "
            "opponent_profile are added to battle_detail view context via "
            "get_or_create_battle_profile(). Mobile breakpoint collapses the comparison "
            "to a single column."
        ),
        "checklist": [
            "views.py battle_detail(): challenger_profile + opponent_profile added to context",
            "battle_detail.html: hero replaced with antechamber-compare + antechamber-cta",
            "chef_battle.css: .antechamber-compare, .antechamber-card, .antechamber-vs, .antechamber-cta added",
            "roadmap: D1 marked done; D2 remains open",
            "manage.py check: 0 issues",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.67",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Arena Stage B2+B4 — Facing pair (pre-combat) + completion return",
        "section": "Chef Battles / Arena (Phase FE-3)",
        "summary": (
            "Stage B2: SCHEDULED and MENU_LOCKED battles now display as a facing pair "
            "in the centre zone instead of the full VS layout. _arena_center() returns "
            "type 'facing_pair' for these statuses and includes battle_id + battle_phase. "
            "drawFacingPair() places two smaller cells (R=28) at distance 48px from centre "
            "at a battle_id-deterministic angle (battle_id % 8 * π/4) so the orientation "
            "is consistent across polls. A crossed swords ⚔ indicator sits between them. "
            "Clicking either cell opens the Battle Room popup (same arena_battle_popup endpoint). "
            "Stage B4 documented: chefs return to their ring cells automatically when the battle "
            "leaves ACTIVE_STATUSES — handled implicitly by the B1+B3 in_battle_map logic. "
            "Demo panel gains a 'Facing pair (pre-battle)' stage for client-side verification."
        ),
        "checklist": [
            "views.py _arena_center(): type 'facing_pair' for SCHEDULED/MENU_LOCKED; battle_id + battle_phase added",
            "views.py roadmap: B2 done, B4 done (implicit), B5 added as pending",
            "arena_puzzle.js: drawFacingPair() added before drawCentre()",
            "arena_puzzle.js: drawCentre() checks facing_pair type first",
            "arena_puzzle.js: demo panel gains 'Facing pair (pre-battle)' stage",
            "manage.py check: 0 issues",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.66",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Arena Stage C — Battle Room popup embedded on the arena",
        "section": "Chef Battles / Arena (Phase FE-3)",
        "summary": (
            "Stage C of the Arena As The Hall plan (owner-approved). "
            "Clicking either combatant cell in the VS centre now opens an inline popup "
            "instead of navigating to the full battle room page. "
            "The popup partial (arena_battle_popup view + arena_battle_popup.html template) "
            "fetches the active battle and renders: chef avatars + vote counts, "
            "up to 6 AVAILABLE/RESERVED artifacts per chef, live chat with 10-second polling "
            "and AJAX send (fire-and-forget + repoll), vote buttons (ACTIVE/VOTING phases only, "
            "non-participants, one vote per user), appreciation gift buttons (logged-in "
            "non-participants with sufficient token balance), and a footer link to the full "
            "battle room. Anonymous users see the popup read-only. "
            "_arena_center() now emits popup_url alongside battle_url. "
            "drawBattleCell() accepts popupUrl and calls openBattlePopup() in preference to "
            "navigating. Popup is dismissed on close button, backdrop click, or Escape key. "
            "No battle in progress renders a graceful 'No battle right now' state."
        ),
        "checklist": [
            "views.py _arena_center(): popup_url added",
            "views.py arena_battle_popup(): new view — HTML partial, no auth required",
            "chef_battle/urls.py: arena/battle-popup/ → arena_battle_popup",
            "templates/chef_battle/arena_battle_popup.html: new partial template",
            "templates/chef_battle/arena.html: #arena-battle-popup modal container added",
            "arena_puzzle.js: drawBattleCell() accepts popupUrl, openBattlePopup() added",
            "arena_puzzle.js: drawCentre() passes center.popup_url to drawBattleCell()",
            "arena_puzzle.js: closeBattlePopup(), _initPopupChat(), _escHtml() added",
            "arena_puzzle.js: DOMContentLoaded wires popup close button + backdrop + Escape",
            "arena.css: .arena-popup modal + .abp partial styles added",
            "roadmap: Stage C marked done 2026-07-02",
            "manage.py check: 0 issues",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.65",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Arena Stage B1+B3 — Battle context in payload + ring cell vacated during VS",
        "section": "Chef Battles / Arena (Phase FE-3)",
        "summary": (
            "B1: arena() and arena_state() now build an in_battle_map dict per active battle, "
            "adding battle_id, battle_phase, and battle_url to each in_battle chef dict "
            "(previously only a boolean in_battle was passed). "
            "B3: arena_puzzle.js defines CENTRE_PHASES and FACING_PHASES constant sets. "
            "drawArena() vacates a chef's ring cell when their battle_phase is in either set — "
            "so chefs in active combat (active/cooking/voting/etc.) no longer appear in their "
            "ring cell and the VS centre cell while simultaneously; they are moved, not duplicated."
        ),
        "checklist": [
            "views.py arena(): in_battle_map dict, battle_id/battle_phase/battle_url per chef",
            "views.py arena_state(): same pattern",
            "arena_puzzle.js: CENTRE_PHASES + FACING_PHASES constants",
            "arena_puzzle.js: drawArena() ring-cell vacate when chef.battle_phase in either set",
            "roadmap: B1 + B3 marked done; B2 (facing pair) remains pending",
            "manage.py check: 0 issues",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.64",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Arena Stage A — Chef Popup + Blue Spectator Cells",
        "section": "Chef Battles / Frontend (Arena As The Hall, Phase FE-3)",
        "summary": (
            "Stage A1 and A2 of the Arena As The Hall plan (owner-approved 2026-07-02). "
            "A1: The existing arena tooltip is expanded into a full chef popup card: "
            "W/L/Streak stats row, approximate ATK/DEF potential derived from ChefArtifact "
            "aggregate (hidden when both 0, artifact list never shown), View Profile + "
            "Challenge buttons. Challenge button is suppressed for spectators, self, and "
            "in-battle chefs. challenge_create now accepts ?opponent={slug} GET param for "
            "direct pre-fill from the popup. "
            "A2: Spectator ring (ring 9) colour changed from legacy green (#4a6741) to "
            "cobalt blue (#2a5fb0 / empty #c5d3e8); legend swatch updated to match. "
            "Currently keeps wallet-holder eligibility (_get_spectators unchanged). "
            "arena() and arena_state() now include wins/losses/win_streak/atk/def in "
            "each chef dict; artifact potential is aggregated in a single extra query. "
        ),
        "checklist": [
            "chef_battle/views.py: ChefArtifact import, Q/Sum/Coalesce imports",
            "arena() + arena_state(): list() enrolled, artifact_agg dict, wins/losses/win_streak/atk/def in payload",
            "challenge_create: GET ?opponent={slug} -> RecipeAuthor.objects.get(slug=) -> initial[opponent]=pk",
            "arena.html: window.ARENA_VIEWER JS block, expanded tooltip HTML (stats/potential/actions rows), CSS version bump",
            "arena_puzzle.js: spectator blue #2a5fb0, showTooltip() populates new fields, is_spectator flag hides stats/potential/challenge",
            "arena.css: legend swatch blue, new .arena-tooltip__stats / __potential / __actions / __challenge CSS",
            "manage.py check: 0 issues",
        ],
        "stats": [
            "5 files changed (views.py, arena.html, arena_puzzle.js, arena.css, release_journal.py)",
        ],
        "deployment_status": "pending deployment",
    },
    {
        "version": "2.5.60",
        "date": "2026-07-02",
        "commit": "pending",
        "title": "Gold Accent Pass + Artifact Catalogue Sync (owner-approved)",
        "section": "Chef Battles / Frontend + Content",
        "summary": (
            "Two owner-approved cleanups from the 2026-07-02 site audit. "
            "First, the last legacy greens were replaced with the standardized gold family "
            "site-wide: #1a6b3a/#d6f5e0/#6dce8f/#bfedd0/#4db877 became #c8942a (accent), "
            "#f8d28a (pill background) and #6e4e2c (dark text) across the battle blast card, "
            "combat/pip your-turn pills, token shop, battle guide, moderation done-pills, "
            "coworking dashboard, chef profile, season leaderboard and rules drop table. "
            "The undefined var(--color-success, ...) fallback pattern was removed - the variable "
            "was never defined, so the green fallback always rendered. "
            "Second, the artifact image-prompt catalogue (generate_battle_assets.py) and its spec "
            "(docs/chef_battle/combat_items.md) were synced with the 2026-07-01 Irish-myth renaming: "
            "7 fantasy entries renamed, rune imagery replaced with ogham script."
        ),
        "checklist": [
            "base.html: blast badge/winner gold; version bump",
            "chef_battle.css: combat + pip your-turn pills, token-shop featured/badge/price, battle-guide focus/hover/label",
            "moderation.css: mod-tool-link--done gold pill + hover",
            "coworking dashboard: active badge #c8942a",
            "chef_profile: Wins stat + Won label; season_leaderboard: pts; rules: winner %",
            "generate_battle_assets.py: salamander-grill-sauce, the-dagdas-ladle, skellig-stone-stockpot, the-ogham-cutting-board, the-tir-na-nog-wok, giants-causeway-dome, nuadas-silver-pot-lid; runes -> ogham",
            "combat_items.md: same 7 renames, names/slugs/log lines consistent with the generator",
            "chef_battle roadmap (views.py): 2 new Phase FE-2 entries, stale Known-gap note resolved",
            "NEW: docs/chef_battle/ARENA_HALL_PLAN.md - owner-approved Arena As The Hall plan (avatar relocation, embedded Battle Room popup, antechamber, grey anonymous fields, gifted-artifact rule, sellable appreciation gifts)",
            "NEW: roadmap Phase FE-3 - Arena As The Hall: 9 pending stages mirroring the plan",
            "Zero remaining matches for legacy greens and old fantasy slugs codebase-wide",
            "manage.py check: 0 issues",
        ],
        "stats": [
            "10 files changed (CSS, templates, docs, management command, roadmap)",
        ],
        "notes": (
            "Rollback investigation same day: no git-level rollback found. All July 1 work intact "
            "in main; prod matches origin/main. The arena ?demo panel stages the full duel lifecycle "
            "visually - choreography Phases 2 (movement) and 3 (spectator popup) were never coded "
            "(see recovered docs/chef_battle/HANDOFF_CRESTEDTEN.md at commit 9badb2ca). "
            "From this release on: every step is logged in Deployment Journal, Chef Battle Roadmap "
            "and CoWork per owner instruction."
        ),
        "deployment_status": "pending deployment",
    },
    {
        "version": "feature/chef-battle-home-redesign",
        "date": "2026-06-19",
        "commit": "70a47ea",
        "title": "Chef Battles Home Page — Visual Redesign",
        "section": "Chef Battles / Frontend",
        "summary": (
            "Full visual redesign of the /chef-battle/ home page. "
            "The page now carries a warm arena identity: chocolate-toned hero gradient, "
            "centred CHEF'S BATTLE wordmark in Playfair Display, crossed-swords divider, "
            "and a structured CTA row (orange primary + ghost secondary buttons). "
            "Active Battles use arena cards with an orange status border and VS notation. "
            "An empty-state card holds arena-flavoured copy when no battles are live. "
            "The sidebar gained gold/silver/bronze position circles for Top Chefs and an "
            "icon-and-timestamp layout for Battle Pulse. "
            "Palette: cream #faf6f0, chocolate overlay, orange #e8630a — no dark green. "
            "All JS hooks preserved (hero__burger / hero__actions-list). Mobile-responsive."
        ),
        "checklist": [
            "Added battle-home scoped CSS block (~350 lines) to chef_battle.css",
            "New wordmark block: pre-title + CHEF'S BATTLE h1 + swords divider",
            "Hero: dark chocolate gradient overlay on hero-battle.png",
            "CTA row: orange pill primary + ghost secondary buttons",
            "More burger nav: pill-style secondary links (Season, Gifts, Artifacts, etc.)",
            "Active Battles section: battle-home__card with orange left-border status",
            "Empty arena state: dashed-border card with inline Issue a Challenge CTA",
            "Recent Results: themed row layout",
            "Top Chefs: gold (#c8941a) / silver (#9ca0a4) / bronze (#a06840) rank circles",
            "Battle Pulse: icon + message link + time layout",
            "Pulsing live dot animation on Active Battles header",
            "Responsive breakpoint at 768px: centred CTA and nav rows",
            "collectstatic run — manifest hash 9b810bed59b8",
            "NGINX Unit restarted to clear compiled template cache",
        ],
        "stats": [
            "2 files changed: templates/chef_battle/home.html + static/css/chef_battle.css",
            "724 insertions, 125 deletions",
        ],
        "notes": "CHEF_BATTLE_ENABLED remains False — home redesign is first step of frontend rollout.",
        "deployment_status": "deployed",
    },
    {
        "version": "feature/chef-battle",
        "date": "2026-06-10",
        "commit": "0cfe995",
        "title": "Chef Battles — Phase 1 progress: Admin, selectors, expiry, tests",
        "section": "Chef Battles / Backend",
        "summary": (
            "Four solid sessions of backend groundwork for Chef Battles. "
            "Every model is now fully visible in Django Admin with filters, search and read-only timestamps. "
            "Staff have seven one-click actions to manage battles without touching the database directly. "
            "All read queries were extracted into a clean selectors.py layer — views no longer build "
            "QuerySets inline. The system now handles the full no-show scenario: if a chef doesn't submit "
            "before the deadline, their opponent wins by forfeit; if both miss it, the battle is cancelled. "
            "A management command covers challenge expiry and no-shows in one scheduled job. "
            "On top of all that, the public homepage now has an Announcements block teasing Chef Battles "
            "to every visitor, and a management command is ready to post the news to the site feed and Telegram. "
            "The test suite grew from 5 to 20 tests, all green."
        ),
        "checklist": [
            "CB-0013: All 13 chef_battle models registered in Django Admin",
            "CB-0013: list_display, list_filter, search_fields, readonly_fields on every model",
            "CB-0013: BattleAdmin fieldsets: Participants / Status+Timing / Result / Timestamps",
            "CB-0013: BattleEntryInline + BattleEventInline inside BattleAdmin",
            "CB-0014: cancel_challenges — bulk-cancel pending/expired challenges",
            "CB-0014: cancel_battles — cancel any non-final battle, emits BATTLE_FINISHED event",
            "CB-0014: force_reveal_entries — reveal hidden entries, advance to Voting",
            "CB-0014: force_complete_battles — call calculate_battle_result() on demand",
            "CB-0014: reset_disputed_battles — return disputed battle to Voting",
            "CB-0014: mark_votes_suspicious / clear_votes_suspicious — anti-abuse moderation",
            "Created chef_battle/selectors.py with 9 named read functions",
            "views.py updated to import from selectors; unused Count/Q imports removed",
            "services.py: expire_stale_challenges() — marks PENDING challenges past expires_at as EXPIRED",
            "services.py: handle_no_show_battles() — double no-show → CANCELLED; single no-show → forfeit win",
            "services.py: submit_battle_entry() — sets is_late=True when deadline passed",
            "services.py: _award_forfeit_win() — forfeit result helper (rep penalty, no Elo change)",
            "management/commands/expire_stale_battles.py — run periodically; --dry-run flag",
            "Permission tests: anon → 404, regular user → 404, staff → 200 (flag off)",
            "Anti-abuse tests: duplicate vote IntegrityError, self-vote ValidationError, outsider vote ValidationError, suspicious flag persistence",
            "Expiry tests: stale challenge expires, future challenge untouched, double no-show cancel, forfeit win, is_late flag",
            "Homepage: public Announcements block added (hero-battle.png, teaser copy, all visitors)",
            "newsfeed/management/commands/publish_chef_battle_announcement.py — posts to feed + Telegram",
            "CSS: announcements-grid responsive layout added to base.css",
            "Tests: 20/20 pass",
        ],
        "stats": [
            "New file: chef_battle/selectors.py",
            "New file: chef_battle/management/commands/expire_stale_battles.py",
            "New file: newsfeed/management/commands/publish_chef_battle_announcement.py",
            "Tests: 20/20 pass (was 5)",
            "Django check: passed",
        ],
        "deployment_status": "feature branch — not yet on production",
        "notes": (
            "All work stays in feature/chef-battle. Not deployed to production. "
            "After merge and migrations: admins can access /chef-battle/ and use all admin actions. "
            "Homepage Announcements block is visible to everyone immediately after deploy. "
            "Run 'python manage.py publish_chef_battle_announcement' after deploy to send the news to feed and Telegram. "
            "Run 'python manage.py expire_stale_battles' periodically (or add to cron). "
            "Next: Founding Chef programme, 7-day battle timer, battle rules page, full regression test."
        ),
    },
    {
        "version": "feature/chef-battle",
        "date": "2026-06-10",
        "commit": "09178e6",
        "title": "Chef Battles — Phase 0: Core model foundation + access control",
        "section": "Chef Battles / Backend",
        "summary": (
            "We started building Chef Battles — the new culinary PvP system for CulinEire. "
            "The full ТЗ was loaded, every gap between the existing code and the spec was identified, "
            "and all missing model fields were added in one migration. "
            "A proper access control layer was introduced: Chef Battles is completely invisible "
            "to regular and anonymous users until the public launch flag is set. "
            "Admins and superusers can preview everything as it will look, right now."
        ),
        "checklist": [
            "ChefBattleProfile: added ignored_battles, best_win_streak, crown_count, created_at",
            "BattleChallenge: added CANCELLED status and cancelled_at timestamp",
            "Battle: added AWAITING_SUBMISSIONS, REVEALED, DISPUTED statuses",
            "Battle: added reveal_time, voting_deadline, rating_delta_challenger, rating_delta_opponent, crown_awarded fields",
            "Battle: increased status max_length to 24 to fit 'awaiting_submissions'",
            "BattleEntry: renamed note → battle_statement (matches ТЗ field name)",
            "BattleEntry: added is_late, moderation_status (pending/approved/rejected/flagged), created_at, updated_at",
            "BattleVote: added session_key_hash, is_suspicious, moderation_note",
            "BattleEvent: added payload_json field",
            "BattleEvent: added CHALLENGE_EXPIRED, BATTLE_REVEALED, BATTLE_FINISHED, CHEF_DEFEATED, CROWN_AWARDED, RANK_PROMOTED event types",
            "Migration 0002_add_missing_fields_phase0 created and verified",
            "Created chef_battle/access.py: is_battle_visible() and @chef_battle_guard decorator",
            "Applied @chef_battle_guard to all 8 chef_battle views — non-admins get 404 when flag is off",
            "config/urls.py: chef_battle URLs now always registered (guard is at view level, not URL level)",
            "context_processors.py: chef_battle_enabled=True for admins/superusers regardless of flag",
            "services.py: battle events only published to public newsfeed when CHEF_BATTLE_ENABLED=True",
            "Updated /chefs-battle/roadmap/ with full Phase 0–7 milestone list (55 items)",
            "All 5 existing tests pass",
        ],
        "stats": [
            "Migration: chef_battle/migrations/0002_add_missing_fields_phase0.py",
            "New file: chef_battle/access.py",
            "Tests: 5/5 pass",
        ],
        "deployment_status": "feature branch — not yet on production",
        "notes": (
            "feature/chef-battle only. Not deployed to production. "
            "Admins can access /chef-battle/ on production after this merges and migrations run. "
            "Regular users and anonymous visitors see nothing. "
            "Next: CB-0013 admin registration, CB-0014 admin actions, permission and anti-abuse tests."
        ),
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-09",
        "commit": "1d6294f",
        "title": "Site Audit — Roadmap and Checklist Status",
        "section": "Documentation / Project",
        "summary": "Marked all closed roadmaps and checklists with status headers. Sponsors module confirmed complete. Stripe live switch confirmed closed. Month 1 decisions recorded with mixed status.",
        "checklist": [
            "Marked docs/stripe_sponsors_checklist.md as CLOSED — live switch completed 2026-06-08",
            "Marked docs/sponsor_stripe_live_readiness.md as CLOSED",
            "Marked sponsors/README.md as Complete",
            "Marked docs/month1_decisions.md as MIXED — Content Automation complete, Image Opt / Ads / Affiliates deferred",
            "Marked docs/external_setup_checklist.md as OPEN — Pinterest, Telegram, Instagram/TikTok pending owner action",
        ],
        "stats": [],
        "deployment_status": "deployed",
        "notes": "",
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-09",
        "commit": "c4d7711",
        "title": "Sponsorship Terms Page Redesign + Sponsor of the Month Attribution",
        "section": "Sponsors / Legal / Newsfeed",
        "summary": "Redesigned /sponsors/annual-contract/ to match the legal hub style with anchor navigation, placement cards and full section detail. Added Sponsor of the Month attribution to Telegram messages and newsfeed entries when a central sponsor is active.",
        "checklist": [
            "Redesigned sponsorship terms page: hero, anchor nav, 3 placement cards, 7 legal sections",
            "Removed target=_blank that caused a clipped green-chrome window when opening terms",
            "Added 3-card CSS grid centering fix using :has() selector",
            "Added Sponsor of the Month attribution to Telegram recipe and article messages",
            "Added Sponsored by attribution to newsfeed entry message field",
            "Added Sponsor of the Month attribution clause to sponsorship terms page",
        ],
        "stats": [],
        "deployment_status": "deployed",
        "notes": "When a central sponsor (ring=0, status ACTIVE or SOLD) is active, all new recipe and article publications carry Sponsored by: [name] in Telegram notifications and newsfeed entries.",
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-08",
        "commit": "56f0191",
        "title": "VAT Invoice PDF — Final Layout: Pinned Totals and Meta Balance",
        "section": "Sponsors / PDF / Finance",
        "summary": "Fixed VAT invoice PDF layout: totals, QR code and notes are now pinned to the page bottom via canvas callback. Meta block rebalanced to three rows on each side. ReportLab wrapOn return-value bug fixed.",
        "checklist": [
            "Moved totals, QR block and payment notes to _draw_page canvas callback (pinned to page bottom)",
            "Set b_margin=88mm to prevent flowable content overlapping pinned block",
            "Fixed AttributeError: captured wrapOn return value for table and paragraph heights",
            "Rebalanced meta block: Invoice No / Issue date / Supply date left; Application ref / Payment date / Stripe Ref right",
            "Story now contains only header, rule, meta, parties and items table — no floating totals",
        ],
        "stats": [],
        "deployment_status": "deployed",
        "notes": "Totals, QR code and payment notes are drawn at absolute page coordinates, independent of content length. Invoice fits on a single page.",
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-08",
        "commit": "b2d0c85",
        "title": "VAT Invoice PDF — New Document: Billing Address, generate_invoice_pdf, Dual PDF Email",
        "section": "Sponsors / PDF / Finance",
        "summary": "Added full VAT invoice PDF generation alongside the existing sponsor agreement PDF. Both documents are attached to the sponsor activation email. Added billing_address field to SponsorPayment.",
        "checklist": [
            "Added generate_invoice_pdf() in sponsors/services.py",
            "Added billing_address field to SponsorPayment model (migration 0017)",
            "Attached VAT invoice PDF alongside sponsor agreement PDF in activation email",
            "Invoice includes: Bearcave Limited header, sponsor details, VAT breakdown, QR code, payment reference",
            "Invoice design: single page, Heritage Legal Paper style consistent with agreement PDF",
        ],
        "stats": [
            "Migration 0017: billing_address field on SponsorPayment",
        ],
        "deployment_status": "deployed",
        "notes": "The VAT invoice is generated at activation time. Supply date on the invoice equals the activation date. Suitable for accountant and tax records.",
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-08",
        "commit": "1100961",
        "title": "Sponsor Contract Automation — Agreement Emails, Contract Reference, Resend Action",
        "section": "Sponsors / PDF / Email",
        "summary": "Added automated sponsor agreement PDF generation and email delivery on activation. Added contract reference field, staff resend action and legacy email branding cleanup.",
        "checklist": [
            "Added generate_agreement_pdf() to sponsors/services.py (Heritage Legal Paper style)",
            "Agreement PDF sent to sponsor email on activation",
            "Added contract_reference field to SponsorApplication",
            "Added staff resend-agreement action in sponsor moderation",
            "Removed legacy email branding and outdated weekly sponsor display wording",
            "Fixed sponsor regression test isolation and 7-day checkout expectation",
        ],
        "stats": [
            "Sponsor confirmation email PDF attachment regression: fixed",
        ],
        "deployment_status": "deployed",
        "notes": "Related commit: d3e8212 Remove legacy email branding and weekly sponsor display wording.",
    },
    {
        "version": "2.3.5",
        "date": "2026-06-08",
        "commit": "8dee2be",
        "title": "Weekly Sponsor Ring Pricing, Legal Hub Sync, Privacy Policy Rebuild, Sponsor Puzzle Fixes",
        "section": "Sponsors / Legal / UI",
        "summary": "Added tiered weekly ring pricing (€5–€25/wk). Rebuilt Privacy Policy with legal card system. Synchronised Legal Hub hero with homepage. Fixed sponsor puzzle logo transform propagation and modal close-button overlap. Fixed Open Graph and Twitter meta tags for all section pages.",
        "checklist": [
            "Added weekly sponsor ring (Ring 6) with tiered €5–€25/wk pricing",
            "Updated sponsor puzzle compact ring labels for weekly tier",
            "Rebuilt Privacy Policy using accepted legal card components",
            "Synchronised Legal Hub hero image and overlay with homepage style",
            "Fixed sponsor logo transform not propagating to public puzzle after approval",
            "Fixed sponsor modal close button overlapping form fields on scroll",
            "Fixed Open Graph and Twitter meta tags missing on several section pages",
            "Bumped version to v2.3.5",
        ],
        "stats": [],
        "deployment_status": "deployed",
        "notes": "Ring 6 is a weekly placement (not annual, not auto-renewing). One-off payment for 7 calendar days.",
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-07",
        "commit": "8659459",
        "title": "Sponsors Phase 6 — Stripe Live Readiness Checklist",
        "section": "Sponsors / Stripe / Live Readiness",
        "summary": "Added Stripe live-readiness checklist, safety guards for Stripe mode/key mismatch, webhook secret validation, and documentation for owner/accountant review before real sponsor payments.",
        "checklist": [
            "Added docs/sponsor_stripe_live_readiness.md",
            "Updated docs/stripe_sponsors_checklist.md",
            "Updated Sponsors README with Phase 6 readiness notes",
            "Added safety guards against test/live Stripe key mismatch",
            "Added STRIPE_PRICE_MODE validation",
            "Kept webhook signing secret mandatory for webhook verification",
            "Confirmed no live mode switch was performed",
            "Confirmed no real payments were created",
            "Confirmed sandbox sponsor cleanup completed after smoke testing",
            "Listed unresolved owner/accountant/live-readiness actions",
        ],
        "stats": [
            "Sponsors tests: 139 passed",
            "Legal/newsfeed/recipes tests: 259 passed, 2 skipped",
            "Django check: passed",
            "Migration: not required",
            "Collectstatic: not required",
            "Production health: /sponsors/ HTTP/2 200",
            "Webhook route probe: GET /sponsors/stripe/webhook/ returns HTTP 405, expected POST-only behaviour",
            "Sandbox cleanup: SponsorApplication 0, SponsorPayment 0, SponsorSanctionsMatch 0, SponsorAuditLog 0",
            "Sanctions subjects retained: 6996",
            "Sponsor cells unavailable: 0",
        ],
        "deployment_status": "deployed",
        "notes": "Phase 6 is readiness-only. It records live-readiness documentation and safety guards, not a live Stripe switch. It does not create real payments and does not replace owner/accountant review. Remaining blockers before live payments include Stripe account activation confirmation, VAT/Stripe Tax review, production email delivery confirmation, live webhook setup/signing secret, database backup and explicit project owner authorisation.",
    },
    {
        "version": "2.3.4",
        "date": "2026-06-06",
        "commit": "9ac1665",
        "title": "Author Dashboard Filter Navigation",
        "section": "Author Dashboard / Recipes",
        "summary": "Simplified and unified category filter navigation across the author dashboard and recipe mood sections.",
        "checklist": [
            "Simplified dashboard filter navigation",
            "Replaced standalone filter buttons with category navigation links",
            "Unified recipe mood categories with category navigation",
            "Aligned dashboard filter buttons with the site button design system",
        ],
        "stats": [],
        "deployment_status": "deployed",
        "notes": "",
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-06",
        "commit": "fb1800e",
        "title": "Sponsors Compliance Phase 1 - Stripe Purchase and Manual Compliance Review",
        "section": "Sponsors / Stripe / Compliance",
        "summary": "Added sponsor declaration before Stripe, paid_pending_compliance_review, manual compliance clear before approval, admin attention badges and the full sponsor approval flow.",
        "checklist": [
            "Added mandatory sponsor declaration checkboxes before Stripe",
            "Moved paid sponsor applications to paid_pending_compliance_review",
            "Required staff manual compliance clear before approve and publish",
            "Added sponsor moderation attention badges",
            "Confirmed annual sponsor sandbox purchase flow",
            "Confirmed Stripe test payment flow",
            "Confirmed Telegram announcement sends only after Approve and publish",
            "Confirmed sponsor becomes active after staff approval",
        ],
        "stats": [
            "Manual smoke test Phase 1: passed",
            "Sandbox annual sponsor purchase: passed",
            "Stripe test payment: passed",
            "Admin badge after payment: passed",
            "Telegram after approval only: passed",
            "Production health: /sponsors/ HTTP/2 200",
        ],
        "deployment_status": "deployed",
        "notes": "Related commit: 4ab2936 Add sponsor moderation attention badges. This is an internal staff release ledger entry based on project owner smoke-test notes and production deployment records.",
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-06",
        "commit": "1f5eb89",
        "title": "Sponsors Compliance Phase 2 - Official Sanctions Source Ingestion",
        "section": "Sponsors / Compliance",
        "summary": "Added official EU/UN sanctions source ingestion, source snapshots, source subject storage, RSS-based EU source discovery, UN source loading and staff source status visibility.",
        "checklist": [
            "Added SanctionsSourceSnapshot and SanctionsSubject data foundation",
            "Added update_sanctions_sources management command",
            "Added official EU FSF RSS discovery",
            "Added tokenized EU XML v1.1 download through official RSS",
            "Added CSV fallback and manual EU file import fallback",
            "Kept --allow-partial update behaviour",
            "Preserved failed snapshots for audit",
            "Kept Phase 3 matching deliberately out of scope",
        ],
        "stats": [
            "EU sanctions source: success, 5994 records",
            "UN sanctions source: skipped_not_modified, 1002 records",
            "Total sanctions subjects: 6996",
            "Django check: passed",
            "Production health: /sponsors/ HTTP/2 200",
        ],
        "deployment_status": "deployed",
        "notes": "Related commits: 8fc01bb Add official sanctions source ingestion; 65062d6 Fix EU sanctions source download fallback; cd44a19 Add manual EU sanctions file import. Phase 2 imports and tracks official sources only. Sponsor matching and possible-match workflow are Phase 3.",
    },
    {
        "version": "version pending backfill",
        "date": "2026-06-07",
        "commit": "628f3f4",
        "title": "Sponsors Compliance Phase 5 - Legal and UI Polish",
        "section": "Sponsors / Compliance / Staff UI",
        "summary": "Polished applicant-facing sponsor wording, staff compliance/refund messages, notification clarity and internal sponsor compliance documentation.",
        "checklist": [
            "Clarified that payment reserves a sponsor spot but does not guarantee approval, publication or activation",
            "Clarified pending compliance review wording on checkout success and sponsor application UI",
            "Clarified manual refund tracking and refund completion wording",
            "Updated sponsor moderation list and detail helper text for staff action queues",
            "Confirmed public pages do not expose sanctions match details, source URLs, staff notes, audit logs or Stripe identifiers",
        ],
        "stats": [
            "Test results pending final Phase 5 run",
        ],
        "deployment_status": "pending deployment",
        "notes": "Phase 5 is wording, UI clarity and documentation only. It does not change Stripe payment/webhook semantics, Telegram trigger behaviour, sanctions source ingestion or sanctions matching logic.",
    },
]


import re
import subprocess


def _detect_section(subject: str, body: str) -> str:
    text = (subject + " " + body).lower()
    if "chef" in text and "battle" in text:
        return "Chef Battles"
    if "recipe" in text:
        return "Recipes"
    if "article" in text:
        return "Articles"
    if "account" in text or "auth" in text or "login" in text:
        return "Accounts"
    if "newsfeed" in text or "news" in text:
        return "Newsfeed"
    if "sponsor" in text or "stripe" in text:
        return "Sponsors"
    if "migration" in text or "migrate" in text:
        return "Database"
    if "static" in text or "css" in text or "js" in text or "template" in text:
        return "Frontend"
    if "deploy" in text or "version" in text or "bump" in text:
        return "Deploy"
    if "test" in text:
        return "Tests"
    return "General"


def _parse_git_log(repo_path: str, limit: int = 60) -> list[dict]:
    try:
        raw = subprocess.check_output(
            ["git", "log", f"--max-count={limit}", "--format=%x00%H%x01%h%x01%ad%x01%s%x01%b", "--date=short"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return []

    entries = []
    for block in raw.split("\x00"):
        block = block.strip()
        if not block:
            continue
        parts = block.split("\x01", 4)
        if len(parts) < 4:
            continue
        full_hash, short_hash, date, subject = parts[0], parts[1], parts[2], parts[3]
        body = parts[4].strip() if len(parts) == 5 else ""

        body_lines = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
        checklist = [ln.lstrip("-• ") for ln in body_lines if ln.lstrip().startswith("-") or re.match(r"^CB-\d+", ln.lstrip())]
        summary_lines = [ln for ln in body_lines if not ln.lstrip().startswith("-") and not re.match(r"^CB-\d+", ln.lstrip()) and "Co-Authored-By" not in ln]
        summary = " ".join(summary_lines) if summary_lines else subject

        entries.append({
            "version": short_hash,
            "date": date,
            "commit": short_hash,
            "title": subject,
            "section": _detect_section(subject, body),
            "summary": summary,
            "checklist": checklist,
            "stats": [],
            "notes": "",
            "deployment_status": "Deployed",
        })

    return entries


def build_git_journal(repo_path: str, limit: int = 60) -> list[dict]:
    git_entries = _parse_git_log(repo_path, limit=limit)
    if not git_entries:
        return list(reversed(RELEASE_JOURNAL))
    return git_entries
