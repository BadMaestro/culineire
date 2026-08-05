"""Make config/release_journal.py match what git says shipped.

Run from the repository root, with no Django and no database:

    python ops/audits/journal_backfill.py --dry-run     # writes nothing
    python ops/audits/journal_backfill.py --write

It does two things, both of them mechanical:

1. **Adds a row for every 2.5 release that shipped without one.** The words come
   from the release commit and from nowhere else: its subject becomes the title,
   its message body becomes the summary, its author date becomes the date, and
   its short hash goes in the "commit" field that hand-written rows leave empty.
   Nothing is invented. Where a commit carried no body, the row says so instead
   of filling the space with a guess, and every added row carries a `notes` line
   saying it was backfilled and from which commit - a reader must be able to
   tell a reconstruction from an account written on the day.

2. **Puts the list back in descending version order.** recipes/views.py reads
   RELEASE_JOURNAL[0] for the current version when the footer cannot be read,
   and the deployment page renders reversed(RELEASE_JOURNAL) when git is
   unavailable; both assume newest first.

WHAT IT DOES NOT DO, deliberately:

- **It does not renumber the 48 duplicated versions.** Those are two deploys that
  really did ship under one number - the failure AGENTS.md section 8 rule 5 is
  written against. Renumbering them would invent versions that never existed and
  turn a visible defect into an invisible one. They are reported, not repaired.
- **It does not invent versions for the twelve rows that have none.** Those are
  June entries from before this project numbered its releases in the commit
  subject; the audit's own definition puts everything before the 2.5 series
  outside the backlog. A version guessed from the footer at the end of that day
  would look exactly like a fact.

HOW IT EDITS THE FILE. Existing blocks are split out as text and put back byte
for byte; only new blocks are rendered, and reordering moves whole blocks. A
round-trip that re-serialises rows it did not need to touch is a round-trip that
can silently change them. Both passes assert their own result before writing:
the backfill checks that every pre-existing row is still present and identical,
and the sort checks that the multiset of rows is unchanged.

Measure before and after with ops/audits/journal_integrity.py.
"""

import argparse
import ast
import io
import re
import subprocess
import sys
from collections import Counter

JOURNAL = "config/release_journal.py"
BACKFILL_DATE = "2026-08-05"

SUBJECT_VERSION = re.compile(r"\s*\(v(\d+(?:\.\d+)+)\)\s*$")
CONVENTIONAL = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?!?:\s*(?P<rest>.*)$")
TRAILER = re.compile(r"^(co-authored-by|signed-off-by|reviewed-by|refs|closes)\s*:", re.I)

# Scope -> a section string that ALREADY appears in the journal. This is not a
# new taxonomy; a second vocabulary for the same thing is how a file ends up
# with two names for one section.
SECTION_BY_SCOPE = {
    "arena": "Chef Battles / Arena",
    "board": "Chef Battles / Arena",
    "chef_battle": "Chef Battles",
    "chef-battle": "Chef Battles",
    "palette": "UI",
    "recipes": "Recipes / Hero",
    "release": "Chef Battles / Deployment",
    "company": "Legal",
    "coworking": "Coworking",
    "audits": "Agents / Governance",
    "ai": "Agents / Governance",
    "git": "Agents / Governance",
    "deps": "Agents / Governance",
    "sponsors": "Sponsors",
    "tests": "Chef Battles / Tests",
}
SECTION_BY_TYPE = {"deploy": "Chef Battles / Deployment"}


def resolve_section(scope, ctype, subject):
    if scope in SECTION_BY_SCOPE:
        return SECTION_BY_SCOPE[scope]
    if ctype in SECTION_BY_TYPE:
        return SECTION_BY_TYPE[ctype]
    low = subject.lower()
    if "hero chef" in low:
        return "Recipes / Hero"
    if "console" in low:
        return "Chef Battles / Arena Master Console"
    if "arena" in low or "battle" in low:
        return "Chef Battles / Arena"
    if "pinch" in low:
        return "Pinch / Mobile TikTok feed"
    return "Chef Battles"


