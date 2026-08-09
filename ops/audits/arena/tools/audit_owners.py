"""ACCEPTANCE AUDIT section 5 / 6 - hunt for a SECOND owner of a position.

For each component, every CSS rule whose selector mentions it is listed with
the positional properties it sets, and every JavaScript statement that writes a
positional property to it. Two independent mechanisms able to decide the final
position is a FAIL, whatever the intent was.
"""
import os, re, sys

ROOT = "/mnt/e/CulinEire Project/CulinEire/CulinEire"
SHEETS = ["static/css/arena.css", "static/css/arena_atmosphere.css"]
SCRIPTS = ["static/js/arena_render.js", "static/js/arena_page_layout.js",
           "static/js/arena_octagon.js", "static/js/arena_deck.js",
           "static/js/arena_lamp_console.js", "static/js/arena_master_console.js",
           "static/js/arena_console_mirror.js"]
POS = re.compile(r"^\s*(top|left|right|bottom|inset|transform|translate|position|margin|"
                 r"width|height|grid-area|place-self|align-self|justify-self)\s*:", re.I)
JSWRITE = re.compile(r"\.style\.(top|left|right|bottom|transform|transformOrigin|width|height|"
                     r"margin[A-Za-z]*|inset[A-Za-z]*)\s*=|setProperty\(\s*['\"]--arena-(shift|fit)")

COMPONENTS = {
    "rank ladder": ["arena-rank-spine"],
    "floor caption": ["arena-floor-caption"],
    "octagon / render container": ["arena-render-container", "#arena-render", "arena-floor-stage"],
    "deck": ["arena-command-deck {", "arena-command-deck{"],
}


def strip_comments(s):
    out, i = [], 0
    while i < len(s):
        if s.startswith("/*", i):
            j = s.find("*/", i + 2)
            j = len(s) if j < 0 else j + 2
            out.append(" " * (j - i)); i = j
        else:
            out.append(s[i]); i += 1
    return "".join(out)


def css_rules(path):
    text = strip_comments(open(os.path.join(ROOT, path), encoding="utf-8").read())
    line = 1
    i = 0
    while i < len(text):
        j = text.find("{", i)
        if j < 0:
            break
        k = text.find("}", j)
        if k < 0:
            break
        sel = " ".join(text[i:j].split())
        body = text[j + 1:k]
        yield text[:j].count("\n") + 1, sel, body
        i = k + 1


for name, needles in COMPONENTS.items():
    print("\n" + "=" * 70)
    print(name.upper())
    print("=" * 70)
    css_hits = 0
    for path in SHEETS:
        for ln, sel, body in css_rules(path):
            if not any(n.rstrip(" {") in sel for n in needles):
                continue
            props = [l.strip() for l in body.split(";") if POS.match(l + ":")]
            props = [p for p in (x.strip() for x in body.split(";")) if POS.match(p + ";")]
            if props:
                css_hits += 1
                print("  CSS  %s:%d  %s" % (os.path.basename(path), ln, sel[:70]))
                for p in props:
                    print("           %s" % p)
    if not css_hits:
        print("  CSS  no rule sets a positional property")

    js_hits = 0
    for path in SCRIPTS:
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            continue
        lines = open(full, encoding="utf-8").read().replace("\r\n", "\n").split("\n")
        for n, l in enumerate(lines, 1):
            if not JSWRITE.search(l):
                continue
            window = "\n".join(lines[max(0, n - 40):n])
            if any(x.rstrip(" {") in window for x in needles):
                js_hits += 1
                print("  JS   %s:%d  %s" % (os.path.basename(path), n, l.strip()[:80]))
    if not js_hits:
        print("  JS   nothing writes a positional property")
