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

Three rules from AGENTS.md section 5 are enforced here rather than trusted to
the sender, in the order a body meets them:

  1. pure ASCII on the wire;
  2. the body is a JSON OBJECT, not prose;
  3. the language between agents is ENGLISH - no Cyrillic outside the one field
     reserved for relaying the Owner's own words verbatim.

All three were rules before they were checks, and all three were broken by this
command's own author on 2026-08-04 while the command sat there saying nothing.
"""

import json
import re
import sys

from django.core.management.base import BaseCommand, CommandError

from coworking.models import CoworkingMessage

# The one field where the Owner's own words may be carried in Russian.
# Translating an instruction changes it, and an agent relaying what he said must
# be able to hand over exactly what he said (AGENTS.md 5).
OWNER_VERBATIM_FIELD = "owner_verbatim"

CYRILLIC = re.compile(r"[Ѐ-ӿԀ-ԯ]")


def _cyrillic_paths(value, path="body"):
    """Every place Cyrillic appears, named by its JSON path.

    Reports WHERE, not just THAT: a sender who is told "there is Cyrillic
    somewhere" in a 4,000-character body will delete the wrong thing.
    """
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == OWNER_VERBATIM_FIELD:
                continue                     # the one sanctioned exception
            found.extend(_cyrillic_paths(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_cyrillic_paths(item, f"{path}[{index}]"))
    elif isinstance(value, str) and CYRILLIC.search(value):
        sample = CYRILLIC.search(value).group(0)
        found.append(f"  {path}: contains Cyrillic (first is {sample!r})")
    return found


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

        # AGENTS.md section 5: every Carpet message goes over the wire as pure
        # ASCII, with any other character carried as a \uXXXX escape. Reading the
        # body from a file protects it from the shell's codepage but not from the
        # author: on 2026-08-04 this command sent message #3473 carrying a single
        # stray a-circumflex inside a JavaScript snippet, and nothing objected.
        # A rule the tooling does not enforce survives exactly as long as the
        # author's attention does, so the check lives here now.
        #
        # It REFUSES rather than escapes. Rewriting somebody's body silently is
        # how a message stops saying what its author wrote, and only the sender
        # can tell whether that character was a slip or the subject of the
        # sentence — which, in #3473, it was.
        if not body.isascii():
            offenders = []
            for lineno, line in enumerate(body.splitlines(), start=1):
                for column, char in enumerate(line, start=1):
                    if not char.isascii():
                        offenders.append(
                            f"  line {lineno}, col {column}: {char!r} "
                            f"(escape as \\u{ord(char):04x})"
                        )
                        if len(offenders) >= 10:
                            break
                if len(offenders) >= 10:
                    break
            total = sum(1 for char in body if not char.isascii())
            raise CommandError(
                f"Body is not ASCII: {total} character(s) outside ASCII, first "
                f"{len(offenders)} shown. AGENTS.md section 5 requires the body to "
                f"reach the wire as pure ASCII — the shell and the OS codepage "
                f"corrupt anything else and a charset header does not save it.\n"
                + "\n".join(offenders)
                + "\n\nFix the body file, or serialise it with json.dumps(), which "
                "produces these escapes by default. NOTHING WAS SENT."
            )

        # AGENTS.md section 5: the body is a JSON object, not prose. This is not
        # tidiness — json.dumps emits ASCII by default, so a JSON body satisfies
        # the rule above by construction instead of by the author remembering.
        try:
            parsed = json.loads(body)
        except ValueError as exc:
            raise CommandError(
                f"Body is not JSON: {exc}. AGENTS.md section 5 requires an agent-"
                f"to-agent body to be a JSON object, e.g.\n"
                f'  {{"from": "GreenBear", "to": "Bolt", "subject": "...", '
                f'"message": "..."}}\n'
                f"Build it with json.dumps() and write that to the body file. "
                f"NOTHING WAS SENT."
            ) from exc
        if not isinstance(parsed, dict):
            raise CommandError(
                f"Body parsed as {type(parsed).__name__}, not a JSON object. "
                f"A bare string or list carries no field names, so the receiving "
                f"agent has to guess what it is reading. NOTHING WAS SENT."
            )

        # AGENTS.md section 5: agents write to each other in English. Language is
        # not detectable in general and this does not try — it checks the one
        # case the Owner ruled on and the only one that is decidable: Cyrillic in
        # a body between agents. The Owner's own words are exempt, in their own
        # field, because translating an instruction changes it.
        offending = _cyrillic_paths(parsed)
        if offending:
            raise CommandError(
                "Cyrillic in an agent-to-agent message. AGENTS.md section 5: the "
                "language between agents is English.\n"
                + "\n".join(offending)
                + f"\n\nIf this is the OWNER'S OWN WORDS being relayed, move them "
                f"into a {OWNER_VERBATIM_FIELD!r} field, which is exempt, and keep "
                f"everything you say yourself in English. If it is your own text, "
                f"write it in English. NOTHING WAS SENT."
            )

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
