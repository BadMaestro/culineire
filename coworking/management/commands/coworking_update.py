"""Agent self-reporting CLI: updates this agent's row in the live database.

Run on whichever machine has access to manage.py against the target
database (typically via SSH on the production server, same as other ops
commands in this project). No git involved — the database itself is the
shared state across agents/machines.

Usage:
    python manage.py coworking_update --agent bolt --label Bolt --status active \
        --task "Fix sponsors N+1 query" --next "Run audit.py to verify fix" \
        --log "Modified sponsors/views.py" --log-result ok
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from coworking.models import CoworkingAgent, CoworkingSharedMemory

MAX_FIELD_LENGTH = 4000


def _truncate(value: str) -> str:
    if not value:
        return value
    if len(value) > MAX_FIELD_LENGTH:
        return value[:MAX_FIELD_LENGTH] + "\n...[truncated]"
    return value


class Command(BaseCommand):
    help = "Update a coworking agent's status/task/log in the database."

    def add_arguments(self, parser):
        parser.add_argument("--agent", required=True, help="Agent id, e.g. bolt")
        parser.add_argument("--label", help="Human-readable label, e.g. Bolt")
        parser.add_argument("--status", choices=[c.value for c in CoworkingAgent.Status])
        parser.add_argument("--task", help="task_title")
        parser.add_argument("--task-desc", help="task_description")
        parser.add_argument("--branch", help="task_branch")
        parser.add_argument("--files", help="Comma-separated list, merged into task_files_touched")
        parser.add_argument("--next", help="task_next_step (be specific!)")
        parser.add_argument("--prompt", help="Path to a file with the active prompt text")
        parser.add_argument("--log", help="Log entry action text")
        parser.add_argument("--log-result", choices=["ok", "blocked", "pending"], default="ok")
        parser.add_argument("--log-note", default="")
        parser.add_argument("--key-fact", action="append", default=[])
        parser.add_argument("--decision", action="append", default=[])
        parser.add_argument("--blocker", action="append", default=[])
        parser.add_argument("--shared-memory", action="append", default=[])
        parser.add_argument("--open-question", action="append", default=[])
        parser.add_argument("--completed", action="append", default=[])

    def handle(self, *args, **options):
        agent, created = CoworkingAgent.objects.get_or_create(
            agent_id=options["agent"],
            defaults={"label": options.get("label") or options["agent"]},
        )
        if created:
            self.stdout.write(f"Created new agent: {agent.agent_id}")

        if options.get("label"):
            agent.label = _truncate(options["label"])
        if options.get("status"):
            agent.status = options["status"]
        if options.get("task") is not None:
            agent.task_title = _truncate(options["task"])
            if not agent.task_started_at:
                agent.task_started_at = timezone.now()
        if options.get("task_desc") is not None:
            agent.task_description = _truncate(options["task_desc"])
        if options.get("branch") is not None:
            agent.task_branch = _truncate(options["branch"])
        if options.get("next") is not None:
            agent.task_next_step = _truncate(options["next"])
        if options.get("files"):
            existing = set(agent.task_files_touched or [])
            existing.update(f.strip() for f in options["files"].split(",") if f.strip())
            agent.task_files_touched = sorted(existing)
        if options.get("prompt"):
            with open(options["prompt"], encoding="utf-8") as f:
                agent.active_prompt = _truncate(f.read())

        agent.key_facts = (agent.key_facts or []) + [_truncate(v) for v in options["key_fact"]]
        agent.decisions_made = (agent.decisions_made or []) + [_truncate(v) for v in options["decision"]]
        agent.blockers = (agent.blockers or []) + [_truncate(v) for v in options["blocker"]]

        agent.last_seen = timezone.now()
        agent.save()

        if options.get("log"):
            agent.log_entries.create(
                action=_truncate(options["log"]),
                result=options["log_result"],
                note=_truncate(options["log_note"]),
            )
            # Trim to last 50 entries for this agent.
            stale_ids = list(
                agent.log_entries.order_by("-ts").values_list("pk", flat=True)[50:]
            )
            if stale_ids:
                agent.log_entries.filter(pk__in=stale_ids).delete()

        if options["shared_memory"] or options["open_question"] or options["completed"]:
            shared = CoworkingSharedMemory.load()
            shared.project_memory = (shared.project_memory or []) + [_truncate(v) for v in options["shared_memory"]]
            shared.open_questions = (shared.open_questions or []) + [_truncate(v) for v in options["open_question"]]
            shared.completed_today = (shared.completed_today or []) + [_truncate(v) for v in options["completed"]]
            shared.save()

        self.stdout.write(self.style.SUCCESS(f"Updated agent '{agent.agent_id}'."))
