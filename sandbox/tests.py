from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from recipes.models import RecipeAuthor


@override_settings(OWNER_SLUG="owner-bear")
class SandboxAccessTests(TestCase):
    def test_greenbear_owner_can_open_sandbox_without_django_superuser_flag(self):
        user = get_user_model().objects.create_user(username="owner-bear-user", password="pass")
        RecipeAuthor.objects.create(user=user, name="Owner Bear", slug="owner-bear")
        self.client.force_login(user)

        response = self.client.get(reverse("sandbox:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sandbox")

    def test_regular_user_gets_404(self):
        user = get_user_model().objects.create_user(username="regular", password="pass")
        RecipeAuthor.objects.create(user=user, name="Regular Author", slug="regular")
        self.client.force_login(user)

        response = self.client.get(reverse("sandbox:index"))

        self.assertEqual(response.status_code, 404)

    def test_django_superuser_can_open_sandbox(self):
        user = get_user_model().objects.create_superuser(
            username="superuser",
            password="pass",
            email="super@example.com",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("sandbox:index"))

        self.assertEqual(response.status_code, 200)
