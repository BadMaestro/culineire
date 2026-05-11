import re
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from monitoring.models import PageView
from monitoring.tracker import hash_ip

LOG_PATH = Path("/var/log/nginx/blocked.log")
STATE_PATH = Path("/srv/culineire/shared/nginx_blocked_log.pos")

_LOG_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) \S+" '
    r'(?P<status>\d+) \d+ '
    r'"(?P<referrer>[^"]*)" '
    r'"(?P<ua>[^"]*)"'
)


def _parse_time(raw: str) -> datetime:
    return datetime.strptime(raw, "%d/%b/%Y:%H:%M:%S %z")


class Command(BaseCommand):
    help = "Import NGINX blocked.log entries into PageView monitoring records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--full",
            action="store_true",
            help="Re-import from the beginning of the log (ignores saved position)",
        )

    def handle(self, *args, **options):
        if not LOG_PATH.exists():
            return

        offset = 0
        if not options["full"] and STATE_PATH.exists():
            try:
                offset = int(STATE_PATH.read_text().strip())
            except ValueError:
                offset = 0

        rows = []  # list of (PageView instance, datetime)
        new_offset = offset

        with LOG_PATH.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            for line in fh:
                new_offset += len(line.encode("utf-8", errors="replace"))
                m = _LOG_RE.match(line)
                if not m:
                    continue
                try:
                    ts = _parse_time(m.group("time"))
                except ValueError:
                    continue

                path = m.group("path")[:500]
                ua = m.group("ua")[:200]
                referrer = m.group("referrer")[:500]
                referrer = "" if referrer == "-" else referrer
                status = int(m.group("status"))
                ip_hash = hash_ip(m.group("ip"))

                pv = PageView(
                    path=path,
                    referrer=referrer,
                    user_agent=ua,
                    ip_hash=ip_hash,
                    status_code=status,
                )
                rows.append((pv, ts))

        if rows:
            created = PageView.objects.bulk_create([pv for pv, _ in rows])
            # bulk_create returns objects with PKs on PostgreSQL; fix created_at
            updates = []
            for obj, ts in zip(created, [t for _, t in rows]):
                obj.created_at = ts
                updates.append(obj)
            PageView.objects.bulk_update(updates, ["created_at"])

        STATE_PATH.write_text(str(new_offset))

        if rows:
            self.stdout.write(self.style.SUCCESS(f"Imported {len(rows)} blocked requests"))
