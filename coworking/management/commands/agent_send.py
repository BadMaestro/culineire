"""Send one Carpet message from the command line.

Written 2026-08-03. agent_inbox could read the mail and nothing could post it,
so every reply meant hand-written code against production — which is exactly the
shape of access that should be built once instead of improvised each time.

The body comes from a FILE or from stdin, never from an argument. That is not a
convenience: AGENTS.md section 5 forbids passing non-ASCII as a raw command-line
argument, because the Windows shell re-encodes those bytes to ANSI before the
process ever sees them, and that is how an agent's Russian once reached the
Owner as a row of question marks. A file is read as UTF-8 by this process, so
the shell never touches the characters.
"""

import sys

from django.core.management.base import BaseCommand, CommandError

from coworking.models import CoworkingMessage


class Command(BaseCommand):
    help = "Send one Carpet message. Body is read from a file or stdin, never from an argument."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="from_agent", required=True,
                            help="Sender agent_id, lowercase (bolt, ember, greenbear).")
        parser.add_argument("--to", dest="to_agent", required=True,
                            help="Recipient agent_id, lowercase.")
        parser.add_argument("--subject", default="", help="Subject line.")
        parser.add_argument("--body-file", required=True,
                            help="Path to the UTF-8 body, or - to read stdin.")

    def handle(self, *args, **options):
        from_agent = options["from_agent"]
        to_agent = options["to_agent"]

        # An id is a system key, not a name: mailbox ids are lowercase and case
        # sensitive, and a capitalised one silently creates a second mailbox
        # while the sender is told SENT (AGENTS.md section 5).
        for label, value in (("--from", from_agent), ("--to", to_agent)):
            if value != value.lower():
                raise CommandError(
                    f"{label}={value!r} is not a mailbox id. Ids are lowercase; "
                    f"a capitalised one creates a second mailbox and loses the message."
                )
        if from_agent == to_agent:
            raise CommandError("Refusing to send a message to its own sender.")

        path = options["body_file"]
        if path == "-":
            body = sys.stdin.read()
        else:
            try:
                with open(path, encoding="utf-8") as handle:
                    body = handle.read()
            except OSError as exc:
                raise CommandError(f"Cannot read body file {path!r}: {exc}") from exc

        if not body.strip():
            raise CommandError("Empty body — refusing to send.")

        message = CoworkingMessage.send(
            from_agent=from_agent,
            to_agent=to_agent,
            subject=options["subject"],
            body=body,
        )
        self.stdout.write(
            f"SENT id={message.pk} from={message.from_agent.agent_id} "
            f"to={message.to_agent.agent_id} chars={len(body)}"
        )
