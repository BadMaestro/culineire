#!/usr/bin/env python3
"""CLI for agents to update coworking/state.json.

IMPORTANT: this script never runs git. It only reads, merges and writes
coworking/state.json on disk. Committing/pushing that file is a separate,
human-confirmed step (show the diff, wait for explicit "yes", then commit).

Usage:
    python coworking/update_state.py --agent agent_a --label "GreenBear / Code A" \
        --task "Fix sponsors N+1 query" --next "Run audit.py to verify fix" \
        --log "Modified sponsors/views.py - removed N+1 in get_sponsors()" \
        --log-result ok --status active
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from state_manager import (
    MAX_LOG_ENTRIES,
    truncate,
    get_state,
    new_agent_skeleton,
    write_state,
)

VALID_STATUSES = {"active", "idle", "limit_hit", "blocked"}
VALID_LOG_RESULTS = {"ok", "blocked", "pending"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--agent", required=True, help="Agent id, e.g. agent_a")
    p.add_argument("--label", help="Human-readable label for this agent")
    p.add_argument("--status", choices=sorted(VALID_STATUSES))
    p.add_argument("--task", help="current_task.title")
    p.add_argument("--task-desc", help="current_task.description")
    p.add_argument("--branch", help="current_task.branch")
    p.add_argument("--files", help="Comma-separated list, merged into current_task.files_touched")
    p.add_argument("--next", help="current_task.next_step (be specific!)")
    p.add_argument("--prompt", help="Path to a file containing the active prompt to store")
    p.add_argument("--log", help="Log entry action text")
    p.add_argument("--log-result", choices=sorted(VALID_LOG_RESULTS), default="ok")
    p.add_argument("--log-note", help="Optional extra note for the log entry")
    p.add_argument("--key-fact", action="append", default=[], help="Append to memory.key_facts")
    p.add_argument("--decision", action="append", default=[], help="Append to memory.decisions_made")
    p.add_argument("--blocker", action="append", default=[], help="Append to memory.blockers")
    p.add_argument("--shared-memory", action="append", default=[], help="Append to shared.project_memory")
    p.add_argument("--open-question", action="append", default=[], help="Append to shared.open_questions")
    p.add_argument("--completed", action="append", default=[], help="Append to shared.completed_today")
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    state = get_state()
    agents = state.setdefault("agents", {})
    agent = agents.get(args.agent)
    if agent is None:
        agent = new_agent_skeleton(args.agent, label=args.label or args.agent)
        agents[args.agent] = agent
        print(f"[coworking] Created new agent slot: {args.agent}")

    if args.label:
        agent["label"] = truncate(args.label)
    if args.status:
        agent["status"] = args.status

    task = agent.setdefault("current_task", {})
    if args.task is not None:
        task["title"] = truncate(args.task)
        task.setdefault("started_at", _now_iso())
    if args.task_desc is not None:
        task["description"] = truncate(args.task_desc)
    if args.branch is not None:
        task["branch"] = truncate(args.branch)
    if args.next is not None:
        task["next_step"] = truncate(args.next)
    if args.files:
        existing = set(task.get("files_touched", []))
        existing.update(f.strip() for f in args.files.split(",") if f.strip())
        task["files_touched"] = sorted(existing)

    if args.prompt:
        try:
            with open(args.prompt, encoding="utf-8") as f:
                agent["active_prompt"] = truncate(f.read())
        except OSError as exc:
            print(f"[coworking] WARNING: could not read --prompt file: {exc}", file=sys.stderr)

    memory = agent.setdefault("memory", {"key_facts": [], "decisions_made": [], "blockers": []})
    memory.setdefault("key_facts", []).extend(truncate(v) for v in args.key_fact)
    memory.setdefault("decisions_made", []).extend(truncate(v) for v in args.decision)
    memory.setdefault("blockers", []).extend(truncate(v) for v in args.blocker)

    if args.log:
        log = agent.setdefault("log", [])
        log.append({
            "ts": _now_iso(),
            "action": truncate(args.log),
            "result": args.log_result,
            "note": truncate(args.log_note or ""),
        })
        agent["log"] = log[-MAX_LOG_ENTRIES:]

    agent["last_seen"] = _now_iso()

    shared = state.setdefault("shared", {"project_memory": [], "open_questions": [], "completed_today": []})
    shared.setdefault("project_memory", []).extend(truncate(v) for v in args.shared_memory)
    shared.setdefault("open_questions", []).extend(truncate(v) for v in args.open_question)
    shared.setdefault("completed_today", []).extend(truncate(v) for v in args.completed)

    write_state(state)
    print(f"[coworking] state.json updated for {args.agent}.")
    print("[coworking] Reminder: this is a LOCAL change only. Ask the human before "
          "committing/pushing coworking/state.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
