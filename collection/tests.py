from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from articles.models import Article, ArticleImage
from recipes.models import Recipe, RecipeAuthor

from .models import SavedArticle, SavedRecipe


class CollectionVisibilityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="reader", password="pass")
        self.author_user = user_model.objects.create_user(username="author", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Author",
            slug="author",
        )

    def recipe(self, title, status):
        return Recipe.objects.create(
            title=title,
            slug=title.lower().replace(" ", "-"),
            author=self.author,
            ingredients="Potatoes",
            method="Boil",
            status=status,
        )

    def article(self, title, status):
        return Article.objects.create(
            title=title,
            slug=title.lower().replace(" ", "-"),
            author=self.author,
            body=f"{title} body",
            published=date(2026, 5, 20),
            status=status,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )

    def test_my_collection_shows_only_approved_saved_content(self):
        approved_recipe = self.recipe("Approved Recipe", Recipe.Status.APPROVED)
        pending_recipe = self.recipe("Pending Recipe", Recipe.Status.PENDING)
        needs_changes_recipe = self.recipe("Needs Changes Recipe", Recipe.Status.NEEDS_CHANGES)
        approved_article = self.article("Approved Article", Article.Status.APPROVED)
        rejected_article = self.article("Rejected Article", Article.Status.REJECTED)
        needs_changes_article = self.article("Needs Changes Article", Article.Status.NEEDS_CHANGES)
        SavedRecipe.objects.create(user=self.user, recipe=approved_recipe)
        SavedRecipe.objects.create(user=self.user, recipe=pending_recipe)
        SavedRecipe.objects.create(user=self.user, recipe=needs_changes_recipe)
        SavedArticle.objects.create(user=self.user, article=approved_article)
        SavedArticle.objects.create(user=self.user, article=rejected_article)
        SavedArticle.objects.create(user=self.user, article=needs_changes_article)
        self.client.force_login(self.user)

        response = self.client.get(reverse("collection:my_collection"))

        self.assertContains(response, "Approved Recipe")
        self.assertNotContains(response, "Pending Recipe")
        self.assertNotContains(response, "Needs Changes Recipe")
        self.assertEqual(len(response.context["saved_recipes"]), 1)

        response = self.client.get(f"{reverse('collection:my_collection')}?tab=articles")

        self.assertContains(response, "Approved Article")
        self.assertNotContains(response, "Rejected Article")
        self.assertNotContains(response, "Needs Changes Article")
        self.assertEqual(len(response.context["saved_articles"]), 1)

    def test_collection_uses_article_gallery_image_when_article_image_is_missing(self):
        approved_article = self.article("Gallery Saved Article", Article.Status.APPROVED)
        gallery_image = ArticleImage.objects.create(
            article=approved_article,
            image="articles/gallery-saved/gallery/img1-test.png",
            sort_order=1,
        )
        SavedArticle.objects.create(user=self.user, article=approved_article)
        self.client.force_login(self.user)

        response = self.client.get(f"{reverse('collection:my_collection')}?tab=articles")

        self.assertContains(response, gallery_image.image.url, html=False)

    def test_cannot_add_unapproved_article_to_collection(self):
        article = self.article("Pending Article", Article.Status.PENDING)
        self.client.force_login(self.user)

        response = self.client.post(reverse("collection:add_article", kwargs={"slug": article.slug}))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(SavedArticle.objects.filter(user=self.user, article=article).exists())

    def test_cannot_add_needs_changes_recipe_or_article_to_collection(self):
        recipe = self.recipe("Needs Changes Recipe", Recipe.Status.NEEDS_CHANGES)
        article = self.article("Needs Changes Article", Article.Status.NEEDS_CHANGES)
        self.client.force_login(self.user)

        recipe_response = self.client.post(reverse("collection:add_recipe", kwargs={"slug": recipe.slug}))
        article_response = self.client.post(reverse("collection:add_article", kwargs={"slug": article.slug}))

        self.assertEqual(recipe_response.status_code, 404)
        self.assertEqual(article_response.status_code, 404)
        self.assertFalse(SavedRecipe.objects.filter(user=self.user, recipe=recipe).exists())
        self.assertFalse(SavedArticle.objects.filter(user=self.user, article=article).exists())

    def test_can_remove_existing_unapproved_article_from_collection(self):
        article = self.article("Rejected Article", Article.Status.REJECTED)
        SavedArticle.objects.create(user=self.user, article=article)
        self.client.force_login(self.user)

        response = self.client.post(reverse("collection:remove_article", kwargs={"slug": article.slug}))

        self.assertRedirects(response, article.get_absolute_url(), fetch_redirect_response=False)
        self.assertFalse(SavedArticle.objects.filter(user=self.user, article=article).exists())
