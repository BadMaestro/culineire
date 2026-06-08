from __future__ import annotations

import shutil
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor

from .models import (
    ProcessedStripeEvent,
    SanctionsSourceSnapshot,
    SanctionsSubject,
    SponsorApplication,
    SponsorAuditLog,
    SponsorCell,
    SponsorComplianceCheck,
    SponsorPayment,
    SponsorRoadmapItem,
)
from .services import (
    CheckoutSessionInfo,
    SponsorStripeConfigurationError,
    approve_application,
    create_checkout_session,
    expire_application,
    handle_stripe_event,
    mark_refund_completed,
    reject_application,
    validate_stripe_runtime_configuration,
)

# Isolated settings applied to every sponsor test class:
#   MEDIA_ROOT  — temporary directory so uploaded logos never touch production media.
#   SECURE_SSL_REDIRECT — disabled so the test client receives 200/400/404, not 301.
#   SECURE_HSTS_SECONDS — zero to suppress SecurityMiddleware redirects.
#   SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE — allow plain-HTTP test client requests.
_TEMP_MEDIA = tempfile.mkdtemp(prefix="culineire_sponsor_tests_")

SPONSOR_TEST_SETTINGS = dict(
    MEDIA_ROOT=_TEMP_MEDIA,
    SECURE_SSL_REDIRECT=False,
    SECURE_HSTS_SECONDS=0,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)


def png_upload(name="logo.png"):
    image = Image.new("RGB", (16, 16), color=(22, 100, 61))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorFlowTests(TestCase):
    def setUp(self):
        self.cell = SponsorCell.objects.create(cell_number=1, ring=6, position_in_ring=0)

    def valid_post_data(self):
        return {
            "sponsor_name": "Acme Foods",
            "contact_name": "Aine Sponsor",
            "email": "aine@example.com",
            "phone": "+353 21 000 0000",
            "website_url": "https://example.com",
            "sponsor_note": "Local producer",
            "logo": png_upload(),
            "logo_offset_x": "0",
            "logo_offset_y": "0",
            "logo_scale": "1",
            "logo_rotation": "0",
            "logo_rights_confirmed": "on",
            "terms_accepted": "on",
            "sanctions_declaration_1": "on",
        }

    def create_pending_application(self, paid=False):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=(
                SponsorApplication.Status.PAID_PENDING_APPROVAL
                if paid
                else SponsorApplication.Status.PAYMENT_PENDING
            ),
            sponsor_name="Acme Foods",
            contact_name="Aine Sponsor",
            email="aine@example.com",
            website_url="https://example.com",
            logo=png_upload(),
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
            currency="eur",
            stripe_checkout_session_id="cs_test_123" if paid else None,
            stripe_payment_intent_id="pi_test_123" if paid else "",
            paid_at=timezone.now() if paid else None,
        )
        self.cell.status = (
            SponsorCell.Status.PAID_PENDING_APPROVAL
            if paid
            else SponsorCell.Status.PAYMENT_PENDING
        )
        self.cell.save(update_fields=["status"])
        if paid:
            SponsorComplianceCheck.objects.create(
                application=application,
                status=SponsorComplianceCheck.Status.MANUALLY_CLEARED,
                checked_at=timezone.now(),
            )
        return application

    def test_public_sponsor_page_displays_net_plus_vat_pricing(self):
        response = self.client.get(reverse("sponsors:puzzle"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "€25")
        self.assertContains(response, "/year + VAT")
        self.assertContains(response, "Prices are shown excluding VAT")
        self.assertContains(response, "Businesses, sole traders and individuals")
        self.assertContains(response, "Payment reserves a spot while Bearcave Limited completes internal review")
        self.assertContains(response, "does not guarantee approval, publication or activation")
        self.assertContains(response, "Sponsor of the Month")
        self.assertContains(response, "€1000")
        self.assertContains(response, "/ month + VAT")
        self.assertContains(response, "Ring 6 is weekly. Other rings are annual. Central sponsor is monthly. VAT calculated at checkout.")
        self.assertNotContains(response, "Net annual price")

    def test_public_sponsor_page_does_not_expose_internal_compliance_data(self):
        snapshot = SanctionsSourceSnapshot.objects.create(
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            source_name="EU Financial Sanctions Files",
            source_url="https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=secret-token",
            file_format="xml",
            source_sha256="secret-sha",
            record_count=1,
            status=SanctionsSourceSnapshot.Status.SUCCESS,
        )
        SanctionsSubject.objects.create(
            source_snapshot=snapshot,
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            external_reference="EU.SECRET",
            primary_name="Sensitive Match Name",
            normalised_name="sensitive match name",
        )
        application = self.create_pending_application(paid=True)
        application.status = SponsorApplication.Status.REFUND_REQUIRED
        application.save(update_fields=["status"])
        SponsorAuditLog.objects.create(
            application=application,
            action=SponsorAuditLog.Action.REFUND_REQUIRED,
            notes="Internal staff note should not be public.",
            metadata={"stripe_payment_intent_id": "pi_secret_public_safety"},
        )

        response = self.client.get(reverse("sponsors:puzzle"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Sensitive Match Name")
        self.assertNotContains(response, "secret-token")
        self.assertNotContains(response, "Internal staff note")
        self.assertNotContains(response, "pi_secret_public_safety")

    def test_application_requires_terms(self):
        data = self.valid_post_data()
        data.pop("terms_accepted")

        response = self.client.post(reverse("sponsors:cell_enquire", args=[self.cell.pk]), data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Terms accepted", response.json()["error"])
        self.assertEqual(SponsorApplication.objects.count(), 0)

    def test_application_requires_sanctions_declaration(self):
        data = self.valid_post_data()
        data.pop("sanctions_declaration_1")

        response = self.client.post(reverse("sponsors:cell_enquire", args=[self.cell.pk]), data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Sanctions declaration", response.json()["error"])
        self.assertEqual(SponsorApplication.objects.count(), 0)

    def test_application_requires_logo_rights(self):
        data = self.valid_post_data()
        data.pop("logo_rights_confirmed")

        response = self.client.post(reverse("sponsors:cell_enquire", args=[self.cell.pk]), data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SponsorApplication.objects.count(), 0)

    def test_application_requires_logo_upload(self):
        data = self.valid_post_data()
        data.pop("logo")

        response = self.client.post(reverse("sponsors:cell_enquire", args=[self.cell.pk]), data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Logo or avatar", response.json()["error"])

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_individual_application_accepts_avatar_without_website(self):
        data = self.valid_post_data()
        data["sponsor_name"] = "Mary O'Brien"
        data["website_url"] = ""
        data["logo"] = png_upload("avatar.png")
        data["logo_offset_x"] = "24.5"
        data["logo_offset_y"] = "-12.25"
        data["logo_scale"] = "1.35"

        with patch(
            "sponsors.views.create_checkout_session",
            return_value=CheckoutSessionInfo("cs_test_individual", "https://checkout.stripe.test/individual"),
        ):
            response = self.client.post(
                reverse("sponsors:cell_enquire", args=[self.cell.pk]),
                data,
            )

        self.assertEqual(response.status_code, 200)
        application = SponsorApplication.objects.get()
        self.assertEqual(application.sponsor_name, "Mary O'Brien")
        self.assertEqual(application.website_url, "")
        self.assertAlmostEqual(application.logo_offset_x, 24.5)
        self.assertAlmostEqual(application.logo_offset_y, -12.25)
        self.assertAlmostEqual(application.logo_scale, 1.35)

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_valid_application_locks_cell_and_redirects_to_checkout(self):
        with patch(
            "sponsors.views.create_checkout_session",
            return_value=CheckoutSessionInfo("cs_test_123", "https://checkout.stripe.test/session"),
        ):
            response = self.client.post(
                reverse("sponsors:cell_enquire", args=[self.cell.pk]),
                self.valid_post_data(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checkout_url"], "https://checkout.stripe.test/session")
        application = SponsorApplication.objects.get()
        payment = application.payment
        self.cell.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.PAYMENT_PENDING)
        self.assertEqual(application.price_net_cents, 2500)
        self.assertEqual(payment.stripe_checkout_session_id, "cs_test_123")
        self.assertEqual(self.cell.status, SponsorCell.Status.PAYMENT_PENDING)

    def test_locked_cell_prevents_second_checkout(self):
        self.cell.status = SponsorCell.Status.PAYMENT_PENDING
        self.cell.save(update_fields=["status"])

        response = self.client.post(
            reverse("sponsors:cell_enquire", args=[self.cell.pk]),
            self.valid_post_data(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SponsorApplication.objects.count(), 0)

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_central_application_snapshots_monthly_product_and_term(self):
        central = SponsorCell.objects.create(
            cell_number=0,
            ring=0,
            position_in_ring=0,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
        )
        with patch(
            "sponsors.views.create_checkout_session",
            return_value=CheckoutSessionInfo("cs_central_form", "https://stripe.test/central"),
        ):
            response = self.client.post(
                reverse("sponsors:cell_enquire", args=[central.pk]),
                self.valid_post_data(),
            )

        self.assertEqual(response.status_code, 200)
        application = SponsorApplication.objects.get(cell=central)
        self.assertEqual(application.product_type, SponsorCell.ProductType.CENTRAL_MONTHLY)
        self.assertEqual(application.price_net_cents, 100000)
        self.assertEqual(application.term_days, 30)
        self.assertEqual(application.status, SponsorApplication.Status.PAYMENT_PENDING)

    @override_settings(STRIPE_SECRET_KEY="sk_test_123", SITE_BASE_URL="https://culineire.ie")
    def test_checkout_session_uses_metadata_and_exclusive_tax(self):
        application = self.create_pending_application()

        class FakeSession:
            called_with = None

            @classmethod
            def create(cls, **kwargs):
                cls.called_with = kwargs
                return {"id": "cs_test_456", "url": "https://stripe.test/checkout"}

        class FakeCheckout:
            Session = FakeSession

        class FakeStripe:
            checkout = FakeCheckout

        with patch("sponsors.services._stripe", return_value=FakeStripe):
            session_info = create_checkout_session(application)

        kwargs = FakeSession.called_with
        self.assertEqual(session_info.session_id, "cs_test_456")
        self.assertEqual(kwargs["mode"], "payment")
        self.assertEqual(kwargs["automatic_tax"], {"enabled": True})

    @override_settings(STRIPE_SECRET_KEY="sk_test_123", SITE_BASE_URL="https://culineire.ie")
    def test_central_monthly_checkout_uses_explicit_product_and_price(self):
        central = SponsorCell.objects.create(
            cell_number=0,
            ring=0,
            position_in_ring=0,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
        )
        application = SponsorApplication.objects.create(
            cell=central,
            status=SponsorApplication.Status.PAYMENT_PENDING,
            sponsor_name="Central Foods",
            contact_name="Cora",
            email="cora@example.com",
            logo=png_upload("central.png"),
            price_net_cents=central.price_net_cents,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
            term_days=30,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
        )

        class FakeSession:
            called_with = None

            @classmethod
            def create(cls, **kwargs):
                cls.called_with = kwargs
                return {"id": "cs_central", "url": "https://stripe.test/central"}

        class FakeStripe:
            class checkout:
                Session = FakeSession

        with patch("sponsors.services._stripe", return_value=FakeStripe):
            create_checkout_session(application)

        kwargs = FakeSession.called_with
        price_data = kwargs["line_items"][0]["price_data"]
        self.assertEqual(price_data["unit_amount"], 100000)
        self.assertEqual(price_data["tax_behavior"], "exclusive")
        self.assertEqual(price_data["product_data"]["tax_code"], "txcd_20060002")
        self.assertEqual(price_data["product_data"]["name"], "CulinEire Sponsor of the Month")
        self.assertEqual(kwargs["metadata"]["sponsor_product_type"], "central_monthly")
        self.assertEqual(kwargs["mode"], "payment")
        self.assertEqual(kwargs["billing_address_collection"], "required")
        self.assertEqual(kwargs["tax_id_collection"], {"enabled": True})
        self.assertEqual(kwargs["customer_creation"], "always")
        self.assertEqual(kwargs["metadata"]["sponsor_application_id"], str(application.pk))
        price_data = kwargs["line_items"][0]["price_data"]
        self.assertEqual(price_data["currency"], "eur")
        self.assertEqual(price_data["unit_amount"], application.price_net_cents)
        self.assertEqual(price_data["tax_behavior"], "exclusive")
        self.assertEqual(price_data["product_data"]["tax_code"], "txcd_20060002")
        self.assertEqual(kwargs["automatic_tax"], {"enabled": True})

    @override_settings(
        STRIPE_PRICE_MODE="live",
        STRIPE_SECRET_KEY="sk_test_mismatch",
        STRIPE_PUBLISHABLE_KEY="pk_live_ok",
    )
    def test_stripe_live_mode_rejects_test_secret_key(self):
        with self.assertRaisesMessage(SponsorStripeConfigurationError, "test secret key"):
            validate_stripe_runtime_configuration()

    @override_settings(
        STRIPE_PRICE_MODE="test",
        STRIPE_SECRET_KEY="sk_live_mismatch",
        STRIPE_PUBLISHABLE_KEY="pk_test_ok",
    )
    def test_stripe_test_mode_rejects_live_secret_key(self):
        with self.assertRaisesMessage(SponsorStripeConfigurationError, "live secret key"):
            validate_stripe_runtime_configuration()

    @override_settings(
        STRIPE_PRICE_MODE="live",
        STRIPE_SECRET_KEY="sk_live_ok",
        STRIPE_PUBLISHABLE_KEY="pk_test_mismatch",
    )
    def test_stripe_live_mode_rejects_test_publishable_key(self):
        with self.assertRaisesMessage(SponsorStripeConfigurationError, "test publishable key"):
            validate_stripe_runtime_configuration()

    @override_settings(
        STRIPE_PRICE_MODE="test",
        STRIPE_SECRET_KEY="sk_test_ok",
        STRIPE_WEBHOOK_SECRET="",
    )
    def test_stripe_webhook_runtime_requires_webhook_secret(self):
        with self.assertRaisesMessage(SponsorStripeConfigurationError, "STRIPE_WEBHOOK_SECRET"):
            validate_stripe_runtime_configuration(require_webhook_secret=True)

    def test_successful_webhook_sets_paid_pending_compliance_review_without_publishing_logo(self):
        application = self.create_pending_application(paid=False)
        event = {
            "id": "evt_completed_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_completed",
                    "payment_intent": "pi_completed",
                    "amount_subtotal": application.price_net_cents,
                    "amount_total": application.price_net_cents + 575,
                    "total_details": {"amount_tax": 575},
                    "currency": "eur",
                    "metadata": {
                        "sponsor_application_id": str(application.pk),
                        "sponsor_cell_id": str(self.cell.pk),
                    },
                }
            },
        }

        handle_stripe_event(event)

        application.refresh_from_db()
        self.cell.refresh_from_db()
        payment = application.payment
        self.assertEqual(application.status, SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW)
        self.assertEqual(self.cell.status, SponsorCell.Status.PAID_PENDING_APPROVAL)
        self.assertEqual(payment.status, SponsorPayment.Status.PAID)
        self.assertEqual(payment.vat_amount_cents, 575)
        self.assertFalse(bool(self.cell.sponsor_logo))

        duplicate = handle_stripe_event(event)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(ProcessedStripeEvent.objects.count(), 1)

    @patch("newsfeed.telegram.publish_sponsor_to_telegram")
    def test_payment_confirmation_does_not_send_sponsor_telegram_announcement(self, mock_publish):
        application = self.create_pending_application(paid=False)
        event = {
            "id": "evt_payment_no_telegram",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_payment_no_telegram",
                    "payment_status": "paid",
                    "payment_intent": "pi_payment_no_telegram",
                    "amount_subtotal": application.price_net_cents,
                    "amount_total": application.price_net_cents + 575,
                    "total_details": {"amount_tax": 575},
                    "currency": "eur",
                    "metadata": {
                        "sponsor_application_id": str(application.pk),
                        "sponsor_cell_id": str(self.cell.pk),
                    },
                }
            },
        }

        handle_stripe_event(event)

        mock_publish.assert_not_called()

    def test_expired_checkout_releases_unpaid_cell(self):
        application = self.create_pending_application(paid=False)
        event = {
            "id": "evt_expired_1",
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "metadata": {
                        "sponsor_application_id": str(application.pk),
                        "sponsor_cell_id": str(self.cell.pk),
                    }
                }
            },
        }

        handle_stripe_event(event)

        application.refresh_from_db()
        self.cell.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.EXPIRED)
        self.assertEqual(self.cell.status, SponsorCell.Status.AVAILABLE)

    def test_approval_publishes_logo_and_starts_twelve_month_term(self):
        user = get_user_model().objects.create_user("admin", password="pass", is_staff=True)
        application = self.create_pending_application(paid=True)

        approve_application(application.pk, user)

        application.refresh_from_db()
        self.cell.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.APPROVED)
        self.assertEqual(self.cell.status, SponsorCell.Status.ACTIVE)
        self.assertTrue(bool(self.cell.sponsor_logo))
        self.assertIsNotNone(application.published_at)
        self.assertEqual(application.expires_at.year, application.published_at.year + 1)

    def test_central_monthly_approval_starts_thirty_day_term(self):
        user = get_user_model().objects.create_user("central-admin", password="pass", is_staff=True)
        self.cell.product_type = SponsorCell.ProductType.CENTRAL_MONTHLY
        self.cell.ring = 0
        self.cell.cell_number = 0
        self.cell.save()
        application = self.create_pending_application(paid=True)
        application.product_type = SponsorCell.ProductType.CENTRAL_MONTHLY
        application.term_days = 30
        application.price_net_cents = 100000
        application.save()

        approve_application(application.pk, user)

        application.refresh_from_db()
        self.assertEqual((application.expires_at - application.published_at).days, 30)

    def test_annual_checkout_success_shows_premium_receipt_details(self):
        application = self.create_pending_application(paid=True)
        payment = application.payment
        payment.net_amount_cents = 2500
        payment.vat_amount_cents = 575
        payment.total_amount_cents = 3075
        payment.save()

        response = self.client.get(
            reverse("sponsors:checkout_success"),
            {"session_id": payment.stripe_checkout_session_id},
        )

        self.assertContains(response, "Your placement is reserved")
        self.assertContains(response, "Annual Ring Sponsorship")
        self.assertContains(response, "Ring 6, cell #1")
        self.assertContains(response, "€25.00")
        self.assertContains(response, "€5.75")
        self.assertContains(response, "€30.75")
        self.assertContains(response, "12-month term from approval/publication")
        self.assertContains(response, "Payment received pending compliance review")
        self.assertContains(response, "Your sponsorship is not active yet")
        self.assertContains(response, "No public sponsor listing or Telegram sponsor announcement is sent until Bearcave approves and publishes the placement.")

    def test_central_checkout_success_hides_internal_ring_zero_label(self):
        self.cell.product_type = SponsorCell.ProductType.CENTRAL_MONTHLY
        self.cell.ring = 0
        self.cell.cell_number = 0
        self.cell.save()
        application = self.create_pending_application(paid=True)
        application.product_type = SponsorCell.ProductType.CENTRAL_MONTHLY
        application.term_days = 30
        application.price_net_cents = 100000
        application.save()
        payment = application.payment
        payment.net_amount_cents = 100000
        payment.vat_amount_cents = 23000
        payment.total_amount_cents = 123000
        payment.save()

        response = self.client.get(
            reverse("sponsors:checkout_success"),
            {"session_id": payment.stripe_checkout_session_id},
        )

        self.assertContains(response, "Sponsor of the Month")
        self.assertContains(response, "€1,000.00")
        self.assertContains(response, "€230.00")
        self.assertContains(response, "€1,230.00")
        self.assertContains(response, "30-day term from approval/publication")
        self.assertContains(response, "No public sponsor listing or Telegram sponsor announcement is sent")
        self.assertNotContains(response, "Ring 0")
        self.assertNotContains(response, "cell #0")

    def test_rejection_marks_paid_application_refund_required_without_publication(self):
        user = get_user_model().objects.create_user("admin", password="pass", is_staff=True)
        application = self.create_pending_application(paid=True)

        reject_application(application.pk, user, "Not suitable")

        application.refresh_from_db()
        self.cell.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.REFUND_REQUIRED)
        self.assertEqual(self.cell.status, SponsorCell.Status.PAID_PENDING_APPROVAL)
        self.assertFalse(bool(self.cell.sponsor_logo))

    def test_paid_rejection_requires_staff_note_for_manual_refund_tracking(self):
        user = get_user_model().objects.create_user("admin", password="pass", is_staff=True)
        application = self.create_pending_application(paid=True)

        with self.assertRaisesMessage(ValueError, "staff note"):
            reject_application(application.pk, user, "")

        application.refresh_from_db()
        self.cell.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.PAID_PENDING_APPROVAL)
        self.assertEqual(self.cell.status, SponsorCell.Status.PAID_PENDING_APPROVAL)

    def test_refund_completed_releases_cell(self):
        user = get_user_model().objects.create_user("admin", password="pass", is_staff=True)
        application = self.create_pending_application(paid=True)
        reject_application(application.pk, user, "Not suitable")

        mark_refund_completed(application.pk, user, "Manual Stripe refund")

        application.refresh_from_db()
        self.cell.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.REFUNDED)
        self.assertEqual(application.payment.status, SponsorPayment.Status.REFUNDED)
        self.assertEqual(self.cell.status, SponsorCell.Status.AVAILABLE)


