from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (
    ProcessedStripeEvent,
    SponsorApplication,
    SponsorAuditLog,
    SponsorCell,
    SponsorPayment,
    SponsorRoadmapItem,
)


def logo_upload():
    return SimpleUploadedFile("cleanup-logo.png", b"cleanup-test", content_type="image/png")


class SponsorCleanupCommandTestBase(TestCase):
    def make_cell(self, *, number=1, ring=6, product_type=SponsorCell.ProductType.ANNUAL_RING):
        return SponsorCell.objects.create(
            cell_number=number,
            ring=ring,
            position_in_ring=0,
            product_type=product_type,
            status=SponsorCell.Status.PAYMENT_PENDING,
            sponsor_name="Temporary sponsor",
            sponsor_url="https://example.com",
            enquiry_email="test@example.com",
        )

    def make_application(self, cell, *, status=SponsorApplication.Status.DRAFT):
        return SponsorApplication.objects.create(
            cell=cell,
            status=status,
            sponsor_name="Cleanup Test",
            contact_name="Test Contact",
            email="test@example.com",
            logo=logo_upload(),
            price_net_cents=cell.price_net_cents,
            product_type=cell.product_type,
        )


@override_settings(STRIPE_PRICE_MODE="test", STRIPE_SECRET_KEY="sk_test_cleanup")
class SandboxSponsorCleanupCommandTests(SponsorCleanupCommandTestBase):
    def setUp(self):
        self.central = self.make_cell(
            number=0,
            ring=0,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
        )
        self.annual = self.make_cell()
        self.central_application = self.make_application(
            self.central,
            status=SponsorApplication.Status.APPROVED,
        )
        self.annual_application = self.make_application(
            self.annual,
            status=SponsorApplication.Status.PAID_PENDING_APPROVAL,
        )
        SponsorPayment.objects.create(
            application=self.central_application,
            status=SponsorPayment.Status.PAID,
            stripe_payment_intent_id="pi_test_cleanup",
        )
        SponsorAuditLog.objects.create(
            application=self.central_application,
            cell=self.central,
            action=SponsorAuditLog.Action.APPROVED,
        )
        ProcessedStripeEvent.objects.create(
            event_id="evt_test_cleanup",
            event_type="checkout.session.completed",
            application=self.central_application,
        )
        self.roadmap = SponsorRoadmapItem.objects.create(title="Preserve roadmap")

    def test_dry_run_deletes_nothing(self):
        call_command("cleanup_sponsor_sandbox_data", "--dry-run", stdout=StringIO())
        self.assertEqual(SponsorApplication.objects.count(), 2)
        self.assertEqual(SponsorPayment.objects.count(), 1)
        self.assertEqual(SponsorAuditLog.objects.count(), 1)
        self.assertEqual(ProcessedStripeEvent.objects.count(), 1)

    def test_confirm_deletes_records_resets_cells_and_preserves_permanent_data(self):
        call_command("cleanup_sponsor_sandbox_data", "--confirm", stdout=StringIO())

        self.assertFalse(SponsorApplication.objects.exists())
        self.assertFalse(SponsorPayment.objects.exists())
        self.assertFalse(SponsorAuditLog.objects.exists())
        self.assertFalse(ProcessedStripeEvent.objects.exists())
        self.assertTrue(SponsorRoadmapItem.objects.filter(pk=self.roadmap.pk).exists())
        self.central.refresh_from_db()
        self.annual.refresh_from_db()
        self.assertEqual(self.central.status, SponsorCell.Status.AVAILABLE)
        self.assertEqual(self.central.cell_number, 0)
        self.assertEqual(self.central.ring, 0)
        self.assertEqual(self.central.product_type, SponsorCell.ProductType.CENTRAL_MONTHLY)
        self.assertEqual(self.central.price_net_cents, 100000)
        self.assertEqual(self.annual.status, SponsorCell.Status.AVAILABLE)
        self.assertEqual(self.annual.product_type, SponsorCell.ProductType.ANNUAL_RING)
        self.assertEqual(self.annual.price_net_cents, 2500)
        self.assertEqual(self.annual.sponsor_name, "")

    @override_settings(STRIPE_PRICE_MODE="live", STRIPE_SECRET_KEY="sk_live_cleanup")
    def test_command_refuses_live_mode(self):
        with self.assertRaises(CommandError):
            call_command("cleanup_sponsor_sandbox_data", "--confirm", stdout=StringIO())
        self.assertEqual(SponsorApplication.objects.count(), 2)


