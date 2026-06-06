from django.core.management.base import BaseCommand, CommandError

from sponsors.sanctions_sources import OFFICIAL_SOURCES, update_source


class Command(BaseCommand):
    help = "Fetch and parse official EU/UN sanctions source XML files."

    def add_arguments(self, parser):
        parser.add_argument("--source", choices=("eu", "un", "all"), default="all")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--timeout", type=int, default=30)
        parser.add_argument("--no-raw-store", action="store_true", help="Accepted for operational compatibility; raw files are not stored by default.")

    def handle(self, *args, **options):
        if options["timeout"] <= 0:
            raise CommandError("--timeout must be positive.")
        sources = OFFICIAL_SOURCES.keys() if options["source"] == "all" else (options["source"],)
        failed = False
        for source in sources:
            snapshot = update_source(
                source,
                dry_run=options["dry_run"],
                force=options["force"],
                timeout=options["timeout"],
            )
            self.stdout.write(
                f"{source}: {snapshot.status} / records={snapshot.record_count} / sha256={snapshot.source_sha256 or '-'}"
            )
            if snapshot.error_message:
                self.stdout.write(self.style.ERROR(snapshot.error_message))
            failed = failed or snapshot.status == "failed"
        if failed:
            raise CommandError("One or more sanctions source updates failed.")
