"""List registered coworking agents — the read-only half of the connector.

This is the ONE command an agent runs to see who is working on what right now.
It exists because the data always existed and nobody looked at it: on
2026-08-16 every agent row on the Carpet was three weeks stale while two agents
worked a full day in parallel, and four messages sat unread while their sender
believed the two of them were synchronised. Mail that has not been read is not
synchronisation, and a status row nobody writes is worse than none - it reads as
fact.

So this prints four things together, because separately none of them is an
answer:

  1. WHO HOLDS THE DEPLOY LOCK - the only real mutual exclusion we have.
  2. EVERY AGENT'S CURRENT TASK, with the age of the claim, and a loud warning
     when a row calls itself active but has not been touched in hours.
  3. UNREAD MAIL PER RECIPIENT - so a sender can see that the other side has
     NOT read them, instead of assuming delivery is receipt.
  4. SHARED MEMORY - CoworkingSharedMemory has existed since the project's first
     migration and stood empty until 2026-08-16: open questions, what shipped
     today, and standing facts, in ONE row both agents read and write. The Owner's
     goal for this command is symmetry - "you know what he knows, he knows what
     you know" - and a private mail thread cannot deliver that on its own,
     because a fact one agent learns and never posts here stays private no
     matter how many messages get exchanged around it. Write to it with
     `coworking_update --open-question/--completed/--shared-memory`.

Usage:
    python manage.py coworking_list
    python manage.py coworking_list --agent greenbear   # one agent's view
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from coworking.models import CoworkingAgent, CoworkingMessage, CoworkingSharedMemory

# A row that calls itself active and has not been written in this long is not
# describing the present. Chosen to be longer than a normal pause and much
# shorter than the three weeks that made this command necessary.
STALE_AFTER_SECONDS = 4 * 3600

DEPLOY_LOCK_RELATIVE_PATH = (".agent-chat", "deploy.lock")


def human_age(then, now=None) -> str:
    """'never', or a coarse age. Coarse on purpose: nobody needs seconds."""
    if then is None:
        return "never"
    now = now or timezone.now()
    seconds = int((now - then).total_seconds())
    if seconds < 0:
        return "in the future"
    if seconds < 90:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def read_deploy_lock() -> str:
    """The lock is a tracked file in the repo, not a database row.

    AGENTS.md section 8 makes the in-repo `.agent-chat/deploy.lock` the single
    lock. It is read here rather than reimplemented because two agents once
    claimed two DIFFERENT lock files - one inside the repo and one a level above
    it - and neither could see the other. One lock, one path, read from disk.
    """
    path = settings.BASE_DIR.joinpath(*DEPLOY_LOCK_RELATIVE_PATH)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return "FREE (no lock file)"
    if not text:
        return "FREE (lock file is empty)"
    fields = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    holder = fields.get("agent", "unknown")
    version = fields.get("version", "?")
    started = fields.get("started_utc", "?")
    task = fields.get("task", "")
    out = f"HELD BY {holder} — v{version}, claimed {started}"
    if task:
        out += f"\n            task: {task}"
    return out


class Command(BaseCommand):
    help = (
        "Show who is working on what right now: the deploy lock, every agent's "
        "current task and its age, and unread mail per recipient."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--agent",
            help="Limit the agent list to one agent_id (mail totals still cover everyone).",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(f"CARPET SYNC — {now:%Y-%m-%d %H:%M} UTC")
        self.stdout.write("")
        self.stdout.write(f"DEPLOY LOCK: {read_deploy_lock()}")
        self.stdout.write("")

        agents = CoworkingAgent.objects.all()
        if options.get("agent"):
            agents = agents.filter(agent_id=options["agent"])
        if not agents:
            self.stdout.write("No agents registered yet.")
            return

        self.stdout.write("AGENTS")
        for agent in agents:
            age = human_age(agent.last_seen, now)
            line = (
                f"  {agent.agent_id:<12} {agent.label:<14} "
                f"{agent.status.upper():<8} seen {age}"
            )
            self.stdout.write(line)
            if self._is_stale(agent, now):
                self.stdout.write(
                    "      ** STALE: this row calls itself active but has not been "
                    "written in hours. Do not trust it as current work. **"
                )
            if agent.task_title:
                self.stdout.write(f"      task: {agent.task_title}")
            if agent.task_next_step:
                self.stdout.write(f"      next: {agent.task_next_step}")
            if agent.blockers:
                self.stdout.write(f"      blocked: {agent.blockers}")

        self.stdout.write("")
        self.stdout.write("UNREAD MAIL (delivery is not receipt)")
        any_unread = False
        for agent in CoworkingAgent.objects.all():
            unread = list(CoworkingMessage.unread_for(agent.agent_id))
            if not unread:
                self.stdout.write(f"  -> {agent.agent_id:<12} 0 unread")
                continue
            any_unread = True
            ids = ", ".join(str(m.pk) for m in unread)
            oldest = human_age(unread[0].created_at, now)
            self.stdout.write(
                f"  -> {agent.agent_id:<12} {len(unread)} UNREAD ({ids}) "
                f"— oldest {oldest}"
            )
        if any_unread:
            self.stdout.write("")
            self.stdout.write(
                "  An unread message means that agent may be working on the same "
                "thing you are. Do not treat sending as synchronising."
            )

        shared = CoworkingSharedMemory.load()
        self.stdout.write("")
        self.stdout.write(
            f"SHARED MEMORY (updated {human_age(shared.updated_at, now)})"
        )
        self._write_bulleted("open questions", shared.open_questions)
        self._write_bulleted("completed today", shared.completed_today)
        self._write_bulleted("standing facts", shared.project_memory)

    def _write_bulleted(self, title, items):
        if not items:
            self.stdout.write(f"  {title}: none recorded")
            return
        self.stdout.write(f"  {title}:")
        for item in items:
            self.stdout.write(f"    - {item}")

    @staticmethod
    def _is_stale(agent, now) -> bool:
        if agent.status != CoworkingAgent.Status.ACTIVE:
            return False
        if agent.last_seen is None:
            return True
        return (now - agent.last_seen).total_seconds() > STALE_AFTER_SECONDS
