# ORDERS → ARENAFRONT

Written by Bolt, Production Director. Tracked in git on `main`. Keep this file
open in your window: every order lands here, newest at the top, and the Owner
watches it arrive.

Your lane is ARENA VISUAL ASSETS through the paid image system, plus
`static/img/arena/**`, `static/css/arena_atmosphere.css` and
`static/images/crowd/`. Site-wide work is Bolt's and never yours.

Answer in CoWork to `bolt`, one line, with a hash and a number.

---

## ORDER B1 — verify the `round/` face set

**Status: OPEN. Issued 2026-07-26 12:30 Dublin.**

Confirm the set that will actually be wired: 96 files, all distinct, all the
same pixel size, and report the total byte weight.

The ruling stands: wire `round/` — 96 files, 400 KB — not `tiers/`, which is 288
files and 1,124 KB to express a near/mid/far difference that is brightness and
blur, both free in CSS off `rowDepth`. Overturn it only with a MEASUREMENT
showing what a CSS filter cannot do. An opinion will not.

Report: `B1 | files=<n> | distinct=<n> | size_px=<w>x<h> | total_bytes=<n>`

---

## QUEUED

| # | Order | Done when |
|---|-------|-----------|
| B2 | Contact sheets move to `ops/audits/`, never `static/` | Treated as a merge condition of your a3 branch, not a commit on main |
| B3 | Your 48px icon set at `2b7f72ff` stays unmerged and intact | Nothing deleted. Overturn the 96px ruling only with a measurement at 66 device px |

Why 96px won: the icons render at 1.35rem, about 22 CSS px, which is 66 DEVICE px
on a 3x phone. A 48px source upscales there — rendered side by side at 66px, the
mortar engraving, the laurel separation, the chest clasp and the knife-roll
buckle all turn to blobs. The 96px set costs 19,516 more bytes on a page that
shed 5,350,000.

---

## What is true about your work right now

Your crowd assets are finished and good: 96 faces with head rotation, plus the
round and tier derivations at zero API cost. They are sitting in a branch doing
nothing, because the wiring that uses them has not merged. Assets that never ship
are not delivered work, and that is a sequencing failure — mine, not yours.

## Rules that cost us a day

- Read the peer's DIFF and the INBOX before reporting. Twice you reported against
  code state without order state, and both times it produced waste.
- Never present a local render as evidence. Production is the only test
  environment.
- Report a hash and a number.
