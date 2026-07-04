from django.core.management.base import BaseCommand
from django.utils import timezone

from chef_battle.models import VoteIntegrityEvent


class Command(BaseCommand):
    help = "Delete expired private vote-integrity evidence (90-day retention)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows are expired without deleting them.",
        )

    def handle(self, *args, **options):
        expired = VoteIntegrityEvent.objects.filter(expires_at__lte=timezone.now())
        count = expired.count()
        if options["dry_run"]:
            self.stdout.write(f"Would purge {count} expired vote integrity event(s).")
            return
        expired.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Purged {count} expired vote integrity event(s)."
        ))