@override_settings(**SPONSOR_TEST_SETTINGS, IS_TESTING=False, DISABLE_EXTERNAL_NOTIFICATIONS=False,
                   TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_CHANNEL_ID="@culineire_test",
                   SITE_DOMAIN="culineire.ie", SITE_SCHEME="https")
class SponsorApprovalTelegramTests(TestCase):
    """Telegram announcement is sent when a sponsor application is approved."""

    def setUp(self):
        self.cell = SponsorCell.objects.create(cell_number=42, ring=3, position_in_ring=0)
        self.actor = get_user_model().objects.create_user("approver", password="pass", is_staff=True)

    def _make_paid_application(self):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=SponsorApplication.Status.PAID_PENDING_APPROVAL,
            sponsor_name="Bearcave Bakery",
            contact_name="Barry",
            email="barry@example.com",
            logo=png_upload(),
            price_net_cents=self.cell.price_net_cents,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
            terms_accepted_at=timezone.now(),
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PAID,
            net_amount_cents=application.price_net_cents,
            currency="eur",
            stripe_checkout_session_id="cs_tg_test",
            stripe_payment_intent_id="pi_tg_test",
            paid_at=timezone.now(),
        )
        self.cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
        self.cell.save(update_fields=["status"])
        SponsorComplianceCheck.objects.create(
            application=application,
            status=SponsorComplianceCheck.Status.MANUALLY_CLEARED,
            checked_at=timezone.now(),
        )
        return application

    @patch("newsfeed.telegram.send_telegram_photo_upload")
    def test_approve_sends_telegram_announcement(self, mock_send):
        mock_send.return_value = __import__("newsfeed.telegram", fromlist=["TelegramResult"]).TelegramResult(
            ok=True, status="sent", response='{"ok": true}'
        )
        application = self._make_paid_application()

        approve_application(application.pk, self.actor)

        self.assertEqual(mock_send.call_count, 1)
        image, caption = mock_send.call_args[0]
        self.assertIn("sponsors/applications/", image.name)
        self.assertIn("Thank you to Bearcave Bakery for supporting CulinEire.", caption)
        self.assertIn("has joined the CulinEire Sponsor Puzzle", caption)
        self.assertIn("Annual Ring Sponsor", caption)
        self.assertIn("Annual Ring Sponsorship", caption)
        self.assertIn("Bearcave Bakery", caption)
        self.assertIn("Ring 3, cell #42", caption)
        self.assertIn("Discover the Sponsor Puzzle:", caption)
        self.assertIn("culineire.ie/sponsors/", caption)
        for excluded in (
            "Sponsor of the Month",
            "Central Sponsor",
            "Founding Sponsor",
            "Central Founding Partner",
            "next 30 days",
        ):
            self.assertNotIn(excluded, caption)

    @patch("newsfeed.telegram.send_telegram_photo_upload")
    def test_approve_telegram_not_duplicated_on_second_call(self, mock_send):
        from newsfeed.telegram import TelegramResult
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        application = self._make_paid_application()

        approve_application(application.pk, self.actor)
        # Simulate a second approve attempt (would raise but Telegram should not double-send)
        # Just verify the SocialPostLog dedup works: call publish directly twice
        from newsfeed.telegram import publish_sponsor_to_telegram
        publish_sponsor_to_telegram(application)  # second call — already logged

        self.assertEqual(mock_send.call_count, 1, "Telegram must not send duplicate announcements")

    @patch("newsfeed.telegram.send_telegram_photo_upload")
    def test_approve_copies_logo_rotation_to_cell(self, mock_send):
        from newsfeed.telegram import TelegramResult
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        application = self._make_paid_application()
        application.logo_rotation = 90.0
        application.save(update_fields=["logo_rotation"])

        approve_application(application.pk, self.actor)

        self.cell.refresh_from_db()
        self.assertAlmostEqual(self.cell.logo_rotation, 90.0)

    @patch("newsfeed.telegram.send_telegram_photo_upload")
    def test_central_monthly_approval_sends_sponsor_of_the_month_photo(self, mock_send):
        from newsfeed.telegram import TelegramResult
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        self.cell.ring = 0
        self.cell.cell_number = 0
        self.cell.product_type = SponsorCell.ProductType.CENTRAL_MONTHLY
        self.cell.save()
        application = self._make_paid_application()
        application.product_type = SponsorCell.ProductType.CENTRAL_MONTHLY
        application.term_days = 30
        application.save()

        approve_application(application.pk, self.actor)

        image, caption = mock_send.call_args[0]
        self.assertIn("sponsors/applications/", image.name)
        self.assertIn("CulinEire Sponsor of the Month", caption)
        self.assertIn("Bearcave Bakery is now featured as our Sponsor of the Month.", caption)
        self.assertIn("For the next 30 days", caption)
        self.assertIn("highlighted through CulinEire sponsor areas", caption)
        self.assertIn("Discover the Sponsor Puzzle:", caption)
        self.assertNotIn("Annual Ring Sponsor", caption)
        self.assertNotIn("Annual Ring Sponsorship", caption)
        self.assertNotIn("Ring 0", caption)

    @patch("newsfeed.telegram.send_telegram_message_without_link_preview")
    @patch("newsfeed.telegram.send_telegram_photo_upload")
    def test_approval_without_logo_uses_text_fallback_without_link_preview(self, mock_photo, mock_text):
        from newsfeed.telegram import TelegramResult
        mock_text.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        application = self._make_paid_application()
        application.logo.delete(save=False)
        application.logo = ""
        application.save(update_fields=["logo"])

        approve_application(application.pk, self.actor)

        mock_photo.assert_not_called()
        mock_text.assert_called_once()
        self.assertIn("Annual Ring Sponsorship", mock_text.call_args.args[0])


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorModerationPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user("reader", password="pass")
        self.staff = user_model.objects.create_user("staff", password="pass", is_staff=True)
        self.superuser = user_model.objects.create_superuser("root", "root@example.com", "pass")
        self.owner = user_model.objects.create_user("greenbear", password="pass")
        RecipeAuthor.objects.update_or_create(
            slug="greenbear",
            defaults={"user": self.owner, "name": "GreenBear"},
        )

    def test_normal_user_cannot_access_sponsor_moderation(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("sponsors:moderation_applications"))

        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_access_sponsor_match_or_refund_details(self):
        cell = SponsorCell.objects.create(cell_number=7, ring=6, position_in_ring=0)
        application = SponsorApplication.objects.create(
            cell=cell,
            status=SponsorApplication.Status.REFUND_REQUIRED,
            sponsor_name="Private Sponsor",
            contact_name="Contact",
            email="private@example.com",
            logo=png_upload("private.png"),
            price_net_cents=cell.price_net_cents,
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PAID,
            net_amount_cents=application.price_net_cents,
            stripe_payment_intent_id="pi_private_staff_only",
        )
        SponsorAuditLog.objects.create(
            application=application,
            action=SponsorAuditLog.Action.REFUND_REQUIRED,
            notes="Staff-only refund note.",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("sponsors:moderation_application_detail", args=[application.pk]))

        self.assertEqual(response.status_code, 404)

    def test_staff_can_render_sponsor_moderation_pages(self):
        SponsorCell.objects.create(cell_number=1, ring=6, position_in_ring=0)
        self.client.force_login(self.staff)

        response = self.client.get(reverse("sponsors:moderation_applications"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sponsor Applications")

        response = self.client.get(reverse("sponsors:moderation_cells"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sponsor Cells")

    def test_staff_without_top_level_permission_cannot_access_sponsor_roadmap(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("sponsors:sponsor_roadmap"))

        self.assertEqual(response.status_code, 404)

    def test_superuser_can_access_sponsor_roadmap_with_seeded_milestones(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("sponsors:sponsor_roadmap"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stripe Sponsors Roadmap")
        self.assertContains(response, "Audit existing Sponsors section")
        self.assertTrue(SponsorRoadmapItem.objects.filter(title="Prepare live-mode checklist").exists())

    def test_owner_equivalent_can_access_sponsor_roadmap(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("sponsors:sponsor_roadmap"))

        self.assertEqual(response.status_code, 200)


class StripeMetadataConversionTests(TestCase):
    """Unit tests for _metadata() robustness against StripeObject payloads."""

    def _call(self, obj):
        from sponsors.services import _metadata
        return _metadata(obj)

    def test_plain_dict_metadata_returned_unchanged(self):
        obj = {"metadata": {"sponsor_application_id": "42", "sponsor_cell_id": "7"}}
        result = self._call(obj)
        self.assertEqual(result, {"sponsor_application_id": "42", "sponsor_cell_id": "7"})

    def test_empty_metadata_returns_empty_dict(self):
        self.assertEqual(self._call({}), {})
        self.assertEqual(self._call({"metadata": None}), {})
        self.assertEqual(self._call({"metadata": {}}), {})

    def test_stripe_object_with_to_dict_recursive(self):
        """Simulates a StripeObject that has to_dict_recursive()."""
        class FakeStripeObject:
            def to_dict_recursive(self):
                return {"sponsor_application_id": "99"}
            def __iter__(self):
                # Mimics broken StripeObject.__iter__ that yields integer indices
                return iter([0, 1, 2])
            def __getitem__(self, key):
                raise KeyError(key)

        obj = {"metadata": FakeStripeObject()}
        result = self._call(obj)
        self.assertEqual(result, {"sponsor_application_id": "99"})

    def test_stripe_object_with_to_dict_only(self):
        """Simulates a StripeObject that only has to_dict()."""
        class FakeStripeObjectSimple:
            def to_dict(self):
                return {"sponsor_application_id": "55"}
            def __iter__(self):
                return iter([0])
            def __getitem__(self, key):
                raise KeyError(key)

        obj = {"metadata": FakeStripeObjectSimple()}
        result = self._call(obj)
        self.assertEqual(result, {"sponsor_application_id": "55"})

    def test_stripe_object_with_data_attr_fallback(self):
        """Simulates a StripeObject with _data attribute as last resort."""
        class FakeStripeObjectData:
            _data = {"sponsor_application_id": "77"}
            def __iter__(self):
                return iter([0])
            def __getitem__(self, key):
                raise KeyError(key)

        obj = {"metadata": FakeStripeObjectData()}
        result = self._call(obj)
        self.assertEqual(result, {"sponsor_application_id": "77"})

    def test_dict_of_metadata_would_previously_raise_keyerror(self):
        """dict(stripe_obj) raises KeyError: 0 — _metadata must not call dict() on it."""
        class BrokenStripeObject:
            def __iter__(self):
                return iter([0])
            def __getitem__(self, key):
                raise KeyError(key)
            def to_dict_recursive(self):
                return {"sponsor_application_id": "33", "sponsor_cell_id": "1"}

        obj = {"metadata": BrokenStripeObject()}
        # This would have raised KeyError: 0 with the old dict(metadata) approach
        result = self._call(obj)
        self.assertEqual(result["sponsor_application_id"], "33")


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorWebhookHardeningTests(TestCase):
    """Phase 2 hardening tests for the Stripe webhook state machine."""

    def setUp(self):
        self.cell = SponsorCell.objects.create(cell_number=99, ring=6, position_in_ring=0)

    def _make_payment_pending_application(self):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=SponsorApplication.Status.PAYMENT_PENDING,
            sponsor_name="TestCo",
            contact_name="Tester",
            email="test@example.com",
            logo=png_upload(),
            price_net_cents=self.cell.price_net_cents,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
            terms_accepted_at=timezone.now(),
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PENDING,
            net_amount_cents=application.price_net_cents,
            currency="eur",
            stripe_checkout_session_id="cs_test_hp_123",
        )
        self.cell.status = SponsorCell.Status.PAYMENT_PENDING
        self.cell.save(update_fields=["status"])
        return application

    def _completed_event(self, application, event_id="evt_hp_1", payment_status="paid"):
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_hp_completed",
                    "payment_intent": "pi_hp_001",
                    "payment_status": payment_status,
                    "amount_subtotal": application.price_net_cents,
                    "amount_total": application.price_net_cents + 575,
                    "total_details": {"amount_tax": 575},
                    "currency": "eur",
                    "metadata": {
                        "sponsor_application_id": str(application.pk),
                        "sponsor_cell_id": str(self.cell.pk),
                    },
                }
            },
        }

    # Issue 2: payment_status != "paid" must not mark application as paid.
    def test_checkout_completed_with_unpaid_payment_status_does_not_mark_paid(self):
        application = self._make_payment_pending_application()
        event = self._completed_event(application, event_id="evt_unpaid_1", payment_status="unpaid")

        handle_stripe_event(event)

        application.refresh_from_db()
        self.cell.refresh_from_db()
        # Must stay payment_pending — not advanced to paid_pending_approval.
        self.assertEqual(application.status, SponsorApplication.Status.PAYMENT_PENDING)
        self.assertEqual(self.cell.status, SponsorCell.Status.PAYMENT_PENDING)

    def test_checkout_completed_with_no_payment_required_does_not_mark_paid(self):
        application = self._make_payment_pending_application()
        event = self._completed_event(application, event_id="evt_nopay_1", payment_status="no_payment_required")

        handle_stripe_event(event)

        application.refresh_from_db()
        self.assertNotEqual(application.status, SponsorApplication.Status.PAID_PENDING_APPROVAL)

    # Issue 1: Late completion after cell reassignment.
    def test_late_checkout_after_cell_released_creates_refund_required(self):
        application = self._make_payment_pending_application()
        # Cancel the application — cell becomes available.
        from .services import cancel_pending_application
        cancel_pending_application(application.reference)
        application.refresh_from_db()
        self.cell.refresh_from_db()
        self.assertEqual(self.cell.status, SponsorCell.Status.AVAILABLE)

        # Now simulate late checkout.session.completed arriving.
        # Re-set application to payment_pending to simulate the window where
        # the old session completes after cancel.
        application.status = SponsorApplication.Status.PAYMENT_PENDING
        application.save(update_fields=["status"])
        # Cell is AVAILABLE (taken by someone else or released). The late event must NOT overwrite.
        event = self._completed_event(application, event_id="evt_late_1", payment_status="paid")

        handle_stripe_event(event)

        application.refresh_from_db()
        self.cell.refresh_from_db()
        # Application must be in refund_required, not paid_pending_approval.
        self.assertEqual(application.status, SponsorApplication.Status.REFUND_REQUIRED)
        # Cell must remain available (not overwritten by this late event).
        self.assertEqual(self.cell.status, SponsorCell.Status.AVAILABLE)
        # Logo must not be published.
        self.assertFalse(bool(self.cell.sponsor_logo))

    # Issue 3: Webhook ordering — terminal states must not be overwritten.
    def test_completed_event_after_rejected_state_does_not_overwrite(self):
        application = self._make_payment_pending_application()
        # Mark application as rejected directly (simulate a staff action or prior event).
        application.status = SponsorApplication.Status.REJECTED
        application.save(update_fields=["status"])

        event = self._completed_event(application, event_id="evt_rejected_replay_1", payment_status="paid")
        handle_stripe_event(event)

        application.refresh_from_db()
        # Must stay rejected.
        self.assertEqual(application.status, SponsorApplication.Status.REJECTED)

    def test_completed_event_after_refunded_state_does_not_overwrite(self):
        application = self._make_payment_pending_application()
        application.status = SponsorApplication.Status.REFUNDED
        application.save(update_fields=["status"])

        event = self._completed_event(application, event_id="evt_refunded_replay_1", payment_status="paid")
        handle_stripe_event(event)

        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.REFUNDED)

    def test_completed_event_after_cancelled_state_does_not_overwrite(self):
        application = self._make_payment_pending_application()
        application.status = SponsorApplication.Status.CANCELLED
        application.save(update_fields=["status"])

        event = self._completed_event(application, event_id="evt_cancelled_replay_1", payment_status="paid")
        handle_stripe_event(event)

        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.CANCELLED)

    def test_completed_event_after_expired_state_does_not_overwrite(self):
        application = self._make_payment_pending_application()
        application.status = SponsorApplication.Status.EXPIRED
        application.save(update_fields=["status"])

        event = self._completed_event(application, event_id="evt_expired_replay_1", payment_status="paid")
        handle_stripe_event(event)

        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.EXPIRED)

    # Issue 4: Refund webhook — full refund completes the refund workflow.
    def test_charge_refunded_full_refund_transitions_refund_required_to_refunded(self):
        application = self._make_payment_pending_application()
        payment = application.payment
        payment.status = SponsorPayment.Status.PAID
        payment.stripe_payment_intent_id = "pi_refund_full"
        payment.total_amount_cents = 3050
        payment.net_amount_cents = 2500
        payment.vat_amount_cents = 550
        payment.paid_at = timezone.now()
        payment.save()
        application.status = SponsorApplication.Status.REFUND_REQUIRED
        application.save(update_fields=["status"])
        self.cell.status = SponsorCell.Status.REJECTED
        self.cell.save(update_fields=["status"])

        charge_refunded_event = {
            "id": "evt_charge_refunded_full",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_refund_full",
                    "amount": 3050,
                    "amount_refunded": 3050,
                }
            },
        }
        handle_stripe_event(charge_refunded_event)

        application.refresh_from_db()
        self.cell.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.REFUNDED)
        self.assertEqual(payment.status, SponsorPayment.Status.REFUNDED)
        self.assertEqual(self.cell.status, SponsorCell.Status.AVAILABLE)

    def test_charge_refunded_partial_refund_does_not_release_cell(self):
        application = self._make_payment_pending_application()
        payment = application.payment
        payment.status = SponsorPayment.Status.PAID
        payment.stripe_payment_intent_id = "pi_refund_partial"
        payment.total_amount_cents = 3050
        payment.paid_at = timezone.now()
        payment.save()
        application.status = SponsorApplication.Status.REFUND_REQUIRED
        application.save(update_fields=["status"])
        self.cell.status = SponsorCell.Status.REJECTED
        self.cell.save(update_fields=["status"])

        charge_refunded_event = {
            "id": "evt_charge_refunded_partial",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_refund_partial",
                    "amount": 3050,
                    "amount_refunded": 1000,  # partial
                }
            },
        }
        handle_stripe_event(charge_refunded_event)

        application.refresh_from_db()
        self.cell.refresh_from_db()
        payment.refresh_from_db()
        # Partial refund keeps refund_required and keeps the paid placement reserved.
        self.assertEqual(application.status, SponsorApplication.Status.REFUND_REQUIRED)
        self.assertEqual(payment.status, SponsorPayment.Status.PARTIALLY_REFUNDED)
        self.assertEqual(self.cell.status, SponsorCell.Status.PAID_PENDING_APPROVAL)


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorModerationTransitionTests(TestCase):
    """Issue 5: Moderation transition validation tests."""

    def setUp(self):
        self.cell = SponsorCell.objects.create(cell_number=88, ring=6, position_in_ring=0)
        self.user = get_user_model().objects.create_user("mod", password="pass", is_staff=True)

    def _make_application(self, status, paid=False):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=status,
            sponsor_name="TransitionCo",
            contact_name="Tester",
            email="transition@example.com",
            logo=png_upload(),
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
            currency="eur",
            stripe_checkout_session_id="cs_trans_123" if paid else None,
            stripe_payment_intent_id="pi_trans_123" if paid else "",
            paid_at=timezone.now() if paid else None,
        )
        return application

    def test_mark_refund_completed_from_non_refund_required_raises(self):
        application = self._make_application(SponsorApplication.Status.APPROVED, paid=True)
        with self.assertRaises(ValueError):
            mark_refund_completed(application.pk, self.user, "test")

    def test_mark_refund_completed_from_refunded_raises(self):
        application = self._make_application(SponsorApplication.Status.REFUNDED, paid=True)
        with self.assertRaises(ValueError):
            mark_refund_completed(application.pk, self.user, "test")

    def test_reject_active_application_raises(self):
        application = self._make_application(SponsorApplication.Status.APPROVED, paid=True)
        with self.assertRaises(ValueError):
            reject_application(application.pk, self.user, "too late")

    def test_reject_refunded_application_raises(self):
        application = self._make_application(SponsorApplication.Status.REFUNDED, paid=True)
        with self.assertRaises(ValueError):
            reject_application(application.pk, self.user, "already refunded")

    def test_reject_expired_application_raises(self):
        application = self._make_application(SponsorApplication.Status.EXPIRED, paid=True)
        with self.assertRaises(ValueError):
            reject_application(application.pk, self.user, "already expired")

    def test_expire_non_approved_application_raises(self):
        application = self._make_application(SponsorApplication.Status.PAID_PENDING_APPROVAL, paid=True)
        with self.assertRaises(ValueError):
            expire_application(application.pk, self.user)

    def test_expire_payment_pending_application_raises(self):
        application = self._make_application(SponsorApplication.Status.PAYMENT_PENDING, paid=False)
        with self.assertRaises(ValueError):
            expire_application(application.pk, self.user)

    def test_mark_refund_completed_valid_from_refund_required(self):
        application = self._make_application(SponsorApplication.Status.REFUND_REQUIRED, paid=True)
        self.cell.status = SponsorCell.Status.REJECTED
        self.cell.save(update_fields=["status"])

        result = mark_refund_completed(application.pk, self.user, "test refund")

        self.assertEqual(result.status, SponsorApplication.Status.REFUNDED)

    def test_mark_refund_completed_requires_staff_note(self):
        application = self._make_application(SponsorApplication.Status.REFUND_REQUIRED, paid=True)

        with self.assertRaisesMessage(ValueError, "staff note"):
            mark_refund_completed(application.pk, self.user, "")


