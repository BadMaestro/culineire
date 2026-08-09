"""AN20, master task section 13 - where the renderer reads and writes layout
in the same pass.

A READ is anything that forces the browser to have a current layout:
getBoundingClientRect, getComputedStyle, offset*/client*/scroll*, getBBox.
A WRITE is anything that invalidates it: style.setProperty, style.foo = ,
setAttribute on a geometric attribute, classList changes, textContent.

Reading after writing inside one function is a forced synchronous reflow. The
section asks for the two to be separated: measure everything, then write
everything.
"""
import re, sys, collections

PATH = "static/js/arena_render.js"
src = open(PATH, encoding="utf-8", newline="").read().replace("\r\n", "\n")
lines = src.split("\n")

READ = re.compile(r"getBoundingClientRect|getComputedStyle|\.offset(Width|Height|Top|Left)"
                  r"|\.client(Width|Height|Top|Left)|\.scroll(Width|Height|Top|Left)|getBBox\(")
WRITE = re.compile(r"\.style\.(setProperty|[a-zA-Z]+\s*=)|setAttribute\(\s*['\"](x|y|width|height|"
                   r"points|transform|viewBox|d|cx|cy|r|rx|ry|x1|x2|y1|y2)['\"]"
                   r"|\.classList\.(add|remove|toggle)|\.textContent\s*=|\.innerHTML\s*=")

# crude but sufficient: a function body is from `function name(` to the line
# whose indentation returns to the declaration's level with a closing brace
funcs = []
for i, line in enumerate(lines):
    m = re.match(r"(\s*)(?:function\s+(\w+)|(?:var|const|let)\s+(\w+)\s*=\s*function)\s*\(", line)
    if not m:
        continue
    indent, name = m.group(1), m.group(2) or m.group(3)
    close = indent + "}"
    end = len(lines) - 1
    for j in range(i + 1, len(lines)):
        if lines[j].rstrip() == close or lines[j].rstrip() == close + ";":
            end = j
            break
    funcs.append((name, i + 1, end + 1))

rows = []
for name, start, end in funcs:
    reads, writes = [], []
    for n in range(start, end):
        text = lines[n - 1]
        if text.lstrip().startswith("//") or text.lstrip().startswith("*"):
            continue
        if READ.search(text):
            reads.append(n)
        if WRITE.search(text):
            writes.append(n)
    if not reads or not writes:
        continue
    # a read that happens AFTER a write in the same function forces a reflow
    forced = [r for r in reads if any(w < r for w in writes)]
    rows.append({"fn": name, "lines": (start, end), "reads": len(reads),
                 "writes": len(writes), "reads_after_a_write": len(forced),
                 "first_forced": forced[0] if forced else None})

rows.sort(key=lambda r: -r["reads_after_a_write"])
print("%-34s %6s %6s %8s %s" % ("function", "reads", "writes", "forced", "lines"))
for r in rows:
    print("%-34s %6d %6d %8d  %d-%d%s"
          % (r["fn"], r["reads"], r["writes"], r["reads_after_a_write"],
             r["lines"][0], r["lines"][1],
             ("   first at %d" % r["first_forced"]) if r["first_forced"] else ""))

print("\nfunctions that both read and write layout:", len(rows))
print("of those, with a read after a write (a forced reflow):",
      sum(1 for r in rows if r["reads_after_a_write"]))
print("total forced reads:", sum(r["reads_after_a_write"] for r in rows))
print("\nobservers and listeners in the file:")
for pat in ("new global.ResizeObserver", "new ResizeObserver", "addEventListener('resize'",
            "document.fonts.ready", "setTimeout(", "setInterval(",
            "requestAnimationFrame("):
    print("   %-32s %d" % (pat, src.count(pat)))
