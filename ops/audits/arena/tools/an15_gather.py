#!/usr/bin/env python3
"""AN15: gather one component's rules into a single block, and prove it safe.

A component's rules are scattered - `.arena-chat` owns 332 of them over 11947
lines in eight islands - because new work is written at the end of the file
instead of into the section that already exists. This gathers them.

WHAT IT WILL NOT DO. A move is only safe if it does not change the relative
order of two rules that fight: same context, same specificity, same property,
and one element able to match both. an14_move_guard.py holds that line, and
this tool asks it BEFORE writing rather than hoping afterwards.

So the tool is mostly an analysis. It reports, per candidate destination, how
many conflicting pairs the move would transpose, and moves nothing unless that
number is zero. When it is not zero, the offending rules are named: those are
the ones that have to stay put, or be dealt with some other way.

    an15_gather.py --census static/css/arena.css .arena-chat
    an15_gather.py --plan   static/css/arena.css .arena-chat
    an15_gather.py --apply  static/css/arena.css .arena-chat
"""
import collections
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import an16_cohabit  # noqa: E402
from an14_move_guard import compare, rules, specificity  # noqa: E402

COHABIT = None


def cohabitation():
    """The evidence model from AN16, built once."""
    global COHABIT
    if COHABIT is None:
        COHABIT = an16_cohabit.default_model(".")
    return COHABIT


def owns(selector, component):
    """True when the selector's SUBJECT - its rightmost compound - is the
    component's. A rule reached through `.arena-chat .something-else` styles
    the something-else, and belongs to that component, not to this one."""
    subject = re.split(r"[\s>+~]+", selector.strip())[-1]
    return bool(re.search(re.escape(component) + r"(?![-\w])", subject)
                or re.search(re.escape(component) + r"[-_]{1,2}[\w-]*", subject))


def component_rules(text, component):
    """Rules whose EVERY selector belongs to the component.

    A rule listing `.arena-chat__tag, .arena-deck__tag` styles two components
    at once and cannot be filed under one of them without splitting it, which
    is a rewrite rather than a move. Those are left where they are."""
    chosen, mixed = [], []
    for rule in rules(text):
        parts = [s.strip() for s in rule["sel"].split(",") if s.strip()]
        if not parts:
            continue
        hits = [owns(s, component) for s in parts]
        if all(hits):
            chosen.append(rule)
        elif any(hits):
            mixed.append(rule)
    return chosen, mixed


def islands(rule_list, text):
    """Contiguous runs, counted by how many other rules sit between them."""
    if not rule_list:
        return []
    every = list(rules(text))
    index = {r["index"]: n for n, r in enumerate(every)}
    out, run = [], [rule_list[0]]
    for prev, cur in zip(rule_list, rule_list[1:]):
        if index[cur["index"]] - index[prev["index"]] == 1:
            run.append(cur)
        else:
            out.append(run)
            run = [cur]
    out.append(run)
    return out


def groups_of(text):
    """(context, property, specificity, importance) -> [(rule index, selector, value)].

    Per SELECTOR, not per rule. A rule listing six selectors declares six
    different things, and asking "can these two RULES collide" instead of
    "can these two SELECTORS collide" over-reports badly: one dead selector in
    a list of six makes the whole rule look like it fights with everything."""
    out = collections.defaultdict(list)
    for rule in rules(text):
        for one in rule["sel"].split(","):
            one = one.strip()
            if not one:
                continue
            spec = specificity(one)
            for prop, value, imp in rule["decls"]:
                out[(rule["ctx"], prop, spec, imp)].append(
                    (rule["index"], one, value))
    return out


def values_at(text):
    """(rule index, context, property, specificity, importance) -> value.

    Two rules can only be transposed to any EFFECT if they disagree about the
    value. `.arena-page { margin: 0 }` and `.arena-chat__log { margin: 0 }` can
    be swapped all day; whichever wins, the element gets 0."""
    out = {}
    for rule in rules(text):
        for one in rule["sel"].split(","):
            one = one.strip()
            if not one:
                continue
            spec = specificity(one)
            for prop, value, imp in rule["decls"]:
                out.setdefault(
                    (rule["index"], rule["ctx"], prop, spec, imp), set()
                ).add(value)
    return out


