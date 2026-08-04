# ORDER TO DIRECTOR — Arena visual authority

    from:      Sinus (2D reference / visual)
    to:        Director
    date:      2026-07-27
    subject:   Arena + Master Console — visual canon, rejected build, working rule
    authority: subordinate to /AGENTS.md and the product contract; escalate conflicts to the Owner

---

## 1. What happened

The build at `culineire.ie/chef-battle/arena/` (27 Jul 2026) applied the **site** palette
(`CulinEire_colour_font_scheme.pdf` — parchment `#faf6f0`, forest `#184c3a`, bronze `#a67c3a`)
to the Arena stage. The Arena is a **dark hall**. The result is not a variant; it is a
palette substitution and it is rejected.

Secondary defects in the same build:

- every live widget renders zeros / "No X yet" — a live-fixture surface shipped empty
- the crowd is a grey dot grid, not spectators
- the crown holder plate truncates: `Green…` for `GreenBear`
- the floor does not fill the stage; the composition reads as a diagram, not an arena

## 2. Canon — not open for interpretation

All five approved mockups agree, and contract §12 agrees with them:

    dark green hall  ·  gold accents  ·  parchment floor
    green challenger LEFT  ·  red opponent RIGHT

Approved mockups: `arena.png`, `photo_2026-07-18_18-19-13.jpg` (Arena Hall),
`photo_2026-06-07_12-06-16.jpg` (Broadcast), `photo_2026-06-08_15-50-02.jpg` (Result),
`9065d5fd-…png` (Master Console).

"Brass gala" is a theme toggle inside the reference file only. It is **not** the canon and
must not reach production.

## 3. Governing documents — three files, in this precedence

1. `docs/arena.tokens.css` — the token set. Copy in as-is, reference by name.
   Machine-readable form of handoff §1; the two cannot diverge.
2. `docs/ARENA_VISUAL_CONTRACT.md` — forbidden values, required furniture,
   fixture requirement, and the **PR acceptance checklist** (§7).
3. `docs/ARENA_2D_HANDOFF.md` — layer stack, geometry, numbers, ticket order.

Reference builds to port from, not to reinterpret:
`Chef Battles Arena v2.dc.html`, `Chef Battle Master Console.dc.html`.

## 4. Working rule — what I need you to enforce

1. **No palette derivation from prose or from the site PDF.** Arena colour comes from
   `arena.tokens.css` and nowhere else.
2. **Port, don't reinvent.** Open the reference `.dc.html`, lift the literal values
   (hexes via tokens, clip-paths, transforms, ring insets, type sizes) into the Django
   templates. Any intended deviation is a question to me **before** implementation,
   not a discovery at review.
3. **PR gate.** No Arena PR is reviewed without: a 1920×1080 screenshot placed beside
   `uploads/arena.png` in the PR body, and every box of Visual Contract §7 ticked.
   Grep the diff for the §0 forbidden hexes — that check is mechanical, there is nothing
   to argue about.
4. **Fixtures, not zeros.** Until real data is wired, every widget renders the mockup
   fixture: 2.4K viewers, 3.7K votes, 620 gifts, streak 3, Aidan Byrne vs Luca Moretti,
   COOKING 08:37.

## 5. Rebuild scope for the current Arena page

Order of work — 1 and 2 make the page recognisable, the rest is furniture:

1. Replace the palette with `arena.tokens.css`; hall dark, floor parchment.
2. Crowd: dense tiered ring of spectator sprites with warm rim light. No dot grid.
3. Chef plinths: green octagon left, red octagon right, portraits, flag chip, name plate
   that sizes to its content.
4. Tier ladder: vertical pill stack centred on the floor, above the crown holder.
5. Bottom-left Crown Ladder (top 4 + View Full Ladder); bottom-right Recent Battle Gifts
   (3 entries + Send a Gift); bottom chat ticker with Top Supporter + Join the Crowd.
6. Top strip: `LIVE COOKING IN PROGRESS · CHEFS EARNING THE CROWD`; top-right Arena pulse
   with the four fixture counters.

## 6. Open items requiring the Owner, not me

- Confirm the token names in handoff §1 / `arena.tokens.css`. Renaming after ARENA-01
  ships is expensive; confirm before the first merge.
- §1 + §16 roster amendment so Sinus and Director are on the record with defined authority.

Questions on palette, layout, or geometry come to me. Do not guess.

— Sinus
