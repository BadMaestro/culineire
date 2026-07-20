#!/usr/bin/env python3
"""CulinEire test panel — a small local dashboard for watching server test runs.

Runs on your own machine, not on the site. It reads the regression logs off the
production box over the ssh key you already use, and shows them next to the two
numbers that decide whether a server run is safe to start at all: how many real
people are on the site right now, and what version is live.

    python tools/test_panel.py

Then open http://localhost:8765 — it refreshes itself.

Nothing here writes to the server: it only reads logs, the visitor counter and
the public footer. Safe to leave open.
"""

from __future__ import annotations

import html
import json
import re
import shlex
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST, PORT = "127.0.0.1", 8765
POLL_SECONDS = 10
SSH = "ssh -i ~/.ssh/culineire_linode -o ConnectTimeout=10 deploy@80.85.84.156"

# The visitor count the monitoring dashboard itself shows (monitoring/views.py:
# online_now) — distinct human sessions seen in the last five minutes.
TRAFFIC_PY = """
from django.utils import timezone
from monitoring.models import PageView
now = timezone.now()
def humans(minutes):
    since = now - timezone.timedelta(minutes=minutes)
    return (PageView.objects.filter(created_at__gte=since, is_bot=False)
            .exclude(session_key="").values("session_key").distinct().count())
print(humans(5), humans(60))
"""

_state: dict = {"runs": [], "traffic": None, "version": None, "checked": None, "error": None}
_lock = threading.Lock()