class SafeUnpaidSponsorDeletionCommandTests(SponsorCleanupCommandTestBase):
    def test_dry_run_deletes_nothing(self):
        application = self.make_application(self.make_cell(), status=SponsorApplication.Status.CANCELLED)
        call_command("delete_safe_sponsor_applications", "--dry-run", f"--ids={application.pk}", stdout=StringIO())
        self.assertTrue(SponsorApplication.objects.filter(pk=application.pk).exists())

    def test_confirm_deletes_unpaid_cancelled_application_and_resets_cell(self):
        cell = self.make_cell()
        application = self.make_application(cell, status=SponsorApplication.Status.CANCELLED)
        SponsorPayment.objects.create(application=application, status=SponsorPayment.Status.FAILED)
        SponsorAuditLog.objects.create(application=application, cell=cell, action=SponsorAuditLog.Action.CHECKOUT_FAILED)

        call_command("delete_safe_sponsor_applications", "--confirm", f"--ids={application.pk}", stdout=StringIO())

        self.assertFalse(SponsorApplication.objects.filter(pk=application.pk).exists())
        self.assertFalse(SponsorAuditLog.objects.filter(application_id=application.pk).exists())
        cell.refresh_from_db()
        self.assertEqual(cell.status, SponsorCell.Status.AVAILABLE)
        self.assertEqual(cell.sponsor_name, "")

    def test_refuses_paid_approved_refund_required_and_payment_intent_records(self):
        cases = [
            (SponsorApplication.Status.PAID_PENDING_APPROVAL, SponsorPayment.Status.PAID, ""),
            (SponsorApplication.Status.APPROVED, SponsorPayment.Status.PENDING, ""),
            (SponsorApplication.Status.REFUND_REQUIRED, SponsorPayment.Status.PENDING, ""),
            (SponsorApplication.Status.CANCELLED, SponsorPayment.Status.FAILED, "pi_test_exists"),
        ]
        ids = []
        for index, (status, payment_status, intent_id) in enumerate(cases, start=10):
            cell = self.make_cell(number=index)
            application = self.make_application(cell, status=status)
            SponsorPayment.objects.create(
                application=application,
                status=payment_status,
                stripe_payment_intent_id=intent_id,
            )
            ids.append(application.pk)

        output = StringIO()
        call_command("delete_safe_sponsor_applications", "--confirm", f"--ids={','.join(map(str, ids))}", stdout=output)

        self.assertEqual(SponsorApplication.objects.filter(pk__in=ids).count(), 4)
        self.assertIn("REFUSED", output.getvalue())

    def test_refuses_ambiguous_webhook_history_with_clear_reason(self):
        application = self.make_application(self.make_cell(), status=SponsorApplication.Status.REJECTED)
        ProcessedStripeEvent.objects.create(
            event_id="evt_ambiguous",
            event_type="checkout.session.expired",
            application=application,
        )
        output = StringIO()

        call_command("delete_safe_sponsor_applications", "--confirm", f"--ids={application.pk}", stdout=output)

        self.assertTrue(SponsorApplication.objects.filter(pk=application.pk).exists())
        self.assertIn("processed Stripe webhook history exists", output.getvalue())

    def test_refuses_active_cell_even_for_unpaid_application(self):
        cell = self.make_cell()
        cell.status = SponsorCell.Status.ACTIVE
        cell.save(update_fields=["status"])
        application = self.make_application(cell, status=SponsorApplication.Status.CANCELLED)
        output = StringIO()

        call_command("delete_safe_sponsor_applications", "--confirm", f"--ids={application.pk}", stdout=output)

        self.assertTrue(SponsorApplication.objects.filter(pk=application.pk).exists())
        self.assertIn("cell status is not safely resettable", output.getvalue())

    def test_refuses_published_or_expiring_application(self):
        application = self.make_application(self.make_cell(), status=SponsorApplication.Status.EXPIRED)
        application.published_at = timezone.now()
        application.expires_at = timezone.now()
        application.save()

        call_command("delete_safe_sponsor_applications", "--confirm", f"--ids={application.pk}", stdout=StringIO())

        self.assertTrue(SponsorApplication.objects.filter(pk=application.pk).exists())