def transpositions(text, moving, destination):
    """Pairs the move would reorder, if every `moving` rule went to `destination`.

    A rule that moves and one that does not swap places exactly when the one
    that stays lies between the mover's old seat and the new one. That is the
    whole arithmetic of it."""
    move = set(moving)
    hurt = collections.Counter()
    model = cohabitation()
    for key, members in groups_of(text).items():
        for a, a_sel, a_value in members:
            for b, b_sel, b_value in members:
                if a >= b:
                    continue
                a_moves, b_moves = a in move, b in move
                if a_moves == b_moves:
                    continue          # both move together, or neither moves
                if a_value == b_value:
                    continue          # same value: order cannot matter
                if not model.can_collide(a_sel, b_sel):
                    continue          # no element can match both selectors
                stayer, mover = (b, a) if a_moves else (a, b)
                stay_sel, move_sel = (b_sel, a_sel) if a_moves else (a_sel, b_sel)
                # The mover ends up at `destination`, so afterwards it is above
                # the stayer exactly when the destination is. Keying this on
                # WHICH of the two moved, as the first draft did, silently
                # inverted the test for half the pairs and let a real
                # transposition through - the guard caught it, which is the
                # entire reason the guard runs after the write as well.
                # `<=`, not `<`: the block is inserted BEFORE the rule at the
                # destination, so a mover ends up above everything from the
                # destination onwards - including the destination rule itself.
                before = mover < stayer
                after = destination <= stayer
                if before != after:
                    hurt[(key[1], key[2], stay_sel, move_sel, mover)] += 1
    return hurt


def largest_safe_move(text, moving, destination):
    """Drop movers until nothing is transposed, and return what may move.

    All-or-nothing was the wrong shape. A handful of rules genuinely cannot be
    moved - a state class a script can put on anything, a rule whose selector
    the evidence model cannot read - and refusing the whole gather because of
    them leaves 289 rules scattered over eight islands rather than moving 280
    of them. Whatever cannot be proved safe stays exactly where it is.

    Iterated to a fixpoint: a rule that stops moving becomes a rule that stays,
    which can put a pair that was previously "both move" into conflict."""
    keep, dropped = list(moving), []
    while True:
        hurt = transpositions(text, keep, destination)
        if not hurt:
            return keep, sorted(dropped)
        blocked = {mover for (_p, _s, _ss, _ms, mover) in hurt}
        left = [i for i in keep if i not in blocked]
        if len(left) == len(keep):
            return keep, sorted(set(dropped) | blocked)
        dropped.extend(blocked)
        keep = left


def report(text, component):
    chosen, mixed = component_rules(text, component)
    every = list(rules(text))
    print("%s: %d rules of %d in the file" % (component, len(chosen), len(every)))
    print("rules naming this component AND another:", len(mixed))
    for rule in mixed[:8]:
        print("   ", rule["sel"][:88])
    runs = islands(chosen, text)
    print("islands:", len(runs))
    line_of = lambda off: text.count("\n", 0, off) + 1
    for run in runs:
        print("   lines %5d - %5d  (%d rules)"
              % (line_of(run[0]["start"]), line_of(run[-1]["end"]), len(run)))
    return chosen, runs


def plan(text, component):
    chosen, runs = report(text, component)
    moving = [r["index"] for r in chosen]
    print("\ncandidate destinations, and what each would transpose:")
    every = list(rules(text))
    best = None
    seen = set()
    for run in runs:
        # THE BLOCK HAS TO LAND AT THE TOP LEVEL. An island that begins inside
        # `@media (max-width: 640px)` is a text position INSIDE that block, and
        # inserting there puts every unconditional rule under the media query -
        # which is not a move, it is a rewrite. Land before the whole at-rule.
        where = run[0]["ctx_start"]
        dest = min(r["index"] for r in every if r["start"] >= where)
        if dest in seen:
            continue
        seen.add(dest)
        hurt = transpositions(text, moving, dest)
        line = text.count("\n", 0, where) + 1
        print("   line %5d : %d conflicting pairs reordered" % (line, len(hurt)))
        if best is None or len(hurt) < len(best[1]):
            best = (dest, hurt, line, where)
    if best and best[1]:
        print("\nthe best destination is line %d, and it is NOT clean." % best[2])
        print("the selectors in the way:")
        for (prop, spec, stay_sel, move_sel, _m), _n in best[1].most_common(20):
            print("    %-18s %s  stays: %-42s moves: %s"
                  % (prop, spec, stay_sel[:42], move_sel[:42]))
    return best


