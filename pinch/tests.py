from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from articles.models import Article
from collection.models import ContentReaction, SavedContent
from recipes.models import Recipe, RecipeAuthor
from .models import Pinch


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="", PINCH_PUBLIC=False)
class PinchPublicTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="reader", password="pass")
        self.author = RecipeAuthor.objects.create(name="Test Author", slug="test-author")

    def create_item(self, title, status):
        return Pinch.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    def test_feed_is_hidden_until_public_launch(self):
        self.create_item("Approved Bite", Pinch.Status.APPROVED)
        response = self.client.get(reverse("pinch:feed"))
        self.assertEqual(response.status_code, 404)

    def test_staff_can_preview_feed_before_public_launch(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        approved = self.create_item("Approved Bite", Pinch.Status.APPROVED)
        self.client.force_login(self.user)

        response = self.client.get(reverse("pinch:feed"))

        self.assertContains(response, approved.title)

    @override_settings(PINCH_PUBLIC=True)
    def test_feed_shows_only_approved_items_when_public(self):
        approved = self.create_item("Approved Bite", Pinch.Status.APPROVED)
        self.create_item("Pending Bite", Pinch.Status.PENDING)
        response = self.client.get(reverse("pinch:feed"))
        self.assertContains(response, approved.title)
        self.assertNotContains(response, "Pending Bite")

    @override_settings(PINCH_PUBLIC=True)
    def test_feed_orders_newest_published_items_first(self):
        older_featured = self.create_item("Older Featured Bite", Pinch.Status.APPROVED)
        newest = self.create_item("Newest Bite", Pinch.Status.APPROVED)
        now = timezone.now()
        Pinch.objects.filter(pk=older_featured.pk).update(
            is_featured=True,
            published_at=now - timedelta(days=2),
        )
        Pinch.objects.filter(pk=newest.pk).update(published_at=now)

        response = self.client.get(reverse("pinch:feed"))

        self.assertEqual(
            [item.title for item in response.context["items"][:2]],
            ["Newest Bite", "Older Featured Bite"],
        )

    @override_settings(PINCH_PUBLIC=True)
    def test_detail_hides_unapproved_item(self):
        pending = self.create_item("Pending Bite", Pinch.Status.PENDING)
        response = self.client.get(reverse("pinch:detail", kwargs={"slug": pending.slug}))
        self.assertEqual(response.status_code, 404)

    @override_settings(PINCH_PUBLIC=True)
    def test_authenticated_user_can_like_and_save(self):
        item = self.create_item("Approved Bite", Pinch.Status.APPROVED)
        self.client.force_login(self.user)

        self.client.post(reverse("pinch:toggle_like", kwargs={"slug": item.slug}))
        self.client.post(reverse("pinch:toggle_save", kwargs={"slug": item.slug}))

        self.assertEqual(ContentReaction.objects.count(), 1)
        self.assertEqual(SavedContent.objects.count(), 1)


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="", PINCH_PUBLIC=False)
class PinchGatingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="author", password="pass")
        self.other_user = user_model.objects.create_user(username="other", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Test Author",
            slug="test-author",
        )

    def create_item(self, title="Pending Bite", status=Pinch.Status.PENDING):
        return Pinch.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    def test_author_can_open_create_form_before_public_launch(self):
        self.client.force_login(self.author_user)

        response = self.client.get(reverse("pinch:create"))

        self.assertContains(response, "Submit Pinch")
        self.assertContains(response, 'data-autosave="true"', html=False)
        self.assertContains(response, "pinch-authoring:/pinch/new/", html=False)

    def test_author_can_submit_bite_before_public_launch(self):
        self.client.force_login(self.author_user)

        response = self.client.post(
            reverse("pinch:create"),
            {
                "title": "Tiny Soda Bread Trick",
                "short_description": "Toast the heel and rub it with salted butter.",
                "content_type": Pinch.ContentType.CHEF_TRICK,
                "cover_image_alt": "",
                "image_rights_status": Pinch.ImageRightsStatus.NOT_APPLICABLE,
                "source_type": Pinch.SourceType.ORIGINAL,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "linked_recipe": "",
                "linked_article": "",
                "allow_comments": "on",
                "seo_title": "",
                "seo_description": "",
                "confirm_own_work": "on",
                "confirm_image_rights": "on",
                "confirm_rules": "on",
            },
        )

        item = Pinch.objects.get(title="Tiny Soda Bread Trick")
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.author, self.author)
        self.assertEqual(item.status, Pinch.Status.PENDING)

    def test_greenbear_submit_bite_publishes_without_review(self):
        user_model = get_user_model()
        greenbear_user = user_model.objects.create_user(username="greenbear", password="pass")
        greenbear_author, _ = RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={"user": greenbear_user, "name": "GreenBear"},
        )
        self.client.force_login(greenbear_user)

        response = self.client.post(
            reverse("pinch:create"),
            {
                "title": "GreenBear Soda Bread Trick",
                "short_description": "Toast the heel and rub it with salted butter.",
                "content_type": Pinch.ContentType.CHEF_TRICK,
                "cover_image_alt": "",
                "image_rights_status": Pinch.ImageRightsStatus.NOT_APPLICABLE,
                "source_type": Pinch.SourceType.ORIGINAL,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "linked_recipe": "",
                "linked_article": "",
                "allow_comments": "on",
                "seo_title": "",
                "seo_description": "",
                "confirm_own_work": "on",
                "confirm_image_rights": "on",
                "confirm_rules": "on",
            },
        )

        item = Pinch.objects.get(title="GreenBear Soda Bread Trick")
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.author, greenbear_author)
        self.assertEqual(item.status, Pinch.Status.APPROVED)
        self.assertEqual(item.moderated_by, greenbear_user)
        self.assertIsNotNone(item.moderated_at)
        self.assertIsNotNone(item.published_at)

    def test_author_can_preview_own_pending_bite_before_public_launch(self):
        item = self.create_item()
        self.client.force_login(self.author_user)

        response = self.client.get(reverse("pinch:detail", kwargs={"slug": item.slug}))

        self.assertContains(response, item.title)

    def test_author_profile_workspace_shows_own_bites_before_public_launch(self):
        item = self.create_item()
        self.client.force_login(self.author_user)

        response = self.client.get(reverse("recipes:author_detail", kwargs={"slug": self.author.slug}))

        self.assertIn(item, response.context["dashboard_pinch"])
        self.assertContains(response, item.title)

    def test_other_authenticated_user_cannot_preview_approved_bite_before_public_launch(self):
        item = self.create_item("Approved Bite", Pinch.Status.APPROVED)
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("pinch:detail", kwargs={"slug": item.slug}))

        self.assertEqual(response.status_code, 404)


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="")
class PinchModerationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.moderator = user_model.objects.create_user(
            username="moderator",
            password="pass",
            is_staff=True,
        )
        self.reader = user_model.objects.create_user(username="reader", password="pass")
        self.author = RecipeAuthor.objects.create(name="Test Author", slug="test-author")

    def create_item(self, title="Pending Bite", status=Pinch.Status.PENDING):
        return Pinch.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    def test_moderation_panel_lists_pinch_items(self):
        pending = self.create_item("Pending Bite", Pinch.Status.PENDING)
        needs_changes = self.create_item("Needs Work Bite", Pinch.Status.NEEDS_CHANGES)
        rejected = self.create_item("Rejected Bite", Pinch.Status.REJECTED)
        self.client.force_login(self.moderator)

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertContains(response, "Pinch")
        self.assertIn(pending, response.context["pending_pinch"])
        self.assertIn(needs_changes, response.context["needs_changes_pinch"])
        self.assertIn(rejected, response.context["rejected_pinch"])

    def test_moderation_panel_excludes_greenbear_pinch_items(self):
        greenbear, _ = RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={"name": "GreenBear"},
        )
        owner_pending = Pinch.objects.create(
            author=greenbear,
            title="Owner Pending Bite",
            short_description="Owner bite.",
            status=Pinch.Status.PENDING,
        )
        owner_needs_changes = Pinch.objects.create(
            author=greenbear,
            title="Owner Needs Work Bite",
            short_description="Owner bite.",
            status=Pinch.Status.NEEDS_CHANGES,
        )
        owner_rejected = Pinch.objects.create(
            author=greenbear,
            title="Owner Rejected Bite",
            short_description="Owner bite.",
            status=Pinch.Status.REJECTED,
        )
        self.client.force_login(self.moderator)

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertNotIn(owner_pending, response.context["pending_pinch"])
        self.assertNotIn(owner_needs_changes, response.context["needs_changes_pinch"])
        self.assertNotIn(owner_rejected, response.context["rejected_pinch"])

    def test_moderator_can_preview_pending_detail(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        response = self.client.get(reverse("pinch:detail", kwargs={"slug": item.slug}))

        self.assertContains(response, item.title)

    def test_moderator_can_approve_item(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(reverse("pinch:moderate", kwargs={"slug": item.slug}), {"action": "approve"})
        item.refresh_from_db()

        self.assertEqual(item.status, Pinch.Status.APPROVED)
        self.assertEqual(item.moderation_note, "")
        self.assertEqual(item.moderated_by, self.moderator)
        self.assertIsNotNone(item.moderated_at)
        self.assertIsNotNone(item.published_at)

    def test_reject_requires_note(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        response = self.client.post(
            reverse("pinch:moderate", kwargs={"slug": item.slug}),
            {"action": "reject"},
        )
        item.refresh_from_db()

        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.status, Pinch.Status.PENDING)

    def test_moderator_can_request_changes(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(
            reverse("pinch:moderate", kwargs={"slug": item.slug}),
            {"action": "request_changes", "moderation_note": "Clarify image rights."},
        )
        item.refresh_from_db()

        self.assertEqual(item.status, Pinch.Status.NEEDS_CHANGES)
        self.assertEqual(item.moderation_note, "Clarify image rights.")
        self.assertEqual(item.moderated_by, self.moderator)

    def test_moderator_archive_hides_item_from_moderation_queue(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(reverse("pinch:moderate", kwargs={"slug": item.slug}), {"action": "delete"})
        item.refresh_from_db()

        self.assertEqual(item.status, Pinch.Status.ARCHIVED)
        response = self.client.get(reverse("recipes:moderation_panel"))
        self.assertNotIn(item, response.context["pending_pinch"])

    def test_non_moderator_cannot_moderate(self):
        item = self.create_item()
        self.client.force_login(self.reader)

        response = self.client.post(reverse("pinch:moderate", kwargs={"slug": item.slug}), {"action": "approve"})

        self.assertEqual(response.status_code, 404)


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="")
class PinchGenerateFromRecipeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="chef", password="pass")
        self.other_user = user_model.objects.create_user(username="other", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Chef Author",
            slug="chef-author",
        )
        self.recipe = Recipe.objects.create(
            author=self.author,
            title="Boxty Pancakes",
            slug="boxty-pancakes",
            short_description="A classic Irish potato pancake.",
            hero_image_alt_text="Golden boxty on a plate",
            category=Recipe.Category.IRISH_CULINARY_HERITAGE,
            ingredients="500g potatoes",
            method="Grate the potatoes.",
            status=Recipe.Status.APPROVED,
        )
        self.url = reverse("pinch:generate_from_recipe", kwargs={"slug": self.recipe.slug})

    def test_author_can_generate_bite_from_approved_recipe(self):
        self.client.force_login(self.author_user)
        response = self.client.post(self.url)

        item = Pinch.objects.get(linked_recipe=self.recipe)
        edit_url = reverse("pinch:edit", kwargs={"slug": item.slug})
        self.assertRedirects(response, f"{edit_url}?from_recipe=1")
        self.assertEqual(item.title, self.recipe.title)
        self.assertEqual(item.author, self.author)
        self.assertEqual(item.status, Pinch.Status.PENDING)
        self.assertEqual(item.content_type, Pinch.ContentType.BEHIND_THE_DISH)
        self.assertEqual(item.linked_recipe, self.recipe)
        self.assertEqual(item.cover_image_alt, self.recipe.hero_image_alt_text)

    def test_greenbear_recipe_generation_publishes_without_review(self):
        user_model = get_user_model()
        greenbear_user = user_model.objects.create_user(username="greenbear", password="pass")
        greenbear_author, _ = RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={"user": greenbear_user, "name": "GreenBear"},
        )
        recipe = Recipe.objects.create(
            author=greenbear_author,
            title="GreenBear Boxty",
            slug="greenbear-boxty",
            short_description="A classic Irish potato pancake.",
            hero_image_alt_text="Golden boxty on a plate",
            category=Recipe.Category.IRISH_CULINARY_HERITAGE,
            ingredients="500g potatoes",
            method="Grate the potatoes.",
            status=Recipe.Status.APPROVED,
        )
        self.client.force_login(greenbear_user)

        response = self.client.post(reverse("pinch:generate_from_recipe", kwargs={"slug": recipe.slug}))

        item = Pinch.objects.get(linked_recipe=recipe)
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.author, greenbear_author)
        self.assertEqual(item.status, Pinch.Status.APPROVED)
        self.assertEqual(item.moderated_by, greenbear_user)
        self.assertIsNotNone(item.moderated_at)
        self.assertIsNotNone(item.published_at)

    def test_duplicate_generation_redirects_to_existing_bite(self):
        self.client.force_login(self.author_user)
        self.client.post(self.url)
        self.client.post(self.url)

        self.assertEqual(Pinch.objects.filter(linked_recipe=self.recipe).count(), 1)

    def test_unauthenticated_user_cannot_generate(self):
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(Pinch.objects.filter(linked_recipe=self.recipe).exists())

    def test_unrelated_user_cannot_generate(self):
        self.client.force_login(self.other_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_method_not_allowed(self):
        self.client.force_login(self.author_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_draft_recipe_returns_404(self):
        self.recipe.status = Recipe.Status.DRAFT
        self.recipe.save(update_fields=["status"])
        self.client.force_login(self.author_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_archived_bite_does_not_block_new_generation(self):
        Pinch.objects.create(
            author=self.author,
            title=self.recipe.title,
            linked_recipe=self.recipe,
            status=Pinch.Status.ARCHIVED,
        )
        self.client.force_login(self.author_user)
        self.client.post(self.url)
        self.assertEqual(
            Pinch.objects.filter(linked_recipe=self.recipe).exclude(status=Pinch.Status.ARCHIVED).count(),
            1,
        )


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="")
class PinchGenerateFromArticleTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="writer", password="pass")
        self.other_user = user_model.objects.create_user(username="other2", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Writer Author",
            slug="writer-author",
        )
        self.article = Article.objects.create(
            author=self.author,
            title="The History of Irish Soda Bread",
            slug="history-irish-soda-bread",
            excerpt="A deep dive into the origins of Irish soda bread.",
            hero_image_alt_text="A golden loaf of soda bread",
            category=Article.Category.BAKING,
            body="Soda bread is a staple of Irish cuisine.",
            status=Article.Status.APPROVED,
            published=timezone.now(),
        )
        self.url = reverse("pinch:generate_from_article", kwargs={"slug": self.article.slug})

    def test_author_can_generate_bite_from_approved_article(self):
        self.client.force_login(self.author_user)
        response = self.client.post(self.url)

        item = Pinch.objects.get(linked_article=self.article)
        edit_url = reverse("pinch:edit", kwargs={"slug": item.slug})
        self.assertRedirects(response, f"{edit_url}?from_article=1")
        self.assertEqual(item.title, self.article.title)
        self.assertEqual(item.author, self.author)
        self.assertEqual(item.status, Pinch.Status.PENDING)
        self.assertEqual(item.content_type, Pinch.ContentType.BEHIND_THE_DISH)
        self.assertEqual(item.linked_article, self.article)
        self.assertEqual(item.cover_image_alt, self.article.hero_image_alt_text)

    def test_greenbear_article_generation_publishes_without_review(self):
        user_model = get_user_model()
        greenbear_user = user_model.objects.create_user(username="greenbear", password="pass")
        greenbear_author, _ = RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={"user": greenbear_user, "name": "GreenBear"},
        )
        article = Article.objects.create(
            author=greenbear_author,
            title="GreenBear Soda Bread History",
            slug="greenbear-soda-bread-history",
            excerpt="A deep dive into the origins of Irish soda bread.",
            hero_image_alt_text="A golden loaf of soda bread",
            category=Article.Category.BAKING,
            body="Soda bread is a staple of Irish cuisine.",
            status=Article.Status.APPROVED,
            published=timezone.now(),
        )
        self.client.force_login(greenbear_user)

        response = self.client.post(reverse("pinch:generate_from_article", kwargs={"slug": article.slug}))

        item = Pinch.objects.get(linked_article=article)
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.author, greenbear_author)
        self.assertEqual(item.status, Pinch.Status.APPROVED)
        self.assertEqual(item.moderated_by, greenbear_user)
        self.assertIsNotNone(item.moderated_at)
        self.assertIsNotNone(item.published_at)

    def test_duplicate_generation_redirects_to_existing_bite(self):
        self.client.force_login(self.author_user)
        self.client.post(self.url)
        self.client.post(self.url)

        self.assertEqual(Pinch.objects.filter(linked_article=self.article).count(), 1)

    def test_unauthenticated_user_cannot_generate(self):
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(Pinch.objects.filter(linked_article=self.article).exists())

    def test_unrelated_user_cannot_generate(self):
        self.client.force_login(self.other_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_method_not_allowed(self):
        self.client.force_login(self.author_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_draft_article_returns_404(self):
        self.article.status = Article.Status.DRAFT
        self.article.save(update_fields=["status"])
        self.client.force_login(self.author_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_archived_bite_does_not_block_new_generation(self):
        Pinch.objects.create(
            author=self.author,
            title=self.article.title,
            linked_article=self.article,
            status=Pinch.Status.ARCHIVED,
        )
        self.client.force_login(self.author_user)
        self.client.post(self.url)
        self.assertEqual(
            Pinch.objects.filter(linked_article=self.article).exclude(status=Pinch.Status.ARCHIVED).count(),
            1,
        )


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="", PINCH_PUBLIC=True)
class PinchTelegramPreviewTests(TestCase):
    def setUp(self):
        self.author = RecipeAuthor.objects.create(name="Preview Author", slug="preview-author")

    @staticmethod
    def uploaded_image(name="preview.png", size=(1600, 1000), color=(24, 76, 58)):
        image_file = BytesIO()
        Image.new("RGB", size, color).save(image_file, format="PNG")
        image_file.seek(0)
        return SimpleUploadedFile(name, image_file.read(), content_type="image/png")

    def test_card_image_falls_back_to_linked_article_image(self):
        article = Article.objects.create(
            author=self.author,
            title="Preview Article",
            slug="preview-article",
            excerpt="Article excerpt.",
            body="Article body.",
            status=Article.Status.APPROVED,
            published=timezone.localdate(),
        )
        article.hero_image.save("article-cover.png", self.uploaded_image("article-cover.png"), save=True)
        item = Pinch.objects.create(
            author=self.author,
            title="Article Bite",
            short_description="A bite from an article.",
            linked_article=article,
            status=Pinch.Status.APPROVED,
        )

        self.assertEqual(item.card_image.url, article.hero_image.url)

    def test_detail_uses_generated_telegram_preview_image_metadata(self):
        item = Pinch.objects.create(
            author=self.author,
            title="Preview Bite",
            short_description="A bite with a large cover image.",
            status=Pinch.Status.APPROVED,
        )
        item.cover_image.save("large-cover.png", self.uploaded_image("large-cover.png"), save=True)

        response = self.client.get(item.get_absolute_url())

        preview = response.context["telegram_preview_image"]
        self.assertIn(f"/media/pinch/telegram-previews/{item.pk}/", preview.url)
        self.assertNotEqual(preview.url, f"http://testserver{item.cover_image.url}")
        self.assertEqual((preview.width, preview.height), (640, 640))
        self.assertIn(f'<meta content="{preview.url}" property="og:image">', response.content.decode())
        with default_storage.open(preview.name, "rb") as generated_file:
            with Image.open(generated_file) as generated_image:
                self.assertEqual(generated_image.size, (640, 640))
                self.assertEqual(generated_image.format, "JPEG")

    def test_detail_uses_short_description_for_telegram_preview_text(self):
        description = "Tender orchard apples baked in whiskey caramel with a crisp oat crown."
        item = Pinch.objects.create(
            author=self.author,
            title="Orchard Apples in Whiskey Sauce",
            short_description=description,
            status=Pinch.Status.APPROVED,
        )

        response = self.client.get(item.get_absolute_url())
        html = response.content.decode()

        self.assertIn(f'<meta content="{description}" property="og:title">', html)
        self.assertIn(f'<meta content="{description}" name="twitter:title">', html)
        self.assertNotIn(
            '<meta content="Orchard Apples in Whiskey Sauce | Pinch" property="og:title">',
            html,
        )
        self.assertNotIn(
            '<meta content="Orchard Apples in Whiskey Sauce | Pinch" name="twitter:title">',
            html,
        )
        self.assertNotIn('<meta content="Pinch on CulinEire" property="og:description">', html)
        self.assertNotIn('<meta content="Pinch on CulinEire" name="twitter:description">', html)

    @patch("pinch.telegram_preview._create_preview_image", side_effect=OSError("preview write failed"))
    def test_detail_falls_back_to_source_image_when_preview_generation_fails(self, _mock_create):
        item = Pinch.objects.create(
            author=self.author,
            title="Fallback Preview Bite",
            short_description="A bite with a cover image.",
            status=Pinch.Status.APPROVED,
        )
        item.cover_image.save("fallback-cover.png", self.uploaded_image("fallback-cover.png"), save=True)

        response = self.client.get(item.get_absolute_url())

        preview = response.context["telegram_preview_image"]
        self.assertEqual(preview.url, f"http://testserver{item.cover_image.url}")
        self.assertNotIn("/static/images/hero", preview.url)
        self.assertIn(f'<meta content="{preview.url}" property="og:image">', response.content.decode())


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="", PINCH_PUBLIC=False)
class PinchRegressionTests(TestCase):
    """
    Regression tests for the five quality fixes applied after Phase 10 completion:

    1. Pinch.save() must never call the Anthropic API (emoji_description is opt-in).
    2. Public AB links stay hidden while PINCH_PUBLIC=False.
    3. Cancel link on the form resolves to a safe URL (author profile or item detail), not the gated feed.
    4. Back link on the detail page is suppressed when the user cannot access the feed.
    5. Authors can create/edit/preview pending bites without hitting the gated feed.
    """

    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="reg_author", password="pass")
        self.plain_user = user_model.objects.create_user(username="reg_plain", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Reg Author",
            slug="reg-author",
        )

    def _create_item(self, title="Bite", status=Pinch.Status.PENDING):
        return Pinch.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    # ── Regression 1: save() must not call Anthropic ──────────────────────────

    def test_save_does_not_call_anthropic_api(self):
        """Creating or updating an Pinch must never invoke generate_emoji_description automatically."""
        with patch.object(Pinch, "generate_emoji_description") as mock_gen:
            item = Pinch.objects.create(
                author=self.author,
                title="No API Bite",
                short_description="Should not trigger API.",
                status=Pinch.Status.PENDING,
            )
            mock_gen.assert_not_called()

            item.short_description = "Updated text."
            item.save(update_fields=["short_description"])
            mock_gen.assert_not_called()

    def test_generate_emoji_description_is_explicit_call_only(self):
        """Calling generate_emoji_description() explicitly with no API key fails silently and leaves field blank."""
        item = self._create_item()
        item.generate_emoji_description()  # ANTHROPIC_API_KEY="" via @override_settings
        self.assertEqual(item.emoji_description, "")  # Fails silently, field unchanged

    # ── Regression 2: public CTA links stay hidden when gated ─────────────────

    def test_anonymous_user_sees_no_ab_cta_on_homepage(self):
        """Homepage AB CTA must be absent for anonymous users while PINCH_PUBLIC=False."""
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, reverse("pinch:feed"))

    def test_plain_authenticated_user_sees_no_ab_cta_on_homepage(self):
        """Regular logged-in user (not staff/moderator) must not see the AB feed link when gated."""
        self.client.force_login(self.plain_user)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, reverse("pinch:feed"))

    def test_staff_user_sees_ab_nav_link_before_public_launch(self):
        """Staff users can see the AB nav link even before public launch."""
        self.author_user.is_staff = True
        self.author_user.save(update_fields=["is_staff"])
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("pinch:feed"))

    # ── Regression 3: Cancel link on the form is safe ─────────────────────────

    def test_create_form_cancel_url_is_author_profile_not_feed(self):
        """On the create form, cancel_url must be the author profile, not the gated feed."""
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:create"))
        self.assertEqual(response.status_code, 200)
        cancel_url = response.context.get("cancel_url", "")
        self.assertNotEqual(cancel_url, reverse("pinch:feed"))
        self.assertIn(self.author.slug, cancel_url)

    def test_edit_form_cancel_url_is_item_detail_not_feed(self):
        """On the edit form, cancel_url must be the item's detail page, not the gated feed."""
        item = self._create_item()
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:edit", kwargs={"slug": item.slug}))
        self.assertEqual(response.status_code, 200)
        cancel_url = response.context.get("cancel_url", "")
        self.assertNotEqual(cancel_url, reverse("pinch:feed"))
        self.assertEqual(cancel_url, item.get_absolute_url())

    # ── Regression 4: Back link on detail is suppressed when feed is gated ────

    def test_back_link_absent_on_detail_for_author_when_gated(self):
        """
        While PINCH_PUBLIC=False, can_view_ab_public is False for a plain author
        (not staff/moderator), so the Back to Pinch link must not appear on their
        detail page preview.
        """
        item = self._create_item()
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:detail", kwargs={"slug": item.slug}))
        self.assertNotContains(response, "Back to Pinch")

    @override_settings(PINCH_PUBLIC=True)
    def test_back_link_present_on_detail_when_public(self):
        """When PINCH_PUBLIC=True, the Back link must appear on the detail page."""
        item = self._create_item(status=Pinch.Status.APPROVED)
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:detail", kwargs={"slug": item.slug}))
        self.assertContains(response, "Back to Pinch")

    # ── Regression 5: Authors can work on bites without hitting the gated feed ─

    def test_author_feed_returns_404_when_gated(self):
        """Regular authors (not staff/mod) must get 404 on the feed while gated."""
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:feed"))
        self.assertEqual(response.status_code, 404)

    def test_author_can_open_edit_form_while_gated(self):
        """Author must be able to open the edit form for their own post while the feed is gated."""
        item = self._create_item()
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:edit", kwargs={"slug": item.slug}))
        self.assertEqual(response.status_code, 200)

    def test_likes_and_saves_gated_for_anonymous(self):
        """Anonymous users must be redirected when trying to like or save a bite."""
        item = self._create_item(status=Pinch.Status.APPROVED)
        like_resp = self.client.post(reverse("pinch:toggle_like", kwargs={"slug": item.slug}))
        save_resp = self.client.post(reverse("pinch:toggle_save", kwargs={"slug": item.slug}))
        self.assertEqual(ContentReaction.objects.count(), 0)
        self.assertEqual(SavedContent.objects.count(), 0)
        # Should redirect to login or return 302
        self.assertIn(like_resp.status_code, [302, 403])
        self.assertIn(save_resp.status_code, [302, 403])


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="", PINCH_PUBLIC=False)
class PinchLegalComplianceTests(TestCase):
    """
    Tests covering the legal/image-rights compliance requirements for Pinch.

    Covers:
    - Source attribution validation on the create form
    - Form shows source fields
    - generate_from_recipe prefills legal and source data, redirects to edit form
    - generate_from_article prefills legal and source data, redirects to edit form
    - AB stores its own legal snapshot; editing source does not overwrite it
    - Edit form loads from AB, not dynamically from recipe
    """

    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="legal_chef", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Legal Chef",
            slug="legal-chef",
        )
        self.recipe = Recipe.objects.create(
            author=self.author,
            title="Colcannon",
            slug="colcannon-legal",
            short_description="Classic mashed potato dish.",
            hero_image_alt_text="Bowl of colcannon",
            category=Recipe.Category.IRISH_CULINARY_HERITAGE,
            ingredients="Potatoes, kale, butter.",
            method="Boil and mash.",
            status=Recipe.Status.APPROVED,
            image_rights_status=Recipe.ImageRightsStatus.OWN,
            image_rights_note="",
            source_type=Recipe.SourceType.COOKBOOK,
            source_title="The Complete Irish Cookbook",
            source_author="Darina Allen",
            source_url="https://example.com/cookbook",
            source_note="Page 42",
        )
        self.article = Article.objects.create(
            author=self.author,
            title="Irish Food History",
            slug="irish-food-history-legal",
            excerpt="A short history.",
            category=Article.Category.BAKING,
            body="Food history content.",
            status=Article.Status.APPROVED,
            published=timezone.now(),
            image_rights_status=Article.ImageRightsStatus.LICENSED,
            image_rights_note="CC BY 4.0",
            source_type=Article.SourceType.ADAPTED,
            source_title="Adapted Source",
            source_author="Some Author",
            source_url="https://example.com/article-source",
            source_note="Adapted with permission",
        )

    # ── Form field visibility ────────────────────────────────────────────────

    def test_create_form_shows_source_fields(self):
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:create"))
        self.assertContains(response, 'name="source_type"')
        self.assertContains(response, 'name="source_title"')
        self.assertContains(response, 'name="source_url"')

    def test_edit_form_shows_source_fields(self):
        item = Pinch.objects.create(
            author=self.author,
            title="Test Bite",
            status=Pinch.Status.PENDING,
        )
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:edit", kwargs={"slug": item.slug}))
        self.assertContains(response, 'name="source_type"')
        self.assertContains(response, 'name="source_title"')

    # ── Source attribution validation ────────────────────────────────────────

    def test_form_requires_source_title_or_url_for_cookbook(self):
        self.client.force_login(self.author_user)
        response = self.client.post(
            reverse("pinch:create"),
            {
                "title": "Source Test Bite",
                "short_description": "Test.",
                "content_type": Pinch.ContentType.IRISH_BITE,
                "cover_image_alt": "",
                "image_rights_status": Pinch.ImageRightsStatus.NOT_APPLICABLE,
                "source_type": Pinch.SourceType.COOKBOOK,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "linked_recipe": "",
                "linked_article": "",
                "allow_comments": "on",
                "seo_title": "",
                "seo_description": "",
                "confirm_own_work": "on",
                "confirm_rules": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Pinch.objects.filter(title="Source Test Bite").exists())
        self.assertFormError(
            response.context["form"],
            "source_title",
            "Please provide a source title or URL for this type of content.",
        )

    def test_form_accepts_original_source_without_attribution(self):
        self.client.force_login(self.author_user)
        response = self.client.post(
            reverse("pinch:create"),
            {
                "title": "Original Bite",
                "short_description": "Test.",
                "content_type": Pinch.ContentType.IRISH_BITE,
                "cover_image_alt": "",
                "image_rights_status": Pinch.ImageRightsStatus.NOT_APPLICABLE,
                "source_type": Pinch.SourceType.ORIGINAL,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "linked_recipe": "",
                "linked_article": "",
                "allow_comments": "on",
                "seo_title": "",
                "seo_description": "",
                "confirm_own_work": "on",
                "confirm_rules": "on",
            },
        )
        self.assertTrue(Pinch.objects.filter(title="Original Bite").exists())

    def test_form_saves_source_snapshot(self):
        self.client.force_login(self.author_user)
        self.client.post(
            reverse("pinch:create"),
            {
                "title": "Snapshot Bite",
                "short_description": "Test.",
                "content_type": Pinch.ContentType.IRISH_BITE,
                "cover_image_alt": "",
                "image_rights_status": Pinch.ImageRightsStatus.NOT_APPLICABLE,
                "source_type": Pinch.SourceType.COOKBOOK,
                "source_title": "My Cookbook",
                "source_author": "Chef One",
                "source_url": "",
                "source_note": "p.10",
                "linked_recipe": "",
                "linked_article": "",
                "allow_comments": "on",
                "seo_title": "",
                "seo_description": "",
                "confirm_own_work": "on",
                "confirm_rules": "on",
            },
        )
        item = Pinch.objects.get(title="Snapshot Bite")
        self.assertEqual(item.source_type, Pinch.SourceType.COOKBOOK)
        self.assertEqual(item.source_title, "My Cookbook")
        self.assertEqual(item.source_author, "Chef One")
        self.assertEqual(item.source_note, "p.10")
        self.assertTrue(item.confirmed_own_work)
        self.assertTrue(item.confirmed_rules)

    # ── generate_from_recipe prefill ─────────────────────────────────────────

    def test_generate_from_recipe_prefills_image_rights(self):
        self.client.force_login(self.author_user)
        self.client.post(
            reverse("pinch:generate_from_recipe", kwargs={"slug": self.recipe.slug})
        )
        item = Pinch.objects.get(linked_recipe=self.recipe)
        self.assertEqual(item.image_rights_status, self.recipe.image_rights_status)
        self.assertEqual(item.image_rights_note, self.recipe.image_rights_note)

    def test_generate_from_recipe_prefills_source_fields(self):
        self.client.force_login(self.author_user)
        self.client.post(
            reverse("pinch:generate_from_recipe", kwargs={"slug": self.recipe.slug})
        )
        item = Pinch.objects.get(linked_recipe=self.recipe)
        self.assertEqual(item.source_type, self.recipe.source_type)
        self.assertEqual(item.source_title, self.recipe.source_title)
        self.assertEqual(item.source_author, self.recipe.source_author)
        self.assertEqual(item.source_url, self.recipe.source_url)
        self.assertEqual(item.source_note, self.recipe.source_note)

    def test_generate_from_recipe_redirects_to_edit_form(self):
        self.client.force_login(self.author_user)
        response = self.client.post(
            reverse("pinch:generate_from_recipe", kwargs={"slug": self.recipe.slug})
        )
        item = Pinch.objects.get(linked_recipe=self.recipe)
        edit_url = reverse("pinch:edit", kwargs={"slug": item.slug})
        self.assertRedirects(response, f"{edit_url}?from_recipe=1")

    def test_generate_from_recipe_edit_form_shows_review_banner(self):
        self.client.force_login(self.author_user)
        self.client.post(
            reverse("pinch:generate_from_recipe", kwargs={"slug": self.recipe.slug})
        )
        item = Pinch.objects.get(linked_recipe=self.recipe)
        response = self.client.get(
            reverse("pinch:edit", kwargs={"slug": item.slug}) + "?from_recipe=1"
        )
        self.assertContains(response, "Legal details copied from the original recipe")

    # ── AB snapshot independence ──────────────────────────────────────────────

    def test_editing_recipe_does_not_change_ab_source_snapshot(self):
        self.client.force_login(self.author_user)
        self.client.post(
            reverse("pinch:generate_from_recipe", kwargs={"slug": self.recipe.slug})
        )
        item = Pinch.objects.get(linked_recipe=self.recipe)
        original_source_title = item.source_title

        self.recipe.source_title = "Updated Cookbook Title"
        self.recipe.save(update_fields=["source_title"])

        item.refresh_from_db()
        self.assertEqual(item.source_title, original_source_title)

    def test_edit_form_loads_source_from_ab_not_recipe(self):
        item = Pinch.objects.create(
            author=self.author,
            title="Snapshot Edit Bite",
            status=Pinch.Status.PENDING,
            linked_recipe=self.recipe,
            source_type=Pinch.SourceType.OTHER,
            source_title="AB Own Source",
        )
        self.client.force_login(self.author_user)
        response = self.client.get(reverse("pinch:edit", kwargs={"slug": item.slug}))
        self.assertContains(response, "AB Own Source")
        self.assertNotContains(response, self.recipe.source_title)

    # ── generate_from_article prefill ────────────────────────────────────────

    def test_generate_from_article_prefills_image_rights(self):
        self.client.force_login(self.author_user)
        self.client.post(
            reverse("pinch:generate_from_article", kwargs={"slug": self.article.slug})
        )
        item = Pinch.objects.get(linked_article=self.article)
        self.assertEqual(item.image_rights_status, self.article.image_rights_status)
        self.assertEqual(item.image_rights_note, self.article.image_rights_note)

    def test_generate_from_article_prefills_source_fields(self):
        self.client.force_login(self.author_user)
        self.client.post(
            reverse("pinch:generate_from_article", kwargs={"slug": self.article.slug})
        )
        item = Pinch.objects.get(linked_article=self.article)
        # ADAPTED maps to OTHER in AB SourceType
        self.assertEqual(item.source_type, Pinch.SourceType.OTHER)
        self.assertEqual(item.source_title, self.article.source_title)
        self.assertEqual(item.source_author, self.article.source_author)
        self.assertEqual(item.source_url, self.article.source_url)

    def test_generate_from_article_redirects_to_edit_form(self):
        self.client.force_login(self.author_user)
        response = self.client.post(
            reverse("pinch:generate_from_article", kwargs={"slug": self.article.slug})
        )
        item = Pinch.objects.get(linked_article=self.article)
        edit_url = reverse("pinch:edit", kwargs={"slug": item.slug})
        self.assertRedirects(response, f"{edit_url}?from_article=1")


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="", ANTHROPIC_API_KEY="")
class PinchCommentSafetyTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="commenter", password="pass")
        self.author = RecipeAuthor.objects.create(name="Test Author", slug="test-author")
        self.item = Pinch.objects.create(
            author=self.author,
            title="Announcement Host",
            short_description="A quick bite.",
            status=Pinch.Status.APPROVED,
            is_announcement=True,
            allow_comments=True,
        )
        self.submit_url = reverse(
            "pinch:submit_comment", kwargs={"slug": self.item.slug}
        )

    def post_comment(self, body):
        return self.client.post(
            self.submit_url, {"body": body}, headers={"X-AB-Fetch": "1"}
        )

    def test_clean_comment_is_accepted(self):
        self.client.force_login(self.user)
        response = self.post_comment("Lovely idea, looking forward to it!")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(self.item.comments.filter(is_deleted=False).count(), 1)

    def test_profane_comment_is_rejected(self):
        self.client.force_login(self.user)
        response = self.post_comment("this is fucking great")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "profanity")
        self.assertIn("forbidden words", data["message"])
        self.assertEqual(self.item.comments.count(), 0)

    def test_moderator_can_delete_other_users_comment(self):
        from .models import PinchComment

        comment = PinchComment.objects.create(
            pinch=self.item, user=self.user, body="to be removed"
        )
        user_model = get_user_model()
        moderator = user_model.objects.create_user(
            username="mod", password="pass", is_staff=True
        )
        self.client.force_login(moderator)
        delete_url = reverse(
            "pinch:delete_comment",
            kwargs={"slug": self.item.slug, "comment_id": comment.pk},
        )
        response = self.client.post(delete_url, headers={"X-AB-Fetch": "1"})
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)

    def test_regular_user_cannot_delete_other_users_comment(self):
        from .models import PinchComment

        comment = PinchComment.objects.create(
            pinch=self.item, user=self.user, body="protected"
        )
        user_model = get_user_model()
        stranger = user_model.objects.create_user(username="stranger", password="pass")
        self.client.force_login(stranger)
        delete_url = reverse(
            "pinch:delete_comment",
            kwargs={"slug": self.item.slug, "comment_id": comment.pk},
        )
        response = self.client.post(delete_url, headers={"X-AB-Fetch": "1"})
        self.assertEqual(response.status_code, 404)
        comment.refresh_from_db()
        self.assertFalse(comment.is_deleted)
