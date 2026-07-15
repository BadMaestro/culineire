# Chef Battle — UI Polish Backlog (per-page visual quality)

Owner directive: as we play the chef journey, log the crude/ugly appearance on
each page so we fix it later — every screen should feel like the premium dark
broadcast Live Arena, not a barren default.

Reviewer: GreenBear (live walk as CrestedTen). Severity: HIGH / MED / LOW.

---

## /chef-battle/arena/ — The Arena (ring/lobby)
- **HIGH** — Huge empty ring of pale-blue "stadium seat" tiles dominates the screen and
  reads as barren/empty (no chefs seated). The centrepiece should be the battle, not
  acres of empty seating.
- **HIGH** — Centre shows two tiny avatars + a micro "VS"; for the focal point of a
  battle arena this is underwhelming. Should echo the Live Arena matchup (portraits,
  gold VS, green/red).
- **HIGH** — Pale beige/cream palette is bland and off-brand vs the dark broadcast
  aesthetic we built for the Live Arena. Arena hub should feel premium/dark.
- **MED** — Broken emoji glyphs render as boxes: "□ Battle Chest", "□ Changing Room".
  Replace with the owned SVG icon set (_live_arena_svg.html) or proper icons.
- **MED** — Arena Menu panel (bottom-right) is flat text links with inconsistent button
  styling (outlined vs solid vs plain); looks like a rough widget, not a control deck.
- **LOW** — "Click any chef to view their profile" is unstyled centred text.

---

## /chef-battle/battles/<id>/ — Battle detail (menu_locked, verified live on #12)
- FUNCTIONAL OK — leaked `{# #}` fixed (v2.5.236), menu_locked CTA = "Go to Changing
  Room" (v2.5.234), both-ready hero renders. Fixes confirmed live.
- **MED** — the floating "Chef Battles Arena" menu panel overlaps the right-side
  Gifts/Send panel content (covers token balance / gift buttons).
- **MED** — broken emoji "□ Battle Chest" in the floating panel (recurs site-wide).
- **LOW** — VS hero here is decent (portraits + gold VS on a food photo) — closest to
  the Live Arena look; use it as the reference for other pages.

## /chef-battle/changing-room/ — Changing Room hub
- **MED** — title emoji renders as a box "□ Changing Room".
- **MED** — "Active Loadout / No artifacts" text is clipped/overlapped by the floating
  Arena Menu panel (bottom-right) — the panel collides with page content on multiple pages.
- **LOW** — Chef Status stat cards are plain outlined boxes; fine but flat vs broadcast look.

## /chef-battle/battles/<id>/changing-room/ — Declare Your Menu (verified live)
- FUNCTIONAL OK — form renders (TemplateSyntaxError fix v2.5.234 confirmed: was 500),
  "vs Jam O'Liver" line renders (the fixed inline conditional), 5–7 ingredient rows + lock.
- **MED** — floating Arena Menu panel again overlaps the ingredient rows / lock labels
  on the right. This panel needs to stop colliding with primary content everywhere.
- **LOW** — ingredient inputs are plain dark boxes; lock affordance ("🔒 Lock") is small.

## Cross-cutting (every page)
- ~~The floating "Chef Battles Arena" menu panel~~ — **NOT a bug. Owner-intentional
  floating quick-nav (owner/god-user only). Do NOT "fix" or reposition it.**
- **HIGH** — Broken emoji glyphs (□) recur ("Battle Chest" &#x1F4BC;, "Changing Room"
  &#x1F9E5;). Some systems don't render these emoji — replace with the owned SVG icon set.
- **MED** — Two visual worlds: the new Live Arena is premium dark broadcast; the rest of
  Chef Battles is pale beige/cream. Unify toward the broadcast system.

## (next screens logged here as the walk continues)
