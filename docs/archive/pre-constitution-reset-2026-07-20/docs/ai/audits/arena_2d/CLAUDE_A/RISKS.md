# CLAUDE_A — Risks (Frontend and Presentation Audit)

## R1 — Deleting the photographic-backdrop subsystem without an explicit owner confirmation
`arena_render.js`'s backdrop-matching code and `arena_render.css`'s
`.has-arena-backdrop` rules (EVIDENCE.md §1.2) were the single largest piece of
verified, tested work landed this session (8/8 corner match within 2%, live-spectator
billboard fix, v2.5.379). AUDIT.txt's "simpler 2D interface" direction reads as
retiring this subsystem too, but it does not name it explicitly the way it names the
retirement of "cinematic or pseudo-3D." **Risk: deleting §1.2 based on inference
rather than an explicit confirmation could destroy verified, recently-shipped work
the owner still wants.** Recommend the synthesis stage surface this as an explicit
user-decision-required item, not resolve it silently either way.

## R2 — `arena_deck_polish.css` / `arena_effects.css` not read line-by-line this pass
Both are small (126 / 132 lines) but their full rule sets were not read in this
audit pass — only their load site and general purpose (from filename + commit-date
cache-bust suffix) are confirmed. **Risk: a 2D rebuild that assumes these are purely
additive polish could silently drop rules that are load-bearing (e.g. a focus-visible
state or a responsive override) if they turn out to override rather than extend
`arena_command_deck.css`.** Recommend a full read before any deletion/consolidation.

## R3 — `arena_hall.css` history as a two-owner conflict file
Per `GOLDEN_RULES.md` (§"Два исполнителя правят один макет"), `arena_hall.css` was
the exact file where two agents (Bolt and GreenBear/CLAUDE_A) editing the same
selectors from different files produced a broken cascade the owner described as
"на неё насрали" ("they crapped on it"). This file was not fully read this session
(only its load site and a few grep hits were captured). **Risk: this is the highest-
probability location for leftover conflicting rules, duplicate selectors, or
"win the cascade" hacks from that incident.** Recommend CLAUDE_B's cross-lane CSS
loading-order audit treat this file as priority one, and that no rule in it be
assumed authoritative without checking whether `arena_render.css` or
`arena_command_deck.css` declares the same selector later in the load order.

## R4 — `arena.css` is shared between the public floor and the staff Master Console
`arena.css` (785 lines) is loaded by both `arena.html` (public) and
`arena_master_console.html` (staff-only). A 2D-rebuild edit aimed at the public
floor's presentation could unintentionally change the Master Console's appearance
too, since both pages share this one file. **Risk: regression on a staff tool that
nobody is actively testing, discovered late.** Recommend: before editing any rule in
`arena.css`, confirm via its selector name whether it's consumed by
`_arena_render_ring.html` (shared by both pages) or only by `arena.html`'s own
markup, and prefer adding new page-scoped rules over editing shared ones.

## R5 — Anonymous-viewer frontend state may not exist yet, contradicting the golden rule's endgame
The owner's golden rule (recorded `docs/agents/memory/golden_rule_author_can_visit_arena.md`,
this session) states unauthenticated visitors get view-only access "once the arena
goes public." The current `arena.html` template's only unauthenticated branch is a
"Sign in to join" CTA in the crowd-rail footer (l.178-180) — there is no distinct
"you are viewing as a guest" banner or vote-disabled affordance elsewhere on the
page. **Risk: if/when the dark-launch flag (`CHEF_BATTLE_ENABLED`) opens the arena to
true anonymous traffic, the current frontend has no visible signal to a guest that
they can watch but not vote/challenge**, beyond the one CTA. This is listed as
MISSING (partial) in `FEATURE_MAP.md`; flagging here as a risk because it's easy to
miss since the backend gate change (v2.5.380) makes this path newly reachable for
plain authors, and anonymous access is the next logical step per the golden rule's
own wording ("Even not a registered user at all... will be able to enter the arena
and observe the battles").

## R6 — `.site-battle-widget`'s independent `--arena-*` token block
See EVIDENCE.md §5. If a future pass edits `base.css`'s `--arena-*` values assuming
they cascade everywhere "the `--arena-*` namespace" is used, `.site-battle-widget`'s
own scoped redeclaration (`chef_battle.css` ~l.3854-3863) will silently not follow,
producing a visual mismatch between the arena floor and the site-wide battle widget
that nobody notices until a design-system review. Flagged for CLAUDE_B's
design-system-compliance lane as the primary owner of this finding; recorded here
because it was discovered while auditing arena-adjacent CSS.

## R7 — Scope of "2D interface" is not yet specified beyond "not 3D"
AUDIT.txt's `current_decision` says only that the future direction is "a simpler 2D
interface" and that "no new 2D implementation may begin during this audit." No
mockup, wireframe, or measured spec for the target 2D layout was found anywhere in
the repository as of this audit (the only measured spec found,
`arena_mockup_spec.md`, is for the now-abandoned perspective direction — see
BOOTSTRAP.yml conflict). **This is not a code risk but a process risk**: the
`PROPOSED_2D_REBUILD_BOUNDARY.md` the synthesis stage is asked to produce can define
what stays/goes, but cannot itself invent what the 2D floor should look like — that
remains a `user_decision_required` item.