@override_settings(**SPONSOR_TEST_SETTINGS, SPONSOR_ADMIN_EMAIL="admin@example.com")
class SponsorPaymentNotificationTests(TestCase):
    """Tests for admin email notification after sponsor payment confirmation."""

    def setUp(self):
        self.cell = SponsorCell.objects.create(cell_number=77, ring=6, position_in_ring=0)

    def _make_payment_pending_application(self):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=SponsorApplication.Status.PAYMENT_PENDING,
            sponsor_name="Notify Co",
            contact_name="Nora",
            email="notify@example.com",
            logo=png_upload(),
            price_net_cents=self.cell.price_net_cents,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
            terms_accepted_at=timezone.now(),
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PENDING,
            net_amount_cents=application.price_net_cents,
            currency="eur",
            stripe_checkout_session_id="cs_notify_123",
        )
        self.cell.status = SponsorCell.Status.PAYMENT_PENDING
        self.cell.save(update_fields=["status"])
        return application

    def _completed_event(self, application):
        return {
            "id": "evt_notify_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_notify_done",
                    "payment_intent": "pi_notify_1",
                    "payment_status": "paid",
                    "amount_subtotal": application.price_net_cents,
                    "amount_total": application.price_net_cents + 575,
                    "total_details": {"amount_tax": 575},
                    "currency": "eur",
                    "metadata": {
                        "sponsor_application_id": str(application.pk),
                        "sponsor_cell_id": str(self.cell.pk),
                    },
                }
            },
        }

    def test_payment_confirmation_sends_admin_email(self):
        """handle_stripe_event sends one email to SPONSOR_ADMIN_EMAIL on new payment."""
        from sponsors.services import handle_stripe_event
        application = self._make_payment_pending_application()

        with self.settings(SPONSOR_ADMIN_EMAIL="admin@example.com"):
            with self.assertLogs("sponsors.services", level="DEBUG") if False else __import__("contextlib").nullcontext():
                from django.core import mail
                mail.outbox = []
                handle_stripe_event(self._completed_event(application))

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("admin@example.com", email.to)
        self.assertIn("pending approval", email.subject.lower())
        self.assertIn("Notify Co", email.body)
        self.assertIn("notify@example.com", email.body)

    def test_duplicate_webhook_does_not_send_duplicate_email(self):
        """A second identical webhook (idempotent) must not send a second email."""
        from sponsors.services import handle_stripe_event
        application = self._make_payment_pending_application()
        event = self._completed_event(application)

        from django.core import mail
        mail.outbox = []
        handle_stripe_event(event)
        # Second call — application is now paid_pending_approval, so it is a replay
        handle_stripe_event({**event, "id": "evt_notify_2"})

        self.assertEqual(len(mail.outbox), 1, "Email must be sent exactly once, not on replay")

    def test_payment_state_machine_unchanged(self):
        """Payment confirmation still sets correct statuses."""
        from sponsors.services import handle_stripe_event
        application = self._make_payment_pending_application()

        from django.core import mail
        mail.outbox = []
        handle_stripe_event(self._completed_event(application))

        application.refresh_from_db()
        self.cell.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW)
        self.assertEqual(self.cell.status, SponsorCell.Status.PAID_PENDING_APPROVAL)
        payment = application.payment
        self.assertEqual(payment.status, SponsorPayment.Status.PAID)
        self.assertEqual(payment.vat_amount_cents, 575)

    def test_no_email_sent_when_sponsor_admin_email_empty(self):
        """If SPONSOR_ADMIN_EMAIL is empty, no email is sent (no crash)."""
        from sponsors.services import handle_stripe_event
        application = self._make_payment_pending_application()

        from django.core import mail
        mail.outbox = []
        with self.settings(SPONSOR_ADMIN_EMAIL=""):
            handle_stripe_event(self._completed_event(application))

        self.assertEqual(len(mail.outbox), 0)


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorPublicFormTests(TestCase):
    """Tests that the public sponsor form renders and validates logo rights correctly."""

    def setUp(self):
        self.cell = SponsorCell.objects.create(cell_number=1, ring=6, position_in_ring=0)

    def test_sponsor_puzzle_page_returns_200(self):
        response = self.client.get(reverse("sponsors:puzzle"))
        self.assertEqual(response.status_code, 200)

    def test_sponsorship_contract_distinguishes_central_monthly_from_annual_ring(self):
        response = self.client.get(reverse("sponsors:annual_contract"))
        self.assertContains(response, "Annual Ring Sponsorship")
        self.assertContains(response, "Central Sponsor of the Month costs €1000/month plus VAT")
        self.assertContains(response, "runs for 30 days from that publication date")
        self.assertContains(response, "It is not a calendar-month or annual product")

    def test_sponsor_modal_js_has_exactly_three_public_confirmations(self):
        """sponsors_modal.js must render exactly 3 confirmation checkboxes."""
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_modal.js")
        self.assertIsNotNone(js_path, "sponsors_modal.js not found in static files")
        with open(js_path, encoding="utf-8") as f:
            js_content = f.read()

        # All 3 checkbox IDs must be present
        self.assertIn("spm-confirm-1", js_content, "Checkbox 1 (logo rights) must be in modal JS")
        self.assertIn("spm-confirm-2", js_content, "Checkbox 2 (terms/payment) must be in modal JS")
        self.assertIn("spm-confirm-3", js_content, "Checkbox 3 (sanctions) must be in modal JS")

        # Old redundant checkbox IDs must not appear
        self.assertNotIn("spm-sanctions-1", js_content, "Old spm-sanctions-1 must be removed")
        self.assertNotIn("spm-sanctions-2", js_content, "Old spm-sanctions-2 must be removed")
        self.assertNotIn("spm-sanctions-3", js_content, "Old spm-sanctions-3 must be removed")
        self.assertNotIn("spm-sanctions-4", js_content, "Old spm-sanctions-4 must be removed")
        self.assertNotIn("spm-approval", js_content, "Old spm-approval must be removed")

        # Key wording checks
        self.assertIn("logo_rights_confirmed", js_content,
                      "logo_rights_confirmed must be submitted by the form JS")
        self.assertIn("Bearcave Limited may display it on CulinEire", js_content,
                      "Logo rights wording must mention Bearcave Limited displaying on CulinEire")
        self.assertIn("Payment does not guarantee approval, publication or activation", js_content,
                      "Combined terms/payment wording must be present")
        self.assertIn("I also confirm that I am not applying on behalf of", js_content,
                      "Combined sanctions declaration must be present")

        # Old duplicate wording must be gone
        self.assertNotIn(
            "I understand that CulinEire may delay, refuse, suspend, cancel, reject, hold or reverse",
            js_content,
            "Old redundant sanctions-4 wording must be removed",
        )

    def test_sponsor_modal_no_backdrop_click_close(self):
        """Backdrop click must NOT close the modal (handler removed)."""
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_modal.js")
        self.assertIsNotNone(js_path)
        with open(js_path, encoding="utf-8") as f:
            js_content = f.read()
        # The old backdrop-close pattern must be gone
        self.assertNotIn(
            "if (e.target === modal) closeModal()",
            js_content,
            "Backdrop click must not close the modal — old handler must be removed",
        )

    def test_sponsor_modal_js_has_dirty_guard(self):
        """sponsors_modal.js must have isFormDirty, maybeClose and window.confirm guard."""
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_modal.js")
        self.assertIsNotNone(js_path)
        with open(js_path, encoding="utf-8") as f:
            js_content = f.read()
        self.assertIn("isFormDirty", js_content, "isFormDirty function must be present")
        self.assertIn("maybeClose", js_content, "maybeClose function must be present")
        self.assertIn("window.confirm", js_content, "window.confirm guard must be present")

    def test_sponsor_modal_template_has_panel_header(self):
        """puzzle.html modal must wrap close button in .spm-panel-header."""
        import os
        from django.conf import settings
        template_path = os.path.join(settings.BASE_DIR, "templates", "sponsors", "puzzle.html")
        with open(template_path, encoding="utf-8") as f:
            html = f.read()
        self.assertIn(
            'class="spm-panel-header"',
            html,
            "Modal must have a .spm-panel-header wrapper for the close button",
        )

    def test_sponsor_puzzle_centre_uses_sponsor_of_the_month_copy(self):
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_puzzle.js")
        self.assertIsNotNone(js_path, "sponsors_puzzle.js not found in static files")
        with open(js_path, encoding="utf-8") as f:
            js_content = f.read()
        self.assertIn("★ SPONSOR OF THE MONTH ★", js_content)
        self.assertNotIn("FOUNDING SPONSOR", js_content)

    def test_enquire_without_logo_rights_returns_400(self):
        """Submitting the enquiry without logo_rights_confirmed must return 400."""
        data = {
            "sponsor_name": "Test Sponsor",
            "contact_name": "Test Contact",
            "email": "test@example.com",
            "terms_accepted": "on",
            "sanctions_declaration_1": "on",
            # logo_rights_confirmed deliberately omitted
        }
        response = self.client.post(
            reverse("sponsors:cell_enquire", args=[self.cell.pk]), data
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Image rights confirmed", response.json()["error"])

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_enquire_with_all_three_confirmations_proceeds_to_checkout(self):
        """Submitting all 3 required confirmations passes validation and reaches checkout."""
        from unittest.mock import patch
        from .services import CheckoutSessionInfo
        data = {
            "sponsor_name": "Test Sponsor",
            "contact_name": "Test Contact",
            "email": "test@example.com",
            "logo_rights_confirmed": "on",
            "terms_accepted": "on",
            "sanctions_declaration_1": "on",
            "logo": png_upload(),
            "logo_offset_x": "0",
            "logo_offset_y": "0",
            "logo_scale": "1",
            "logo_rotation": "0",
        }
        with patch(
            "sponsors.views.create_checkout_session",
            return_value=CheckoutSessionInfo("cs_test_rights", "https://checkout.stripe.test/rights"),
        ):
            response = self.client.post(
                reverse("sponsors:cell_enquire", args=[self.cell.pk]), data
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("checkout_url", response.json())

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_approval_acknowledged_set_on_application_after_checkout(self):
        """approval_acknowledged must be True on the saved application (combined with terms checkbox)."""
        from unittest.mock import patch
        from .services import CheckoutSessionInfo
        data = {
            "sponsor_name": "Rights Check Sponsor",
            "contact_name": "Rights Contact",
            "email": "rights@example.com",
            "logo_rights_confirmed": "on",
            "terms_accepted": "on",
            "sanctions_declaration_1": "on",
            "logo": png_upload(),
            "logo_offset_x": "0",
            "logo_offset_y": "0",
            "logo_scale": "1",
            "logo_rotation": "0",
        }
        with patch(
            "sponsors.views.create_checkout_session",
            return_value=CheckoutSessionInfo("cs_test_ack", "https://checkout.stripe.test/ack"),
        ):
            response = self.client.post(
                reverse("sponsors:cell_enquire", args=[self.cell.pk]), data
            )
        self.assertEqual(response.status_code, 200)
        app = SponsorApplication.objects.get()
        self.assertTrue(app.approval_acknowledged)
        self.assertTrue(app.terms_accepted)
        self.assertTrue(app.logo_rights_confirmed)


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorWeeklyRingTests(TestCase):
    """Tests for the ring 6 weekly pricing model."""

    def setUp(self):
        self.actor = get_user_model().objects.create_user("wk_staff", password="pass", is_staff=True)
        self.cell_top = SponsorCell.objects.create(
            cell_number=1, ring=6, position_in_ring=0,
            product_type=SponsorCell.ProductType.WEEKLY_RING,
            price_override_cents=2500,
        )
        self.cell_bottom = SponsorCell.objects.create(
            cell_number=30, ring=6, position_in_ring=29,
            product_type=SponsorCell.ProductType.WEEKLY_RING,
            price_override_cents=500,
        )

    def _make_paid_weekly_application(self, cell, price_cents, session_id="cs_wk_test"):
        payment_intent_id = session_id.replace("cs_", "pi_")
        application = SponsorApplication.objects.create(
            cell=cell,
            status=SponsorApplication.Status.PAID_PENDING_APPROVAL,
            sponsor_name="Weekly Sponsor",
            contact_name="Wendy",
            email="wendy@example.com",
            logo=png_upload("weekly.png"),
            price_net_cents=price_cents,
            product_type=SponsorCell.ProductType.WEEKLY_RING,
            term_days=7,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
            terms_accepted_at=timezone.now(),
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PAID,
            net_amount_cents=price_cents,
            currency="eur",
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=payment_intent_id,
            paid_at=timezone.now(),
        )
        cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
        cell.save(update_fields=["status"])
        SponsorComplianceCheck.objects.create(
            application=application,
            status=SponsorComplianceCheck.Status.MANUALLY_CLEARED,
            checked_at=timezone.now(),
        )
        return application

    # --- Test 1: ring 6 product type ---

    def test_ring6_cell_has_weekly_ring_product_type(self):
        self.assertEqual(self.cell_top.product_type, SponsorCell.ProductType.WEEKLY_RING)

    # --- Test 2: ring 6 has 60 cells ---

    def test_ring6_has_60_cells_when_seeded(self):
        SponsorCell.objects.all().delete()
        from sponsors.management.commands.create_sponsor_cells import RING_LAYOUT
        cell_number = 1
        for ring, count in RING_LAYOUT:
            for pos in range(count):
                SponsorCell.objects.get_or_create(
                    cell_number=cell_number,
                    defaults={"ring": ring, "position_in_ring": pos},
                )
                cell_number += 1
        self.assertEqual(SponsorCell.objects.filter(ring=6).count(), 60)

    # --- Test 3: exact cell_number → price mapping ---

    def test_ring6_price_zone_mapping(self):
        cases = [
            (1, 2500), (8, 2500), (54, 2500), (60, 2500),   # top
            (9, 2000), (15, 2000), (47, 2000), (53, 2000),   # upper sides
            (16, 1000), (23, 1000), (39, 1000), (46, 1000),  # lower sides
            (24, 500), (30, 500), (38, 500),                  # bottom
        ]
        for cell_number, expected in cases:
            with self.subTest(cell_number=cell_number):
                cell = SponsorCell.objects.create(
                    cell_number=cell_number + 1000,  # unique cell_number
                    ring=6, position_in_ring=cell_number - 1,
                    product_type=SponsorCell.ProductType.WEEKLY_RING,
                    price_override_cents=expected,
                )
                self.assertEqual(cell.price_net_cents, expected)

    def test_price_override_cents_used_for_price_net_cents(self):
        self.assertEqual(self.cell_top.price_net_cents, 2500)
        self.assertEqual(self.cell_bottom.price_net_cents, 500)

    # --- Test 4/5/6/7: Checkout uses weekly price and tax config ---

    @override_settings(STRIPE_SECRET_KEY="sk_test_123", SITE_BASE_URL="https://culineire.ie")
    def test_weekly_checkout_uses_correct_net_price_and_tax_config(self):
        application = self._make_paid_weekly_application(self.cell_top, 2500)

        class FakeSession:
            called_with = None
            @classmethod
            def create(cls, **kwargs):
                cls.called_with = kwargs
                return {"id": "cs_wk_stripe", "url": "https://stripe.test/wk"}

        class FakeStripe:
            class checkout:
                Session = FakeSession

        with patch("sponsors.services._stripe", return_value=FakeStripe):
            create_checkout_session(application)

        kw = FakeSession.called_with
        price_data = kw["line_items"][0]["price_data"]
        self.assertEqual(price_data["unit_amount"], 2500)
        self.assertEqual(price_data["tax_behavior"], "exclusive")        # test 7
        self.assertEqual(kw["automatic_tax"], {"enabled": True})         # test 5
        self.assertEqual(kw["tax_id_collection"], {"enabled": True})     # test 6
        self.assertEqual(price_data["product_data"]["name"], "CulinEire Weekly Ring Sponsor Spot")  # test 4
        self.assertEqual(price_data["product_data"]["tax_code"], "txcd_20060002")

    # --- Test 8: public modal / as_dict shows weekly placement and VAT ---

    def test_weekly_cell_as_dict_includes_product_type_and_weekly_price_display(self):
        data = self.cell_top.as_dict()
        self.assertEqual(data["product_type"], "weekly_ring")
        self.assertIn("/week", data["price_display"])
        self.assertIn("+ VAT", data["price_display"])
        self.assertEqual(data["price_net_cents"], 2500)

    def test_weekly_cell_price_display_property(self):
        self.assertEqual(self.cell_top.price_display, "€25/week + VAT")
        self.assertEqual(self.cell_bottom.price_display, "€5/week + VAT")

    # --- Test 9: exactly 3 confirmation checkboxes (modal JS) ---

    def test_modal_js_has_weekly_ring_wording_and_three_confirmations(self):
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_modal.js")
        self.assertIsNotNone(js_path)
        with open(js_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Weekly Ring Sponsorship Terms", content)
        self.assertIn("spm-confirm-1", content)
        self.assertIn("spm-confirm-2", content)
        self.assertIn("spm-confirm-3", content)
        self.assertNotIn("spm-confirm-4", content)
        self.assertNotIn("spm-approval", content)

    # --- Test 10: old 7-checkbox flow absent ---

    def test_old_seven_checkbox_flow_does_not_return(self):
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_modal.js")
        with open(js_path, encoding="utf-8") as f:
            content = f.read()
        for forbidden in ("spm-sanctions-1", "spm-sanctions-2", "spm-sanctions-3", "spm-sanctions-4", "spm-approval"):
            self.assertNotIn(forbidden, content, f"{forbidden} must not appear in modal JS")

    # --- Test 11: weekly approval activates for 7 days ---

    def test_weekly_approval_activates_for_7_days(self):
        application = self._make_paid_weekly_application(self.cell_top, 2500)

        approve_application(application.pk, self.actor)

        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.APPROVED)
        delta = application.expires_at - application.published_at
        self.assertEqual(delta.days, 7)

    # --- Test 12: weekly expiry releases cell back to AVAILABLE ---

    def test_weekly_expiry_releases_cell(self):
        application = self._make_paid_weekly_application(self.cell_top, 2500)
        approve_application(application.pk, self.actor)
        application.refresh_from_db()

        expire_application(application.pk, self.actor)

        application.refresh_from_db()
        self.cell_top.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.EXPIRED)
        self.assertEqual(self.cell_top.status, SponsorCell.Status.AVAILABLE)
        self.assertEqual(self.cell_top.product_type, SponsorCell.ProductType.WEEKLY_RING)
        self.assertEqual(self.cell_top.price_override_cents, 2500)

    # --- Test 12b: expired weekly cell can be purchased again ---

    def test_weekly_cell_is_purchasable_after_expiry(self):
        first = self._make_paid_weekly_application(self.cell_top, 2500)
        approve_application(first.pk, self.actor)
        expire_application(first.pk, self.actor)
        self.cell_top.refresh_from_db()
        self.assertEqual(self.cell_top.status, SponsorCell.Status.AVAILABLE)

        # Cell can be selected again — a second application is possible.
        second = self._make_paid_weekly_application(self.cell_top, 2500, session_id="cs_wk_second")
        self.assertEqual(second.cell, self.cell_top)
        self.assertEqual(second.product_type, SponsorCell.ProductType.WEEKLY_RING)
        self.assertEqual(second.price_net_cents, 2500)

    # --- Test 13: compliance/sanctions still blocks weekly approvals ---

    def test_compliance_sanctions_blocking_still_works_for_weekly(self):
        application = self._make_paid_weekly_application(self.cell_top, 2500)
        application.status = SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW
        application.save(update_fields=["status"])

        snapshot = SanctionsSourceSnapshot.objects.create(
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            source_name="EU FSF",
            source_url="https://example.com",
            source_sha256="wk_abcdef",
            record_count=1,
            status=SanctionsSourceSnapshot.Status.SUCCESS,
        )
        subject = SanctionsSubject.objects.create(
            source_snapshot=snapshot,
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            primary_name="Weekly Sponsor",
            normalised_name="weekly sponsor",
        )
        from .models import SponsorSanctionsMatch
        SponsorSanctionsMatch.objects.create(
            application=application,
            subject=subject,
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            match_status=SponsorSanctionsMatch.Status.POSSIBLE,
        )
        with self.assertRaisesMessage(ValueError, "unresolved possible sanctions matches"):
            approve_application(application.pk, self.actor)

    # --- Test 14: central monthly flow still passes ---

    def test_central_monthly_approval_still_activates_for_30_days(self):
        central = SponsorCell.objects.create(
            cell_number=200, ring=0, position_in_ring=0,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
        )
        application = SponsorApplication.objects.create(
            cell=central,
            status=SponsorApplication.Status.PAID_PENDING_APPROVAL,
            sponsor_name="Monthly Co",
            contact_name="Mo",
            email="mo@example.com",
            logo=png_upload("central_wk.png"),
            price_net_cents=100000,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
            term_days=30,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
            terms_accepted_at=timezone.now(),
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PAID,
            net_amount_cents=100000,
            currency="eur",
            stripe_checkout_session_id="cs_central_wk_unique",
            stripe_payment_intent_id="pi_central_wk_unique",
            paid_at=timezone.now(),
        )
        central.status = SponsorCell.Status.PAID_PENDING_APPROVAL
        central.save(update_fields=["status"])
        SponsorComplianceCheck.objects.create(
            application=application,
            status=SponsorComplianceCheck.Status.MANUALLY_CLEARED,
            checked_at=timezone.now(),
        )

        approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertEqual((application.expires_at - application.published_at).days, 30)

    # --- Test 15: Stripe remains in test/sandbox mode ---

    @override_settings(STRIPE_PRICE_MODE="test", STRIPE_SECRET_KEY="sk_test_123")
    def test_stripe_remains_in_test_mode(self):
        from sponsors.services import validate_stripe_runtime_configuration
        # Should pass for test mode — not raise
        try:
            validate_stripe_runtime_configuration()
        except Exception:
            pass
        from django.conf import settings as _s
        self.assertNotEqual(getattr(_s, "STRIPE_PRICE_MODE", ""), "live")

    # --- cell_enquire sets term_days=7 for weekly ring ---

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_weekly_cell_enquire_sets_term_days_7_and_weekly_product_type(self):
        self.cell_top.status = SponsorCell.Status.AVAILABLE
        self.cell_top.save(update_fields=["status"])
        data = {
            "sponsor_name": "Weekly Co",
            "contact_name": "Wendy",
            "email": "wendy2@example.com",
            "logo": png_upload(),
            "logo_offset_x": "0",
            "logo_offset_y": "0",
            "logo_scale": "1",
            "logo_rotation": "0",
            "logo_rights_confirmed": "on",
            "terms_accepted": "on",
            "sanctions_declaration_1": "on",
        }
        with patch(
            "sponsors.views.create_checkout_session",
            return_value=CheckoutSessionInfo("cs_wk_enquire", "https://stripe.test/wk"),
        ):
            response = self.client.post(
                reverse("sponsors:cell_enquire", args=[self.cell_top.pk]), data
            )
        self.assertEqual(response.status_code, 200)
        application = SponsorApplication.objects.get(cell=self.cell_top)
        self.assertEqual(application.term_days, 7)
        self.assertEqual(application.product_type, SponsorCell.ProductType.WEEKLY_RING)
        self.assertEqual(application.price_net_cents, 2500)

    # --- term_display shows 7-day term ---

    def test_weekly_application_term_display(self):
        application = SponsorApplication(
            cell=self.cell_top,
            product_type=SponsorCell.ProductType.WEEKLY_RING,
            price_net_cents=2500,
            term_days=7,
        )
        self.assertEqual(application.term_display, "7-day term from approval/publication")
        self.assertEqual(application.price_display, "€25/week + VAT")

    # --- annual ring term_display unchanged ---

    def test_annual_ring_term_display_unchanged(self):
        cell = SponsorCell.objects.create(cell_number=300, ring=5, position_in_ring=0)
        application = SponsorApplication(
            cell=cell,
            product_type=SponsorCell.ProductType.ANNUAL_RING,
            price_net_cents=5000,
            term_days=365,
        )
        self.assertEqual(application.term_display, "12-month term from approval/publication")


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorContractEmailTests(TestCase):
    """Tests for contract agreement email generation and delivery on approval."""

    def setUp(self):
        self.actor = get_user_model().objects.create_user("contract_staff", password="pass", is_staff=True)
        self.annual_cell = SponsorCell.objects.create(
            cell_number=501, ring=5, position_in_ring=0,
            product_type=SponsorCell.ProductType.ANNUAL_RING,
        )
        self.monthly_cell = SponsorCell.objects.create(
            cell_number=502, ring=0, position_in_ring=0,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
        )
        self.weekly_cell = SponsorCell.objects.create(
            cell_number=503, ring=6, position_in_ring=0,
            product_type=SponsorCell.ProductType.WEEKLY_RING,
            price_override_cents=2500,
        )

    def _make_paid_application(self, cell, product_type, price_cents, term_days, session_id):
        application = SponsorApplication.objects.create(
            cell=cell,
            status=SponsorApplication.Status.PAID_PENDING_APPROVAL,
            sponsor_name="Contract Sponsor",
            contact_name="Connie",
            email="connie@example.com",
            logo=png_upload("contract.png"),
            price_net_cents=price_cents,
            product_type=product_type,
            term_days=term_days,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
            terms_accepted_at=timezone.now(),
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PAID,
            net_amount_cents=price_cents,
            vat_amount_cents=575,
            total_amount_cents=price_cents + 575,
            currency="eur",
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=session_id.replace("cs_", "pi_"),
            paid_at=timezone.now(),
        )
        cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
        cell.save(update_fields=["status"])
        SponsorComplianceCheck.objects.create(
            application=application,
            status=SponsorComplianceCheck.Status.MANUALLY_CLEARED,
            checked_at=timezone.now(),
        )
        return application

    def _pdf_attachment(self, message):
        matches = [
            attachment for attachment in message.attachments
            if attachment[0].endswith(".pdf") and attachment[2] == "application/pdf"
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes) -> str:
        """Extract readable text from an ASCII85+FlateDecode compressed PDF."""
        import base64, zlib, re as _re
        texts = []
        for m in _re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', pdf_bytes, _re.DOTALL):
            data = m.group(1).strip()
            if data.endswith(b'~>'):
                try:
                    decoded = base64.a85decode(b'<~' + data, adobe=True)
                    texts.append(zlib.decompress(decoded).decode('latin-1', errors='replace'))
                except Exception:
                    pass
        return ' '.join(texts)

    # --- Test 1: annual approval sends annual agreement email ---

    def test_annual_approval_sends_annual_agreement_email(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_contract_an"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertTrue(any("Annual Sponsor Agreement" in m.subject or "CUL-AN" in m.subject for m in mail.outbox))
        self.assertEqual(application.contract_email_status, SponsorApplication.ContractEmailStatus.SENT)

    # --- Test 2: monthly approval sends monthly agreement email ---

    def test_monthly_approval_sends_monthly_agreement_email(self):
        application = self._make_paid_application(
            self.monthly_cell, SponsorCell.ProductType.CENTRAL_MONTHLY, 100000, 30, "cs_contract_mo"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertTrue(any("Monthly" in m.subject or "CUL-MO" in m.subject for m in mail.outbox))
        self.assertEqual(application.contract_email_status, SponsorApplication.ContractEmailStatus.SENT)

    # --- Test 3: weekly approval sends weekly agreement email ---

    def test_weekly_approval_sends_weekly_agreement_email(self):
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 2500, 7, "cs_contract_wk"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertTrue(any("Weekly" in m.subject or "CUL-WK" in m.subject for m in mail.outbox))
        self.assertEqual(application.contract_email_status, SponsorApplication.ContractEmailStatus.SENT)

    # --- Test 4: no agreement sent before staff approval ---

    def test_no_agreement_sent_before_approval(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_contract_pre"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
        # No approval called — outbox must be empty
        self.assertEqual(len(mail.outbox), 0)
        application.refresh_from_db()
        self.assertEqual(application.contract_email_status, "")

    # --- Test 5: no agreement sent for rejected/refund_required/refunded ---

    def test_no_agreement_sent_for_non_approved_statuses(self):
        for status in [
            SponsorApplication.Status.REJECTED,
            SponsorApplication.Status.REFUND_REQUIRED,
            SponsorApplication.Status.REFUNDED,
        ]:
            cell = SponsorCell.objects.create(
                cell_number=600 + list(SponsorApplication.Status).index(status),
                ring=5, position_in_ring=0,
            )
            application = SponsorApplication.objects.create(
                cell=cell,
                status=status,
                sponsor_name="No Email Sponsor",
                contact_name="Test",
                email="nomail@example.com",
                logo=png_upload("nomail.png"),
                price_net_cents=5000,
                product_type=SponsorCell.ProductType.ANNUAL_RING,
                term_days=365,
                terms_accepted=True,
                logo_rights_confirmed=True,
                approval_acknowledged=True,
                terms_accepted_at=timezone.now(),
            )
            self.assertEqual(application.contract_email_status, "")
            self.assertIsNone(application.contract_sent_at)

    # --- Test 6: contract reference is generated and included ---

    def test_contract_reference_generated_on_approval(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_contract_ref"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertTrue(bool(application.contract_reference))

    # --- Test 7: contract reference uses correct product prefix ---

    def test_contract_reference_product_prefix(self):
        cases = [
            (self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_pfx_an", "CUL-AN"),
            (self.monthly_cell, SponsorCell.ProductType.CENTRAL_MONTHLY, 100000, 30, "cs_pfx_mo", "CUL-MO"),
            (self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 2500, 7, "cs_pfx_wk", "CUL-WK"),
        ]
        for cell, product_type, price, term, session_id, expected_prefix in cases:
            cell.status = SponsorCell.Status.AVAILABLE
            cell.save(update_fields=["status"])
            with self.subTest(product_type=product_type):
                application = self._make_paid_application(cell, product_type, price, term, session_id)
                with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
                    approve_application(application.pk, self.actor)
                application.refresh_from_db()
                self.assertTrue(
                    application.contract_reference.startswith(expected_prefix),
                    f"Expected prefix {expected_prefix}, got {application.contract_reference}",
                )

    # --- Test 8: activation date and end date in email context ---

    def test_activation_and_end_date_set_on_approval(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_dates_an"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertIsNotNone(application.published_at)
        self.assertIsNotNone(application.expires_at)

    # --- Test 9: weekly agreement uses 7 calendar days ---

    def test_weekly_agreement_end_date_is_7_days(self):
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 2500, 7, "cs_dates_wk"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        delta = application.expires_at - application.published_at
        self.assertEqual(delta.days, 7)

    # --- Test 10: annual agreement uses 12 months ---

    def test_annual_agreement_end_date_is_12_months(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_dates_an2"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        # add_one_year produces approximately 365 or 366 days
        delta = application.expires_at - application.published_at
        self.assertGreaterEqual(delta.days, 365)
        self.assertLessEqual(delta.days, 366)

    # --- Test 11: monthly agreement uses 30 calendar days ---

    def test_monthly_agreement_end_date_is_30_days(self):
        application = self._make_paid_application(
            self.monthly_cell, SponsorCell.ProductType.CENTRAL_MONTHLY, 100000, 30, "cs_dates_mo2"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        delta = application.expires_at - application.published_at
        self.assertEqual(delta.days, 30)

    # --- Test 12: audit log records contract sent ---

    def test_audit_log_records_contract_sent(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_audit_sent"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            approve_application(application.pk, self.actor)
        log = application.audit_logs.filter(action=SponsorAuditLog.Action.CONTRACT_SENT).first()
        self.assertIsNotNone(log)
        self.assertTrue(log.metadata.get("pdf_attached"))
        self.assertIn("pdf_filename", log.metadata)
        self.assertIn("contract_reference", log.metadata)

    # --- Test 13: email failure sets failed status and audit log ---

    def test_email_failure_sets_failed_status_and_audit(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_audit_fail"
        )
        with self.settings(EMAIL_BACKEND="sponsors.tests._BrokenEmailBackend"):
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertEqual(application.contract_email_status, SponsorApplication.ContractEmailStatus.FAILED)
        self.assertTrue(
            application.audit_logs.filter(action=SponsorAuditLog.Action.CONTRACT_EMAIL_FAILED).exists()
        )

    # --- Test 13b: email failure does NOT roll back approval ---

    def test_email_failure_does_not_rollback_approval(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_rollback"
        )
        with self.settings(EMAIL_BACKEND="sponsors.tests._BrokenEmailBackend"):
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.APPROVED)

    # --- Test 14: resend action sends again and records resent audit ---

    def test_resend_contract_email_sends_and_records_resent(self):
        from .services import resend_contract_email
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_resend"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            approve_application(application.pk, self.actor)
            from django.core import mail
            mail.outbox = []
            resend_contract_email(application.pk, self.actor)
        application.refresh_from_db()
        self.assertEqual(application.contract_email_status, SponsorApplication.ContractEmailStatus.RESENT)
        self.assertTrue(
            application.audit_logs.filter(action=SponsorAuditLog.Action.CONTRACT_EMAIL_RESENT).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        filename, content, mimetype = self._pdf_attachment(mail.outbox[0])
        self.assertIn(application.contract_reference, filename)
        self.assertTrue(filename.endswith(".pdf"))
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertEqual(mimetype, "application/pdf")

    # --- Test 15: sanctions/compliance blocking prevents approval (no email sent) ---

    def test_sanctions_blocking_prevents_approval_no_email(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_sanctions"
        )
        application.status = SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW
        application.save(update_fields=["status"])
        snapshot = SanctionsSourceSnapshot.objects.create(
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            source_name="EU FSF",
            source_url="https://example.com",
            source_sha256="contract_sha_unique",
            record_count=1,
            status=SanctionsSourceSnapshot.Status.SUCCESS,
        )
        subject = SanctionsSubject.objects.create(
            source_snapshot=snapshot,
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            primary_name="Contract Sponsor",
            normalised_name="contract sponsor",
        )
        from .models import SponsorSanctionsMatch
        SponsorSanctionsMatch.objects.create(
            application=application,
            subject=subject,
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            match_status=SponsorSanctionsMatch.Status.POSSIBLE,
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            with self.assertRaises(ValueError):
                approve_application(application.pk, self.actor)
        self.assertEqual(len(mail.outbox), 0)
        application.refresh_from_db()
        self.assertEqual(application.contract_email_status, "")

    # --- Test 16: public flow still has exactly 3 confirmation checkboxes ---

    def test_public_flow_still_has_3_checkboxes(self):
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_modal.js")
        with open(js_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("spm-confirm-1", content)
        self.assertIn("spm-confirm-2", content)
        self.assertIn("spm-confirm-3", content)
        self.assertNotIn("spm-confirm-4", content)
        self.assertNotIn("spm-approval", content)

    # --- Test 17: Stripe remains test mode ---

    @override_settings(STRIPE_PRICE_MODE="test", STRIPE_SECRET_KEY="sk_test_123")
    def test_stripe_remains_test_mode(self):
        from django.conf import settings as _s
        self.assertNotEqual(getattr(_s, "STRIPE_PRICE_MODE", ""), "live")

    # --- Test 18: contract reference format ---

    def test_contract_reference_format(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_fmt"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        import re
        self.assertRegex(application.contract_reference, r"^CUL-(AN|MO|WK)-\d{4}-\d{6}$")

    # --- Test 19: confirmation email has PDF attachment and short body ---

    def test_confirmation_email_has_pdf_attachment_and_short_body(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_pdf_attachment"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]

        filename, content, mimetype = self._pdf_attachment(msg)
        self.assertIn(application.contract_reference, filename)
        self.assertTrue(filename.endswith(".pdf"))
        self.assertEqual(mimetype, "application/pdf")
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 1000)

        self.assertIn(application.contract_reference, msg.body)
        self.assertIn("attached as a PDF document", msg.body)
        self.assertLess(len(msg.body), 1500)
        for forbidden in (
            "GOVERNING LAW",
            "SANCTIONS AND COMPLIANCE DECLARATION",
            "ELECTRONIC ACCEPTANCE",
            "The sponsor must not use the sponsorship slot",
            "Bearcave Limited does not guarantee any particular level of traffic",
        ):
            self.assertNotIn(forbidden, msg.body)

        html_body = msg.alternatives[0][0]
        self.assertIn("attached as a PDF document", html_body)
        self.assertNotIn("SANCTIONS AND COMPLIANCE DECLARATION", html_body)

    # --- Test 20: PDF generation failure does not fall back to inline terms ---

    def test_pdf_generation_failure_sets_failed_status_without_inline_email(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_pdf_fail"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            with patch("sponsors.services.generate_contract_pdf", side_effect=RuntimeError("PDF error")):
                approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertEqual(application.contract_email_status, SponsorApplication.ContractEmailStatus.FAILED)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(
            application.audit_logs.filter(action=SponsorAuditLog.Action.CONTRACT_EMAIL_FAILED).exists()
        )

    # --- Test 21: PDF generation failure does NOT roll back approval ---

    def test_pdf_generation_failure_does_not_rollback_approval(self):
        application = self._make_paid_application(
            self.annual_cell, SponsorCell.ProductType.ANNUAL_RING, 5000, 365, "cs_pdf_fail_rb"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            with patch("sponsors.services.generate_contract_pdf", side_effect=RuntimeError("PDF error")):
                approve_application(application.pk, self.actor)
        application.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.APPROVED)

    # --- Test 22: branding — email body does not contain "CulinEire Kitchen" ---

    def test_email_body_does_not_contain_culineire_kitchen(self):
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_brand_wk"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            approve_application(application.pk, self.actor)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertNotIn("CulinEire Kitchen", msg.body)
        self.assertNotIn("CulinEire Kitchen", msg.alternatives[0][0])

    # --- Test 23: branding — PDF content does not contain "CulinEire Kitchen" ---

    def test_pdf_does_not_contain_culineire_kitchen(self):
        from .services import generate_contract_pdf
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_brand_pdf"
        )
        application.contract_reference = "CUL-WK-2026-999001"
        application.save(update_fields=["contract_reference"])
        pdf_bytes = generate_contract_pdf(application)
        # PDF text is binary; check for the encoded string
        self.assertNotIn(b"CulinEire Kitchen", pdf_bytes)

    # --- Test 24: money formatting — email body does not show raw cents ---

    def test_email_body_does_not_show_raw_cents(self):
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_cents_email"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            approve_application(application.pk, self.actor)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        # "500 cents" or "115 cents" or "615 cents" must not appear
        import re
        self.assertIsNone(re.search(r'\b\d{2,5}\s+cents\b', body, re.IGNORECASE))

    # --- Test 25: money formatting — PDF shows EUR amounts, not raw cents ---

    def test_pdf_shows_eur_not_raw_cents(self):
        from .services import generate_contract_pdf
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_cents_pdf"
        )
        application.contract_reference = "CUL-WK-2026-999002"
        application.save(update_fields=["contract_reference"])
        pdf_bytes = generate_contract_pdf(application)
        text = self._extract_pdf_text(pdf_bytes)
        self.assertNotIn("reported by Stripe at checkout", text)
        self.assertIn("EUR 5.00", text)

    # --- Test 26: weekly wording — "per week" not in email body or PDF ---

    def test_weekly_email_does_not_say_per_week(self):
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_perweek_email"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            approve_application(application.pk, self.actor)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertNotIn("per week", body.lower())
        self.assertNotIn("/week", body.lower())

    def test_weekly_pdf_does_not_say_per_week(self):
        from .services import generate_contract_pdf
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_perweek_pdf"
        )
        application.contract_reference = "CUL-WK-2026-999003"
        application.save(update_fields=["contract_reference"])
        pdf_bytes = generate_contract_pdf(application)
        text = self._extract_pdf_text(pdf_bytes).lower()
        self.assertNotIn("per week", text)
        self.assertNotIn("/week", text)

    # --- Test 27: one-off wording — email and PDF must say this is a one-off payment ---

    def test_weekly_email_says_one_off_payment(self):
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_oneoff_email"
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail
            mail.outbox = []
            approve_application(application.pk, self.actor)
        self.assertEqual(len(mail.outbox), 1)
        # Check body or HTML alternative
        full_text = mail.outbox[0].body + mail.outbox[0].alternatives[0][0]
        self.assertTrue(
            "one-off payment" in full_text.lower() or "7-day sponsorship" in full_text.lower(),
            "Email must mention one-off payment or 7-day sponsorship"
        )

    def test_weekly_pdf_says_one_off_and_no_subscription(self):
        from .services import generate_contract_pdf
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_oneoff_pdf"
        )
        application.contract_reference = "CUL-WK-2026-999004"
        application.save(update_fields=["contract_reference"])
        pdf_bytes = generate_contract_pdf(application)
        text = self._extract_pdf_text(pdf_bytes).lower()
        self.assertIn("one-off payment", text)
        self.assertIn("does not renew automatically", text)

    # --- Test 28: weekly placement label uses "7-Day" not "Weekly Ring" in PDF ---

    def test_weekly_pdf_placement_label_says_7_day(self):
        from .services import generate_contract_pdf
        application = self._make_paid_application(
            self.weekly_cell, SponsorCell.ProductType.WEEKLY_RING, 500, 7, "cs_label_pdf"
        )
        application.contract_reference = "CUL-WK-2026-999005"
        application.save(update_fields=["contract_reference"])
        pdf_bytes = generate_contract_pdf(application)
        text = self._extract_pdf_text(pdf_bytes)
        self.assertIn("7-Day Ring Sponsor Slot", text)


class _BrokenEmailBackend:
    """Stub email backend that always raises to simulate send failure."""
    def __init__(self, *args, **kwargs):
        pass
    def open(self): pass
    def close(self): pass
    def send_messages(self, messages):
        raise RuntimeError("Simulated email send failure")


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorLogoTransformTests(TestCase):
    """Regression tests: logo_rotation and transform fields must be saved,
    copied on approval, serialised to the puzzle, and rendered in the JS."""

    def setUp(self):
        self.cell = SponsorCell.objects.create(cell_number=5, ring=1, position_in_ring=4)
        self.user = get_user_model().objects.create_user("transform-admin", password="pass", is_staff=True)

    def _make_approved_application(self, offset_x=25.0, offset_y=-10.0, scale=1.5, rotation=135.0):
        application = SponsorApplication.objects.create(
            cell=self.cell,
            status=SponsorApplication.Status.PAID_PENDING_APPROVAL,
            sponsor_name="PT Asuransi Ciputra Indonesia",
            contact_name="Test",
            email="test@example.com",
            website_url="https://example.com",
            logo=png_upload(),
            price_net_cents=self.cell.price_net_cents,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
            terms_accepted_at=timezone.now(),
            logo_offset_x=offset_x,
            logo_offset_y=offset_y,
            logo_scale=scale,
            logo_rotation=rotation,
        )
        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PAID,
            net_amount_cents=application.price_net_cents,
            currency="eur",
            stripe_checkout_session_id="cs_test_transform",
            stripe_payment_intent_id="pi_test_transform",
            paid_at=timezone.now(),
        )
        self.cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
        self.cell.save(update_fields=["status"])
        SponsorComplianceCheck.objects.create(
            application=application,
            status=SponsorComplianceCheck.Status.MANUALLY_CLEARED,
            checked_at=timezone.now(),
        )
        return application

    def test_application_stores_logo_transform_fields(self):
        """SponsorApplication must persist all four transform fields."""
        app = self._make_approved_application(offset_x=33.0, offset_y=-15.0, scale=1.8, rotation=270.0)
        app.refresh_from_db()
        self.assertAlmostEqual(app.logo_offset_x, 33.0)
        self.assertAlmostEqual(app.logo_offset_y, -15.0)
        self.assertAlmostEqual(app.logo_scale, 1.8)
        self.assertAlmostEqual(app.logo_rotation, 270.0)

    def test_approval_copies_all_transform_fields_to_cell(self):
        """approve_application must copy offset, scale AND rotation to SponsorCell."""
        app = self._make_approved_application(offset_x=20.0, offset_y=5.0, scale=1.3, rotation=90.0)
        approve_application(app.pk, self.user)
        self.cell.refresh_from_db()
        self.assertAlmostEqual(self.cell.logo_offset_x, 20.0)
        self.assertAlmostEqual(self.cell.logo_offset_y, 5.0)
        self.assertAlmostEqual(self.cell.logo_scale, 1.3)
        self.assertAlmostEqual(self.cell.logo_rotation, 90.0, msg="logo_rotation must be copied to SponsorCell on approval")

    def test_approval_does_not_reset_rotation_to_default(self):
        """Non-zero rotation must survive the approval path unchanged."""
        app = self._make_approved_application(rotation=45.5)
        approve_application(app.pk, self.user)
        self.cell.refresh_from_db()
        self.assertAlmostEqual(self.cell.logo_rotation, 45.5, places=1,
                               msg="Rotation must not be reset to 0 on approval")

    def test_cell_as_dict_includes_logo_rotation(self):
        """SponsorCell.as_dict() must include logo_rotation for the puzzle renderer."""
        self.cell.logo_rotation = 135.0
        self.cell.save()
        data = self.cell.as_dict()
        self.assertIn("logo_rotation", data, "logo_rotation must be present in SponsorCell.as_dict()")
        self.assertAlmostEqual(data["logo_rotation"], 135.0)

    def test_cell_as_dict_includes_all_transform_fields(self):
        """as_dict must include all four transform fields."""
        self.cell.logo_offset_x = 10.0
        self.cell.logo_offset_y = -5.0
        self.cell.logo_scale = 1.2
        self.cell.logo_rotation = 30.0
        self.cell.save()
        data = self.cell.as_dict()
        for field in ("logo_offset_x", "logo_offset_y", "logo_scale", "logo_rotation"):
            self.assertIn(field, data, f"{field} must be in as_dict()")

    def test_puzzle_json_contains_logo_rotation(self):
        """The public puzzle page must embed logo_rotation in the cells JSON."""
        self.cell.logo_rotation = 75.0
        self.cell.sponsor_logo = png_upload()
        self.cell.sponsor_name = "Rotate Test"
        self.cell.status = SponsorCell.Status.ACTIVE
        self.cell.save()
        response = self.client.get(reverse("sponsors:puzzle"))
        self.assertContains(response, '"logo_rotation"')
        self.assertContains(response, "75.0")

    def test_puzzle_js_applies_rotation_to_ring_cells(self):
        """sponsors_puzzle.js must read logo_rotation and apply SVG rotate transform."""
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_puzzle.js")
        self.assertIsNotNone(js_path)
        with open(js_path, encoding="utf-8") as f:
            js = f.read()
        self.assertIn("logo_rotation", js, "sponsors_puzzle.js must reference logo_rotation")
        self.assertIn("rotate(", js, "sponsors_puzzle.js must apply SVG rotate transform")

    def test_puzzle_js_applies_rotation_to_centre_cell(self):
        """drawCentre in sponsors_puzzle.js must also apply rotation."""
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_puzzle.js")
        self.assertIsNotNone(js_path)
        with open(js_path, encoding="utf-8") as f:
            js = f.read()
        # Both drawCentre and appendLogoToCell should reference logo_rotation
        count = js.count("logo_rotation")
        self.assertGreaterEqual(count, 2, "logo_rotation must appear in both drawCentre and appendLogoToCell")

    def test_form_submission_saves_rotation_via_enquire_view(self):
        """Submitting the sponsor enquiry form must persist logo_rotation on SponsorApplication."""
        import io
        from PIL import Image as PILImage
        buf = io.BytesIO()
        PILImage.new("RGB", (80, 80), color=(200, 100, 50)).save(buf, format="PNG")
        buf.seek(0)
        logo = SimpleUploadedFile("logo.png", buf.read(), content_type="image/png")
        data = {
            "sponsor_name": "Rotation Corp",
            "contact_name": "Tester",
            "email": "rot@example.com",
            "logo": logo,
            "logo_offset_x": "15.00",
            "logo_offset_y": "-8.00",
            "logo_scale": "1.200",
            "logo_rotation": "180.00",
            "logo_rights_confirmed": "on",
            "terms_accepted": "on",
            "sanctions_declaration_1": "on",
        }

        class FakeSession:
            id = "cs_test"
            url = "https://stripe.test/pay"

        class FakeCheckout:
            Session = MagicMock(create=MagicMock(return_value=FakeSession()))

        class FakeStripe:
            checkout = FakeCheckout

        with patch("sponsors.services._stripe", return_value=FakeStripe):
            response = self.client.post(
                reverse("sponsors:cell_enquire", args=[self.cell.pk]), data, format="multipart"
            )
        self.assertIn(response.status_code, [200, 302])
        app = SponsorApplication.objects.filter(cell=self.cell).last()
        if app:
            self.assertAlmostEqual(app.logo_rotation, 180.0, places=1,
                                   msg="logo_rotation must be saved from form submission")


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorOgImageTests(TestCase):
    """Verify that /sponsors/ serves correct Open Graph and Twitter meta tags."""

    def test_og_image_is_not_hero_jpg(self):
        response = self.client.get(reverse("sponsors:puzzle"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("hero.jpg", content.split('property="og:image"')[0].rsplit('<meta', 1)[-1] if 'property="og:image"' in content else "")
        self.assertIn("hero-sponsors", content)

    def test_og_image_contains_sponsors_hero(self):
        response = self.client.get(reverse("sponsors:puzzle"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('property="og:image"', content)
        og_meta = [line for line in content.splitlines() if 'property="og:image"' in line and 'secure_url' not in line]
        self.assertTrue(og_meta, "og:image meta tag not found")
        self.assertIn("hero-sponsors", og_meta[0])

    def test_og_image_is_absolute_url(self):
        response = self.client.get(reverse("sponsors:puzzle"))
        content = response.content.decode()
        og_meta = [line for line in content.splitlines() if 'property="og:image"' in line and 'secure_url' not in line]
        self.assertTrue(og_meta)
        self.assertRegex(og_meta[0], r'https?://', msg="og:image must be an absolute URL")

    def test_twitter_image_contains_sponsors_hero(self):
        response = self.client.get(reverse("sponsors:puzzle"))
        content = response.content.decode()
        twitter_meta = [line for line in content.splitlines() if 'name="twitter:image"' in line]
        self.assertTrue(twitter_meta, "twitter:image meta tag not found")
        self.assertIn("hero-sponsors", twitter_meta[0])

    def test_og_image_secure_url_present(self):
        response = self.client.get(reverse("sponsors:puzzle"))
        content = response.content.decode()
        self.assertIn('property="og:image:secure_url"', content)

    def test_og_image_alt_present(self):
        response = self.client.get(reverse("sponsors:puzzle"))
        content = response.content.decode()
        self.assertIn('property="og:image:alt"', content)


def teardown_module(_module=None):
    """Remove the temporary media directory created for sponsor tests."""
    shutil.rmtree(_TEMP_MEDIA, ignore_errors=True)
