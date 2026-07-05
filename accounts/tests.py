from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from recipes.models import RecipeAuthor


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="forgetful", password="OldPass123!", email="forgetful@example.com"
        )

    def test_login_page_links_to_password_reset(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, reverse("password_reset"))
        self.assertContains(response, "Forgot password?")

    def test_reset_form_page_renders(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset Password")

    def test_reset_request_sends_branded_email_with_working_link(self):
        response = self.client.post(
            reverse("password_reset"), {"email": "forgetful@example.com"}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Reset your CulinEire password")
        self.assertIn("/accounts/reset/", message.body)
        # Extract the confirm link from the plain-text body and follow it
        reset_link = next(
            line for line in message.body.splitlines() if "/accounts/reset/" in line
        ).strip()
        path = "/" + reset_link.split("://", 1)[-1].split("/", 1)[1]
        response = self.client.get(path, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set New Password")

    def test_reset_request_for_unknown_email_does_not_reveal_account_absence(self):
        response = self.client.post(
            reverse("password_reset"), {"email": "nobody@example.com"}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_flow_sets_new_password(self):
        self.client.post(reverse("password_reset"), {"email": "forgetful@example.com"})
        reset_link = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if "/accounts/reset/" in line
        ).strip()
        path = "/" + reset_link.split("://", 1)[-1].split("/", 1)[1]
        # Django redirects to a session-backed URL before showing the form
        response = self.client.get(path)
        form_url = response.url
        response = self.client.post(
            form_url,
            {"new_password1": "BrandNewPass456!", "new_password2": "BrandNewPass456!"},
        )
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.assertTrue(
            self.client.login(username="forgetful", password="BrandNewPass456!")
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminSetPasswordTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin", password="AdminPass123!", email="admin@example.com"
        )
        self.member = user_model.objects.create_user(
            username="member", password="MemberPass123!", email="member@example.com"
        )
        self.author = RecipeAuthor.objects.create(
            name="Member Author", slug="member-author", user=self.member
        )
        self.url = reverse(
            "recipes:moderation_author_set_password", kwargs={"slug": self.author.slug}
        )

    def set_password(self, password1, password2=None):
        return self.client.post(
            self.url,
            {"new_password1": password1, "new_password2": password2 or password1},
        )

    def test_superuser_can_set_password_and_email_is_sent(self):
        self.client.force_login(self.admin)
        response = self.set_password("FreshSecret789!")
        self.assertRedirects(
            response,
            reverse(
                "recipes:moderation_author_edit", kwargs={"slug": self.author.slug}
            ),
        )
        self.assertTrue(
            self.client.login(username="member", password="FreshSecret789!")
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["member@example.com"])
        self.assertIn("FreshSecret789!", message.body)

    def test_regular_user_gets_404(self):
        self.client.force_login(self.member)
        response = self.set_password("FreshSecret789!")
        self.assertEqual(response.status_code, 404)

    def test_anonymous_cannot_set_password(self):
        response = self.set_password("FreshSecret789!")
        self.assertIn(response.status_code, (302, 404))
        self.assertFalse(
            self.client.login(username="member", password="FreshSecret789!")
        )

    def test_mismatched_passwords_rejected(self):
        self.client.force_login(self.admin)
        response = self.set_password("FreshSecret789!", "Different000!")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            self.client.login(username="member", password="FreshSecret789!")
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_weak_password_rejected(self):
        self.client.force_login(self.admin)
        response = self.set_password("123")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.client.login(username="member", password="123"))
        self.assertEqual(len(mail.outbox), 0)

    def test_superuser_may_target_other_superuser_but_not_owner(self):
        # Contract changed in ea6a599c: superusers may manage other superuser
        # accounts (regular moderators still cannot - covered by
        # test_regular_user_gets_404). The owner account stays untouchable.
        from django.conf import settings as django_settings

        other_admin = get_user_model().objects.create_superuser(
            username="admin2", password="AdminPass123!", email="admin2@example.com"
        )
        peer_author = RecipeAuthor.objects.create(
            name="Admin Author", slug="admin-author", user=other_admin
        )
        self.client.force_login(self.admin)
        url = reverse(
            "recipes:moderation_author_set_password",
            kwargs={"slug": peer_author.slug},
        )
        response = self.client.post(
            url, {"new_password1": "FreshSecret789!", "new_password2": "FreshSecret789!"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.client.login(username="admin2", password="FreshSecret789!")
        )

        # The owner (OWNER_SLUG) is always protected, even from superusers.
        owner_user = get_user_model().objects.create_superuser(
            username="owner-test", password="OwnerPass123!", email="owner@example.com"
        )
        # A data migration may already have created the owner author row.
        owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"name": "Owner", "user": owner_user},
        )
        self.client.force_login(self.admin)
        url = reverse(
            "recipes:moderation_author_set_password",
            kwargs={"slug": owner_author.slug},
        )
        response = self.client.post(
            url, {"new_password1": "FreshSecret789!", "new_password2": "FreshSecret789!"}
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_section_visible_on_moderation_edit_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("recipes:moderation_author_edit", kwargs={"slug": self.author.slug})
        )
        self.assertContains(response, "Admin: Set New Password")
        self.assertContains(response, self.url)
