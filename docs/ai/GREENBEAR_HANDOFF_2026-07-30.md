# GreenBear handoff — 2026-07-30 (pre-compaction)

Production: **v2.5.750**. `origin/main` = local, tree clean, no open branches.

## Standing rules the Owner hardened today

- **Half the text.** No step narration, no explaining how I got there. Finding →
  decision → question.
- **Never report who broke what or when.** Five developers have touched this
  project; blame archaeology burns tokens and he does not care. State the fact,
  fix it. No self-justification.
- **No initiative.** Only the plan and his orders. Never take a product decision
  (what is on screen, its colour, its geometry).
- **Colours of the arena and the octagon are FROZEN.** He said this twice; I broke
  it once (moat colour) and it cost his patience. Palette work is closed (AR2).
- **Verify in the browser BEFORE deploying.** Every runtime break today shipped
  because `node --check` proves syntax only.
- Confirmations: `diff` fence + **each answer in its own code block**.

## The reference chain (settled today)

1. `mockups/arena.png` — the Owner-approved visual. **3D + illustration, we are
   not building this yet.**
2. `Chef Battles Arena v2.dc.html` — the Design Template, derived from it. **This
   is what we implement.** Unpacked from `C:\Users\Denis\Desktop\Arena.zip` to the
   scratchpad; served locally on `127.0.0.1:8794`.
3. The vendored `ops/prototypes/arena_visual_shell/` is **NOT** the reference —
   he rejected it.

Current task framing: **transfer functionality from the template and merge it with
ours.** Not colours, not the octagon.

## Functional deltas against the template (measured, not guessed)

Missing on our side, with the board card that owns each:

| Gap | Card |
|---|---|
| Two fighters flanking the crown — name + country + flag | **A09** |
| `Send a Gift` action in the gifts panel | **A13** |
| `Join the Crowd` + rolling supporter messages in the ticker | **A14** |
| Phase 5 named `MOD REVIEW` (ours: `REVIEW`) | **A11** |
| `Fandom / Rewards / Shop` entries in the masthead | **no card yet** |

Ours that the template lacks — keep: Treasury, Artifacts, Knife Roll, Changing
Room, Issue a Challenge.

## Board

AR1, AR2, AR3 **DONE**. **AR4 is NEXT** (author seat rows, two top and two
bottom). A09 is the Owner's stated priority but is dependency-chained behind
A07 → AR5; he has not yet approved re-sequencing.

## Shipped today (v2.5.728 → v2.5.750)

- `--ink` neutralised sitewide (`#1f2c25` → `#292929`): it was a dark **green**
  and painted the whole hall on mobile. Luminance-matched, contrasts unchanged.
- **One visual style, the desktop one.** All width media queries removed from
  arena CSS (131 → 2; only `prefers-reduced-motion` remains). Desktop verified
  byte-identical against a captured baseline.
- **One widget system**: four variables on `.page--arena`
  (`--arena-widget-bg/-border/-radius/-shadow`) + one selector list now drive all
  seven arena widgets, including the phase rail that had been left out.
- AR3: eight lanterns in the moat, each breathing on its own clock.
- VIP ring: 32 boxes, velvet fill, gold liner, `SPONSORS` at the corners and
  `V·I·P` between — **the word is still cut in half, not bent**; the fix is a
  single `<text>` on a `<textPath>` whose guide turns at the vertex.
- Chef click restored (listener on the container; the chef is resolved from the
  portrait's on-screen box) and the card now opens beside the chef (it is
  `position: fixed` inside a transformed ancestor, so it had to move to `<body>`).
- Deleted: the `Rank ladder` ::before caption that ran down the centre of the
  floor, and the eight glint plates around the crown.

## Open / unverified

1. The eight glint plates were removed in v2.5.750 — **not verified by eye**.
2. Chefs were not visible on the floor in the last screenshot — **check first**.
3. `SPONSORS` still split, not bent.
4. The heading overlaps the octagon at browser zoom; the real fix belongs in
   `fitScene`, not CSS.
5. Crown-ladder chips lost their background in an earlier over-broad edit.

## Rollbacks

- Glint plates only: `git revert ffbf1123`
- Style unification: `git reset --hard rollback/pre-unify-v2.5.728`
- The whole eleven-ring arc: `git reset --hard rollback/pre-ar1-v2.5.708`

Then `deploy.sh` and verify over HTTP, never by service status.
