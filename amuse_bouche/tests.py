from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from collection.models import ContentReaction, SavedContent
from recipes.models import RecipeAuthor
from .models import AmuseBouche


class AmuseBouchePublicTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="reader", password="pass")
        self.author = RecipeAuthor.objects.create(name="Test Author", slug="test-author")

    def create_item(self, title, status):
        return AmuseBouche.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    def test_feed_is_hidden_until_public_launch(self):
        self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        response = self.client.get(reverse("amuse_bouche:feed"))
        self.assertEqual(response.status_code, 404)

    def test_staff_can_preview_feed_before_public_launch(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        approved = self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        self.client.force_login(self.user)

        response = self.client.get(reverse("amuse_bouche:feed"))

        self.assertContains(response, approved.title)

    @override_settings(AMUSE_BOUCHE_PUBLIC=True)
    def test_feed_shows_only_approved_items_when_public(self):
        approved = self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        self.create_item("Pending Bite", AmuseBouche.Status.PENDING)
        response = self.client.get(reverse("amuse_bouche:feed"))
        self.assertContains(response, approved.title)
        self.assertNotContains(response, "Pending Bite")

    @override_settings(AMUSE_BOUCHE_PUBLIC=True)
    def test_detail_hides_unapproved_item(self):
        pending = self.create_item("Pending Bite", AmuseBouche.Status.PENDING)
        response = self.client.get(reverse("amuse_bouche:detail", kwargs={"slug": pending.slug}))
        self.assertEqual(response.status_code, 404)

    @override_settings(AMUSE_BOUCHE_PUBLIC=True)
    def test_authenticated_user_can_like_and_save(self):
        item = self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        self.client.force_login(self.user)

        self.client.post(reverse("amuse_bouche:toggle_like", kwargs={"slug": item.slug}))
        self.client.post(reverse("amuse_bouche:toggle_save", kwargs={"slug": item.slug}))

        self.assertEqual(ContentReaction.objects.count(), 1)
        self.assertEqual(SavedContent.objects.count(), 1)