def quote(value):
    """A double-quoted Python string literal, matching the file's existing style.

    repr() emits single quotes for most strings and switches to double for any
    string containing an apostrophe - two styles in one file, chosen by the
    content. This picks one.
    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def key(version):
    try:
        return tuple(int(part) for part in version.split("."))
    except (ValueError, AttributeError):
        return None


def split_blocks(text):
    """Return (header, [block, ...], footer). A block is one dict literal, verbatim."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if ln.rstrip("\n") == "    {"]
    ends = [i for i, ln in enumerate(lines) if ln.rstrip("\n") == "    },"]
    if len(starts) != len(ends):
        raise SystemExit(f"block delimiters do not pair: {len(starts)} starts, {len(ends)} ends")
    blocks = ["".join(lines[s:e + 1]) for s, e in zip(starts, ends)]
    return "".join(lines[:starts[0]]), blocks, "".join(lines[ends[-1] + 1:])


def journal_rows(text):
    node = [
        n for n in ast.parse(text).body
        if getattr(n, "targets", None)
        and getattr(n.targets[0], "id", "") == "RELEASE_JOURNAL"
    ][0]
    return ast.literal_eval(node.value)


def shipped():
    log = subprocess.run(
        ["git", "log", "--all", "--format=%H%x01%s"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    found = {}
    for line in log.splitlines():
        if "\x01" not in line:
            continue
        sha, subject = line.split("\x01", 1)
        match = SUBJECT_VERSION.search(subject)
        if match:
            found.setdefault(match.group(1), (sha, subject.strip()))
    return found


def commit_facts(sha):
    out = subprocess.run(
        ["git", "show", "-s", "--format=%h%x01%ad%x01%an%x01%B", "--date=short", sha],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    short, date, author, message = out.split("\x01", 3)
    stat = subprocess.run(
        ["git", "show", "--stat", "--format=", sha],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    files = [
        line.split("|")[0].strip()
        for line in stat.splitlines()
        if "|" in line and not line.strip().startswith("Bin ")
    ]
    # The commit body is hard-wrapped at ~72 columns and the journal is prose, so
    # lines inside a paragraph are rejoined and blank lines separate paragraphs.
    paragraphs, current = [], []
    for line in message.splitlines()[1:]:
        stripped = line.strip()
        if not stripped or TRAILER.match(stripped):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    return short, date.strip(), author.strip(), "  ".join(paragraphs).strip(), files


def title_from(subject):
    text = SUBJECT_VERSION.sub("", subject).strip()
    match = CONVENTIONAL.match(text)
    if match:
        text = match.group("rest").strip()
    return text[:1].upper() + text[1:] if text else subject


def render(version, sha, date, body, files, subject):
    match = CONVENTIONAL.match(SUBJECT_VERSION.sub("", subject).strip())
    scope = (match.group("scope") or "") if match else ""
    ctype = (match.group("type") or "") if match else ""
    count = len(files)
    plural = "" if count == 1 else "s"

    if body:
        summary = body
    else:
        shown = ", ".join(files[:4]) + (", ..." if count > 4 else "")
        summary = f"The commit carried no message body. It changed {count} file{plural}: {shown}."

    fields = [
        ("version", version),
        ("date", date),
        ("commit", sha),
        ("title", title_from(subject)),
        ("section", resolve_section(scope, ctype, subject)),
        ("summary", summary),
        ("notes", f"Backfilled {BACKFILL_DATE} from commit {sha} ({count} file{plural}). "
                  f"The words above are the commit's own message, not a "
                  f"contemporaneous account of the release."),
    ]
    body_text = "".join(f'        "{name}": {quote(value)},\n' for name, value in fields)
    return "    {\n" + body_text + "    },\n"


def ascending_runs(versions):
    """Places where the list ASCENDS. Two adjacent rows sharing a version are not
    disorder - they are the version collisions, and they belong side by side."""
    keys = [key(v) for v in versions]
    return [
        (versions[i], versions[i + 1])
        for i in range(len(keys) - 1)
        if keys[i] and keys[i + 1] and keys[i] < keys[i + 1]
    ]


def signature(row):
    return repr(sorted(row.items(), key=lambda item: item[0]))


def backfill(header, blocks, footer, original_rows):
    versions = [ast.literal_eval(b.strip().rstrip(","))["version"] for b in blocks]
    recorded = set(versions)

    all_shipped = shipped()
    missing = sorted(
        (v for v in all_shipped if v not in recorded and (key(v) or (0,))[:2] == (2, 5)),
        key=key,
    )
    print(f"existing rows {len(blocks)}   2.5 releases with no row {len(missing)}")

    keys = [key(v) for v in versions]
    last_numeric = max(i for i, k in enumerate(keys) if k is not None)

    new_blocks, new_keys = list(blocks), list(keys)
    # Newest first, so an earlier insertion never shifts a later one's target.
    for version in sorted(missing, key=key, reverse=True):
        sha, subject = all_shipped[version]
        short, date, _author, body, files = commit_facts(sha)
        target = next(
            (i for i, k in enumerate(new_keys) if k is not None and k < key(version)),
            last_numeric + 1,
        )
        new_blocks.insert(target, render(version, short, date, body, files, subject))
        new_keys.insert(target, key(version))

    result = header + "".join(new_blocks) + footer
    parsed = journal_rows(result)
    assert len(parsed) == len(blocks) + len(missing), "row count wrong after backfill"
    present = Counter(signature(r) for r in parsed)
    for row in original_rows:
        assert present[signature(row)] >= 1, f"a pre-existing row changed: {row.get('version')}"
    added = [r for r in parsed if r["version"] in set(missing)]
    assert all(r.get("commit") for r in added), "a backfilled row has no commit hash"
    print(f"  added {len(added)} rows, each carrying its commit hash; "
          f"all {len(original_rows)} pre-existing rows unchanged")
    return result


def reorder(text):
    header, blocks, footer = split_blocks(text)
    rows = [ast.literal_eval(b.strip().rstrip(",")) for b in blocks]
    versions = [r.get("version", "") for r in rows]
    before = ascending_runs(versions)

    order = sorted(range(len(blocks)), key=lambda i: (key(versions[i]) or (0,)), reverse=True)
    new_blocks = [blocks[i] for i in order]
    moved = sum(1 for a, b in zip(order, range(len(order))) if a != b)

    result = header + "".join(new_blocks) + footer
    parsed = journal_rows(result)
    assert Counter(map(signature, parsed)) == Counter(map(signature, rows)), \
        "the sort changed content, not just order"
    newest = max((v for v in versions if key(v)), key=key)
    assert parsed[0]["version"] == newest, "RELEASE_JOURNAL[0] is not the newest version"
    after = ascending_runs([r.get("version", "") for r in parsed])
    print(f"  ordering: {len(before)} ascending places -> {len(after)}; "
          f"{moved} blocks moved; head {parsed[0]['version']}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.dry_run):
        parser.error("choose --dry-run or --write")

    text = io.open(JOURNAL, encoding="utf-8").read()
    header, blocks, footer = split_blocks(text)
    result = backfill(header, blocks, footer, journal_rows(text))
    result = reorder(result)

    if args.write:
        io.open(JOURNAL, "w", encoding="utf-8", newline="\n").write(result)
        print(f"written: {JOURNAL}")
    else:
        print("dry run - nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
