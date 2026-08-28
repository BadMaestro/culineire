#!/usr/bin/env python3
"""AN14: prove that MOVING a rule in arena.css changed nothing.

AN13's invariant - "the set of declarations that actually apply is byte-identical
before and after" - is a complete proof for DELETING a copy the cascade already
overrides. It is NOT a proof for moving a rule, and the difference is the whole
reason this file exists:

    .a { color: red }      /* one element can match both;   */
    .b { color: blue }     /* equal specificity, so the LOWER one wins */

Move `.a` past `.b` and the colour changes. AN13's map would not notice: it is
keyed per selector, and neither selector's own winner changed. Order decides
between two DIFFERENT selectors of EQUAL specificity setting the SAME property,
and nothing in AN13 looks at that.

THE INVARIANT HERE: group every declaration by (context, property, specificity,
importance). Inside a group, and only inside a group, source order is what
decides. So the relative order of the rules within every group must be exactly
the same before and after. If it is, no move can have changed a pixel; if it is
not, the tool prints which pair was transposed and refuses.

Deliberately conservative on "can one element match both". It does not try to
decide - it assumes every selector in a group can collide with every other. A
guard that guesses wrong in the permissive direction is worth nothing, and being
too strict only costs a move that has to be done differently.

Usage:
    an14_move_guard.py BEFORE.css AFTER.css     compare two files
    an14_move_guard.py --selftest FILE.css      transpose a known conflicting
                                                pair and prove it is caught
"""
import collections
import io
import re
import sys

NESTED = re.compile(r"@(media|supports|layer|container)\b")
ID = re.compile(r"#[-\w]+")
CLS = re.compile(r"\.[-\w]+|\[[^\]]+\]|:(?!:)(?!not\b|is\b|where\b|has\b)[-\w]+(?:\([^)]*\))?")
EL = re.compile(r"(?:^|[\s>+~(])([a-zA-Z][-\w]*)")


def blank_comments(text):
    """Replace every comment with spaces, keeping all offsets."""
    out, i = [], 0
    while i < len(text):
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = len(text) if j < 0 else j + 2
            out.append(" " * (j - i))
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def specificity(sel):
    """(a, b, c) for ONE compound selector - no commas."""
    a = len(ID.findall(sel))
    b = len(CLS.findall(ID.sub(" ", sel)))
    c = len(EL.findall(" " + CLS.sub(" ", ID.sub(" ", sel))))
    return (a, b, c)


def rules(text):
    """Yield each style rule as a dict, in source order.

    Skips at-rule blocks that are not nested style contexts: @keyframes holds
    STEPS, not declarations, and reading its 0%/100% as duplicate properties is
    how AN13's first draft nearly deleted an animation.
    """
    clean = blank_comments(text)
    stack, i, prelude, idx = [], 0, 0, 0
    while i < len(clean):
        c = clean[i]
        if c == "{":
            head = " ".join(clean[prelude:i].split())
            if NESTED.match(head):
                stack.append((head, prelude))
                i += 1
                prelude = i
                continue
            j, depth = i + 1, 1
            while j < len(clean) and depth:
                if clean[j] == "{":
                    depth += 1
                elif clean[j] == "}":
                    depth -= 1
                j += 1
            if head.startswith("@"):
                i = j
                prelude = i
                continue
            decls = []
            for chunk in clean[i + 1:j - 1].split(";"):
                name, sep, value = chunk.partition(":")
                prop = name.strip().lower()
                if sep and prop and not prop.startswith("@"):
                    decls.append((prop, " ".join(value.split()),
                                  "!important" in value.lower()))
            yield {
                "ctx": tuple(level for level, _at in stack),
                "ctx_start": stack[0][1] if stack else prelude,
                "sel": head, "decls": decls, "index": idx,
                "start": prelude, "end": j,
            }
            idx += 1
            i = j
            prelude = i
            continue
        if c == "}":
            if stack:
                stack.pop()
            i += 1
            prelude = i
            continue
        if c == ";" and clean[prelude:i].strip().startswith("@"):
            i += 1
            prelude = i
            continue
        i += 1


def signature(text):
    """group -> the rules in that group, in source order.

    A rule's identity has to survive being moved, so it cannot be its offset or
    its index. It is what the rule SAYS - context, selector, property, value,
    importance - plus an ordinal that separates genuinely identical twins.
    """
    groups = collections.defaultdict(list)
    seen = collections.Counter()
    for rule in rules(text):
        for one in rule["sel"].split(","):
            one = one.strip()
            if not one:
                continue
            spec = specificity(one)
            for prop, value, imp in rule["decls"]:
                ident = (rule["ctx"], one, prop, value, imp)
                seen[ident] += 1
                groups[(rule["ctx"], prop, spec, imp)].append(
                    ident + (seen[ident],))
    return groups


