from django.core.management.base import BaseCommand
from django.utils import timezone

from monitoring.models import PageView, SecurityEvent, UserActivity


class Command(BaseCommand):
    help = "Delete old monitoring data older than --days (default 90)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Delete records older than this many days (default: 90)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show counts without deleting anything",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timezone.timedelta(days=days)

        label = "Would delete" if dry_run else "Deleted"

        models = [
            (PageView, "page views"),
            (UserActivity, "user activity records"),
            (SecurityEvent, "security events"),
        ]

        total = 0
        for Model, name in models:
            qs = Model.objects.filter(created_at__lt=cutoff)
            count = qs.count()
            total += count
            if not dry_run:
                qs.delete()
            self.stdout.write(f"  {label} {count:,} {name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY RUN] ' if dry_run else ''}Total: {total:,} records"
                f" older than {days} days"
                f" ({'not ' if dry_run else ''}deleted)"
            )
        )
