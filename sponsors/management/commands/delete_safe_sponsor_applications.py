from django.core.management.base import BaseCommand, CommandError

from sponsors.cleanup import assess_safe_unpaid_deletion, delete_application_records
from sponsors.models import SponsorApplication, SponsorSanctionsMatch


class Command(BaseCommand):
    help = "Dry-run or delete explicitly selected unpaid sponsor applications with no financial history."

    def add_arguments(self, parser):
        parser.add_argument("--ids", required=True, help="Comma-separated SponsorApplication IDs.")
        parser.add_argument("--dry-run", action="store_true", help="Preview deletion (default).")
        parser.add_argument("--confirm", action="store_true", help="Confirm deletion of eligible records.")

    def handle(self, *args, **options):
        if options["confirm"] and options["dry_run"]:
            raise CommandError("Use either --dry-run or --confirm, not both.")
        try:
            ids = sorted({int(value.strip()) for value in options["ids"].split(",") if value.strip()})
        except ValueError as exc:
            raise CommandError("--ids must be a comma-separated list of integers.") from exc
        if not ids:
            raise CommandError("At least one application ID is required.")

        applications = {
            application.pk: application
            for application in SponsorApplication.objects.select_related("cell", "payment").filter(pk__in=ids)
        }
        refused = False
        eligible: list[SponsorApplication] = []
        for application_id in ids:
            application = applications.get(application_id)
            if not application:
                self.stdout.write(self.style.ERROR(f"REFUSED application #{application_id}: not found"))
                refused = True
                continue
            assessment = assess_safe_unpaid_deletion(application)
            if not assessment.allowed:
                self.stdout.write(
                    self.style.ERROR(
                        f"REFUSED application #{application_id}: {'; '.join(assessment.reasons)}"
                    )
                )
                refused = True
                continue
            eligible.append(application)
            match_count = SponsorSanctionsMatch.objects.filter(application=application).count()
            self.stdout.write(f"ELIGIBLE application #{application_id}: {application.sponsor_name} [{application.status}]")
            self.stdout.write(f"  Sponsor sanctions matches to delete by cascade: {match_count}")

        if not options["confirm"]:
            self.stdout.write("Dry run only. Re-run with --confirm to delete eligible applications.")
            return
        for application in eligible:
            delete_application_records(application)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted application #{application.pk}; its cell was reset only if no other application references it."
                )
            )
        if refused:
            self.stdout.write(self.style.WARNING("One or more requested applications were refused and left unchanged."))