def _sh(cmd: str, timeout: int = 30) -> str:
    """Run a command through WSL bash and return stdout (empty string on failure)."""
    try:
        out = subprocess.run(
            ["wsl", "-e", "bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def _parse_run(name: str, body: str, running: bool, age: int | None) -> dict:
    """Turn a raw regression log into something worth looking at.

    Deliberately no progress bar: the runner's dots share their lines with the
    app's own log output, so any count of them is a guess. A run reports its own
    honest total when it finishes; until then all we truly know is that it is
    still going, and for how long.
    """
    ran = re.search(r"^Ran (\d+) tests? in ([\d.]+)s", body, re.M)
    failures = re.findall(r"^(?:FAIL|ERROR): (\S+)", body, re.M)
    verdict = "running"
    if re.search(r"^OK", body, re.M):
        verdict = "passed"
    elif re.search(r"^FAILED", body, re.M):
        verdict = "failed"
    elif not running:
        verdict = "died"
    found = re.search(r"Found (\d+) test", body)
    return {
        "name": name,
        "verdict": verdict,
        "running": running,
        "total": int(ran.group(1)) if ran else (int(found.group(1)) if found else None),
        "seconds": float(ran.group(2)) if ran else None,
        "elapsed": age if running else None,
        "failures": failures,
    }


def poll_once() -> None:
    logs = _sh(f"{SSH} 'ls -t /tmp/bolt_reg*.log 2>/dev/null | head -4'")
    running_raw = _sh(f"{SSH} 'pgrep -f bolt_fresh.py | head -1'")
    running = bool(running_raw.strip())
    log_paths = [p for p in logs.splitlines() if p.strip()]

    runs = []
    for path in log_paths:
        body = _sh(f"{SSH} 'cat {path} 2>/dev/null | tail -c 20000'", timeout=40)
        if not body:
            continue
        is_live = running and path == log_paths[0]
        age = None
        if is_live:
            started = _sh(f"{SSH} 'stat -c %Y {path} 2>/dev/null; date +%s'")
            nums = [int(n) for n in started.split() if n.isdigit()]
            if len(nums) == 2:
                age = max(0, nums[1] - nums[0])
        runs.append(_parse_run(path.split("/")[-1], body, is_live, age))

    traffic_out = _sh(
        f"{SSH} 'cd /srv/culineire/current && set -a && source /srv/culineire/shared/.env "
        f"&& set +a && /srv/culineire/venv/bin/python manage.py shell < /tmp/panel_traffic.py 2>/dev/null | tail -1'",
        timeout=60,
    )
    traffic = None
    m = re.search(r"(\d+)\s+(\d+)\s*$", traffic_out.strip())
    if m:
        traffic = {"now": int(m.group(1)), "hour": int(m.group(2))}

    version = _sh("curl -s https://culineire.ie/ | grep -oE 'v2\\.5\\.[0-9]+' | head -1", timeout=30)

    with _lock:
        _state.update({
            "runs": runs,
            "traffic": traffic,
            "version": version or None,
            "checked": datetime.now().strftime("%H:%M:%S"),
        })


def upload_traffic_query() -> None:
    """Put the visitor query on the server once. Piping a multi-line script
    through `shell -c` over ssh mangles its quoting; a plain file does not."""
    _sh(f"printf %s {shlex.quote(TRAFFIC_PY)} | {SSH} 'cat > /tmp/panel_traffic.py'", timeout=30)


def poller() -> None:
    upload_traffic_query()
    while True:
        try:
            poll_once()
        except Exception as exc:  # a panel that dies on one bad poll is useless
            with _lock:
                _state["error"] = str(exc)[:200]
        time.sleep(POLL_SECONDS)


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>CulinEire — test panel</title>
<meta http-equiv="refresh" content="10">
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; padding:24px; background:#14110e; color:#e8e0d2;
         font:14px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace; }}
  h1 {{ font-size:15px; letter-spacing:.14em; text-transform:uppercase;
        color:#c8942a; margin:0 0 18px; }}
  .row {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }}
  .tile {{ background:#1d1915; border:1px solid #342d24; border-radius:10px;
           padding:12px 16px; min-width:150px; }}
  .tile b {{ display:block; font-size:24px; margin-top:4px; }}
  .k {{ color:#8b7355; font-size:11px; letter-spacing:.08em; text-transform:uppercase; }}
  .run {{ background:#1d1915; border:1px solid #342d24; border-left-width:4px;
          border-radius:10px; padding:14px 16px; margin-bottom:10px; }}
  .passed {{ border-left-color:#4c9a5a; }}
  .failed {{ border-left-color:#c0504d; }}
  .running {{ border-left-color:#c8942a; }}
  .died {{ border-left-color:#6b6157; }}
  .verdict {{ font-weight:700; letter-spacing:.1em; text-transform:uppercase; }}
  .passed .verdict {{ color:#6cc47e; }}
  .failed .verdict {{ color:#e2726e; }}
  .running .verdict {{ color:#e8b04b; }}
  .died .verdict {{ color:#9b9086; }}
  .fail {{ color:#e2726e; margin-left:14px; }}
  .muted {{ color:#8b7355; }}
  .bar {{ height:5px; background:#2b241d; border-radius:3px; overflow:hidden; margin-top:8px; }}
  .bar i {{ display:block; height:100%; background:#c8942a; }}
  .safe {{ color:#6cc47e; }} .busy {{ color:#e8b04b; }}
</style></head><body>
<h1>CulinEire — test panel</h1>
<div class="row">
  <div class="tile"><span class="k">People on site now</span><b class="{traffic_cls}">{now}</b>
    <span class="muted">{hour} in the last hour</span></div>
  <div class="tile"><span class="k">Server runs</span><b class="{safe_cls}">{safe}</b>
    <span class="muted">{safe_note}</span></div>
  <div class="tile"><span class="k">Live version</span><b>{version}</b></div>
  <div class="tile"><span class="k">Checked</span><b>{checked}</b>
    <span class="muted">every {poll}s</span></div>
</div>
{runs}
<p class="muted">Reads only: regression logs, the visitor counter, the public footer.</p>
</body></html>"""


def render() -> str:
    with _lock:
        s = dict(_state)
    t = s.get("traffic")
    now = "?" if not t else t["now"]
    hour = "?" if not t else t["hour"]
    quiet = bool(t) and t["now"] == 0
    runs_html = ""
    for r in s["runs"] or []:
        fails = "".join(
            f'<div class="fail">✗ {html.escape(f)}</div>' for f in r["failures"][:12]
        )
        total = f' · {r["total"]} tests' if r["total"] else ""
        if r["seconds"]:
            timing = f' · took {r["seconds"] / 60:.0f} min'
        elif r["elapsed"] is not None:
            timing = f' · {r["elapsed"] // 60} min so far'
        else:
            timing = ""
        runs_html += (
            f'<div class="run {r["verdict"]}">'
            f'<span class="verdict">{r["verdict"]}</span> '
            f'<span class="muted">{html.escape(r["name"])}{total}{timing}</span>'
            f'{fails}</div>'
        )
    if not runs_html:
        runs_html = '<div class="run died"><span class="muted">No regression logs on the server yet.</span></div>'
    return PAGE.format(
        now=now, hour=hour,
        traffic_cls="safe" if quiet else "busy",
        safe="clear" if quiet else "hold",
        safe_cls="safe" if quiet else "busy",
        safe_note="nobody to disturb" if quiet else "someone is on the site",
        version=s.get("version") or "?",
        checked=s.get("checked") or "…",
        poll=POLL_SECONDS,
        runs=runs_html,
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.startswith("/json"):
            body, ctype = json.dumps(_state, indent=2).encode(), "application/json"
        else:
            body, ctype = render().encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the console quiet
        pass


if __name__ == "__main__":
    threading.Thread(target=poller, daemon=True).start()
    print(f"CulinEire test panel -> http://{HOST}:{PORT}   (Ctrl+C to stop)")
    HTTPServer((HOST, PORT), Handler).serve_forever()
