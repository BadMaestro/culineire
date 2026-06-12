from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from recipes.models import RecipeAuthor


class ContactPageLayoutTests(TestCase):
    def setUp(self):
        self.url = reverse("messaging:contact")
        self.user_model = get_user_model()

    def _create_owner(self):
        owner = self.user_model.objects.create_user(username="greenbear", password="pass")
        RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={
                "user": owner,
                "name": "GreenBear",
            },
        )
        return owner

    def test_anonymous_contact_page_uses_contact_layout(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="hero hero--home hero--contact"')
        self.assertContains(response, 'class="contact-shell"')
        self.assertContains(response, 'class="contact-layout"')
        self.assertContains(response, 'class="contact-info-panel"')
        self.assertContains(response, 'class="contact-panel"')
        self.assertContains(response, reverse("login"))
        self.assertContains(response, reverse("signup"))
        self.assertContains(response, reverse("legal:legal_hub"))
        self.assertContains(response, reverse("legal:report_content"))

    def test_authenticated_contact_page_shows_message_form_when_owner_available(self):
        self._create_owner()
        user = self.user_model.objects.create_user(username="author", password="pass")
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="auth-form contact-form"')
        self.assertContains(response, 'id="id_subject"')
        self.assertContains(response, 'id="id_body"')
        self.assertContains(response, "Send Message")

    def test_owner_contact_page_links_to_inbox(self):
        owner = self._create_owner()
        self.client.force_login(owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You cannot send a message to yourself")
        self.assertContains(response, reverse("messaging:inbox"))
