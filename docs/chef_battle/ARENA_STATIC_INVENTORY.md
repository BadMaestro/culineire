# Static asset inventory — AN22, master task section 15

**2026-08-08, at v2.5.944.** 627 assets under `static/`, 117.3 MB.
**Nothing was deleted, resized or re-encoded.** Section 15's own rule is that an
original the company paid for is REPORTED, not altered, and three of the four
categories below are exactly that kind of file.

| Category | Files | Size | What it is |
|---|---:|---:|---|
| **REFERENCED** | 188 | 53.6 MB | named by a template, a stylesheet, a script or Python |
| **ORIGINAL** | 28 | 43.9 MB | a master nothing names, sitting beside the derivative everything names — `categories/salads.png` next to `salads.webp` |
| **UNREFERENCED** | 411 | 19.8 MB | named by nothing in the repository |
| **RESIDUE** | 35 | 3.2 MB | on the server only, for files the repository no longer contains |

---

## UNREFERENCED is not UNUSED, and the breakdown says why

| Where | Files | Size | Reading |
|---|---:|---:|---|
| `images/crowd/tiers/` | 288 | 1.15 MB | the near/mid/far depth tiers. Superseded by a decision, not by neglect: `_arena_render_ring.html` records it — *"depth via CSS filter (rowDepth), not tiers/"*. Generated assets from a paid pass. |
| `images/crowd/` | 99 | 0.35 MB | crowd faces beyond the 96 the template lists by name |
| `images/` | 14 | 18.29 MB | old logo cuts and two UUID-named uploads: `kitchen-logo.png`, `logo-culineire-header-transparent.png`, `logo-social.png`, `logo3.png` and their neighbours |
| `images/chef_battle/` | 10 | 0.01 MB | battle art no current template names |

**None of it is proposed for deletion.** 17.10 is explicit: never delete an
asset the Owner paid for or approved. Three of these four groups are exactly
that, and the fourth — the UUID uploads — cannot be told apart from live
content by a filename. This is an inventory; what leaves the tree is his call.

**One asset is over four megapixels:** `images/logo-social.png`, 2085×2084,
0.76 MB, and nothing references it. Reported, untouched.

---

## RESIDUE — the only finding that is a defect

35 files, 3.2 MB, sit in `/srv/culineire/shared/staticfiles/css` for stylesheets
that **no longer exist in the repository**: every historical hash of
`arena_command_deck.css`, `arena_hall.css`, `arena_deck_polish.css`,
`arena_render.css` and `arena_effects.css`, deleted across AN4 and AN12.

`collectstatic` copies and never deletes. The manifest references none of them,
and `curl` still serves each one a 200. Nothing on the site loads them, so this
costs disk rather than correctness — but a deleted file that a URL still answers
is the kind of thing that makes an audit disbelieve its own numbers later.

It was NOT removed under this card: deleting files on production is outside a
static inventory, and `collectstatic --clear` would take out every asset on the
box before re-copying them, which is a far larger action than the problem.

**The safe removal, when the Owner wants it**, is a targeted delete of exactly
those five stems and nothing else, verified against the manifest first:

```bash
cd /srv/culineire/shared/staticfiles/css
python3 - <<'PY'
import json, os, glob
manifest = json.load(open("../staticfiles.json"))["paths"]
stems = ("arena_command_deck", "arena_hall", "arena_deck_polish",
         "arena_render", "arena_effects")
kept = set(os.path.basename(v) for v in manifest.values())
doomed = [f for s in stems for f in glob.glob(s + "*.css")
          if os.path.basename(f) not in kept]
print(len(doomed), "files,", sum(os.path.getsize(f) for f in doomed), "bytes")
for f in doomed[:10]:
    print("   ", f)
PY
```

It counts first and shows examples before anything is removed, which is the
rule 17.10 asks for. Run it, read it, and only then delete.
