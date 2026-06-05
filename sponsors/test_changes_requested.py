from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SponsorApplication, SponsorAuditLog, SponsorCell, SponsorPayment
from .services import (
    mark_application_ready_for_review,
    reject_application,
    request_application_changes,
)
from .tests import SPONSOR_TEST_SETTINGS


def workflow_logo():
    image = Image.new("RGB", (16, 16), color=(20, 70, 45))
    output = BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile("workflow.png", output.getvalue(), content_type="image/png")


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorChangesRequestedWorkflowTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user("workflow-staff", password="pass", is_staff=True)
        self.cell = SponsorCell.objects.create(
            cell_number=30,
            ring=3,
            position_in_ring=0,
            status=SponsorCell.Status.PAID_PENDING_APPROVAL,
        )
        self.application = SponsorApplication.objects.create(
            cell=self.cell,
            status=SponsorApplication.Status.PAID_PENDING_APPROVAL,
            sponsor_name="Workflow Sponsor",
            contact_name="Contact",
            email="sponsor@example.com",
            logo=workflow_logo(),
            price_net_cents=self.cell.price_net_cents,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
        )
        self.payment = SponsorPayment.objects.create(
            application=self.application,
            status=SponsorPayment.Status.PAID,
            net_amount_cents=self.application.price_net_cents,
            stripe_checkout_session_id="cs_workflow",
            stripe_payment_intent_id="pi_workflow",
        )

    def detail(self):
        self.client.force_login(self.actor)
        return self.client.get(reverse("sponsors:moderation_application_detail", args=[self.application.pk]))

    def test_request_changes_transition_preserves_paid_reserved_unpublished_state_and_sends_email(self):
        request_application_changes(self.application.pk, self.actor, "Please provide a clearer logo.")

        self.application.refresh_from_db()
        self.cell.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.application.status, SponsorApplication.Status.CHANGES_REQUESTED)
        self.assertEqual(self.payment.status, SponsorPayment.Status.PAID)
        self.assertEqual(self.cell.status, SponsorCell.Status.PAID_PENDING_APPROVAL)
        self.assertIsNone(self.application.published_at)
        self.assertIsNone(self.application.expires_at)
        log = self.application.audit_logs.get(action=SponsorAuditLog.Action.CHANGES_REQUESTED)
        self.assertEqual(log.notes, "Please provide a clearer logo.")
        self.assertEqual(log.from_status, SponsorApplication.Status.PAID_PENDING_APPROVAL)
        self.assertEqual(log.to_status, SponsorApplication.Status.CHANGES_REQUESTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Changes requested", mail.outbox[0].subject)
        self.assertIn("Please provide a clearer logo.", mail.outbox[0].body)
        self.assertIn("payment remains received", mail.outbox[0].body)
        self.assertIn("placement remains reserved", mail.outbox[0].body)

    def test_request_changes_requires_note_and_valid_transition(self):
        with self.assertRaisesMessage(ValueError, "note explaining"):
            request_application_changes(self.application.pk, self.actor, "")
        self.application.status = SponsorApplication.Status.APPROVED
        self.application.save(update_fields=["status"])
        with self.assertRaisesMessage(ValueError, "paid applications pending approval"):
            request_application_changes(self.application.pk, self.actor, "Wrong state")

    def test_ready_for_review_transition_and_invalid_transition(self):
        request_application_changes(self.application.pk, self.actor, "Update logo")
        result = mark_application_ready_for_review(self.application.pk, self.actor, "Updated details received")

        self.assertEqual(result.status, SponsorApplication.Status.PAID_PENDING_APPROVAL)
        self.assertEqual(result.payment.status, SponsorPayment.Status.PAID)
        log = result.audit_logs.get(action=SponsorAuditLog.Action.READY_FOR_REVIEW)
        self.assertEqual(log.notes, "Updated details received")
        with self.assertRaisesMessage(ValueError, "changes requested"):
            mark_application_ready_for_review(self.application.pk, self.actor)

    def test_changes_requested_can_be_rejected_into_existing_refund_workflow(self):
        with patch("newsfeed.telegram.publish_sponsor_to_telegram") as publish:
            request_application_changes(self.application.pk, self.actor, "Update logo")
            mark_application_ready_for_review(self.application.pk, self.actor)
            request_application_changes(self.application.pk, self.actor, "Update logo again")
            reject_application(self.application.pk, self.actor, "Cannot be resolved")

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, SponsorApplication.Status.REFUND_REQUIRED)
        publish.assert_not_called()

    def test_paid_pending_approval_action_visibility(self):
        response = self.detail()
        for text in ("Approve and publish", "Request Changes", "Reject and mark refund required"):
            self.assertContains(response, text)
        for text in ("Mark ready for review", "Mark refund completed", "Unpublish", "Expire sponsorship"):
            self.assertNotContains(response, text)

    def test_changes_requested_action_visibility(self):
        self.application.status = SponsorApplication.Status.CHANGES_REQUESTED
        self.application.save(update_fields=["status"])
        response = self.detail()
        for text in ("Mark ready for review", "Reject and mark refund required"):
            self.assertContains(response, text)
        for text in ("Approve and publish", "Request Changes", "Mark refund completed", "Unpublish", "Expire sponsorship"):
            self.assertNotContains(response, text)

    def test_approved_action_visibility(self):
        self.application.status = SponsorApplication.Status.APPROVED
        self.application.save(update_fields=["status"])
        response = self.detail()
        self.assertContains(response, "Unpublish")
        self.assertContains(response, "Expire sponsorship")
        for text in ("Approve and publish", "Request Changes", "Reject and mark refund required", "Mark refund completed"):
            self.assertNotContains(response, text)

    def test_refund_required_action_visibility(self):
        self.application.status = SponsorApplication.Status.REFUND_REQUIRED
        self.application.save(update_fields=["status"])
        response = self.detail()
        self.assertContains(response, "Mark refund completed")
        for text in ("Approve and publish", "Request Changes", "Reject and mark refund required", "Unpublish", "Expire sponsorship"):
            self.assertNotContains(response, text)

    def test_terminal_and_pre_payment_statuses_show_no_actions_message(self):
        for status in (
            SponsorApplication.Status.DRAFT,
            SponsorApplication.Status.PAYMENT_PENDING,
            SponsorApplication.Status.CANCELLED,
            SponsorApplication.Status.REJECTED,
            SponsorApplication.Status.REFUNDED,
            SponsorApplication.Status.EXPIRED,
        ):
            self.application.status = status
            self.application.save(update_fields=["status"])
            response = self.detail()
            self.assertContains(response, "No moderation actions are currently available for this status.")
            self.assertNotContains(response, "Approve and publish")

    def test_central_list_uses_product_label_not_ring_zero(self):
        self.cell.ring = 0
        self.cell.cell_number = 0
        self.cell.product_type = SponsorCell.ProductType.CENTRAL_MONTHLY
        self.cell.save()
        self.application.product_type = SponsorCell.ProductType.CENTRAL_MONTHLY
        self.application.save(update_fields=["product_type"])
        self.client.force_login(self.actor)

        response = self.client.get(reverse("sponsors:moderation_applications"), {"status": "all"})

        self.assertContains(response, "Sponsor of the Month")
        self.assertNotContains(response, "Ring 0")
        self.assertNotContains(response, "cell #0")
