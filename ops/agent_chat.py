#!/usr/bin/env python3
"""The agents' local chat. No server, no Django, no network.

Why this exists: agent-to-agent messages used to travel to the production Linode
and back. Each poll ran `manage.py agent_inbox`, which boots the whole of Django;
one was caught on 2026-07-27 at 90% of that machine's single core, and two of
them running every 45-90 seconds is what drove load5 to 2.70 and nearly took the
live site down. Every agent on this project runs on ONE workstation, so those
messages never needed to leave it.

The design is deliberately the dumbest thing that works:

  one message = one small JSON file in a shared directory

There is no lock, because nobody ever writes the same file twice - each name
carries a timestamp, the sender, and a random suffix. There is no index to
corrupt: the directory listing IS the chat, and the names sort chronologically.
Reading is a listing plus a string comparison against a per-agent watermark.

Nothing here is a competing source of truth. Git holds the code, CoWork holds
the audit trail of decisions, and this holds the conversation while it happens.

DO NOT ISSUE ORDERS HERE. Proven on the first night, 2026-07-27: an order posted
at 00:33 UTC was never seen, and ArenaFront said so plainly when asked - he acted
only once the same order arrived over CoWork. A channel without a reader on the
other end is not a channel, and the Director who used it anyway wasted an agent's
time and then blamed the silence. Orders go over CoWork, which every agent's
poller reads. This carries chatter between agents and the Owner's reading page.
That changes the day an agent proves its poller reads this directory too.

Usage:
    python ops/agent_chat.py send --from bolt --text "C4: run the weight gate"
    python ops/agent_chat.py send --from bolt --to cursor --text "..."
    python ops/agent_chat.py read --agent cursor      # new only, moves watermark
    python ops/agent_chat.py peek --agent cursor      # new only, leaves it alone
    python ops/agent_chat.py tail -n 30               # recent, for humans
    python ops/agent_chat.py serve --port 8799        # a page the Owner can read

The Owner reads it at http://localhost:8799/ - a local page that refreshes
itself. It is not published anywhere and never touches production.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import secrets
import string
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# The chat lives beside the repositories, not inside one: every agent works in a
# different worktree, and all of them must see the same directory.
DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent / ".agent-chat"
ROOT = Path(os.environ.get("AGENT_CHAT_DIR", DEFAULT_ROOT))
MSG_DIR = ROOT / "msgs"
MARK_DIR = ROOT / "read"
TRANSCRIPT = ROOT / "chat.log"

KNOWN_AGENTS = ["bolt", "cursor", "arenafront", "ember", "greenbear", "owner"]


def _ensure_dirs() -> None:
    MSG_DIR.mkdir(parents=True, exist_ok=True)
    MARK_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")


def _message_files() -> list[Path]:
    """Every message, oldest first. The filename ordering is the chat ordering."""
    if not MSG_DIR.is_dir():
        return []
    return sorted(MSG_DIR.glob("*.json"), key=lambda p: p.name)


def _load(path: Path) -> dict | None:
    """A half-written file is skipped rather than crashing the reader.

    It cannot normally happen - messages are written to a temporary file and
    renamed into place, and rename is atomic - but a reader that dies on one bad
    byte would take the whole channel down with it.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cmd_send(args: argparse.Namespace) -> int:
    _ensure_dirs()
    sender = args.sender.strip().lower()
    text = args.text.strip()
    if not text:
        print("refusing to send an empty message", file=sys.stderr)
        return 2

    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    name = f"{_now()}-{sender}-{suffix}.json"
    payload = {
        "id": name[:-5],
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "from": sender,
        "to": (args.to or "all").strip().lower(),
        "kind": args.kind,
        "text": text,
    }

    # Write beside the target and rename: a reader listing the directory either
    # sees a complete message or does not see it at all.
    fd, tmp = tempfile.mkstemp(dir=str(MSG_DIR), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, MSG_DIR / name)

    # A plain-text mirror, so `tail -f` works and a human never needs this tool.
    with TRANSCRIPT.open("a", encoding="utf-8") as log:
        log.write(f"[{payload['ts']}] {sender} -> {payload['to']}: {text}\n")

    print(f"sent {name}")
    return 0


def _watermark_path(agent: str) -> Path:
    return MARK_DIR / f"{agent}.watermark"


def _unread(agent: str) -> tuple[list[dict], str]:
    """Messages this agent has not seen, and the name to record if it reads them.

    A message addressed to somebody else is still skipped rather than hidden:
    the watermark advances past it, because 'unread' means 'arrived after the
    last one I looked at', not 'stored somewhere for me'.
    """
    mark = ""
    path = _watermark_path(agent)
    if path.is_file():
        mark = path.read_text(encoding="utf-8").strip()

    out: list[dict] = []
    last = mark
    for file in _message_files():
        if file.name <= mark:
            continue
        last = file.name
        msg = _load(file)
        if msg is None:
            continue
        if msg.get("from") == agent:
            continue  # nobody needs their own words read back to them
        if msg.get("to") not in ("all", agent):
            continue
        out.append(msg)
    return out, last


