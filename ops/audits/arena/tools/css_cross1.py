"""AN12 - cross-sheet conflicts at the level of a SINGLE selector.

css_cross.py compares whole rule preludes, so `.a, .b {}` and `.b {}` look
unrelated to it.  They are not: an element matching `.b` sees both.  This one
splits every selector list and reports each single selector written in both
sheets for the same property, with the value each sheet gives it.
"""
import sys, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = open(os.path.join(HERE, "scratchpad", "css_supersede.py"), encoding="utf-8").read()


def load(path):
    mod = type(sys)("m")
    saved, sys.argv = sys.argv, [sys.argv[0]]
    exec(compile(CODE.replace('PATH = "static/css/arena.css"', "PATH = %r" % path),
                 path, "exec"), mod.__dict__)
    sys.argv = saved
    return mod


def index(path):
    out = collections.defaultdict(list)
    for r in load(path).rules:
        for one in (s.strip() for s in r.sel.split(",")):
            if not one:
                continue
            for d in r.decls:
                out[(r.ctx, one, d.prop)].append((d.value, d.important, d.line))
    return out


A, B = sys.argv[1], sys.argv[2]
ia, ib = index(A), index(B)
shared = sorted(set(ia) & set(ib), key=lambda k: (k[1], k[2]))
same = [k for k in shared if {v[:2] for v in ia[k]} == {v[:2] for v in ib[k]}]
print("\n%s  ->  %s" % (os.path.basename(A), os.path.basename(B)))
print("single selectors written in both, same property: %d  (identical value: %d)"
      % (len(shared), len(same)))
for k in shared:
    tag = "SAME " if k in same else "DIFF "
    print("  %s%-58s %-16s A=%-26s B=%s"
          % (tag, k[1][:58], k[2], str(ia[k][-1][0])[:26], str(ib[k][-1][0])[:34]))
    if k[0]:
        print("        context", k[0])
