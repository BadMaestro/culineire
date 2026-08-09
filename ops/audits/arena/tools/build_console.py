import os
"""AN-R2/3 — the Master Console mirror, in the engine, with the console's own
stylesheet order.

The console view is staff-gated and I have no staff session, so this does not
render the console's DATA. It does not need to: the question item 2 asks is
about GEOMETRY and CAMERA ownership, and that is decided entirely by

    the markup the console includes   (_arena_render_ring.html, whole)
    the body classes it sets          (page--amc page--arena page--arena-mirror)
    the sheets it loads, in order     (arena.css, arena_master_console.css,
                                       arena_console_mirror.css)

all three of which are in the repository and are reproduced here exactly. The
octagon markup is lifted from the arena harness, so it is the same SVG the same
renderer built.
"""
import io, os, re

ROOT = "/mnt/e/CulinEire Project/CulinEire/CulinEire"
CSS = os.path.join(ROOT, "static", "css")
OUT = os.environ.get("ARENA_HARNESS_OUT",
       os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out"))

arena = io.open(os.path.join(OUT, "b.html"), encoding="utf-8").read()

# the container and everything in it, exactly as the console includes it
i = arena.index('<div class="arena-render-container">')
depth, j = 0, i
while True:
    m = re.compile(r"</?div\b").search(arena, j)
    depth += 1 if arena[m.start():m.start() + 5] == "<div " or arena[m.start():m.start() + 4] == "<div" and arena[m.start() + 4] in " >" else -1
    j = m.end()
    if depth == 0:
        j = arena.index(">", j) + 1
        break
ring = arena[i:j]

# the console's stylesheet order, verbatim from arena_master_console.html
SHEETS = ["base.css", "header.css", "footer.css",
          "arena.css", "arena_master_console.css", "arena_console_mirror.css"]
styles = []
for name in SHEETS:
    path = os.path.join(CSS, name)
    if os.path.exists(path):
        styles.append('<style data-sheet="%s">\n%s\n</style>'
                      % (name, io.open(path, encoding="utf-8").read()))

page = """<!doctype html>
<meta charset="utf-8">
<title>Master Console mirror — geometry harness</title>
%s
<body class="page--amc page--arena page--arena-mirror">
  <div class="amc-page">
    <section class="amc-overview">
      <article class="amc-chef amc-chef--one"><h2>Chef #1</h2></article>
      <div class="amc-ring">
%s
      </div>
      <article class="amc-chef amc-chef--two"><h2>Chef #2</h2></article>
    </section>
  </div>
</body>
""" % ("\n".join(styles), ring)

io.open(os.path.join(OUT, "console.html"), "w", encoding="utf-8").write(page)
print("console.html %d bytes, ring %d bytes, %d sheets" % (len(page), len(ring), len(styles)))
