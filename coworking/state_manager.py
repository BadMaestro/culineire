"""Read/write helpers for coworking/state.json.

This module never touches git. Committing and pushing state.json is a
manual, human-confirmed step — see AGENT_INSTRUCTIONS.md.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

COWORKING_DIR = Path(__file__).resolve().parent
STATE_FILE = COWORKING_DIR / "state.json"
EXAMPLE_FILE = COWORKING_DIR / "state.example.json"

MAX_LOG_ENTRIES = 50
MAX_FIELD_LENGTH = 4000  # guards against accidentally dumping secrets/huge blobs


def _bootstrap_if_missing() -> None:
    if not STATE_FILE.exists():
        if not EXAMPLE_FILE.exists():
            raise FileNotFoundError(
                f"Neither {STATE_FILE} nor {EXAMPLE_FILE} exist. Cannot bootstrap state."
            )
        shutil.copy(EXAMPLE_FILE, STATE_FILE)


def get_state() -> dict[str, Any]:
    _bootstrap_if_missing()
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_agent(agent_id: str) -> dict[str, Any] | None:
    return get_state().get("agents", {}).get(agent_id)


def truncate(value: str) -> str:
    if value is None:
        return value
    value = str(value)
    if len(value) > MAX_FIELD_LENGTH:
        return value[:MAX_FIELD_LENGTH] + "\n...[truncated]"
    return value


def write_state(state: dict[str, Any]) -> None:
    """Validate and atomically write state.json. Never calls git."""
    # Validate it round-trips through JSON cleanly before touching disk.
    serialized = json.dumps(state, indent=2, ensure_ascii=False)
    json.loads(serialized)  # raises if somehow invalid

    tmp_path = STATE_FILE.with_suffix(".json.tmp")
    tmp_path.write_text(serialized + "\n", encoding="utf-8")
    tmp_path.replace(STATE_FILE)  # atomic on POSIX and Windows (same filesystem)


def new_agent_skeleton(agent_id: str, label: str = "") -> dict[str, Any]:
    return {
        "id": agent_id,
        "label": label or agent_id,
        "last_seen": "",
        "status": "idle",
        "current_task": {
            "title": "",
            "description": "",
            "started_at": "",
            "branch": "",
            "files_touched": [],
            "next_step": "",
        },
        "active_prompt": "",
        "memory": {
            "key_facts": [],
            "decisions_made": [],
            "blockers": [],
        },
        "log": [],
    }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify_agent_id(label: str) -> str:
    """Turn a free-text label into a stable agent_id slug, e.g. 'Mac Mini / Code C' -> 'mac_mini_code_c'."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug or "agent"


def add_agent(state: dict[str, Any], agent_id: str, label: str = "") -> dict[str, Any]:
    """Add a new agent slot if it doesn't already exist. Returns the (new or existing) agent dict.

    This is how new agents get registered for future handoffs — no hardcoded
    limit on agent count, no code change required to add one.
    """
    agents = state.setdefault("agents", {})
    if agent_id not in agents:
        agents[agent_id] = new_agent_skeleton(agent_id, label=label or agent_id)
    elif label:
        agents[agent_id]["label"] = truncate(label)
    return agents[agent_id]


def list_agents(state: dict[str, Any]) -> list[dict[str, Any]]:
    return list(state.get("agents", {}).values())


def perform_handoff(state: dict[str, Any], from_id: str, to_id: str, note: str = "") -> None:
    """Mark from_id as done/idle and to_id as active, with a logged note on both sides.

    This only flips status + appends log entries. It does not move
    current_task data automatically — the receiving agent reads the
    handing-off agent's current_task/next_step themselves (see
    ONBOARDING.md step 6), which keeps the source of truth in one place.
    """
    agents = state.setdefault("agents", {})
    if from_id not in agents:
        raise KeyError(f"Unknown agent id: {from_id}")
    if to_id not in agents:
        raise KeyError(f"Unknown agent id: {to_id}")
    if from_id == to_id:
        raise ValueError("Cannot hand off to the same agent.")

    ts = _now_iso()
    note = truncate(note)

    from_agent = agents[from_id]
    from_agent["status"] = "idle"
    from_agent["last_seen"] = ts
    from_agent.setdefault("log", []).append({
        "ts": ts,
        "action": f"Handed off to {agents[to_id].get('label', to_id)}",
        "result": "ok",
        "note": note,
    })
    from_agent["log"] = from_agent["log"][-MAX_LOG_ENTRIES:]

    to_agent = agents[to_id]
    to_agent["status"] = "active"
    to_agent["last_seen"] = ts
    to_agent.setdefault("log", []).append({
        "ts": ts,
        "action": f"Received handoff from {from_agent.get('label', from_id)}",
        "result": "ok",
        "note": note,
    })
    to_agent["log"] = to_agent["log"][-MAX_LOG_ENTRIES:]
