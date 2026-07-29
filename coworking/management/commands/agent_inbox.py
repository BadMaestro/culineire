"""Print (and optionally clear) an agent's directed-message inbox.

Used by the live CoWork poller: `agent_inbox bolt --since <id>` prints only
messages newer than a watermark, one per line as `<id>\t<friendly text>`, so the
poller can surface each new message once and advance its local watermark without
mutating the database.

With `--wait` the command blocks until a message is actually available, waking
the instant one is sent (Postgres LISTEN on the `cowork_inbox` channel that
CoworkingMessage.send NOTIFYs) and re-checking the table periodically as a
self-heal. That turns "poll every N seconds and hope" into "return the moment
mail arrives", so agents stop waiting on each other's timers.
"""
import time

from django.core.management.base import BaseCommand
from django.db import connection

from coworking.models import COWORK_INBOX_CHANNEL, CoworkingMessage


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
        parser.add_argument(
            "--wait", action="store_true",
            help="Block until at least one matching message exists, then print it.",
        )
        parser.add_argument(
            "--timeout", type=float, default=55.0,
            help="With --wait, seconds to block before returning empty (default 55).",
        )

    def _matching(self, agent_id, options):
        qs = CoworkingMessage.objects.filter(to_agent_id=agent_id).select_related("from_agent")
        if options["since"] is not None:
            qs = qs.filter(id__gt=options["since"])
        elif options["unread"] or options["wait"]:
            # --wait implies "tell me about something new"; default it to unread
            # when no explicit watermark was given.
            qs = qs.filter(read_at__isnull=True)
        return qs.order_by("id")

    def handle(self, *args, **options):
        agent_id = options["agent_id"]

        if options["wait"] and not self._matching(agent_id, options).exists():
            self._wait_for_message(agent_id, options)

        qs = self._matching(agent_id, options)
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

    def _wait_for_message(self, agent_id, options):
        """Block until a matching message exists or the timeout elapses.

        Waits on a dedicated Postgres LISTEN connection so a NOTIFY wakes it
        immediately; a short per-slice timeout also re-queries the table, so a
        missed or cross-machine notification still self-heals within seconds."""
        if connection.vendor != "postgresql":
            # Off Postgres (local sqlite): degrade to a light poll loop.
            self._poll_until(agent_id, options)
            return

        import psycopg

        sd = connection.settings_dict
        conninfo = psycopg.conninfo.make_conninfo(
            dbname=sd["NAME"],
            user=sd.get("USER") or None,
            password=sd.get("PASSWORD") or None,
            host=sd.get("HOST") or None,
            port=str(sd["PORT"]) if sd.get("PORT") else None,
        )
        deadline = time.monotonic() + float(options["timeout"])
        with psycopg.connect(conninfo, autocommit=True) as conn:
            conn.execute(f'LISTEN "{COWORK_INBOX_CHANNEL}"')
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                # Wake on a NOTIFY for us, or fall through every couple of
                # seconds to re-check the table regardless.
                for note in conn.notifies(timeout=min(2.0, remaining)):
                    if not note.payload or note.payload == agent_id:
                        break
                if self._matching(agent_id, options).exists():
                    return

    def _poll_until(self, agent_id, options):
        deadline = time.monotonic() + float(options["timeout"])
        while time.monotonic() < deadline:
            if self._matching(agent_id, options).exists():
                return
            time.sleep(0.5)
