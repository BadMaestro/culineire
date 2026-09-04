from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(LEDO_ENABLED=True)
class LedoHomeTests(TestCase):
    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse("ledo:home"))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("ledo:home")}',
        )

    def test_regular_user_cannot_open_preview(self):
        user = get_user_model().objects.create_user(
            username="ledo-author",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("ledo:home"))

        self.assertEqual(response.status_code, 302)

    def test_staff_user_can_open_preview(self):
        user = get_user_model().objects.create_user(
            username="ledo-staff",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("ledo:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LEDO")

    @override_settings(LEDO_ENABLED=False)
    def test_disabled_preview_returns_not_found(self):
        user = get_user_model().objects.create_user(
            username="ledo-disabled",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("ledo:home"))

        self.assertEqual(response.status_code, 404)
