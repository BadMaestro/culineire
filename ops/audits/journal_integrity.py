"""Measure the release journal against what git says actually shipped.

Run from the repository root, with no Django and no database:

    python ops/audits/journal_integrity.py

Why this is a script in the repository rather than a number in a report: a
measurement whose source cannot be re-run is a rumour (see
ops/reference/design_arena/README.md, which cost this project six days of work
built on a figure nobody could check). Every number below is reproducible.

WHAT IT COUNTS, AND ITS BLIND SPOT, stated together per AGENTS.md 17.15.5:

A version counts as SHIPPED when a commit SUBJECT ends in "(vX.Y.Z)" - the
convention this project uses for a release commit. It deliberately does not
match the version anywhere in the body: a commit that merely mentions v2.5.714
in prose is not the release of v2.5.714, and matching the body inflates the
missing-row count. The blind spot is the mirror of that: a release whose subject
never carried its version is invisible here and will not be reported as missing.

TWO NUMBERS, AND THE DIFFERENCE IS THE DEFINITION, NOT A DISAGREEMENT. The
CURRENT epoch is the 2.5 series, which is what the journal is for and what the
footer serves. Everything before it - the 1.x and 2.0-2.4 releases - predates
this journal entirely, and counting those as "missing rows" inflates the figure
by about twenty. The headline below is the 2.5 series; older epochs are printed
separately as context and are not a backlog. A number that changes when its
definition changes must carry that definition with it (AGENTS.md 17.15.5).
"""

import ast
import io
import re
import subprocess
import sys
from collections import Counter

JOURNAL = "config/release_journal.py"
SUBJECT_VERSION = re.compile(r"\(v(\d+(?:\.\d+)+)\)\s*$")


def load_rows():
    src = io.open(JOURNAL, encoding="utf-8").read()
    node = [
        n for n in ast.parse(src).body
        if getattr(n, "targets", None)
        and getattr(n.targets[0], "id", "") == "RELEASE_JOURNAL"
    ][0]
    return ast.literal_eval(node.value)


def key(version):
    try:
        return tuple(int(part) for part in version.split("."))
    except (ValueError, AttributeError):
        return None


def shipped_versions():
    log = subprocess.run(
        ["git", "log", "--all", "--format=%s"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    found = {}
    for subject in log.splitlines():
        match = SUBJECT_VERSION.search(subject)
        if match:
            found.setdefault(match.group(1), subject.strip())
    return found


def main():
    rows = load_rows()
    versions = [row.get("version", "") for row in rows]
    numeric = [v for v in versions if key(v)]
    placeholders = [v for v in versions if not key(v)]
    recorded = set(versions)

    all_shipped = shipped_versions()
    current = {v: s for v, s in all_shipped.items() if (key(v) or (0,))[:2] == (2, 5)}
    older = {v: s for v, s in all_shipped.items() if v not in current}

    shipped = current
    missing = sorted(
        (v for v in shipped if v not in recorded),
        key=lambda v: key(v) or (0,),
    )
    older_missing = [v for v in older if v not in recorded]

    print(f"journal entries              {len(rows)}")
    print(f"2.5 releases (subjects)      {len(shipped)}")
    print(f"2.5 shipped WITHOUT a row    {len(missing)}     <- the backlog")
    print(f"pre-2.5 without a row        {len(older_missing)}      "
          f"context only: older than this journal, not a backlog")
    print()

    third = lambda v: (key(v) or (0, 0, 0))[2]
    print("by band:")
    for name, lo, hi in (("<600", 0, 599), ("600-699", 600, 699),
                         ("700-769", 700, 769), ("770+", 770, 10 ** 9)):
        band = {v for v in shipped if lo <= third(v) <= hi}
        print(f"   {name:<9} shipped {len(band):>3}   missing {len(band - recorded):>3}")
    print()

    dupes = {v: c for v, c in Counter(numeric).items() if c > 1}
    if dupes:
        ordered = sorted(dupes, key=key)
        print(f"duplicate version numbers    {len(dupes)}  "
              f"({sum(dupes.values())} rows, {ordered[0]} -> {ordered[-1]})")

    # Two different things used to be counted as one number here, and the sum
    # was misleading in both directions: a run that genuinely ascends is
    # disorder, while two adjacent rows carrying the SAME version are the
    # collisions above sitting where they belong. Counting them together
    # reported 43 "ordering breaks" when 20 were real, and made a correctly
    # sorted list score worse than the unsorted one.
    keys = [key(v) for v in versions]
    ascending = [
        (versions[i], versions[i + 1])
        for i in range(len(keys) - 1)
        if keys[i] and keys[i + 1] and keys[i] < keys[i + 1]
    ]
    adjacent_dupes = sum(
        1 for i in range(len(keys) - 1)
        if keys[i] and keys[i + 1] and keys[i] == keys[i + 1]
    )
    print(f"ordering breaks              {len(ascending)}   (places where the list ascends)")
    for before, after in ascending[:5]:
        print(f"   {before} then {after}")
    print(f"adjacent same-version rows   {adjacent_dupes}   "
          f"not disorder: the collisions above, sitting together")

    if placeholders:
        print(f"rows with no version number  {len(placeholders)}  {dict(Counter(placeholders))}")

    required = {"version", "date", "title", "section", "summary"}
    incomplete = [r.get("version") for r in rows if not required.issubset(r)]
    print(f"rows missing a required field {len(incomplete)}")

    if missing:
        print()
        print("MISSING ROWS, oldest first - version and the commit subject that shipped it:")
        for version in missing:
            print(f"   {version:<10} {shipped[version][:88]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
