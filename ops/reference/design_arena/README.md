# The Design Template — the Arena reference we implement

Placed here on the Owner's instruction, 2026-08-04.

## What this is

`Chef Battles Arena v2.dc.html` is **the** reference for the Arena's visual
target. Everything measured for an Arena card is measured against this file.

It is a self-contained export: it needs `image-slot.js`, `support.js` and
`assets/greenbear.png`, all of which sit beside it here, plus Google Fonts over
the network. Open it directly in a browser and it renders.

`Chef Battle Master Console.dc.html` is the same export's Master Console page.
The Master Console is outside the current Arena plan; it is kept because it came
from the same source and splitting a reference in half is how half of it goes
missing.

`docs/` carries the written half of the same handoff: the visual contract, the
2D handoff notes, the token sheet, and the original README as
`ORIGINAL_README.md`.

## Why it is in the repository at all

Because until 2026-08-04 it was not, and that cost real work.

The A06 measurement matrix (`ops/audits/arena/A06_measurement_matrix_2026-07-29.md`)
states its reference source in its own lines 6–8: the vendored prototype at
`ops/prototypes/arena_visual_shell/`. The Owner had **rejected** that prototype.
So the matrix's headline figure — widen and flatten the octagon from aspect 1.30
to 2.05, handed straight to card A07 — was measured against a source that had
been thrown away. Nobody caught it for six days, and A07 was one instruction away
from reshaping the octagon to it.

The template itself was no safer to cite. It lived only inside
`C:\Users\Denis\Desktop\Arena.zip` on one workstation, and a measurement whose
source cannot be opened by the other agent, or by the Owner, or by either of us
next month, cannot be re-run, reviewed or disproved. That is not a filing
problem, it is an evidence problem: it makes a wrong number and a right one look
identical.

A reference that is not in the repository is not a reference. It is a rumour.

## The rule this sets

- Measure against **this** directory. Cite the file and the path in the audit.
- Do not measure against `ops/prototypes/arena_visual_shell/` — it is the
  rejected prototype and is kept only as evidence. See the REJECTED note beside
  it.
- `mockups/arena.png` is cited across the Arena stylesheets as the Owner-approved
  visual and is **not** in this repository either. It is in the same zip, 2.6 MB.
  Left out here deliberately rather than quietly: the Owner asked for the
  template, and 5 MB of mockups is his call to make, not mine to assume.

## Provenance

Extracted 2026-08-04 from `C:\Users\Denis\Desktop\Arena.zip`
(6,461,788 bytes, dated 2026-07-28), directory `Deployment Project/`. File sizes
here match the archive byte for byte; nothing was edited, reformatted or
regenerated on the way in.
