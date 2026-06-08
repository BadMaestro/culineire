from django.core.management.base import BaseCommand, CommandError

from sponsors.models import SponsorApplication


class Command(BaseCommand):
    help = "Resend the sponsor contract agreement email with PDF attachment for an approved application."

    def add_arguments(self, parser):
        parser.add_argument(
            "--application-id",
            type=int,
            required=True,
            help="PK of the SponsorApplication to resend the contract for.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print what would be sent without sending email or mutating the database.",
        )

    def handle(self, *args, **options):
        application_id = options["application_id"]
        dry_run = options["dry_run"]

        try:
            application = SponsorApplication.objects.select_related("cell", "payment").get(pk=application_id)
        except SponsorApplication.DoesNotExist:
            raise CommandError(f"SponsorApplication with id={application_id} does not exist.")

        if application.status != SponsorApplication.Status.APPROVED:
            raise CommandError(
                f"Application {application_id} is not approved (status: {application.status}). "
                f"Contract can only be resent for approved applications."
            )

        if not application.contract_reference:
            raise CommandError(
                f"Application {application_id} has no contract_reference. "
                f"Run the approval workflow first."
            )

        from sponsors.services import generate_contract_pdf
        pdf_filename = f"CulinEire_Sponsor_Agreement_{application.contract_reference}.pdf"

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no email will be sent, no database changes."))
            self.stdout.write(f"  Application ID : {application.pk}")
            self.stdout.write(f"  Sponsor name   : {application.sponsor_name}")
            self.stdout.write(f"  Email          : {application.email}")
            self.stdout.write(f"  Contract ref   : {application.contract_reference}")
            self.stdout.write(f"  PDF filename   : {pdf_filename}")
            self.stdout.write(self.style.SUCCESS("Would send contract email with PDF attachment."))
            return

        # Live send — reuse existing resend_contract_email service which handles
        # status update, audit log, and error handling.
        from sponsors.services import resend_contract_email

        self.stdout.write(f"Sending contract email for application {application.pk} ({application.sponsor_name}) ...")
        try:
            resend_contract_email(application.pk, actor=None)
        except Exception as exc:
            raise CommandError(f"Failed to resend contract email: {exc}") from exc

        application.refresh_from_db()
        if application.contract_email_status in {
            SponsorApplication.ContractEmailStatus.SENT,
            SponsorApplication.ContractEmailStatus.RESENT,
        }:
            self.stdout.write(self.style.SUCCESS(
                f"Contract email sent successfully to {application.email}. "
                f"PDF: {pdf_filename}. Status: {application.contract_email_status}."
            ))
        else:
            raise CommandError(
                f"Email send attempted but status is '{application.contract_email_status}'. "
                f"Check the audit log and server logs for details."
            )
