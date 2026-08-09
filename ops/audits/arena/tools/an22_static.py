"""AN22, master task section 15 - the static asset inventory.

Four categories, and an original the company paid for is REPORTED, never
altered:

    REFERENCED      named by a template, a stylesheet, a script or Python
    UNREFERENCED    named by nothing in the repository
    OVERSIZED       referenced, but far larger than the box it is drawn in
    RESIDUE         on the server only - collectstatic copies and never deletes

The first three are read from the repository. The fourth is read from the
deployment and is the only one that needs the server.
"""
import os, re, json, struct, collections

ROOT = "/mnt/e/CulinEire Project/CulinEire/CulinEire"
STATIC = os.path.join(ROOT, "static")
ASSET = re.compile(r"\.(png|jpe?g|webp|gif|svg|ico|avif|woff2?|ttf|mp4|webm)$", re.I)


def sources():
    out = []
    for sub in ("templates", "static/css", "static/js"):
        for base, dirs, files in os.walk(os.path.join(ROOT, sub)):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "archive")]
            out += [os.path.join(base, f) for f in files]
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "venv", "node_modules", "__pycache__", "staticfiles",
                    "static", "templates", "docs", "ops", "scratchpad")]
        out += [os.path.join(base, f) for f in files if f.endswith(".py")]
    return out


HAYSTACK = []
for f in sources():
    try:
        HAYSTACK.append(open(f, encoding="utf-8", errors="ignore").read())
    except OSError:
        pass
BLOB = "\n".join(HAYSTACK)


def dimensions(path):
    """Width and height for the formats that carry them in the first bytes."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(64)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", head[16:24])
                return w, h
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                if head[12:16] == b"VP8X":
                    w = int.from_bytes(head[24:27], "little") + 1
                    h = int.from_bytes(head[27:30], "little") + 1
                    return w, h
                if head[12:16] == b"VP8 ":
                    w = int.from_bytes(head[26:28], "little") & 0x3FFF
                    h = int.from_bytes(head[28:30], "little") & 0x3FFF
                    return w, h
                if head[12:16] == b"VP8L":
                    b = int.from_bytes(head[21:25], "little")
                    return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
    except OSError:
        pass
    return None, None


rows = []
for base, dirs, files in os.walk(STATIC):
    dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
    for f in files:
        if not ASSET.search(f):
            continue
        path = os.path.join(base, f)
        rel = os.path.relpath(path, STATIC).replace("\\", "/")
        size = os.path.getsize(path)
        named = f in BLOB or rel in BLOB
        w, h = dimensions(path)
        rows.append({"file": rel, "bytes": size, "w": w, "h": h, "referenced": named})

rows.sort(key=lambda r: -r["bytes"])

# A .png that nothing names, next to a .webp that everything names, is not an
# unused file - it is the ORIGINAL the derivative was made from, and section 15
# says an original the company paid for is reported and never altered.
by_stem = collections.defaultdict(list)
for r in rows:
    by_stem[os.path.splitext(r["file"])[0].lower()].append(r)
for r in rows:
    stem = os.path.splitext(r["file"])[0].lower()
    r["original_of"] = (not r["referenced"]
                        and any(o["referenced"] for o in by_stem[stem] if o is not r))

unref = [r for r in rows if not r["referenced"] and not r["original_of"]]
originals = [r for r in rows if r["original_of"]]
print("ORIGINALS behind a referenced derivative: %d, %.1f MB"
      % (len(originals), sum(r["bytes"] for r in originals) / 1e6))
big = [r for r in rows if r["w"] and r["w"] * r["h"] > 4_000_000]

print("assets:", len(rows), " total MB: %.1f" % (sum(r["bytes"] for r in rows) / 1e6))
print("\nUNREFERENCED (%d):" % len(unref))
for r in unref:
    print("   %-56s %8d bytes" % (r["file"], r["bytes"]))
print("\nOVER 4 MEGAPIXELS (%d):" % len(big))
for r in big:
    print("   %-56s %5dx%-5d %8d bytes  referenced=%s"
          % (r["file"], r["w"], r["h"], r["bytes"], r["referenced"]))
print("\nTEN HEAVIEST:")
for r in rows[:10]:
    print("   %-56s %8d bytes  %s" % (r["file"], r["bytes"],
                                      ("%dx%d" % (r["w"], r["h"])) if r["w"] else ""))

json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "an22_inventory.json"), "w", encoding="utf-8"), indent=1)
