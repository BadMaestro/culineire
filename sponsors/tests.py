from __future__ import annotations

import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor

from .models import (
    ProcessedStripeEvent,
    SponsorApplication,
    SponsorCell,
    SponsorPayment,
    SponsorRoadmapItem,
)
from .services import (
    CheckoutSessionInfo,
    approve_application,
    create_checkout_session,
    expire_application,
    handle_stripe_event,
    mark_refund_completed,
    reject_application,
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
            "approval_acknowledged": "on",
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
        return application

    def test_public_sponsor_page_displays_net_plus_vat_pricing(self):
        response = self.client.get(reverse("sponsors:puzzle"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "€25")
        self.assertContains(response, "/year + VAT")
        self.assertContains(response, "Prices are shown excluding VAT")
        self.assertContains(response, "Businesses, sole traders and individuals")
        self.assertContains(response, "Sponsor of the Month")
        self.assertContains(response, "€1000")
        self.assertContains(response, "/ month + VAT")
        self.assertContains(response, "Ring sponsorship is annual. Central sponsor is monthly. VAT calculated at checkout.")
        self.assertNotContains(response, "Net annual price")

    def test_application_requires_terms_logo_rights_and_approval_acknowledgement(self):
        data = self.valid_post_data()
        data.pop("terms_accepted")

        response = self.client.post(reverse("sponsors:cell_enquire", args=[self.cell.pk]), data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Terms accepted", response.json()["error"])
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

    def test_successful_webhook_sets_paid_pending_approval_without_publishing_logo(self):
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
        self.assertEqual(application.status, SponsorApplication.Status.PAID_PENDING_APPROVAL)
        self.assertEqual(self.cell.status, SponsorCell.Status.PAID_PENDING_APPROVAL)
        self.assertEqual(payment.status, SponsorPayment.Status.PAID)
        self.assertEqual(payment.vat_amount_cents, 575)
        self.assertFalse(bool(self.cell.sponsor_logo))

        duplicate = handle_stripe_event(event)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(ProcessedStripeEvent.objects.count(), 1)

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
        self.assertContains(response, "Paid pending approval")

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
        self.assertNotContains(response, "Ring 0")
        self.assertNotContains(response, "cell #0")

    def test_rejection_marks_paid_application_refund_required_without_publication(self):
        user = get_user_model().objects.create_user("admin", password="pass", is_staff=True)
        application = self.create_pending_application(paid=True)

        reject_application(application.pk, user, "Not suitable")

        application.refresh_from_db()
        self.cell.refresh_from_db()
        self.assertEqual(application.status, SponsorApplication.Status.REFUND_REQUIRED)
        self.assertEqual(self.cell.status, SponsorCell.Status.REJECTED)
        self.assertFalse(bool(self.cell.sponsor_logo))

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
        return application

    @patch("newsfeed.telegram.send_telegram_message")
    def test_approve_sends_telegram_announcement(self, mock_send):
        mock_send.return_value = __import__("newsfeed.telegram", fromlist=["TelegramResult"]).TelegramResult(
            ok=True, status="sent", response='{"ok": true}'
        )
        application = self._make_paid_application()

        approve_application(application.pk, self.actor)

        self.assertEqual(mock_send.call_count, 1)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("New sponsor on CulinEire:", sent_text)
        self.assertIn("Bearcave Bakery", sent_text)
        self.assertIn("culineire.ie/sponsors/", sent_text)

    @patch("newsfeed.telegram.send_telegram_message")
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

    @patch("newsfeed.telegram.send_telegram_message")
    def test_approve_copies_logo_rotation_to_cell(self, mock_send):
        from newsfeed.telegram import TelegramResult
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        application = self._make_paid_application()
        application.logo_rotation = 90.0
        application.save(update_fields=["logo_rotation"])

        approve_application(application.pk, self.actor)

        self.cell.refresh_from_db()
        self.assertAlmostEqual(self.cell.logo_rotation, 90.0)


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
        # Partial refund — application must stay refund_required, cell must stay rejected.
        self.assertEqual(application.status, SponsorApplication.Status.REFUND_REQUIRED)
        self.assertEqual(payment.status, SponsorPayment.Status.PARTIALLY_REFUNDED)
        self.assertEqual(self.cell.status, SponsorCell.Status.REJECTED)


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
        self.assertEqual(application.status, SponsorApplication.Status.PAID_PENDING_APPROVAL)
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

    def test_sponsor_puzzle_page_contains_logo_rights_checkbox_js(self):
        """The sponsors_modal.js must contain the logo rights confirmation wording."""
        from django.contrib.staticfiles import finders
        js_path = finders.find("js/sponsors_modal.js")
        self.assertIsNotNone(js_path, "sponsors_modal.js not found in static files")
        with open(js_path, encoding="utf-8") as f:
            js_content = f.read()
        self.assertIn("logo_rights_confirmed", js_content,
                      "logo_rights_confirmed must be submitted by the sponsor form JS")
        self.assertIn("spm-logo-rights", js_content,
                      "spm-logo-rights checkbox must be rendered in the sponsor modal JS")
        self.assertIn("Bearcave Limited may display it on CulinEire", js_content,
                      "Logo rights wording must mention Bearcave Limited displaying on CulinEire")

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
            "approval_acknowledged": "on",
            # logo_rights_confirmed deliberately omitted
        }
        response = self.client.post(
            reverse("sponsors:cell_enquire", args=[self.cell.pk]), data
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Image rights confirmed", response.json()["error"])

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_enquire_with_logo_rights_proceeds_past_validation(self):
        """Submitting with logo_rights_confirmed=on passes the rights check."""
        from unittest.mock import patch
        from .services import CheckoutSessionInfo
        data = {
            "sponsor_name": "Test Sponsor",
            "contact_name": "Test Contact",
            "email": "test@example.com",
            "logo_rights_confirmed": "on",
            "terms_accepted": "on",
            "approval_acknowledged": "on",
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


def teardown_module(_module=None):
    """Remove the temporary media directory created for sponsor tests."""
    shutil.rmtree(_TEMP_MEDIA, ignore_errors=True)