def apply(text, component, path):
    best = plan(text, component)
    if best is None:
        print("\nnothing to move.")
        return 1
    dest, _hurt, line, where = best
    chosen, _mixed = component_rules(text, component)
    every = {r["index"]: r for r in rules(text)}
    movable, blocked = largest_safe_move(
        text, [r["index"] for r in chosen], dest)
    if blocked:
        print("\n%d rules stay where they are, unproved:" % len(blocked))
        for index in blocked[:15]:
            print("   ", every[index]["sel"][:96])
    if not movable:
        print("\nREFUSED: nothing can be moved safely.")
        return 1

    keep = set(movable)
    chosen = [r for r in chosen if r["index"] in keep]
    blocks = [(r["start"], r["end"], text[r["start"]:r["end"]], r["ctx"])
              for r in chosen]
    cut = text
    for start, end, _body, _ctx in sorted(blocks, key=lambda b: -b[0]):
        cut = cut[:start] + cut[end:]

    insert_at = where - sum(
        (end - start) for start, end, _b, _c in blocks if end <= where
    )
    banner = [
        "",
        "",
        "/* %s - every rule for this component that could be proved" % component,
        "   safe to move, in one place. Gathered by an15_gather.py:",
        "   the applying declarations are byte-identical and no",
        "   conflicting pair changed places. */",
    ]

    # A RULE CARRIES ITS CONTEXT WITH IT. Lifting a rule out of
    # `@media (max-width: 640px)` and dropping it at the top level does not
    # move it, it rewrites it - the first run did exactly that and changed 318
    # applying declarations. Each mover is re-wrapped in the at-rules it lived
    # under, and consecutive movers sharing a context share one wrapper.
    # Write the newline the file already uses. Emitting "\n" into a CRLF
    # stylesheet leaves a block whose line endings differ from every other, and
    # guards that read the sheet as text stop matching on formatting alone.
    eol = "\r\n" if text.count("\r\n") > text.count("\n") / 2 else "\n"

    parts, open_ctx = list(banner), ()
    for _s, _e, body, ctx in blocks:
        if ctx != open_ctx:
            for _level in reversed(range(len(open_ctx))):
                parts.append("  " * _level + "}")
            for depth, level in enumerate(ctx):
                parts.append("  " * depth + level + " {")
            open_ctx = ctx
        # VERBATIM. Not re-indented to suit the new nesting: a rule keeps the
        # context it had, so it keeps the indentation it had, and several
        # guards read this file as text - one of them asserts a
        # `grid-template-areas` spanning three lines with its exact leading
        # spaces. Re-padding moved rules broke it while changing nothing about
        # what the browser does, which is the worst kind of diff.
        rows = [row.rstrip("\r") for row in body.splitlines()]
        while rows and not rows[0].strip():
            rows.pop(0)
        while rows and not rows[-1].strip():
            rows.pop()
        parts.extend(rows)
    for _level in reversed(range(len(open_ctx))):
        parts.append("  " * _level + "}")
    parts.append("")
    out = cut[:insert_at] + eol.join(parts) + eol + cut[insert_at:]

    complaints = compare(text, out, collides=cohabitation().can_collide)
    if complaints:
        print("\nREFUSED by the guard after the fact:", len(complaints))
        for c in complaints[:10]:
            print("  -", c)
        return 1
    io.open(path, "w", encoding="utf-8", newline="").write(out)
    print("\nPROVED and written: %d rules gathered at line %d." % (len(blocks), line))
    return 0


def main():
    mode, path, component = sys.argv[1], sys.argv[2], sys.argv[3]
    text = io.open(path, encoding="utf-8", newline="").read()
    if mode == "--census":
        report(text, component)
        return 0
    if mode == "--plan":
        plan(text, component)
        return 0
    if mode == "--apply":
        return apply(text, component, path)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