def applying(text):
    """AN13's map: the declaration that wins per (context, selector, property)."""
    winner = {}
    for rule in rules(text):
        for one in rule["sel"].split(","):
            one = one.strip()
            if not one:
                continue
            for prop, value, imp in rule["decls"]:
                k = (rule["ctx"], one, prop)
                if k in winner and winner[k][1] and not imp:
                    continue
                winner[k] = (value, imp)
    return winner


def compare(before, after, collides=None):
    """Return a list of complaints. Empty means the move is proved safe.

    `collides(selector_a, selector_b)` may be supplied to answer whether one
    element can match both. Without it every selector is assumed to collide
    with every other, which is the honest default for a guard and far too
    coarse to permit any real move - see an16_cohabit.py, which supplies the
    evidence, and an15_gather.py, which uses it."""
    bad = []

    ba, aa = applying(before), applying(after)
    if ba != aa:
        diff = [k for k in set(ba) | set(aa) if ba.get(k) != aa.get(k)]
        bad.append("%d applying declarations changed, e.g. %s: %r -> %r"
                   % (len(diff), diff[0], ba.get(diff[0]), aa.get(diff[0])))

    bg, ag = signature(before), signature(after)
    for key in sorted(set(bg) | set(ag), key=str):
        b, a = bg.get(key, []), ag.get(key, [])
        if b == a:
            continue
        if sorted(b, key=str) != sorted(a, key=str):
            bad.append("group %s: membership changed (%d -> %d)"
                       % ((key[1], key[2]), len(b), len(a)))
            continue
        pos = {ident: n for n, ident in enumerate(a)}
        if collides is None:
            pairs = [(n, n + 1) for n in range(len(b) - 1)]
        else:
            pairs = [(i, j) for i in range(len(b)) for j in range(i + 1, len(b))]
        for i, j in pairs:
            if pos[b[i]] <= pos[b[j]]:
                continue
            one, other = b[i], b[j]
            if collides is not None:
                if one[3] == other[3]:
                    continue          # same value: order cannot matter
                if not collides(one[1], other[1]):
                    continue          # no element can match both
            bad.append(
                "TRANSPOSED, %s at specificity %s%s:\n"
                "      was above: %s\n"
                "      now below: %s"
                % (key[1], key[2], " !important" if key[3] else "",
                   one[1], other[1]))
            break
    return bad


def selftest(path):
    """Transpose two rules that genuinely fight, and require a refusal.

    A guard nobody has seen fail is not a guard.
    """
    text = io.open(path, encoding="utf-8", newline="").read()
    if compare(text, text):
        print("SELFTEST FAILED: the file does not even match itself.")
        return 1

    by_index = {r["index"]: r for r in rules(text)}
    pair = None
    for key, members in signature(text).items():
        if key[0]:                              # top level only: a clean swap
            continue
        owners = []
        for rule in rules(text):
            if rule["ctx"]:
                continue
            for one in rule["sel"].split(","):
                one = one.strip()
                if one and specificity(one) == key[2]:
                    for prop, _v, imp in rule["decls"]:
                        if prop == key[1] and imp == key[3]:
                            owners.append(rule["index"])
        owners = sorted(set(owners))
        if len(owners) >= 2:
            a, b = by_index[owners[0]], by_index[owners[1]]
            if a["end"] <= b["start"]:
                pair = (key, a, b)
                break
    if pair is None:
        print("SELFTEST INCONCLUSIVE: no conflicting top-level pair found.")
        return 1

    key, a, b = pair
    forged = (text[:a["start"]] + text[b["start"]:b["end"]]
              + text[a["end"]:b["start"]] + text[a["start"]:a["end"]]
              + text[b["end"]:])
    complaints = compare(text, forged)
    print("selftest: transposed %r and %r (both write %s at %s)"
          % (a["sel"][:48], b["sel"][:48], key[1], key[2]))
    if not complaints:
        print("SELFTEST FAILED: the transposition was not caught.")
        return 1
    print("caught, as it must be:")
    for line in complaints[:3]:
        print("   ", line)
    return 0


def main():
    args = sys.argv[1:]
    if args[:1] == ["--selftest"]:
        raise SystemExit(selftest(args[1]))
    if len(args) != 2:
        print(__doc__)
        raise SystemExit(2)
    before = io.open(args[0], encoding="utf-8", newline="").read()
    after = io.open(args[1], encoding="utf-8", newline="").read()
    complaints = compare(before, after)
    if complaints:
        print("REFUSED:", len(complaints), "problems.")
        for line in complaints[:20]:
            print("  -", line)
        raise SystemExit(1)
    print("PROVED: applying declarations identical, and no conflicting pair "
          "changed places.")


if __name__ == "__main__":
    main()
