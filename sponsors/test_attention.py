from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from recipes.models import RecipeAuthor

from .attention import get_sponsor_moderation_attention_count
from .models import SponsorApplication, SponsorCell, SponsorPayment
from .tests import SPONSOR_TEST_SETTINGS, png_upload


@override_settings(**SPONSOR_TEST_SETTINGS)
class SponsorModerationAttentionTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("sponsor-staff", password="pass", is_staff=True)
        self.reader = get_user_model().objects.create_user("reader", password="pass")
        RecipeAuthor.objects.update_or_create(
            slug="sponsor-staff",
            defaults={"user": self.staff, "name": "Sponsor Staff", "has_bearseeker_privileges": True},
        )

    def make_application(self, status, *, paid=False, cell_number=None):
        cell = SponsorCell.objects.create(
            cell_number=cell_number or (SponsorCell.objects.count() + 100),
            ring=6,
            position_in_ring=0,
        )
        application = SponsorApplication.objects.create(
            cell=cell,
            status=status,
            sponsor_name=f"Sponsor {status}",
            contact_name="Contact",
            email=f"{status}@example.com",
            logo=png_upload(f"{status}.png"),
            price_net_cents=cell.price_net_cents,
            terms_accepted=True,
            logo_rights_confirmed=True,
            approval_acknowledged=True,
        )
        if paid:
            SponsorPayment.objects.create(
                application=application,
                status=SponsorPayment.Status.PAID,
                net_amount_cents=application.price_net_cents,
            )
        return application

    def test_attention_count_includes_staff_action_statuses(self):
        for status in (
            SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
            SponsorApplication.Status.PAID_PENDING_APPROVAL,
            SponsorApplication.Status.CHANGES_REQUESTED,
            SponsorApplication.Status.REFUND_REQUIRED,
        ):
            self.make_application(status, paid=True)

        self.assertEqual(get_sponsor_moderation_attention_count(), 4)

    def test_attention_count_excludes_non_action_and_terminal_statuses(self):
        for status in (
            SponsorApplication.Status.PAYMENT_PENDING,
            SponsorApplication.Status.APPROVED,
            SponsorApplication.Status.CANCELLED,
            SponsorApplication.Status.REJECTED,
            SponsorApplication.Status.REFUNDED,
            SponsorApplication.Status.EXPIRED,
        ):
            self.make_application(status)

        self.assertEqual(get_sponsor_moderation_attention_count(), 0)

    def test_staff_header_dropdown_shows_sponsor_badge(self):
        self.make_application(SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW, paid=True)
        self.client.force_login(self.staff)

        response = self.client.get(reverse("sponsors:puzzle"))

        self.assertContains(response, "Sponsor Applications")
        self.assertContains(response, 'class="msg-badge">1</span>', html=False)

    def test_non_staff_header_does_not_show_sponsor_moderation_badge(self):
        self.make_application(SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW, paid=True)
        self.client.force_login(self.reader)

        response = self.client.get(reverse("sponsors:puzzle"))

        self.assertNotContains(response, "Sponsor Applications")

    def test_moderation_panel_and_sponsor_list_show_attention_count(self):
        self.make_application(SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW, paid=True)
        self.make_application(SponsorApplication.Status.REFUND_REQUIRED, paid=True)
        self.client.force_login(self.staff)

        panel = self.client.get(reverse("recipes:moderation_panel"))
        sponsor_list = self.client.get(reverse("sponsors:moderation_applications"), {"status": "all"})

        self.assertContains(panel, "Sponsor Applications")
        self.assertContains(panel, "2 requiring attention")
        self.assertContains(panel, "1 pending compliance review")
        self.assertContains(panel, "1 refund required")
        self.assertContains(sponsor_list, "Sponsor work requiring attention: 2")

    def test_sponsor_list_product_labels_still_render(self):
        central_cell = SponsorCell.objects.create(
            cell_number=0,
            ring=0,
            position_in_ring=0,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
        )
        SponsorApplication.objects.create(
            cell=central_cell,
            status=SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
            sponsor_name="Central Sponsor",
            contact_name="Contact",
            email="central@example.com",
            logo=png_upload("central.png"),
            price_net_cents=central_cell.price_net_cents,
            product_type=SponsorCell.ProductType.CENTRAL_MONTHLY,
        )
        self.make_application(SponsorApplication.Status.PAID_PENDING_APPROVAL, paid=True, cell_number=201)
        self.client.force_login(self.staff)

        response = self.client.get(reverse("sponsors:moderation_applications"), {"status": "all"})

        self.assertContains(response, "Sponsor of the Month")
        self.assertContains(response, "Annual Ring Sponsorship")
