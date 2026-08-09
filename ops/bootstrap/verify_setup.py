#!/usr/bin/env python3
"""Verify the local Claude Code integration against the tracked bootstrap.

`.claude/` is gitignored, so the hook REGISTRATION is machine-local by
necessity. What must never be machine-local again is the hook IMPLEMENTATION:
it lived only in `.claude/` once, which meant it existed on exactly one
workstation and a fresh clone could not reproduce it.

This script answers, for the machine it runs on:

    hooks_installed
    hook_targets_exist
    hook_target_is_tracked
    session_start_enabled
    precompact_enabled
    machine_specific_absolute_dependency_present

It reads. It changes nothing, and it prints no secret: only whether a key is
present, never its value.

    python ops/bootstrap/verify_setup.py          # human
    python ops/bootstrap/verify_setup.py --json   # machine
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS = os.path.join(ROOT, ".claude", "settings.json")
CANONICAL = {
    "SessionStart": os.path.join("ops", "bootstrap", "session_start.py"),
    "PreCompact": os.path.join("ops", "bootstrap", "precompact.sh"),
}


def tracked(relpath):
    """Is this path in origin/main? A tracked hook survives a fresh clone."""
    try:
        return subprocess.run(
            ["git", "cat-file", "-e", "origin/main:" + relpath.replace(os.sep, "/")],
            cwd=ROOT, capture_output=True,
        ).returncode == 0
    except Exception:
        return False


def commands_for(cfg, event):
    out = []
    for group in cfg.get("hooks", {}).get(event, []) or []:
        for hook in group.get("hooks", []) or []:
            if hook.get("command"):
                out.append(hook["command"])
    return out


def main():
    report = {
        "repository_root": ROOT,
        "settings_file": SETTINGS,
        "settings_present": os.path.exists(SETTINGS),
        "settings_tracked": False,   # .claude/ is gitignored by design
        "events": {},
        "hooks_installed": False,
        "hook_targets_exist": False,
        "hook_target_is_tracked": False,
        "session_start_enabled": False,
        "precompact_enabled": False,
        "machine_specific_absolute_dependency_present": False,
        "notes": [],
    }

    if not report["settings_present"]:
        report["notes"].append(
            "No .claude/settings.json. Claude Code will still load CLAUDE.md, so "
            "the cold start is reachable - it simply is not announced automatically. "
            "Register the two hooks against ops/bootstrap/ to restore that."
        )
        emit(report)
        return 1

    try:
        cfg = json.load(open(SETTINGS, encoding="utf-8"))
    except Exception as exc:
        report["notes"].append("settings.json does not parse: %s" % exc)
        emit(report)
        return 1

    targets_exist, targets_tracked, absolute = [], [], []
    for event, canonical in CANONICAL.items():
        cmds = commands_for(cfg, event)
        canonical_posix = canonical.replace(os.sep, "/")
        points_at_canonical = any(canonical_posix in c.replace("\\", "/") for c in cmds)
        exists = os.path.exists(os.path.join(ROOT, canonical))
        is_tracked = tracked(canonical)
        # An absolute path in the REGISTRATION is expected: Claude Code resolves
        # the command itself. An absolute path is a defect only when it points
        # somewhere other than the tracked implementation.
        has_abs = any((":" in c or c.strip().startswith("/")) for c in cmds)
        report["events"][event] = {
            "registered": bool(cmds),
            "points_at_tracked_implementation": points_at_canonical,
            "canonical_target": canonical_posix,
            "target_exists": exists,
            "target_tracked_in_origin_main": is_tracked,
            "commands": cmds,
        }
        targets_exist.append(exists)
        targets_tracked.append(is_tracked)
        if has_abs and not points_at_canonical:
            absolute.append(event)

    report["session_start_enabled"] = report["events"]["SessionStart"]["registered"]
    report["precompact_enabled"] = report["events"]["PreCompact"]["registered"]
    report["hooks_installed"] = report["session_start_enabled"] and report["precompact_enabled"]
    report["hook_targets_exist"] = all(targets_exist)
    report["hook_target_is_tracked"] = all(targets_tracked)
    report["machine_specific_absolute_dependency_present"] = bool(absolute)
    if absolute:
        report["notes"].append(
            "These events are registered with an absolute path that is NOT the "
            "tracked implementation: %s. A fresh clone cannot reproduce them." % absolute
        )
    report["notes"].append(
        "The registration in .claude/settings.json is machine-local by necessity "
        "(.claude/ is gitignored) and uses an absolute path because Claude Code "
        "resolves the command itself. That is expected. What matters is that it "
        "points at the tracked implementation under ops/bootstrap/."
    )

    emit(report)
    return 0 if (report["hooks_installed"] and report["hook_targets_exist"]
                 and report["hook_target_is_tracked"]
                 and not report["machine_specific_absolute_dependency_present"]) else 1


def emit(report):
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
        return
    def mark(v):
        return "OK  " if v else "FAIL"
    print("Claude Code bootstrap integration")
    print("  repository            %s" % report["repository_root"])
    print("  %s hooks_installed" % mark(report["hooks_installed"]))
    print("  %s hook_targets_exist" % mark(report["hook_targets_exist"]))
    print("  %s hook_target_is_tracked" % mark(report["hook_target_is_tracked"]))
    print("  %s session_start_enabled" % mark(report["session_start_enabled"]))
    print("  %s precompact_enabled" % mark(report["precompact_enabled"]))
    print("  %s no stray machine-specific dependency"
          % mark(not report["machine_specific_absolute_dependency_present"]))
    for event, info in report["events"].items():
        print("  %-13s -> %s" % (event, info["canonical_target"]
                                 if info["points_at_tracked_implementation"]
                                 else info["commands"]))
    for note in report["notes"]:
        print("  note: %s" % note)


if __name__ == "__main__":
    sys.exit(main())
