#!/usr/bin/env python3
"""AN13: drop every declaration that the cascade already overrides.

MIRRORS chef_battle/tests.py's own walker and is checked against it, because a
script that reads the stylesheet differently from the guard must not be trusted
to edit it. Checking that found three things, every one caught before a byte
reached the stylesheet:

  - @keyframes IS NOT A DECLARATION BLOCK. Read as one, an animation's 0% and
    100% steps look like duplicate properties, and cutting them would delete
    the animation. At-rule blocks are skipped outright.

  - A DECLARATION'S SPAN MUST START AT THE PROPERTY. A chunk begins where the
    previous semicolon left off, so it carries the whitespace and ANY COMMENT
    above it. The first run removed a 44-line comment recording the Owner's own
    Region Model A of 2026-08-09, because it sat above a dead
    `position: absolute`. Comments are blanked to spaces in `clean`, so the
    first non-space character is the property itself.

  - THE GUARD UNDERCOUNTS BY ONE, and this script is the one that is right.
    `.arena-broadcast-ribbon { background }` is declared three times: once with
    !important and twice without. By the cascade the !important wins whatever
    the order, so BOTH plain copies are dead - the guard reports one. Its loop
    `continue`s past an earlier-!important case without counting it, which is
    right for "is this an offence" and wrong for "how many are dead".

THE INVARIANT: the set of declarations that ACTUALLY APPLY - context, selector,
property AND value - is byte-identical before and after. Only copies that
already lose are removed, so no pixel can move. That is checkable, which is the
whole reason to do this mechanically rather than by eye.
"""
import io
import re
import sys


def walk(text):
    """Yield (ctx, selector, name, value, important, start, end) per declaration."""
    # Blank comments, keeping offsets so nothing shifts.
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
    clean = "".join(out)

    stack, i, prelude = [], 0, 0
    nested = re.compile(r"@(media|supports|layer|container)\b")
    while i < len(clean):
        c = clean[i]
        if c == "{":
            head = " ".join(clean[prelude:i].split())
            if nested.match(head):
                stack.append(head)
                i += 1
                prelude = i
                continue
            j = i + 1
            depth = 1
            while j < len(clean) and depth:
                if clean[j] == "{":
                    depth += 1
                elif clean[j] == "}":
                    depth -= 1
                j += 1
            if head.startswith("@"):
                # @keyframes holds STEPS, not one rule's declarations.
                i = j
                prelude = i
                continue
            body_start = i + 1
            body = clean[body_start:j - 1]
            pos = body_start
            for chunk in body.split(";"):
                span_start = pos
                pos += len(chunk) + 1          # + the ';' that split ate
                span_start += len(chunk) - len(chunk.lstrip())
                name, sep, value = chunk.partition(":")
                stripped = name.strip().lower()
                if sep and stripped and not stripped.startswith("@"):
                    yield (
                        tuple(stack), head, stripped,
                        " ".join(value.split()),
                        "!important" in value.lower(),
                        span_start, min(pos, j - 1),
                    )
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


def applying(text):
    """The declaration that wins, per (context, selector, property)."""
    winner = {}
    for ctx, sel, name, value, imp, _s, _e in walk(text):
        k = (ctx, sel, name)
        if k in winner and winner[k][1] and not imp:
            continue                      # an earlier !important still wins
        winner[k] = (value, imp)
    return winner


def superseded_spans(text):
    """Spans of the copies that already lose."""
    order = list(walk(text))
    keeper, counts = {}, {}
    for idx, (ctx, sel, name, value, imp, s, e) in enumerate(order):
        k = (ctx, sel, name)
        counts[k] = counts.get(k, 0) + 1
        if k in keeper and keeper[k][1] and not imp:
            continue                      # the earlier !important is the keeper
        keeper[k] = (idx, imp)

    keep = {idx for idx, _imp in keeper.values()}
    dead = []
    for idx, (ctx, sel, name, value, imp, s, e) in enumerate(order):
        k = (ctx, sel, name)
        if counts[k] > 1 and idx not in keep:
            dead.append((s, e, ctx, sel, name, value))
    return dead


def whole_line(text, start, end):
    """Widen a span to the whole line when the declaration owns that line.

    Cutting the declaration alone leaves its indentation behind as a line of
    spaces - 28 of them on one run. This walks over LITERAL spaces and tabs in
    the ORIGINAL text, never over the blanked comments, so it reaches the line
    edge only when nothing else shares the line.
    """
    s = start
    while s > 0 and text[s - 1] in " \t":
        s -= 1
    if s > 0 and text[s - 1] not in "\n{":
        s = start                              # something else shares the line

    e = end
    while e < len(text) and text[e] in " \t":
        e += 1
    if e < len(text) and text[e] == "\r":
        e += 1
    if e < len(text) and text[e] == "\n":
        e += 1
    else:
        e = end                                # something else follows on it
    return s, e


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = args[0] if args else "static/css/arena.css"
    text = io.open(src, encoding="utf-8", newline="").read()

    dead = superseded_spans(text)
    print("superseded declarations found:", len(dead))
    for _s, _e, ctx, sel, name, value in dead:
        where = ctx[0] if ctx else "top level"
        print("  - {} :: {}: {}   [{}]".format(sel[:56], name, value[:44], where))

    if "--apply" not in sys.argv:
        print("\ndry run. pass --apply to cut them.")
        return

    before = applying(text)
    cut = text
    for s, e, *_rest in sorted(dead, key=lambda d: -d[0]):
        s, e = whole_line(cut, s, e)
        cut = cut[:s] + cut[e:]
    after = applying(cut)

    if before != after:
        diff = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        print("\nREFUSED:", len(diff), "applying declarations would change.")
        for k in sorted(diff, key=str)[:10]:
            print("   ", k, before.get(k), "->", after.get(k))
        raise SystemExit(1)

    if superseded_spans(cut):
        print("\nREFUSED: superseded declarations remain.")
        raise SystemExit(1)

    io.open(src, "w", encoding="utf-8", newline="").write(cut)
    print("\nPROVED:", len(before), "applying declarations, identical before and after.")
    print("removed", len(dead), "dead copies;", len(text) - len(cut), "bytes.")


if __name__ == "__main__":
    main()
