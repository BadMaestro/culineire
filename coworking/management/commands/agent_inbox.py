"""Print (and optionally clear) an agent's directed-message inbox.

Used by the live CoWork poller: `agent_inbox bolt --since <id>` prints only
messages newer than a watermark, one per line as `<id>\t<friendly text>`, so the
poller can surface each new message once and advance its local watermark without
mutating the database.
"""
from django.core.management.base import BaseCommand

from coworking.models import CoworkingMessage


class Command(BaseCommand):
    help = "Show directed messages addressed to an agent (for inbox polling)."

    def add_arguments(self, parser):
        parser.add_argument("agent_id", help="Recipient agent_id, e.g. 'bolt'.")
        parser.add_argument(
            "--since", type=int, default=None,
            help="Only messages with id greater than this (watermark).",
        )
        parser.add_argument(
            "--unread", action="store_true",
            help="Only unread messages (ignored if --since is given).",
        )
        parser.add_argument(
            "--mark-read", action="store_true",
            help="Mark the returned messages as read.",
        )

    def handle(self, *args, **options):
        agent_id = options["agent_id"]
        qs = CoworkingMessage.objects.filter(to_agent_id=agent_id).select_related("from_agent")
        if options["since"] is not None:
            qs = qs.filter(id__gt=options["since"])
        elif options["unread"]:
            qs = qs.filter(read_at__isnull=True)
        qs = qs.order_by("id")

        ids = []
        for m in qs:
            ids.append(m.id)
            body_oneline = " ".join(m.body.split())
            if len(body_oneline) > 240:
                body_oneline = body_oneline[:240] + "…"
            subject = f' "{m.subject}"' if m.subject else ""
            friendly = f"\U0001F4E8 {m.from_agent_id}→{agent_id} #{m.id}{subject}: {body_oneline}"
            # <id>\t<friendly> — the poller splits on the first tab.
            self.stdout.write(f"{m.id}\t{friendly}")

        if options["mark_read"] and ids:
            from django.utils import timezone
            CoworkingMessage.objects.filter(id__in=ids, read_at__isnull=True).update(
                read_at=timezone.now()
            )
