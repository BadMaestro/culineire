#!/usr/bin/env python3
"""The "Передать эстафету" button — as a CLI command, because agents live on
different machines/accounts and a local web server can't reach across that.

This script ONLY edits state.json locally. After it runs, a human still has
to explicitly commit + push (this script prints the exact reminder) so the
other machine can `git pull` and see the handoff. No git command in this
script — that decision always stays with the human.

Usage:
    python coworking/handoff.py --from agent_a --to agent_b --note "Finished the CSS pass, see next_step"

To register a brand-new agent (no code change needed to add more agents):
    python coworking/handoff.py --add-agent --label "Mac Mini / Code C" [--id agent_c]
"""

from __future__ import annotations

import argparse
import sys

from state_manager import add_agent, get_state, list_agents, perform_handoff, slugify_agent_id, write_state


def cmd_list(_args) -> int:
    state = get_state()
    agents = list_agents(state)
    if not agents:
        print("No agents registered yet.")
        return 0
    print("Registered agents:")
    for a in agents:
        print(f"  - {a['id']:<12} {a.get('label', ''):<30} status={a.get('status')}  last_seen={a.get('last_seen') or 'never'}")
    return 0


def cmd_add_agent(args) -> int:
    label = args.label
    agent_id = args.id or slugify_agent_id(label)
    state = get_state()
    add_agent(state, agent_id, label=label)
    write_state(state)
    print(f"[coworking] Registered new agent: {agent_id} ({label})")
    print("[coworking] This is a LOCAL change. Ask the human to commit + push "
          "coworking/state.json so other machines can see this new agent.")
    return 0


def cmd_handoff(args) -> int:
    state = get_state()
    try:
        perform_handoff(state, args.from_id, args.to_id, note=args.note or "")
    except (KeyError, ValueError) as exc:
        print(f"[coworking] ERROR: {exc}", file=sys.stderr)
        print("[coworking] Run 'python coworking/handoff.py list' to see registered agent ids.")
        return 1
    write_state(state)
    print(f"[coworking] Handoff recorded locally: {args.from_id} -> {args.to_id}.")
    print(
        "[coworking] This is a LOCAL change only. The other machine cannot see it "
        "until you ask the human to review the diff of coworking/state.json and "
        "explicitly commit + push it. After that, the receiving agent runs "
        "'git pull' on their own machine and reads this agent's current_task / "
        "next_step to continue."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="List registered agents")
    list_p.set_defaults(func=cmd_list)

    add_p = sub.add_parser("add-agent", help="Register a new agent slot")
    add_p.add_argument("--label", required=True)
    add_p.add_argument("--id", help="Optional explicit agent id; auto-slugified from --label if omitted")
    add_p.set_defaults(func=cmd_add_agent)

    handoff_p = sub.add_parser("handoff", help="Hand off from one agent to another")
    handoff_p.add_argument("--from", dest="from_id", required=True)
    handoff_p.add_argument("--to", dest="to_id", required=True)
    handoff_p.add_argument("--note", default="")
    handoff_p.set_defaults(func=cmd_handoff)

    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
