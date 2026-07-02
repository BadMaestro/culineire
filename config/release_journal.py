RELEASE_JOURNAL = [
    {
        "version": "2.5.69",
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
            "base.html: v2.5.69",
            "manage.py check: 0 issues (pending verify on server)",
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
