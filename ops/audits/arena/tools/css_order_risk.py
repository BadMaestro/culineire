"""AN12 - the part the identical-selector test cannot see.

Two rules in different sheets can fight over the same element even when their
selector TEXT differs: equal specificity, and then source order decides.  So
before moving one sheet past another, list every property written in both at
the SAME specificity, and print the selector pairs so each can be judged on
whether one element can match both.
"""
import sys, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = open(os.path.join(HERE, "scratchpad", "css_supersede.py"), encoding="utf-8").read()


def load(path):
    mod = type(sys)("m")
    saved, sys.argv = sys.argv, [sys.argv[0]]
    exec(compile(CODE.replace('PATH = "static/css/arena.css"', "PATH = %r" % path),
                 path, "exec"), mod.__dict__)
    sys.argv = saved
    return mod


ID = re.compile(r"#[-\w]+")
CLS = re.compile(r"\.[-\w]+|\[[^\]]+\]|:(?!:)(?!not\b|is\b|where\b|has\b)[-\w]+(\([^)]*\))?")
EL = re.compile(r"(?:^|[\s>+~(])([a-zA-Z][-\w]*)")


def spec(sel):
    """Specificity of ONE compound selector (no commas)."""
    s = sel
    a = len(ID.findall(s))
    b = len(CLS.findall(ID.sub(" ", s)))
    c = len(EL.findall(" " + CLS.sub(" ", ID.sub(" ", s))))
    return (a, b, c)


def index(mod):
    out = collections.defaultdict(list)          # (ctx, prop, specificity) -> [selector]
    for r in mod.rules:
        for one in r.sel.split(","):
            one = one.strip()
            if not one:
                continue
            sp = spec(one)
            for d in r.decls:
                out[(r.ctx, d.prop, sp)].append(one)
    return out


A, B = sys.argv[1], sys.argv[2]
ia, ib = index(load(A)), index(load(B))
keys = sorted(set(ia) & set(ib), key=lambda k: (k[1], k[2]))
print("\n%s  vs  %s" % (os.path.basename(A), os.path.basename(B)))
print("properties written in both at the same specificity:", len(keys))
for k in keys:
    print("\n  %s   specificity %s   context %s" % (k[1], k[2], k[0] or "-"))
    print("    A:", "; ".join(sorted(set(ia[k]))[:6]))
    print("    B:", "; ".join(sorted(set(ib[k]))[:6]))
