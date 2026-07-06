RELEASE_JOURNAL = [
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
