from __future__ import annotations

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
    handle_stripe_event,
    mark_refund_completed,
    reject_application,
)


def png_upload(name="logo.png"):
    image = Image.new("RGB", (16, 16), color=(22, 100, 61))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


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
        self.assertEqual(kwargs["billing_address_collection"], "required")
        self.assertEqual(kwargs["tax_id_collection"], {"enabled": True})
        self.assertEqual(kwargs["customer_creation"], "always")
        self.assertEqual(kwargs["metadata"]["sponsor_application_id"], str(application.pk))
        price_data = kwargs["line_items"][0]["price_data"]
        self.assertEqual(price_data["currency"], "eur")
        self.assertEqual(price_data["unit_amount"], application.price_net_cents)
        self.assertEqual(price_data["tax_behavior"], "exclusive")

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
