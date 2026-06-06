from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .compliance import staff_set_compliance_status
from .cleanup import assess_safe_unpaid_deletion
from .forms import DECLARATION_TEXTS
from .models import SponsorApplication, SponsorApplicantDeclaration, SponsorCell, SponsorComplianceCheck, SponsorPayment
from .services import CheckoutSessionInfo, approve_application, handle_stripe_event
from .tests import SPONSOR_TEST_SETTINGS, png_upload


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorCompliancePhaseOneTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("compliance-staff", password="pass", is_staff=True)
        self.cell = SponsorCell.objects.create(cell_number=71, ring=6, position_in_ring=0)

    def post_data(self):
        return {
            "sponsor_name": "Community Sponsor",
            "contact_name": "Compliance Contact",
            "email": "contact@example.com",
            "website_url": "https://example.com",
            "logo": png_upload("compliance.png"),
            "logo_offset_x": "0",
            "logo_offset_y": "0",
            "logo_scale": "1",
            "logo_rotation": "0",
            "logo_rights_confirmed": "on",
            "terms_accepted": "on",
            "approval_acknowledged": "on",
            "sanctions_declaration_1": "on",
            "sanctions_declaration_2": "on",
            "sanctions_declaration_3": "on",
            "sanctions_declaration_4": "on",
        }

    def create_paid_review_application(self):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
            sponsor_name="Community Sponsor",
            contact_name="Compliance Contact",
            email="contact@example.com",
            logo=png_upload(),
            price_net_cents=self.cell.price_net_cents,
        )
        SponsorPayment.objects.create(application=application, status=SponsorPayment.Status.PAID, net_amount_cents=application.price_net_cents)
        SponsorComplianceCheck.objects.create(application=application, status=SponsorComplianceCheck.Status.SCREENING_REQUIRED)
        self.cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
        self.cell.save(update_fields=["status"])
        return application

    def test_all_declarations_are_required_before_checkout(self):
        data = self.post_data()
        data.pop("sanctions_declaration_4")
        with patch("sponsors.views.create_checkout_session") as checkout:
            response = self.client.post(reverse("sponsors:cell_enquire", args=[self.cell.pk]), data)
        self.assertEqual(response.status_code, 400)
        checkout.assert_not_called()

    def test_declaration_snapshot_allows_checkout_without_screening_data(self):
        with patch("sponsors.views.create_checkout_session", return_value=CheckoutSessionInfo("cs_declared", "https://stripe.test/session")):
            response = self.client.post(
                reverse("sponsors:cell_enquire", args=[self.cell.pk]),
                self.post_data(),
                HTTP_USER_AGENT="Compliance test browser",
                REMOTE_ADDR="192.0.2.10",
            )
        declaration = SponsorApplicantDeclaration.objects.get()
        check = SponsorComplianceCheck.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(declaration.declaration_text, DECLARATION_TEXTS)
        self.assertEqual(declaration.applicant_email, "contact@example.com")
        self.assertEqual(declaration.sponsor_name, "Community Sponsor")
        self.assertEqual(declaration.stripe_session_id, "cs_declared")
        self.assertEqual(check.status, SponsorComplianceCheck.Status.SELF_DECLARED)
        self.assertNotEqual(check.status, SponsorComplianceCheck.Status.CLEAR)

    @patch("newsfeed.telegram.publish_sponsor_to_telegram")
    def test_payment_moves_to_compliance_review_without_publication_or_telegram(self, telegram):
        with patch("sponsors.views.create_checkout_session", return_value=CheckoutSessionInfo("cs_paid_review", "https://stripe.test/session")):
            self.client.post(reverse("sponsors:cell_enquire", args=[self.cell.pk]), self.post_data())
        application = SponsorApplication.objects.get()
        handle_stripe_event({
            "id": "evt_paid_review",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_paid_review",
                "payment_status": "paid",
                "payment_intent": "pi_paid_review",
                "amount_subtotal": application.price_net_cents,
                "amount_total": application.price_net_cents,
                "total_details": {"amount_tax": 0},
                "currency": "eur",
                "metadata": {"sponsor_application_id": str(application.pk), "sponsor_cell_id": str(self.cell.pk)},
            }},
        })
        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW)
        self.assertEqual(application.compliance_checks.first().status, SponsorComplianceCheck.Status.SCREENING_REQUIRED)
        self.assertIsNone(application.published_at)
        telegram.assert_not_called()

    def test_manual_clear_requires_note_and_enables_approval(self):
        application = self.create_paid_review_application()
        with self.assertRaisesMessage(ValueError, "note"):
            staff_set_compliance_status(application, SponsorComplianceCheck.Status.MANUALLY_CLEARED, self.staff, "")
        check = staff_set_compliance_status(
            application, SponsorComplianceCheck.Status.MANUALLY_CLEARED, self.staff, "Reviewed against available official sources."
        )
        self.assertEqual(check.reviewed_by, self.staff)
        self.assertIsNotNone(check.reviewed_at)
        with patch("newsfeed.telegram.publish_sponsor_to_telegram"):
            approve_application(application.pk, self.staff)
        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.APPROVED)

    def test_blocked_application_cannot_be_approved(self):
        application = self.create_paid_review_application()
        staff_set_compliance_status(application, SponsorComplianceCheck.Status.BLOCKED, self.staff, "Compliance requirement.")
        with self.assertRaisesMessage(ValueError, "manually cleared"):
            approve_application(application.pk, self.staff)

    def test_paid_compliance_review_application_is_cleanup_protected(self):
        application = self.create_paid_review_application()
        assessment = assess_safe_unpaid_deletion(application)
        self.assertFalse(assessment.allowed)

    def test_moderation_and_success_pages_use_truthful_wording(self):
        application = self.create_paid_review_application()
        payment = application.payment
        payment.stripe_checkout_session_id = "cs_success_review"
        payment.save(update_fields=["stripe_checkout_session_id"])
        self.client.force_login(self.staff)
        detail = self.client.get(reverse("sponsors:moderation_application_detail", args=[application.pk]))
        listing = self.client.get(reverse("sponsors:moderation_applications"), {"status": "all"})
        success = self.client.get(reverse("sponsors:checkout_success"), {"session_id": "cs_success_review"})
        self.assertContains(detail, "Manual compliance review required")
        self.assertNotContains(detail, "Approve and publish")
        self.assertNotContains(detail, "Mark false positive cleared")
        self.assertContains(listing, "Payment received pending compliance review")
        self.assertContains(success, "Payment received pending compliance review")
