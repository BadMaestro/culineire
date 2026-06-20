#!/usr/bin/env python3
"""Generate a self-contained static HTML dashboard from coworking/state.json.

This is a local-only file (coworking/dashboard.html). It is NOT a Django
view, is NOT deployed, and is NOT served by the website. Re-run this script
whenever you want a fresh snapshot; open the generated file directly in a
browser.

Usage:
    python coworking/generate_dashboard.py
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

from state_manager import COWORKING_DIR, get_state

OUTPUT_FILE = COWORKING_DIR / "dashboard.html"

STATUS_BADGES = {
    "active": "\U0001F7E2 active",
    "idle": "\U0001F7E1 idle",
    "limit_hit": "\U0001F534 limit hit",
    "blocked": "\U0001F534 blocked",
}

RESULT_COLORS = {
    "ok": "#1a6b3a",
    "blocked": "#b3261e",
    "pending": "#a86a00",
}


def e(value) -> str:
    """Escape any value for safe HTML embedding."""
    return html.escape(str(value if value is not None else ""))


def render_list(items: list[str]) -> str:
    if not items:
        return "<p class='empty'>(none)</p>"
    return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>"


def render_log(entries: list[dict]) -> str:
    if not entries:
        return "<p class='empty'>(no log entries yet)</p>"
    rows = []
    for entry in reversed(entries[-15:]):
        color = RESULT_COLORS.get(entry.get("result", ""), "#666")
        note = f" &mdash; {e(entry.get('note'))}" if entry.get("note") else ""
        rows.append(
            f"<li><span class='log-ts'>{e(entry.get('ts'))}</span> "
            f"<span class='log-result' style='color:{color}'>[{e(entry.get('result'))}]</span> "
            f"{e(entry.get('action'))}{note}</li>"
        )
    return "<ol class='log'>" + "".join(rows) + "</ol>"


def render_agent_card(agent: dict) -> str:
    status = agent.get("status", "idle")
    badge = STATUS_BADGES.get(status, e(status))
    task = agent.get("current_task", {}) or {}
    memory = agent.get("memory", {}) or {}
    files_touched = ", ".join(task.get("files_touched", [])) or "(none)"
    prompt_text = e(agent.get("active_prompt") or "(none)")

    blockers = memory.get("blockers", [])
    blockers_html = (
        f"<div class='blockers'>{render_list(blockers)}</div>" if blockers else "<p class='empty'>(none)</p>"
    )

    return f"""
    <section class="agent-card">
      <header>
        <h2>{e(agent.get('label', agent.get('id')))}</h2>
        <span class="badge">{badge}</span>
        <span class="last-seen">last seen: {e(agent.get('last_seen') or 'never')}</span>
      </header>

      <h3>Current Task</h3>
      <p><strong>{e(task.get('title') or '(none)')}</strong></p>
      <p>{e(task.get('description') or '')}</p>
      <p>Branch: <code>{e(task.get('branch') or '(none)')}</code></p>
      <p>Files touched: <code>{e(files_touched)}</code></p>
      <p class="next-step">Next step: {e(task.get('next_step') or '(none)')}</p>

      <h3>Active Prompt</h3>
      <pre class="prompt-box">{prompt_text}</pre>
      <button class="copy-btn" data-agent-id="{e(agent.get('id'))}">Подхватить работу (copy handoff prompt)</button>

      <h3>Memory</h3>
      <p>Key facts:</p>
      {render_list(memory.get('key_facts', []))}
      <p>Decisions made:</p>
      {render_list(memory.get('decisions_made', []))}
      <p>Blockers:</p>
      {blockers_html}

      <h3>Log (last 15)</h3>
      {render_log(agent.get('log', []))}
    </section>
    """


def build_handoff_text(agent: dict) -> str:
    task = agent.get("current_task", {}) or {}
    memory = agent.get("memory", {}) or {}
    shared_placeholder = "{{SHARED_MEMORY}}"
    lines = [
        f"=== HANDOFF FROM {agent.get('label', agent.get('id'))} @ {agent.get('last_seen', '?')} ===",
        "",
        f"CURRENT TASK: {task.get('title', '')}",
        task.get("description", ""),
        "",
        f"BRANCH: {task.get('branch', '')}",
        f"FILES TOUCHED: {', '.join(task.get('files_touched', []))}",
        "",
        "NEXT STEP (start here):",
        task.get("next_step", ""),
        "",
        "ACTIVE PROMPT:",
        agent.get("active_prompt", ""),
        "",
        "KEY FACTS:",
        *[f"- {f}" for f in memory.get("key_facts", [])],
        "",
        "DECISIONS MADE:",
        *[f"- {d}" for d in memory.get("decisions_made", [])],
        "",
        "OPEN BLOCKERS:",
        *[f"- {b}" for b in memory.get("blockers", [])],
        "",
        "PROJECT MEMORY:",
        shared_placeholder,
        "=== END HANDOFF ===",
    ]
    return "\n".join(lines)


def render(state: dict) -> str:
    agents = state.get("agents", {})
    shared = state.get("shared", {}) or {}

    cards_html = "".join(render_agent_card(a) for a in agents.values())

    handoff_map = {
        agent_id: build_handoff_text(agent).replace(
            "{{SHARED_MEMORY}}", "\n".join(f"- {m}" for m in shared.get("project_memory", [])) or "(none)"
        )
        for agent_id, agent in agents.items()
    }
    # JSON-encode safely for embedding in a <script> tag.
    import json as _json
    handoff_json = _json.dumps(handoff_map, ensure_ascii=False)

    shared_html = f"""
    <section class="shared">
      <h2>Shared</h2>
      <h3>Project memory</h3>
      {render_list(shared.get('project_memory', []))}
      <h3>Open questions</h3>
      {render_list(shared.get('open_questions', []))}
      <h3>Completed today</h3>
      <ul class="completed">{''.join(f"<li>{e(c)}</li>" for c in shared.get('completed_today', [])) or "<li class='empty'>(none)</li>"}</ul>
    </section>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Знакомство — Agent Coworking (local snapshot)</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #faf8f4; color: #28221e; margin: 0; padding: 1.5rem; }}
  .note {{ background: #fff3cd; border: 1px solid #e0c45a; border-radius: 8px; padding: .75rem 1rem; margin-bottom: 1.5rem; font-size: .9rem; }}
  .board {{ display: flex; gap: 1.5rem; flex-wrap: wrap; }}
  .agent-card {{ flex: 1 1 380px; background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 1rem 1.25rem; }}
  .agent-card header {{ display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap; margin-bottom: .5rem; }}
  .agent-card h2 {{ margin: 0; font-size: 1.1rem; }}
  .badge {{ font-size: .8rem; }}
  .last-seen {{ font-size: .75rem; color: #888; margin-left: auto; }}
  .next-step {{ background: #fff8d6; padding: .4rem .6rem; border-radius: 6px; }}
  .prompt-box {{ background: #f4f1ec; border-radius: 6px; padding: .6rem; max-height: 200px; overflow-y: auto; font-size: .8rem; white-space: pre-wrap; }}
  .copy-btn {{ margin: .5rem 0 1rem; padding: .4rem .8rem; border-radius: 6px; border: 1px solid #aaa; background: #eee; cursor: pointer; }}
  .log {{ font-size: .85rem; padding-left: 1.2rem; }}
  .log-ts {{ color: #888; font-size: .75rem; }}
  .empty {{ color: #999; font-style: italic; }}
  .completed li {{ text-decoration: line-through; color: #888; }}
  .shared {{ margin-top: 2rem; background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 1rem 1.25rem; }}
</style>
</head>
<body>
  <h1>Знакомство — Agent Coworking (local snapshot)</h1>
  <div class="note">
    This is a static, local-only file generated from coworking/state.json.
    It is not part of the website, not deployed, and not auto-refreshing.
    Re-run <code>python coworking/generate_dashboard.py</code> for a fresh snapshot.
  </div>
  <div class="board">
    {cards_html}
  </div>
  {shared_html}
  <script>
    var HANDOFF_TEXT = {handoff_json};
    document.querySelectorAll('.copy-btn').forEach(function (btn) {{
      btn.addEventListener('click', function () {{
        var id = btn.getAttribute('data-agent-id');
        var text = HANDOFF_TEXT[id] || '';
        navigator.clipboard.writeText(text).then(function () {{
          btn.textContent = 'Copied!';
          setTimeout(function () {{ btn.textContent = 'Подхватить работу (copy handoff prompt)'; }}, 1500);
        }});
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> int:
    state = get_state()
    html_out = render(state)
    OUTPUT_FILE.write_text(html_out, encoding="utf-8")
    print(f"[coworking] Dashboard written to {OUTPUT_FILE}")
    print(f"[coworking] Open it directly in a browser: file://{OUTPUT_FILE.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
