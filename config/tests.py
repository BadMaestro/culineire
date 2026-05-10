from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from articles.models import Article
from recipes.models import Recipe, RecipeAuthor


@override_settings(SITE_DOMAIN="culineire.test", SITE_SCHEME="https")
class PublicTechnicalPagesTests(TestCase):
    def test_about_and_privacy_pages_are_public(self):
        for url_name in ("about", "privacy"):
            response = self.client.get(reverse(url_name))

            self.assertEqual(response.status_code, 200)

    def test_robots_txt_points_to_sitemap_and_blocks_private_paths(self):
        response = self.client.get(reverse("robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Disallow: /messages/")
        self.assertContains(response, "Sitemap: https://culineire.test/sitemap.xml")

    def test_sitemap_contains_public_approved_content_only(self):
        author = RecipeAuthor.objects.create(
            name="Public Author",
            slug="public-author",
        )
        approved_recipe = Recipe.objects.create(
            title="Approved Recipe",
            author=author,
            ingredients="Potatoes",
            method="Cook",
            status=Recipe.Status.APPROVED,
        )
        Recipe.objects.create(
            title="Pending Recipe",
            author=author,
            ingredients="Potatoes",
            method="Wait",
            status=Recipe.Status.PENDING,
        )
        approved_article = Article.objects.create(
            title="Approved Article",
            slug="approved-article",
            author=author,
            body="Published article body",
            published=date(2026, 5, 10),
            status=Article.Status.APPROVED,
        )
        Article.objects.create(
            title="Pending Article",
            slug="pending-article",
            author=author,
            body="Pending article body",
            published=date(2026, 5, 10),
            status=Article.Status.PENDING,
        )

        response = self.client.get(reverse("sitemap_xml"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/xml; charset=utf-8")
        self.assertContains(response, "https://culineire.test/")
        self.assertContains(response, f"https://culineire.test{approved_recipe.get_absolute_url()}")
        self.assertContains(response, f"https://culineire.test{approved_article.get_absolute_url()}")
        self.assertNotContains(response, "Pending Recipe")
        self.assertNotContains(response, "pending-article")
