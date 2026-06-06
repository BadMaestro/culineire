from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from sponsors.cleanup import delete_application_records
from sponsors.models import ProcessedStripeEvent, SponsorApplication, SponsorAuditLog, SponsorSanctionsMatch


class Command(BaseCommand):
    help = "Dry-run or delete all sponsor application data in a confirmed Stripe sandbox environment."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview cleanup (default).")
        parser.add_argument("--confirm", action="store_true", help="Confirm destructive sandbox cleanup.")

    def handle(self, *args, **options):
        mode = str(getattr(settings, "STRIPE_PRICE_MODE", "")).lower()
        secret = str(getattr(settings, "STRIPE_SECRET_KEY", ""))
        if mode != "test" or (secret and not secret.startswith("sk_test_")):
            raise CommandError("Refusing sandbox cleanup: Stripe mode/key is not clearly test/sandbox.")
        if options["confirm"] and options["dry_run"]:
            raise CommandError("Use either --dry-run or --confirm, not both.")

        applications = list(SponsorApplication.objects.select_related("cell").order_by("pk"))
        application_ids = [application.pk for application in applications]
        match_count = SponsorSanctionsMatch.objects.filter(application_id__in=application_ids).count()
        self.stdout.write(f"Sandbox sponsor applications found: {len(applications)}")
        self.stdout.write(f"Sponsor sanctions matches to delete by cascade: {match_count}")
        for application in applications:
            self.stdout.write(
                f"  application #{application.pk}: {application.sponsor_name} "
                f"[{application.status}] / cell #{application.cell.cell_number}"
            )
        if not options["confirm"]:
            self.stdout.write("Dry run only. Re-run with --confirm to delete sandbox sponsor application data.")
            return

        for application in applications:
            delete_application_records(application, force_cell_reset=True)
        SponsorAuditLog.objects.all().delete()
        ProcessedStripeEvent.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {len(applications)} sandbox sponsor applications and reset affected cells."))
