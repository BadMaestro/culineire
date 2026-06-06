from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .attention import get_sponsor_moderation_attention_count
from .models import (
    SanctionsSourceSnapshot,
    SanctionsSubject,
    SponsorApplication,
    SponsorAuditLog,
    SponsorCell,
    SponsorComplianceCheck,
    SponsorPayment,
    SponsorSanctionsMatch,
)
from .sanctions_matching import review_sanctions_match, screen_sponsor_application
from .services import approve_application, handle_stripe_event
from .tests import SPONSOR_TEST_SETTINGS, png_upload


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorSanctionsMatchingTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("phase3-staff", password="pass", is_staff=True)
        self.user = get_user_model().objects.create_user("phase3-user", password="pass")
        self.cell = SponsorCell.objects.create(cell_number=371, ring=6, position_in_ring=0)
        self.eu_snapshot = SanctionsSourceSnapshot.objects.create(
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            source_name="EU Financial Sanctions Files",
            source_url="https://example.test/eu.xml",
            file_format="xml",
            fetched_at=timezone.now(),
            source_sha256="eu",
            record_count=2,
            status=SanctionsSourceSnapshot.Status.SUCCESS,
        )
        self.un_snapshot = SanctionsSourceSnapshot.objects.create(
            source_code=SanctionsSourceSnapshot.SourceCode.UN_SC_CONSOLIDATED,
            source_name="UN Security Council Consolidated List",
            source_url="https://example.test/un.xml",
            file_format="xml",
            fetched_at=timezone.now(),
            source_sha256="un",
            record_count=1,
            status=SanctionsSourceSnapshot.Status.SUCCESS,
        )
        self.subject = SanctionsSubject.objects.create(
            source_snapshot=self.eu_snapshot,
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            external_reference="EU.1",
            subject_type=SanctionsSubject.SubjectType.ENTITY,
            primary_name="Example Holdings Limited",
            normalised_name="example holdings limited",
            aliases=["Example Trading"],
            countries=["Ireland"],
            regimes=["Example regime"],
            measures=["Asset freeze"],
        )
        SanctionsSubject.objects.create(
            source_snapshot=self.un_snapshot,
            source_code=SanctionsSourceSnapshot.SourceCode.UN_SC_CONSOLIDATED,
            external_reference="UN.1",
            subject_type=SanctionsSubject.SubjectType.ENTITY,
            primary_name="Distinctive Maritime Group",
            normalised_name="distinctive maritime group",
        )

    def application(self, sponsor_name="Example Holdings Ltd", status=SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=status,
            sponsor_name=sponsor_name,
            contact_name="Contact Person",
            email="phase3@example.com",
            website_url="https://example.com",
            logo=png_upload("phase3.png"),
            price_net_cents=self.cell.price_net_cents,
        )
        SponsorPayment.objects.create(application=application, status=SponsorPayment.Status.PAID, net_amount_cents=application.price_net_cents)
        SponsorComplianceCheck.objects.create(application=application, status=SponsorComplianceCheck.Status.SCREENING_REQUIRED)
        return application

    def test_exact_sponsor_name_match_creates_possible_match(self):
        application = self.application("Example Holdings Limited")

        result = screen_sponsor_application(application)

        match = SponsorSanctionsMatch.objects.get(application=application)
        self.assertEqual(result.possible_matches_count, 1)
        self.assertEqual(match.match_status, SponsorSanctionsMatch.Status.POSSIBLE)
        self.assertEqual(match.match_score, 100)
        self.assertIn("exact normalised name match", match.match_reasons)

    def test_alias_exact_match_creates_possible_match(self):
        application = self.application("Example Trading")

        screen_sponsor_application(application)

        match = SponsorSanctionsMatch.objects.get(application=application)
        self.assertEqual(match.match_score, 95)
        self.assertIn("alias exact normalised match", match.match_reasons)

    def test_non_matching_sponsor_creates_no_possible_match(self):
        application = self.application("Friendly Bakery")

        result = screen_sponsor_application(application)

        self.assertEqual(result.possible_matches_count, 0)
        self.assertFalse(SponsorSanctionsMatch.objects.filter(application=application).exists())

    def test_generic_short_name_does_not_create_noisy_match(self):
        application = self.application("Co")

        screen_sponsor_application(application)

        self.assertFalse(SponsorSanctionsMatch.objects.filter(application=application).exists())

    def test_screening_command_is_idempotent(self):
        application = self.application("Example Holdings Ltd")

        call_command("screen_sponsor_application", application_id=application.pk)
        call_command("screen_sponsor_application", application_id=application.pk)

        self.assertEqual(SponsorSanctionsMatch.objects.filter(application=application).count(), 1)

    def test_reviewed_false_positive_match_is_not_overwritten_on_rerun(self):
        application = self.application("Example Holdings Ltd")
        screen_sponsor_application(application)
        match = SponsorSanctionsMatch.objects.get(application=application)
        review_sanctions_match(match, status=SponsorSanctionsMatch.Status.FALSE_POSITIVE, actor=self.staff, note="Different company.")

        screen_sponsor_application(application, force=True)

        match.refresh_from_db()
        self.assertEqual(match.match_status, SponsorSanctionsMatch.Status.FALSE_POSITIVE)
        self.assertEqual(match.staff_note, "Different company.")

    @patch("newsfeed.telegram.publish_sponsor_to_telegram")
    def test_unresolved_possible_match_blocks_approval(self, telegram):
        application = self.application("Example Holdings Ltd")
        screen_sponsor_application(application)
        SponsorComplianceCheck.objects.create(application=application, status=SponsorComplianceCheck.Status.MANUALLY_CLEARED)

        with self.assertRaisesMessage(ValueError, "unresolved possible sanctions matches"):
            approve_application(application.pk, self.staff)

        application.refresh_from_db()
        self.assertNotEqual(application.status, SponsorApplication.Status.APPROVED)
        self.assertTrue(SponsorAuditLog.objects.filter(application=application, action=SponsorAuditLog.Action.APPROVAL_BLOCKED_SANCTIONS).exists())
        telegram.assert_not_called()

    @patch("newsfeed.telegram.publish_sponsor_to_telegram")
    def test_false_positive_match_allows_normal_approval_after_manual_clear(self, telegram):
        application = self.application("Example Holdings Ltd")
        screen_sponsor_application(application)
        match = SponsorSanctionsMatch.objects.get(application=application)
        review_sanctions_match(match, status=SponsorSanctionsMatch.Status.FALSE_POSITIVE, actor=self.staff, note="Different registration.")
        SponsorComplianceCheck.objects.create(application=application, status=SponsorComplianceCheck.Status.MANUALLY_CLEARED)

        approve_application(application.pk, self.staff)

        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.APPROVED)

    def test_blocked_match_prevents_approval(self):
        application = self.application("Example Holdings Ltd")
        screen_sponsor_application(application)
        match = SponsorSanctionsMatch.objects.get(application=application)
        review_sanctions_match(match, status=SponsorSanctionsMatch.Status.BLOCKED, actor=self.staff, note="Compliance concern.")
        SponsorComplianceCheck.objects.create(application=application, status=SponsorComplianceCheck.Status.MANUALLY_CLEARED)

        with self.assertRaisesMessage(ValueError, "blocked for compliance"):
            approve_application(application.pk, self.staff)

    def test_staff_note_required_for_review_decision(self):
        application = self.application("Example Holdings Ltd")
        screen_sponsor_application(application)
        match = SponsorSanctionsMatch.objects.get(application=application)

        with self.assertRaisesMessage(ValueError, "staff note"):
            review_sanctions_match(match, status=SponsorSanctionsMatch.Status.MANUALLY_CLEARED, actor=self.staff, note="")

    def test_moderation_review_actions_are_staff_only_and_audited(self):
        application = self.application("Example Holdings Ltd")
        screen_sponsor_application(application)
        match = SponsorSanctionsMatch.objects.get(application=application)

        self.client.force_login(self.user)
        response = self.client.post(reverse("sponsors:moderation_application_detail", args=[application.pk]), {
            "action": "sanctions_false_positive",
            "match_id": match.pk,
            "note": "Different entity.",
        })
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.staff)
        response = self.client.post(reverse("sponsors:moderation_application_detail", args=[application.pk]), {
            "action": "sanctions_false_positive",
            "match_id": match.pk,
            "note": "Different entity.",
        })
        self.assertEqual(response.status_code, 302)
        match.refresh_from_db()
        self.assertEqual(match.match_status, SponsorSanctionsMatch.Status.FALSE_POSITIVE)
        self.assertTrue(SponsorAuditLog.objects.filter(application=application, action=SponsorAuditLog.Action.SANCTIONS_MATCH_FALSE_POSITIVE).exists())

    def test_admin_attention_count_includes_unresolved_possible_match(self):
        application = self.application("Example Holdings Ltd", status=SponsorApplication.Status.APPROVED)
        screen_sponsor_application(application)

        self.assertEqual(get_sponsor_moderation_attention_count(), 1)

    def test_payment_success_triggers_screening_and_does_not_publish(self):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=SponsorApplication.Status.PAYMENT_PENDING,
            sponsor_name="Example Holdings Ltd",
            contact_name="Contact",
            email="phase3pay@example.com",
            logo=png_upload("phase3-pay.png"),
            price_net_cents=self.cell.price_net_cents,
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PENDING,
            stripe_checkout_session_id="cs_phase3",
            net_amount_cents=application.price_net_cents,
        )
        self.cell.status = SponsorCell.Status.PAYMENT_PENDING
        self.cell.save(update_fields=["status"])

        handle_stripe_event({
            "id": "evt_phase3_screen",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_phase3",
                "payment_status": "paid",
                "payment_intent": "pi_phase3",
                "amount_subtotal": application.price_net_cents,
                "amount_total": application.price_net_cents,
                "total_details": {"amount_tax": 0},
                "currency": "eur",
                "metadata": {"sponsor_application_id": str(application.pk), "sponsor_cell_id": str(self.cell.pk)},
            }},
        })

        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW)
        self.assertIsNone(application.published_at)
        self.assertTrue(SponsorSanctionsMatch.objects.filter(application=application, match_status=SponsorSanctionsMatch.Status.POSSIBLE).exists())

    def test_command_dry_run_reports_without_creating_matches(self):
        application = self.application("Example Holdings Ltd")
        output = StringIO()

        call_command("screen_sponsor_application", application_id=application.pk, dry_run=True, stdout=output)

        self.assertIn("possible_matches=1", output.getvalue())
        self.assertFalse(SponsorSanctionsMatch.objects.filter(application=application).exists())
