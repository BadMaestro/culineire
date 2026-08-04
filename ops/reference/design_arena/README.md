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
- `mockups/arena.png` is now here too, placed on the Owner's instruction of
  2026-08-04, 2,609,467 bytes. **It is not the same kind of thing as the
  template, and the difference is the whole reason A06 went wrong.** The mockup
  is the Owner-approved *visual* — 3D and illustration, a picture of the
  intended feeling. The template is what we *implement*. Measure structure,
  geometry and layout against the template; cite the mockup for colour and for
  the approved look, which is what the floor-palette releases already did.
  Building the octagon to a number read off the mockup is the same class of
  error as building it to a number read off the rejected prototype.

## Provenance

Extracted 2026-08-04 from `C:\Users\Denis\Desktop\Arena.zip`
(6,461,788 bytes, dated 2026-07-28), directory `Deployment Project/`. File sizes
here match the archive byte for byte; nothing was edited, reformatted or
regenerated on the way in.

`mockups/arena.png` added 2026-08-04 by Bolt on the Owner's instruction, copied
from `Arena/Deployment Project/mockups/arena.png` on the workstation. Four copies
of it existed on that machine, in the extract directories, the scratchpad and the
prompts folder; all four are the same file — sha256
`b9b6ea3af9ed65b8…`, 2,609,467 bytes — so there was no version to choose between.
The `-text` attribute above covers this subdirectory too, which is what keeps the
PNG byte-identical through a Windows checkout.
