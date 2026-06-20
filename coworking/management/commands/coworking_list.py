"""List registered coworking agents — the read-only half of the connector.

Usage:
    python manage.py coworking_list
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from coworking.models import CoworkingAgent


class Command(BaseCommand):
    help = "List registered coworking agents and their current status."

    def handle(self, *args, **options):
        agents = CoworkingAgent.objects.all()
        if not agents:
            self.stdout.write("No agents registered yet.")
            return
        for agent in agents:
            self.stdout.write(
                f"{agent.agent_id:<14} {agent.label:<30} status={agent.status:<8} "
                f"last_seen={agent.last_seen or 'never'}"
            )
            if agent.task_next_step:
                self.stdout.write(f"  -> next_step: {agent.task_next_step}")
