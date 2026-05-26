from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from newsfeed.models import NewsFeedEntry, SocialPostLog
from newsfeed.telegram import TelegramResult

User = get_user_model()


def _make_author():
    from recipes.models import RecipeAuthor
    user = User.objects.create_user(username="testauthor", password="pass", email="a@a.com")
    author, _ = RecipeAuthor.objects.get_or_create(user=user, defaults={"name": "Test Author"})
    return author


def _make_recipe(author, title="Test Recipe", status="pending"):
    from recipes.models import Recipe
    return Recipe.objects.create(
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        status=status,
        category=Recipe.Category.IRISH_CUISINE,
        ingredients="Eggs",
        method="Cook",
    )


def _make_article(author, title="Test Article", status="pending"):
    from articles.models import Article
    from django.utils import timezone
    return Article.objects.create(
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        status=status,
        body="Body text.",
        published=timezone.localdate(),
    )


class RecipeFeedEntryTest(TestCase):
    def setUp(self):
        self.author = _make_author()

    def test_recipe_approval_creates_entry(self):
        recipe = _make_recipe(self.author)
        recipe.status = "approved"
        recipe.save()
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"recipe_published:{recipe.pk}").count(),
            1,
        )

    def test_recipe_edit_does_not_duplicate_entry(self):
        recipe = _make_recipe(self.author)
        recipe.status = "approved"
        recipe.save()
        recipe.title = "Updated Title"
        recipe.save()
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"recipe_published:{recipe.pk}").count(),
            1,
        )

    def test_recipe_rejection_hides_auto_entry_and_reapproval_restores_it(self):
        recipe = _make_recipe(self.author)
        recipe.status = "approved"
        recipe.save()
        event_key = f"recipe_published:{recipe.pk}"

        recipe.status = "rejected"
        recipe.save()

        entry = NewsFeedEntry.objects.get(event_key=event_key)
        self.assertFalse(entry.is_public)

        recipe.title = "Approved Again"
        recipe.status = "approved"
        recipe.save()

        entry.refresh_from_db()
        self.assertTrue(entry.is_public)
        self.assertEqual(entry.title, "New recipe published: Approved Again")

    def test_recipe_delete_hides_auto_entry(self):
        recipe = _make_recipe(self.author)
        recipe.status = "approved"
        recipe.save()
        event_key = f"recipe_published:{recipe.pk}"

        recipe.delete()

        entry = NewsFeedEntry.objects.get(event_key=event_key)
        self.assertFalse(entry.is_public)

    def test_pending_recipe_creates_no_entry(self):
        recipe = _make_recipe(self.author)
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"recipe_published:{recipe.pk}").count(),
            0,
        )


class RecipeTelegramPublishTest(TestCase):
    def setUp(self):
        self.author = _make_author()

    @override_settings(
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHANNEL_ID="@culineire_test",
        SITE_DOMAIN="culineire.test",
        SITE_SCHEME="https",
    )
    @patch("newsfeed.telegram.send_telegram_message")
    def test_recipe_approval_posts_to_telegram_once(self, send_telegram_message):
        send_telegram_message.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        recipe = _make_recipe(self.author)

        recipe.status = "approved"
        recipe.save()
        recipe.title = "Edited After Approval"
        recipe.save()

        self.assertEqual(send_telegram_message.call_count, 1)
        self.assertEqual(
            SocialPostLog.objects.filter(
                platform=SocialPostLog.Platform.TELEGRAM,
                event_key=f"recipe_published:{recipe.pk}",
                status=SocialPostLog.Status.SENT,
            ).count(),
            1,
        )

    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="")
    @patch("newsfeed.telegram.send_telegram_message")
    def test_missing_telegram_settings_create_no_log_or_request(self, send_telegram_message):
        recipe = _make_recipe(self.author)

        recipe.status = "approved"
        recipe.save()

        send_telegram_message.assert_not_called()
        self.assertFalse(SocialPostLog.objects.exists())

    @override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_CHANNEL_ID="@culineire_test")
    @patch("newsfeed.telegram.send_telegram_message")
    def test_pending_recipe_does_not_post_to_telegram(self, send_telegram_message):
        _make_recipe(self.author)

        send_telegram_message.assert_not_called()
        self.assertFalse(SocialPostLog.objects.exists())


class ArticleFeedEntryTest(TestCase):
    def setUp(self):
        self.author = _make_author()

    def test_article_approval_creates_entry(self):
        article = _make_article(self.author)
        article.status = "approved"
        article.save()
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"article_published:{article.pk}").count(),
            1,
        )

    def test_article_edit_does_not_duplicate_entry(self):
        article = _make_article(self.author)
        article.status = "approved"
        article.save()
        article.title = "Updated Article Title"
        article.save()
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"article_published:{article.pk}").count(),
            1,
        )

    def test_article_rejection_hides_auto_entry_and_reapproval_restores_it(self):
        article = _make_article(self.author)
        article.status = "approved"
        article.save()
        event_key = f"article_published:{article.pk}"

        article.status = "rejected"
        article.save()

        entry = NewsFeedEntry.objects.get(event_key=event_key)
        self.assertFalse(entry.is_public)

        article.title = "Approved Again"
        article.status = "approved"
        article.save()

        entry.refresh_from_db()
        self.assertTrue(entry.is_public)
        self.assertEqual(entry.title, "New article published: Approved Again")

    def test_article_delete_hides_auto_entry(self):
        article = _make_article(self.author)
        article.status = "approved"
        article.save()
        event_key = f"article_published:{article.pk}"

        article.delete()

        entry = NewsFeedEntry.objects.get(event_key=event_key)
        self.assertFalse(entry.is_public)

    def test_pending_article_creates_no_entry(self):
        article = _make_article(self.author)
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"article_published:{article.pk}").count(),
            0,
        )


class FeedPageTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("newsfeed:feed")

    def test_public_entries_visible(self):
        NewsFeedEntry.objects.create(
            entry_type="admin_note",
            title="Public note",
            is_public=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public note")

    def test_private_entries_hidden(self):
        NewsFeedEntry.objects.create(
            entry_type="admin_note",
            title="Private note",
            is_public=False,
        )
        response = self.client.get(self.url)
        self.assertNotContains(response, "Private note")

    def test_manual_admin_entry_displayed(self):
        NewsFeedEntry.objects.create(
            entry_type="version_release",
            title="Version 1.4.3 released",
            version="1.4.3",
            is_public=True,
            is_auto=False,
        )
        response = self.client.get(self.url)
        self.assertContains(response, "Version 1.4.3 released")
