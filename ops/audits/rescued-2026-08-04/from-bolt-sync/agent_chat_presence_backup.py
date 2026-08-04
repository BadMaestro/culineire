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
    python ops/agent_chat.py online --agent cursor    # Online (YYYY-MM-DD HH:MM:SS)
    python ops/agent_chat.py offline --agent cursor   # Left the Chat

The Owner reads it at http://localhost:8799/ - a local page that appends new
messages via /api/messages (no full reload). Presence lines appear when an agent
reads/sends (or calls online/offline). Silence longer than ~4 minutes becomes
"Left the Chat". It is not published anywhere and never touches production.
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
PRESENCE_DIR = ROOT / "presence"
TRANSCRIPT = ROOT / "chat.log"

KNOWN_AGENTS = ["bolt", "cursor", "arenafront", "ember", "greenbear", "owner"]
# Pollers run ~180s; leave a little headroom before declaring "Left the Chat".
ONLINE_TIMEOUT_SEC = int(os.environ.get("AGENT_CHAT_ONLINE_TIMEOUT", "240"))


def _ensure_dirs() -> None:
    MSG_DIR.mkdir(parents=True, exist_ok=True)
    MARK_DIR.mkdir(parents=True, exist_ok=True)
    PRESENCE_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")


def _display_when() -> str:
    """Local wall clock for Online lines — date + time only, no timezone label."""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


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


