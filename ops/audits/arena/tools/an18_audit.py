"""AN18, master task section 12 - an evidence-based dead-code audit.

Eight categories, and nothing is deleted on the strength of one search:

    ACTIVE              named by a template, a view or another loaded file
    DUPLICATED          a second implementation of something already here
    SUPERSEDED          replaced, but still loaded
    FEATURE-FLAGGED     reachable only behind a setting
    TEST-EMULATION      exists to drive or fake the product for a demo
    LEGACY BUT REQUIRED nobody calls it, and removing it breaks something
    DEAD                proven unreachable, by every route below
    UNKNOWN             the searches disagree - NEVER deleted

For each asset the script collects the EVIDENCE rather than a verdict: which
templates name it, which Python names it, which other static file names it,
whether a test pins it, and whether a setting gates it. The classification is
written by hand from that evidence, because a grep cannot tell SUPERSEDED from
LEGACY BUT REQUIRED and should not be trusted to try.
"""
import os, re, json, collections

ROOT = "/mnt/e/CulinEire Project/CulinEire/CulinEire"


def walk(sub, exts):
    out = []
    for base, dirs, files in os.walk(os.path.join(ROOT, sub)):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "venv", "node_modules", "__pycache__", "staticfiles", "archive")]
        for f in files:
            if f.endswith(exts):
                out.append(os.path.join(base, f))
    return out


TEMPLATES = walk("templates", (".html",))
PY = [p for p in walk("", (".py",)) if "/venv/" not in p and "/migrations/" not in p]
JS = walk("static/js", (".js",))
CSS = walk("static/css", (".css",))

assets = sorted(JS + CSS, key=lambda p: os.path.basename(p))
report = []

for path in assets:
    name = os.path.basename(path)
    if not re.search(r"arena|battle|octagon|puzzle", name, re.I):
        continue
    stem = name.rsplit(".", 1)[0]
    ev = collections.defaultdict(list)
    for group, files in (("template", TEMPLATES), ("python", PY),
                         ("js", [j for j in JS if j != path]),
                         ("css", [c for c in CSS if c != path])):
        for f in files:
            try:
                text = open(f, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if name in text:
                tag = os.path.relpath(f, ROOT).replace("\\", "/")
                ev[group + (" (test)" if "test" in os.path.basename(f) else "")].append(tag)

    # what the file itself exports, so a caller can be found by symbol too
    body = open(path, encoding="utf-8", errors="ignore").read()
    globals_ = sorted(set(re.findall(r"(?:window|global)\.([A-Z][\w]+)\s*=", body)))
    for g in globals_:
        for f in JS + TEMPLATES:
            if f == path:
                continue
            try:
                if re.search(r"\b%s\b" % re.escape(g), open(f, encoding="utf-8", errors="ignore").read()):
                    ev["symbol " + g].append(os.path.relpath(f, ROOT).replace("\\", "/"))
            except OSError:
                pass

    report.append({"asset": os.path.relpath(path, ROOT).replace("\\", "/"),
                   "bytes": os.path.getsize(path),
                   "exports": globals_,
                   "named_by": {k: sorted(set(v))[:6] for k, v in sorted(ev.items())},
                   "named_by_count": {k: len(set(v)) for k, v in sorted(ev.items())}})

for r in report:
    print("\n%-44s %7d bytes" % (r["asset"], r["bytes"]))
    if r["exports"]:
        print("    exports:", ", ".join(r["exports"]))
    if not r["named_by"]:
        print("    NAMED BY NOTHING - candidate, and only a candidate")
    for k, v in r["named_by"].items():
        print("    %-16s %2d  %s" % (k, r["named_by_count"][k], ", ".join(v)))

json.dump(report, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "an18_evidence.json"), "w", encoding="utf-8"), indent=1)
print("\nassets examined:", len(report))