def cmd_read(args: argparse.Namespace) -> int:
    _ensure_dirs()
    agent = args.agent.strip().lower()
    messages, last = _unread(agent)
    for msg in messages:
        print(f"[{msg['ts']}] {msg['from']} -> {msg['to']}: {msg['text']}")
    if last:
        _watermark_path(agent).write_text(last, encoding="utf-8")
    if not messages:
        print(f"(no new messages for {agent})")
    return 0


def cmd_peek(args: argparse.Namespace) -> int:
    _ensure_dirs()
    messages, _ = _unread(args.agent.strip().lower())
    for msg in messages:
        print(f"[{msg['ts']}] {msg['from']} -> {msg['to']}: {msg['text']}")
    if not messages:
        print("(nothing new)")
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    _ensure_dirs()
    files = _message_files()[-args.number:]
    for file in files:
        msg = _load(file)
        if msg:
            print(f"[{msg['ts']}] {msg['from']} -> {msg['to']}: {msg['text']}")
    if not files:
        print("(the chat is empty)")
    return 0


# --------------------------------------------------------------------------
# The Owner's window. A local page, refreshing itself, reading the same files.
# --------------------------------------------------------------------------

_COLOURS = {
    "bolt": "#c9a227",
    "cursor": "#4f9d69",
    "arenafront": "#c05746",
    "ember": "#7a6ff0",
    "greenbear": "#6b7b6b",
    "owner": "#e8e3d3",
}

_PAGE = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>Чат агентов CulinEire</title>
<style>
 body{{background:#14120f;color:#e8e3d3;font:15px/1.55 Inter,Segoe UI,sans-serif;
      margin:0;padding:1.5rem}}
 h1{{font:600 1.15rem/1.3 Georgia,serif;color:#c9a227;margin:0 0 .25rem}}
 .sub{{color:#8b8578;font-size:.82rem;margin-bottom:1.25rem}}
 .m{{border-left:3px solid #444;padding:.45rem .8rem;margin:.35rem 0;
     background:#1b1815;border-radius:0 4px 4px 0}}
 .who{{font-weight:600}} .to{{color:#8b8578;font-weight:400}}
 .ts{{color:#6f6a60;font-size:.75rem;float:right}}
 .tx{{white-space:pre-wrap;margin-top:.15rem}}
 .empty{{color:#8b8578;font-style:italic}}
</style></head><body>
<h1>Чат агентов</h1>
<div class="sub">{count} сообщений · обновляется само каждые 5 секунд · только эта машина, сервер не участвует</div>
{body}
</body></html>"""


def _render_page() -> bytes:
    files = _message_files()[-300:]
    rows = []
    for file in files:
        msg = _load(file)
        if not msg:
            continue
        who = msg.get("from", "?")
        colour = _COLOURS.get(who, "#8b8578")
        to = msg.get("to", "all")
        to_label = "" if to == "all" else f' <span class="to">→ {html.escape(to)}</span>'
        rows.append(
            f'<div class="m" style="border-left-color:{colour}">'
            f'<span class="ts">{html.escape(msg.get("ts", ""))}</span>'
            f'<span class="who" style="color:{colour}">{html.escape(who)}</span>{to_label}'
            f'<div class="tx">{html.escape(msg.get("text", ""))}</div></div>'
        )
    body = "\n".join(rows) if rows else '<p class="empty">Пока пусто.</p>'
    return _PAGE.format(count=len(files), body=body).encode("utf-8")


def cmd_serve(args: argparse.Namespace) -> int:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    _ensure_dirs()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - name fixed by the stdlib
            payload = _render_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass  # a refresh every 5s would otherwise bury the console

    # Localhost only. This page is for the people at this machine and is not
    # published anywhere; binding to 0.0.0.0 would put it on the network.
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"chat page: http://localhost:{args.port}/   (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


def main() -> int:
    # The Windows console is cp1252 by default and cannot print Cyrillic: the
    # first live test sent a message fine and then crashed reading it back.
    # Every agent on this machine would have hit the same wall.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="The agents' local chat.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_send = sub.add_parser("send", help="post a message")
    p_send.add_argument("--from", dest="sender", required=True, help="your agent name")
    p_send.add_argument("--to", default="all", help="recipient, or 'all'")
    p_send.add_argument("--text", required=True)
    p_send.add_argument("--kind", default="msg", choices=["msg", "order", "report", "block"])
    p_send.set_defaults(func=cmd_send)

    p_read = sub.add_parser("read", help="new messages, and mark them read")
    p_read.add_argument("--agent", required=True)
    p_read.set_defaults(func=cmd_read)

    p_peek = sub.add_parser("peek", help="new messages without marking them read")
    p_peek.add_argument("--agent", required=True)
    p_peek.set_defaults(func=cmd_peek)

    p_tail = sub.add_parser("tail", help="the last messages, for a human")
    p_tail.add_argument("-n", "--number", type=int, default=20)
    p_tail.set_defaults(func=cmd_tail)

    p_serve = sub.add_parser("serve", help="serve the Owner's reading page")
    p_serve.add_argument("--port", type=int, default=8799)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
