from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from newsfeed.models import NewsFeedEntry

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

    def test_pending_recipe_creates_no_entry(self):
        recipe = _make_recipe(self.author)
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"recipe_published:{recipe.pk}").count(),
            0,
        )


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
