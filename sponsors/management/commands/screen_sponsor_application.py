from django.core.management.base import BaseCommand, CommandError

from sponsors.models import SponsorApplication
from sponsors.sanctions_matching import screen_sponsor_application


class Command(BaseCommand):
    help = "Run internal sanctions screening for one sponsor application."

    def add_arguments(self, parser):
        parser.add_argument("--application-id", type=int, required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        try:
            application = SponsorApplication.objects.get(pk=options["application_id"])
        except SponsorApplication.DoesNotExist as exc:
            raise CommandError(f"Sponsor application not found: {options['application_id']}") from exc

        result = screen_sponsor_application(
            application,
            dry_run=options["dry_run"],
            force=options["force"],
        )
        self.stdout.write(
            f"application={application.pk} subjects_checked={result.subjects_checked} "
            f"possible_matches={result.possible_matches_count} "
            f"source_snapshots={','.join(str(item) for item in result.source_snapshot_ids) or '-'}"
        )
