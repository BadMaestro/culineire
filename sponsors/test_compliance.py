from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from .cleanup import assess_safe_unpaid_deletion
from .compliance import run_compliance_check, staff_set_compliance_status
from .models import (
    SanctionsEntry,
    SponsorApplication,
    SponsorAuditLog,
    SponsorCell,
    SponsorComplianceCheck,
    SponsorPayment,
)
from .services import SponsorComplianceReviewRequired, approve_application, create_checkout_session
from .tests import SPONSOR_TEST_SETTINGS, png_upload


@override_settings(**{**SPONSOR_TEST_SETTINGS, "SPONSOR_COMPLIANCE_ALLOW_EMPTY_DATA": False})
class SponsorComplianceTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("compliance-staff", password="pass", is_staff=True)
        self.cell = SponsorCell.objects.create(cell_number=71, ring=6, position_in_ring=0)

    def application(self, *, name="Clear Community Sponsor", paid=False):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=SponsorApplication.Status.PAID_PENDING_APPROVAL if paid else SponsorApplication.Status.PAYMENT_PENDING,
            sponsor_name=name,
            contact_name="Compliance Contact",
            email="contact@example.com",
            website_url="https://example.com",
            logo=png_upload("compliance.png"),
            price_net_cents=self.cell.price_net_cents,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
            terms_accepted_at=timezone.now(),
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PAID if paid else SponsorPayment.Status.PENDING,
            net_amount_cents=application.price_net_cents,
            stripe_checkout_session_id="cs_compliance_paid" if paid else None,
            stripe_payment_intent_id="pi_compliance_paid" if paid else "",
            paid_at=timezone.now() if paid else None,
        )
        self.cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL if paid else SponsorCell.Status.PAYMENT_PENDING
        self.cell.save(update_fields=["status"])
        return application

    def sanctions_entry(self, name="Listed Entity", aliases=None):
        return SanctionsEntry.objects.create(
            source=SanctionsEntry.Source.MANUAL,
            external_id=f"manual-{SanctionsEntry.objects.count() + 1}",
            name=name,
            aliases=aliases or [],
        )

    def test_clear_and_exact_match_screening_create_audit_records(self):
        self.sanctions_entry()
        clear = run_compliance_check(self.application())
        possible = run_compliance_check(self.application(name="Listed Entity"))

        self.assertEqual(clear.status, SponsorComplianceCheck.Status.CLEAR)
        self.assertEqual(possible.status, SponsorComplianceCheck.Status.POSSIBLE_MATCH)
        self.assertEqual(possible.match_score, 1.0)
        self.assertTrue(SponsorAuditLog.objects.filter(action=SponsorAuditLog.Action.COMPLIANCE_CHECK_CLEAR).exists())
        self.assertTrue(SponsorAuditLog.objects.filter(action=SponsorAuditLog.Action.COMPLIANCE_POSSIBLE_MATCH).exists())

    def test_fuzzy_match_requires_review_not_automatic_block(self):
        self.sanctions_entry("International Trading Holdings")

        check = run_compliance_check(self.application(name="International Trading Holding"))

        self.assertEqual(check.status, SponsorComplianceCheck.Status.POSSIBLE_MATCH)

    def test_missing_data_fails_closed_and_blocks_checkout_before_stripe(self):
        application = self.application()

        with patch("sponsors.services._stripe") as stripe:
            with self.assertRaises(SponsorComplianceReviewRequired):
                create_checkout_session(application)

        stripe.assert_not_called()
        self.assertEqual(application.compliance_checks.latest("created_at").status, SponsorComplianceCheck.Status.ERROR)

    def test_possible_match_blocks_checkout_before_stripe(self):
        self.sanctions_entry("Listed Entity")
        application = self.application(name="Listed Entity")

        with patch("sponsors.services._stripe") as stripe:
            with self.assertRaises(SponsorComplianceReviewRequired):
                create_checkout_session(application)

        stripe.assert_not_called()

    def test_public_checkout_block_message_is_neutral_and_stripe_is_not_called(self):
        self.sanctions_entry("Listed Entity")
        self.cell.status = SponsorCell.Status.AVAILABLE
        self.cell.save(update_fields=["status"])
        data = {
            "sponsor_name": "Listed Entity",
            "contact_name": "Contact",
            "email": "contact@example.com",
            "website_url": "https://example.com",
            "logo": png_upload("listed.png"),
            "logo_offset_x": "0",
            "logo_offset_y": "0",
            "logo_scale": "1",
            "logo_rotation": "0",
            "logo_rights_confirmed": "on",
            "terms_accepted": "on",
            "approval_acknowledged": "on",
        }

        with patch("sponsors.views.create_checkout_session", wraps=create_checkout_session) as checkout:
            with patch("sponsors.services._stripe") as stripe:
                response = self.client.post(reverse("sponsors:cell_enquire", args=[self.cell.pk]), data)

        self.assertEqual(response.status_code, 202)
        self.assertIn("requires manual compliance review", response.json()["error"])
        self.assertNotIn("sanctioned", response.json()["error"].lower())
        checkout.assert_called_once()
        stripe.assert_not_called()

    def test_clear_compliance_preserves_checkout_payload(self):
        self.sanctions_entry()
        application = self.application()

        class FakeSession:
            called_with = None

            @classmethod
            def create(cls, **kwargs):
                cls.called_with = kwargs
                return {"id": "cs_clear", "url": "https://stripe.test/clear"}

        class FakeStripe:
            class checkout:
                Session = FakeSession

        with patch("sponsors.services._stripe", return_value=FakeStripe):
            create_checkout_session(application)

        self.assertEqual(FakeSession.called_with["line_items"][0]["price_data"]["unit_amount"], application.price_net_cents)
        self.assertEqual(FakeSession.called_with["line_items"][0]["price_data"]["product_data"]["tax_code"], "txcd_20060002")

    def test_staff_decisions_require_note_and_staff(self):
        application = self.application()
        with self.assertRaisesMessage(ValueError, "note"):
            staff_set_compliance_status(application, SponsorComplianceCheck.Status.FALSE_POSITIVE_CLEARED, self.staff, "")
        result = staff_set_compliance_status(
            application,
            SponsorComplianceCheck.Status.FALSE_POSITIVE_CLEARED,
            self.staff,
            "Confirmed unrelated entity.",
        )
        self.assertEqual(result.status, SponsorComplianceCheck.Status.FALSE_POSITIVE_CLEARED)

    def test_approval_requires_clear_or_false_positive_cleared(self):
        blocked = self.application(paid=True)
        with self.assertRaisesMessage(ValueError, "Compliance must be clear"):
            approve_application(blocked.pk, self.staff)

        SponsorComplianceCheck.objects.create(application=blocked, status=SponsorComplianceCheck.Status.FALSE_POSITIVE_CLEARED)
        with patch("newsfeed.telegram.publish_sponsor_to_telegram"):
            approve_application(blocked.pk, self.staff)
        blocked.refresh_from_db()
        self.assertEqual(blocked.status, SponsorApplication.Status.APPROVED)

    def test_clear_compliance_allows_approval(self):
        self.sanctions_entry()
        application = self.application(paid=True)
        self.assertEqual(run_compliance_check(application).status, SponsorComplianceCheck.Status.CLEAR)

        with patch("newsfeed.telegram.publish_sponsor_to_telegram"):
            approve_application(application.pk, self.staff)

        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.APPROVED)

    def test_moderation_ui_shows_compliance_and_hides_approve_when_blocked(self):
        application = self.application(paid=True)
        SponsorComplianceCheck.objects.create(application=application, status=SponsorComplianceCheck.Status.POSSIBLE_MATCH)
        self.client.force_login(self.staff)

        detail = self.client.get(reverse("sponsors:moderation_application_detail", args=[application.pk]))
        listing = self.client.get(reverse("sponsors:moderation_applications"), {"status": "all"})
        review_queue = self.client.get(reverse("sponsors:moderation_applications"), {"status": "compliance_review"})

        self.assertContains(detail, "Possible sanctions match")
        self.assertNotContains(detail, "Approve and publish")
        self.assertContains(listing, "Compliance: Possible sanctions match")
        self.assertContains(review_queue, application.sponsor_name)

    def test_unpaid_compliance_blocked_application_remains_cleanup_eligible(self):
        application = self.application()
        SponsorComplianceCheck.objects.create(application=application, status=SponsorComplianceCheck.Status.BLOCKED)

        assessment = assess_safe_unpaid_deletion(application)

        self.assertTrue(assessment.allowed)

    def test_terms_include_compliance_wording(self):
        response = self.client.get(reverse("sponsors:annual_contract"))
        self.assertContains(response, "Irish or international sponsors")
        self.assertContains(response, "do not need to be food-related businesses")
        self.assertContains(response, "cannot accept sponsorship, payment, promotional placement")
        self.assertContains(response, "do not replace Bearcave Limited's own compliance review")
