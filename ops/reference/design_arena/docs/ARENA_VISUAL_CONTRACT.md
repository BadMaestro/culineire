# ARENA VISUAL CONTRACT — v1

Binding for every ticket touching `/chef-battle/arena/` and `/chef-battle/master/`.
Source of truth: the approved Arena mockups (`uploads/arena.png`, `uploads/photo_2026-07-18_18-19-13.jpg`,
`uploads/9065d5fd-*.png`) and the reference build `Chef Battles Arena v2.dc.html` /
`Chef Battle Master Console.dc.html`.

A PR that fails any MUST below is rejected without review.

---

## §0 THE TRAP — read before writing any CSS

`CulinEire_colour_font_scheme.pdf` is the **site** palette (parchment `#faf6f0`, forest `#184c3a`,
brass `#a67c3a`). It is **NOT** the Arena palette. The Arena is a dark hall.

The build at `culineire.ie/chef-battle/arena/` dated 27 Jul 2026 applied the site palette to the
Arena. That is the failure this document exists to prevent.

**MUST NOT** appear anywhere on the Arena stage or Master Console:
`#faf6f0`, `#fffdf9`, `#f5eee4`, `#f3f2ee`, `#184c3a`, `#a67c3a`, `#9fafb0`,
or any background lighter than `#1a3326`.

---

## §1 PALETTE — the only legal values

There is exactly one token set: **`docs/arena.tokens.css`**, which is the machine-readable form of
`ARENA_2D_HANDOFF.md` §1. Copy that file in and reference the names. Do not restate the hexes,
do not invent parallel names, do not inline literals (Technical Standards §7).

The shape of it: dark green hall (`--arena-hall-1..3`), gold accents (`--arena-gold`,
`--arena-gold-light`), parchment floor rings (`--arena-floor-*`), green challenger LEFT
(`--arena-challenger`), red opponent RIGHT (`--arena-opponent`).

The parchment floor is the **only** light surface in the design. It is a lit floor inside a dark
hall, not a page background. If the whole viewport reads light, the build is wrong.

## §2 TYPE

- Display / numerals / titles: **Playfair Display** 400/600/700
- UI / labels / body: **Inter** 400/500/600/700
- Eyebrow labels: Inter 700, `letter-spacing:.14em`, uppercase, `#7f8f86`
- No third family. No system-serif fallback rendering in production.

## §3 GEOMETRY

- Floor is an **octagon** — `clip-path: polygon(29% 0,71% 0,100% 29%,100% 71%,71% 100%,29% 100%,0 71%,0 29%)`,
  laid flat with `perspective:1000px; rotateX(58deg)`.
- Concentric tile rings: gold rim → dark gap → 4 parchment rings → cool ring → centre disc.
- Chef plinths are octagons; crown holder is a hexagon.
- Phase stepper is **one row, never two**. Below 1280px it scrolls horizontally.
  Viewports under 1280px are out of scope for the Arena stage.
- Tier ladder: vertical pill stack, centre of the floor, above the crown holder (per mockup).

## §4 REQUIRED FURNITURE (Arena stage)

Every one of these MUST be present and populated:

1. Site header — logo, nav (Arena active), Welcome-back pill, Fandom / Rewards / Shop
2. Phase stepper 1–7, active phase gold-filled, plus status line
   `LIVE COOKING IN PROGRESS · CHEFS EARNING THE CROWD`
3. Top-left: Phase panel — phase name, countdown, "Next: …"
4. Top-right: Arena pulse — Active Viewers / Public Votes / Battle Gifts / Crown Streak
5. Centre: octagon floor, two chef plinths (green left, red right), crown holder centre
6. Tier ladder pill stack
7. Bottom-left: Today's Crown Ladder — top 4 with crown counts + View Full Ladder
8. Bottom-right: Recent Battle Gifts — 3 entries with token amounts + Send a Gift
9. Bottom: chat ticker strip — Top Supporter + rolling messages + Join the Crowd
10. Tiered crowd ring — dense, multi-row, silhouettes with warm rim light

## §5 CONTENT STATE

The Arena is a **live-fixture** surface. Shipping it with zeros and "No X yet" everywhere is a
failed build. Every widget MUST render a seeded demo fixture until real data is wired, and the
fixture MUST match the mockup numbers: 2.4K viewers, 3.7K votes, 620 gifts, streak 3,
Aidan Byrne vs Luca Moretti, phase COOKING 08:37.

Crowd MUST NOT be rendered as grey dots. Use portrait sprites or, until assets exist,
the placeholder slot component — never a dot grid.

## §6 TEXT INTEGRITY

No visible truncation on the reference viewport (1920×1080). "Green…" for "GreenBear" is a
rejection. Name plates size to content; do not fix their width.

## §7 ACCEPTANCE CHECKLIST — paste into every Arena PR

- [ ] No hex from §0 forbidden list appears in the diff (grep the diff, not the file)
- [ ] Screenshot at 1920×1080 placed side by side with `uploads/arena.png` in the PR body
- [ ] All 10 items of §4 present
- [ ] All widgets show §5 fixture values, no zeros, no empty states
- [ ] Phase stepper on one row
- [ ] No truncated text anywhere
- [ ] Green is left, red is right, gold is neutral/crown — no exceptions
- [ ] Crowd is not a dot grid

## §8 WORKING WITH THE REFERENCE BUILD

Do not re-derive the Arena from prose. Open `Chef Battles Arena v2.dc.html` and
`Chef Battle Master Console.dc.html`, lift the literal values — hexes, clip-paths, transforms,
ring insets, font sizes — and port them into Django templates. Any deviation from the reference
must be raised as a question BEFORE implementation, not discovered in review.

Questions to Sinus. Do not guess on palette or layout.
