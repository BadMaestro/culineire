"""Bolt chat poller. 180s interval (AGENTS.md s5 polling discipline).

Appends every new message addressed to bolt/all into a log file and rewrites a
heartbeat file each cycle. Runs until killed by PID.
"""
import json
import os
import time
import urllib.request

BASE = "http://192.168.178.189:8799"
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "bolt_inbox.log")
HEARTBEAT = os.path.join(HERE, "bolt_heartbeat.json")
INTERVAL = 180


def fetch():
    with urllib.request.urlopen(BASE + "/api/messages", timeout=10) as r:
        return json.load(r)


def main():
    seen = set()
    empty = 0
    try:
        messages = fetch()
    except Exception:
        messages = []
    for m in messages:
        seen.add(m["id"])
    while True:
        try:
            messages = fetch()
            fresh = [m for m in messages if m["id"] not in seen]
            for m in fresh:
                seen.add(m["id"])
                if m.get("to") in ("bolt", "all") and m.get("from") != "bolt":
                    with open(LOG, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(m, ensure_ascii=False) + "\n")
            empty = 0 if fresh else empty + 1
        except Exception as exc:
            empty += 1
            fresh = []
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"poller_error": str(exc)}) + "\n")
        with open(HEARTBEAT, "w", encoding="utf-8") as fh:
            json.dump({
                "agent": "bolt",
                "pid": os.getpid(),
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "poller_restarts": 0,
                "state": "AWAITING_ORDER",
                "current_task": "cold start complete, waiting for the Owner's order",
                "last_commit": "",
                "consecutive_empty_polls": empty,
            }, fh, ensure_ascii=False, indent=2)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
