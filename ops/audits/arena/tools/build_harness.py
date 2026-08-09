import os
"""AN12 - build two pages that differ ONLY in how the Arena CSS is packaged.

Page A carries the four sheets exactly as production loaded them before this
card.  Page B carries the two the card produces.  Both wrap the same DOM,
captured read-only from the arena view, so a difference in any computed style
is caused by the packaging and by nothing else.

This proves a fact about the STYLESHEETS.  It is not a claim about how the
Arena looks - appearance is judged on production and nowhere else.
"""
import re, os, sys, subprocess

ROOT = "/mnt/e/CulinEire Project/CulinEire/CulinEire"
CSS = os.path.join(ROOT, "static", "css")
OUT = os.environ.get("ARENA_HARNESS_OUT",
       os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out"))
os.makedirs(OUT, exist_ok=True)

dom = open(os.path.join(OUT, "arena_dom.html"), encoding="utf-8").read()
body = re.sub(r'<link[^>]+rel="stylesheet"[^>]*>', "", dom)
# keep the scripts: the renderer builds the octagon, and its 1900 SVG
# cells are most of what the render sheet has rules for
import time
STAMP = str(int(time.time()))
# the browser caches these by URL, and a stale arena_octagon.js is a
# measurement of the wrong file
body = re.sub(r'"/static/([^"]+)"',
              lambda m: '"http://localhost:8765/' + m.group(1) + '?v=' + STAMP + '"',
              body)
# site-wide sheets load before the arena's and are the same on both pages
SITE = [n for n in re.findall(r'href="[^"]*?/css/([\w.]+\.css)', dom)
        if not n.startswith("arena")]


def at_head(name):
    """The file as it stood before this card (git HEAD)."""
    return subprocess.run(["git", "show", "HEAD:static/css/" + name],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def on_disk(name):
    return open(os.path.join(CSS, name), encoding="utf-8").read()


def page(path, sheets):
    styles = "\n".join("<style data-sheet=\"%s\">\n%s\n</style>" % (label, text)
                       for label, text in sheets)
    html = body.replace("</head>", styles + "\n</head>", 1)
    open(os.path.join(OUT, path), "w", encoding="utf-8").write(html)
    print("%-8s %d sheets, %d bytes" % (path, len(sheets), len(html)))


site = [(n, on_disk(n)) for n in dict.fromkeys(SITE) if os.path.exists(os.path.join(CSS, n))]
print("site sheets carried on both pages:", [n for n, _ in site])

#page("a.html", site + [(n, at_head(n)) for n in
#                       ("arena_effects.css", "arena.css",
#                        "arena_atmosphere.css", "arena_render.css")])
page("b.html", site + [(n, on_disk(n)) for n in
                       ("arena.css", "arena_atmosphere.css")])