def write_message(sender: str, text: str, to: str = "all", kind: str = "msg") -> str:
    """Append one message. The single writer for the CLI, the web form and the API.

    Three callers writing three slightly different files is how a channel starts
    lying about itself, so they all come through here.
    """
    _ensure_dirs()
    sender = (sender or "").strip().lower() or "unknown"
    text = (text or "").strip()
    if not text:
        raise ValueError("refusing to send an empty message")

    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    name = f"{_now()}-{sender}-{suffix}.json"
    payload = {
        "id": name[:-5],
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "from": sender,
        "to": (to or "all").strip().lower(),
        "kind": kind,
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
    return name


def _presence_path(agent: str) -> Path:
    return PRESENCE_DIR / f"{agent}.json"


def _load_presence(agent: str) -> dict:
    path = _presence_path(agent)
    if not path.is_file():
        return {"agent": agent, "online": False, "last_seen": None}
    data = _load(path) or {}
    return {
        "agent": agent,
        "online": bool(data.get("online")),
        "last_seen": data.get("last_seen"),
    }


def _save_presence(agent: str, online: bool, last_seen: str | None) -> None:
    _ensure_dirs()
    path = _presence_path(agent)
    payload = {"agent": agent, "online": online, "last_seen": last_seen}
    fd, tmp = tempfile.mkstemp(dir=str(PRESENCE_DIR), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def mark_online(agent: str) -> bool:
    """Touch presence. On offline→online, append the Online system line.

    Returns True when an Online announcement was written.
    """
    agent = (agent or "").strip().lower()
    if not agent or agent == "unknown":
        return False
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prev = _load_presence(agent)
    announced = False
    if not prev.get("online"):
        when = _display_when()
        write_message(
            agent,
            f"Online ({when})",
            to="all",
            kind="presence",
        )
        announced = True
    _save_presence(agent, True, now)
    return announced


def mark_offline(agent: str) -> bool:
    """Mark left. On online→offline, append the Left the Chat system line."""
    agent = (agent or "").strip().lower()
    if not agent or agent == "unknown":
        return False
    prev = _load_presence(agent)
    if not prev.get("online"):
        _save_presence(agent, False, prev.get("last_seen"))
        return False
    write_message(
        agent,
        "Left the Chat",
        to="all",
        kind="presence",
    )
    _save_presence(agent, False, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return True


def sweep_stale_presence() -> list[str]:
    """Anyone online whose last heartbeat is too old → Left the Chat."""
    left: list[str] = []
    if not PRESENCE_DIR.is_dir():
        return left
    now = datetime.now(timezone.utc)
    for path in PRESENCE_DIR.glob("*.json"):
        data = _load(path) or {}
        agent = (data.get("agent") or path.stem).strip().lower()
        if not data.get("online"):
            continue
        raw = data.get("last_seen") or ""
        try:
            seen = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
        except ValueError:
            mark_offline(agent)
            left.append(agent)
            continue
        age = (now - seen).total_seconds()
        if age > ONLINE_TIMEOUT_SEC:
            mark_offline(agent)
            left.append(agent)
    return left


def list_online_agents() -> list[dict]:
    sweep_stale_presence()
    out: list[dict] = []
    if not PRESENCE_DIR.is_dir():
        return out
    for path in sorted(PRESENCE_DIR.glob("*.json")):
        data = _load(path) or {}
        if data.get("online"):
            out.append({
                "agent": data.get("agent") or path.stem,
                "last_seen": data.get("last_seen"),
            })
    return out


def cmd_send(args: argparse.Namespace) -> int:
    try:
        mark_online(args.sender)
        name = write_message(args.sender, args.text, args.to, args.kind)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"sent {name}")
    return 0


def cmd_online(args: argparse.Namespace) -> int:
    agent = args.agent.strip().lower()
    if mark_online(agent):
        print(f"online announced: {agent}")
    else:
        print(f"already online / heartbeat: {agent}")
    return 0


def cmd_offline(args: argparse.Namespace) -> int:
    agent = args.agent.strip().lower()
    if mark_offline(agent):
        print(f"left announced: {agent}")
    else:
        print(f"already offline: {agent}")
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
        if msg.get("kind") == "presence":
            continue  # Online/Left is for the Owner window, not poller wakeups
        if msg.get("to") not in ("all", agent):
            continue
        out.append(msg)
    return out, last


def cmd_read(args: argparse.Namespace) -> int:
    _ensure_dirs()
    agent = args.agent.strip().lower()
    mark_online(agent)
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
    agent = args.agent.strip().lower()
    mark_online(agent)
    messages, _ = _unread(agent)
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Чат агентов CulinEire</title>
<style>
 body{{background:#14120f;color:#e8e3d3;font:15px/1.55 Inter,Segoe UI,sans-serif;
      margin:0;padding:1.5rem 1.5rem 12rem}}
 h1{{font:600 1.15rem/1.3 Georgia,serif;color:#c9a227;margin:0 0 .25rem}}
 .sub{{color:#8b8578;font-size:.82rem;margin-bottom:.55rem}}
 .roster{{color:#8b8578;font-size:.82rem;margin-bottom:1.1rem}}
 .roster b{{color:#c9a227;font-weight:600}}
 .dot{{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;
       background:#4f9d69;margin-right:.3rem;vertical-align:middle}}
 .m{{border-left:3px solid #444;padding:.45rem .8rem;margin:.35rem 0;
     background:#1b1815;border-radius:0 4px 4px 0}}
 .m.presence{{background:transparent;color:#9a9488;font-style:italic}}
 .m.presence .who{{font-style:normal}}
 .m.presence .tx{{margin-top:.15rem}}
 .who{{font-weight:600}} .to{{color:#8b8578;font-weight:400}}
 .ts{{color:#6f6a60;font-size:.75rem;float:right}}
 .tx{{white-space:pre-wrap;margin-top:.15rem;overflow-wrap:anywhere}}
 .empty{{color:#8b8578;font-style:italic}}
 form{{position:fixed;left:0;right:0;bottom:0;background:#0f0d0b;
       border-top:1px solid #2a2622;padding:.7rem 1.5rem;display:flex;gap:.5rem;
       align-items:flex-start;flex-wrap:wrap}}
 select,textarea,button{{font:inherit;background:#1b1815;color:#e8e3d3;
       border:1px solid #3a352f;border-radius:4px;padding:.45rem .6rem}}
 textarea{{flex:1;min-width:14rem;min-height:2.6rem;resize:vertical}}
 button{{background:#c9a227;color:#14120f;font-weight:600;border:0;cursor:pointer;
       padding:.5rem 1.1rem}}
 .hint{{flex-basis:100%;color:#6f6a60;font-size:.72rem;margin-top:.15rem}}
</style></head><body>
<h1>Чат агентов</h1>
<div class="sub"><span id="count">{count}</span> сообщений · новые дописываются каждые 5 секунд · {net}</div>
<div class="roster"><span class="dot"></span>Online: <b id="roster">{roster}</b></div>
<div id="log" data-last="{last_id}">{body}</div>
<form method="post" action="/" id="send">
  <select name="from" title="от кого">{who_options}</select>
  <select name="to" title="кому">{to_options}</select>
  <textarea name="text" placeholder="Написать в чат — Enter отправит, Shift+Enter перенесёт строку" autofocus></textarea>
  <button type="submit">Отправить</button>
  <div class="hint">Enter отправляет · Shift+Enter — новая строка · страница не перезагружается · Online/Left пишутся в ленту</div>
</form>
<script>
 var box    = document.querySelector('textarea');
 var log    = document.getElementById('log');
 var count  = document.getElementById('count');
 var roster = document.getElementById('roster');
 var form   = document.getElementById('send');
 var COLOURS = {colours};

 function atBottom() {{
   return (window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 120);
 }}
 function toBottom() {{ window.scrollTo(0, document.body.scrollHeight); }}

 function esc(s) {{
   return String(s).replace(/[&<>"]/g, function (c) {{
     return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c];
   }});
 }}

 function render(m) {{
   var colour = COLOURS[m.from] || '#8b8578';
   var d = document.createElement('div');
   if (m.kind === 'presence') {{
     d.className = 'm presence';
     d.style.borderLeftColor = colour;
     d.innerHTML = '<span class="ts">' + esc(m.ts) + '</span>'
                 + '<span class="who" style="color:' + colour + '">' + esc(m.from) + '</span>'
                 + '<div class="tx">' + esc(m.text) + '</div>';
     return d;
   }}
   var to = (m.to && m.to !== 'all') ? ' <span class="to">&rarr; ' + esc(m.to) + '</span>' : '';
   d.className = 'm';
   d.style.borderLeftColor = colour;
   d.innerHTML = '<span class="ts">' + esc(m.ts) + '</span>'
               + '<span class="who" style="color:' + colour + '">' + esc(m.from) + '</span>' + to
               + '<div class="tx">' + esc(m.text) + '</div>';
   return d;
 }}

 function paintRoster(list) {{
   if (!list || !list.length) {{ roster.textContent = 'nobody'; return; }}
   roster.textContent = list.map(function (x) {{ return x.agent; }}).join(', ');
 }}

 function refreshRoster() {{
   fetch('/api/presence')
     .then(function (r) {{ return r.json(); }})
     .then(paintRoster)
     .catch(function () {{}});
 }}

 function appendList(list, forceBottom) {{
   if (!list.length) {{ return; }}
   var empty = log.querySelector('.empty');
   if (empty) {{ empty.remove(); }}
   var stick = forceBottom || atBottom();
   list.forEach(function (m) {{
     log.appendChild(render(m));
     if (m.id) {{ log.dataset.last = m.id; }}
   }});
   count.textContent = log.querySelectorAll('.m').length;
   if (stick) {{ toBottom(); }}
   refreshRoster();
 }}

 function poll() {{
   fetch('/api/messages?since=' + encodeURIComponent(log.dataset.last || ''))
     .then(function (r) {{ return r.json(); }})
     .then(function (list) {{ appendList(list, false); }})
     .catch(function () {{}});
   refreshRoster();
 }}

 form.addEventListener('submit', function (e) {{
   e.preventDefault();
   var text = box.value.trim();
   if (!text) {{ return; }}
   var body = new URLSearchParams(new FormData(form)).toString();
   box.value = '';
   fetch('/', {{
     method: 'POST',
     headers: {{
       'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
       'Accept': 'application/json'
     }},
     body: body
   }})
     .then(function (r) {{
       if (!r.ok) {{ throw new Error('send failed'); }}
       return fetch('/api/messages?since=' + encodeURIComponent(log.dataset.last || ''))
         .then(function (r2) {{ return r2.json(); }})
         .then(function (list) {{ appendList(list, true); }});
     }})
     .catch(function () {{ box.value = text; }});
 }});

 box.addEventListener('keydown', function (e) {{
   if (e.key !== 'Enter' || e.shiftKey) {{ return; }}
   e.preventDefault();
   if (!box.value.trim()) {{ return; }}
   if (form.requestSubmit) {{ form.requestSubmit(); }}
   else {{ form.dispatchEvent(new Event('submit', {{ cancelable: true }})); }}
 }});

 toBottom();
 refreshRoster();
 setInterval(poll, 5000);
</script>
</body></html>"""


def _lan_addresses(port: int) -> list[str]:
    """Every address another machine on this network could use to reach us."""
    import socket

    out = []
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and f"http://{ip}:{port}/" not in out:
                out.append(f"http://{ip}:{port}/")
    except OSError:
        pass
    return out


def _render_page(port: int = 8799, network: bool = False) -> bytes:
    sweep_stale_presence()
    files = _message_files()[-300:]
    rows = []
    for file in files:
        msg = _load(file)
        if not msg:
            continue
        if msg.get("kind") == "presence":
            who = msg.get("from", "?")
            colour = _COLOURS.get(who, "#8b8578")
            rows.append(
                f'<div class="m presence" style="border-left-color:{colour}">'
                f'<span class="ts">{html.escape(msg.get("ts", ""))}</span>'
                f'<span class="who" style="color:{colour}">{html.escape(who)}</span>'
                f'<div class="tx">{html.escape(msg.get("text", ""))}</div></div>'
            )
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

    who_options = "".join(
        f'<option value="{a}"{" selected" if a == "owner" else ""}>{a}</option>'
        for a in KNOWN_AGENTS
    )
    to_options = '<option value="all" selected>всем</option>' + "".join(
        f'<option value="{a}">{a}</option>' for a in KNOWN_AGENTS if a != "owner"
    )

    if network:
        addrs = _lan_addresses(port)
        net = "открыт для сети: " + (", ".join(addrs) if addrs else f"порт {port}")
    else:
        net = "только эта машина"

    last_id = files[-1].name[:-5] if files else ""
    online = list_online_agents()
    roster = ", ".join(x["agent"] for x in online) if online else "nobody"

    return _PAGE.format(
        count=len(files),
        body=body,
        net=html.escape(net),
        who_options=who_options,
        to_options=to_options,
        last_id=html.escape(last_id),
        colours=json.dumps(_COLOURS, ensure_ascii=False),
        roster=html.escape(roster),
    ).encode("utf-8")


def cmd_serve(args: argparse.Namespace) -> int:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    _ensure_dirs()
    host = "0.0.0.0" if args.network else "127.0.0.1"
    port = args.port
    networked = bool(args.network)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, code, body: bytes, ctype="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            # Owner window must never keep a stale full-reload page in cache.
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - name fixed by the stdlib
            path = urlparse(self.path).path
            if path == "/api/presence":
                body = json.dumps(list_online_agents(), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if path == "/api/messages":
                # Stale heartbeats become "Left the Chat" before the next poll.
                sweep_stale_presence()
                qs = parse_qs(urlparse(self.path).query)
                since = (qs.get("since") or [""])[0]
                out = []
                for file in _message_files():
                    if since and file.name[:-5] <= since:
                        continue
                    msg = _load(file)
                    if msg:
                        out.append(msg)
                self._send(200, json.dumps(out, ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")
                return
            self._send(200, _render_page(port, networked))

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""

            if path == "/api/presence":
                try:
                    data = json.loads(raw or "{}")
                    agent = (data.get("agent") or "").strip().lower()
                    state = (data.get("state") or "heartbeat").strip().lower()
                    if not agent:
                        raise ValueError("agent required")
                    if state in ("offline", "left", "leave"):
                        changed = mark_offline(agent)
                    else:
                        changed = mark_online(agent)
                    payload = {"ok": True, "agent": agent, "state": state, "announced": changed}
                    self._send(200, json.dumps(payload).encode("utf-8"),
                               "application/json; charset=utf-8")
                except (ValueError, TypeError) as exc:
                    self._send(400, json.dumps({"error": str(exc)}).encode("utf-8"),
                               "application/json; charset=utf-8")
                return

            if path == "/api/send":
                # Agents post JSON; a bad body must not take the server down.
                try:
                    data = json.loads(raw or "{}")
                    sender = data.get("from", "")
                    mark_online(sender)
                    name = write_message(sender, data.get("text", ""),
                                         data.get("to", "all"), data.get("kind", "msg"))
                except (ValueError, TypeError) as exc:
                    self._send(400, json.dumps({"error": str(exc)}).encode("utf-8"),
                               "application/json; charset=utf-8")
                    return
                self._send(200, json.dumps({"ok": True, "id": name[:-5]}).encode("utf-8"),
                           "application/json; charset=utf-8")
                return

            form = parse_qs(raw)
            want_json = "application/json" in (self.headers.get("Accept") or "")
            try:
                sender = (form.get("from") or [""])[0]
                mark_online(sender)
                write_message(sender,
                              (form.get("text") or [""])[0],
                              (form.get("to") or ["all"])[0])
            except ValueError:
                if want_json:
                    self._send(400, b'{"ok":false,"error":"empty"}',
                               "application/json; charset=utf-8")
                    return
                self._send(200, _render_page(port, networked))
                return
            # JS posts with Accept: application/json — no redirect, no scroll jump.
            if want_json:
                self._send(200, b'{"ok":true}', "application/json; charset=utf-8")
                return
            # Non-JS fallback: redirect so a refresh does not resend.
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_args):
            pass  # polls must not bury the console

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"chat page: http://localhost:{port}/   (Ctrl+C to stop)")
    if networked:
        for addr in _lan_addresses(port) or [f"http://<this-machine>:{port}/"]:
            print(f"  from other machines on this network: {addr}")
        print("  agents elsewhere: GET /api/messages?since=<id> , POST /api/send")
        print("  NOTE: no password. Anyone who can reach this port can read and post.")
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
    p_send.add_argument("--kind", default="msg", choices=["msg", "order", "report", "block", "presence"])
    p_send.set_defaults(func=cmd_send)

    p_read = sub.add_parser("read", help="new messages, and mark them read")
    p_read.add_argument("--agent", required=True)
    p_read.set_defaults(func=cmd_read)

    p_peek = sub.add_parser("peek", help="new messages without marking them read")
    p_peek.add_argument("--agent", required=True)
    p_peek.set_defaults(func=cmd_peek)

    p_online = sub.add_parser("online", help="announce Agent online (or heartbeat)")
    p_online.add_argument("--agent", required=True)
    p_online.set_defaults(func=cmd_online)

    p_offline = sub.add_parser("offline", help="announce Agent left the chat")
    p_offline.add_argument("--agent", required=True)
    p_offline.set_defaults(func=cmd_offline)

    p_tail = sub.add_parser("tail", help="the last messages, for a human")
    p_tail.add_argument("-n", "--number", type=int, default=20)
    p_tail.set_defaults(func=cmd_tail)

    p_serve = sub.add_parser("serve", help="serve the chat page (read and write)")
    p_serve.add_argument("--port", type=int, default=8799)
    p_serve.add_argument("--network", action="store_true",
                         help="bind to the LAN so other machines and their agents can join")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
