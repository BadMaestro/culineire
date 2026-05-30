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


class AmuseBoucheModerationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.moderator = user_model.objects.create_user(
            username="moderator",
            password="pass",
            is_staff=True,
        )
        self.reader = user_model.objects.create_user(username="reader", password="pass")
        self.author = RecipeAuthor.objects.create(name="Test Author", slug="test-author")

    def create_item(self, title="Pending Bite", status=AmuseBouche.Status.PENDING):
        return AmuseBouche.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    def test_moderation_panel_lists_amuse_bouche_items(self):
        pending = self.create_item("Pending Bite", AmuseBouche.Status.PENDING)
        needs_changes = self.create_item("Needs Work Bite", AmuseBouche.Status.NEEDS_CHANGES)
        rejected = self.create_item("Rejected Bite", AmuseBouche.Status.REJECTED)
        self.client.force_login(self.moderator)

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertContains(response, "Amuse-Bouche")
        self.assertIn(pending, response.context["pending_amuse_bouche"])
        self.assertIn(needs_changes, response.context["needs_changes_amuse_bouche"])
        self.assertIn(rejected, response.context["rejected_amuse_bouche"])

    def test_moderator_can_preview_pending_detail(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        response = self.client.get(reverse("amuse_bouche:detail", kwargs={"slug": item.slug}))

        self.assertContains(response, item.title)

    def test_moderator_can_approve_item(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}), {"action": "approve"})
        item.refresh_from_db()

        self.assertEqual(item.status, AmuseBouche.Status.APPROVED)
        self.assertEqual(item.moderation_note, "")
        self.assertEqual(item.moderated_by, self.moderator)
        self.assertIsNotNone(item.moderated_at)
        self.assertIsNotNone(item.published_at)

    def test_reject_requires_note(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        response = self.client.post(
            reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}),
            {"action": "reject"},
        )
        item.refresh_from_db()

        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.status, AmuseBouche.Status.PENDING)

    def test_moderator_can_request_changes(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(
            reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}),
            {"action": "request_changes", "moderation_note": "Clarify image rights."},
        )
        item.refresh_from_db()

        self.assertEqual(item.status, AmuseBouche.Status.NEEDS_CHANGES)
        self.assertEqual(item.moderation_note, "Clarify image rights.")
        self.assertEqual(item.moderated_by, self.moderator)

    def test_moderator_archive_hides_item_from_moderation_queue(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}), {"action": "delete"})
        item.refresh_from_db()

        self.assertEqual(item.status, AmuseBouche.Status.ARCHIVED)
        response = self.client.get(reverse("recipes:moderation_panel"))
        self.assertNotIn(item, response.context["pending_amuse_bouche"])

    def test_non_moderator_cannot_moderate(self):
        item = self.create_item()
        self.client.force_login(self.reader)

        response = self.client.post(reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}), {"action": "approve"})

        self.assertEqual(response.status_code, 404)
