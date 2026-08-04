# Deployment Project — CulinÉire Chef Battle Arena

Hand this folder to the implementing agent (Director). Everything needed to port the
Arena and the Master Console to production is here.

## Contents

    Chef Battles Arena v2.dc.html      Reference build — the Arena stage (1920×1080)
    Chef Battle Master Console.dc.html Reference build — 8-module operator deck (1920 wide)
    support.js, image-slot.js          Runtime for the two reference files (open them in a browser)
    assets/greenbear.png               Operator avatar used by both

    docs/ORDER_TO_DIRECTOR.md          READ FIRST — what was rejected, canon, working rules, PR gate
    docs/ARENA_VISUAL_CONTRACT.md      Forbidden values, required furniture, fixtures, PR checklist
    docs/ARENA_2D_HANDOFF.md           Layer stack, geometry, numbers, ticket order
    docs/arena.tokens.css              Token set (see OPEN ITEM below)

    mockups/arena.png                  Approved Arena Hall
    mockups/master-console.png         Approved Master Console
    mockups/broadcast.jpg              Approved Battle Broadcast
    mockups/result-winner.jpg          Approved Result / Winner

## How to work with the reference builds

Open the two `.dc.html` files directly in a browser. They are self-contained apart from the
two sibling `.js` files and `assets/`. All geometry is inline CSS with literal numbers —
octagon clip-paths, ring insets, transforms, crowd positions. Port those values verbatim into
the Django templates. Do not re-derive the Arena from prose or from a screenshot.

## ⚠ OPEN ITEM — colour authority changed, docs not yet updated

The Owner has ruled that **the site colour scheme (`CulinEire_colour_font_scheme.pdf`) is
binding for the Arena**. `Chef Battles Arena v2.dc.html` has already been recoloured to it:

- brass `#a67c3a` (+ light `#c49a5c`) replaces the previous gold
- ink `#1f2c25` and its darker steps replace the green hall and panels
- floor: sea-fog `#9fafb0` outer ring, then `#ebe1d2 → #f0e8dc → #f5eee4 → #faf6f0 → #fffdf9`
- challenger `#169b62` (Irish green, LEFT), opponent `#c0492f` (warm red, RIGHT)

`docs/arena.tokens.css` and `ARENA_VISUAL_CONTRACT.md` §0/§1 still carry the OLD rule
(gold + dark green hall, site palette forbidden). **Where they disagree with the recoloured
reference build, the build wins.** Sinus will reconcile the documents next session; until then
take colour from the reference file, not from the token CSS.

`Chef Battle Master Console.dc.html` has NOT been recoloured yet — it is still on the old
gold/green palette. Treat its layout as approved and its colour as pending.

## Still true regardless of palette

- Challenger is always LEFT and green; opponent always RIGHT and red (contract §12).
- Every flag is Irish until a country-data source is approved.
- Phase stepper is one row; the Arena stage is not supported below 1280px.
- Ship fixtures, not zeros: 2.4K viewers, 3.7K votes, 620 gifts, streak 3,
  Aidan Byrne vs Luca Moretti, COOKING 08:37.
- Portraits and dish photos are drop-in image slots; no portrait assets exist yet.

Questions on layout or geometry go to Sinus. Do not guess.
