from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from recipes.models import RecipeAuthor

from .models import Article


class ArticleAuthoringPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner_user = user_model.objects.create_user(
            username="owner",
            password="pass",
        )
        self.owner_author = RecipeAuthor.objects.create(
            user=self.owner_user,
            name="Original Author",
            slug="original-author",
        )
        self.other_user = user_model.objects.create_user(
            username="other",
            password="pass",
        )
        self.other_author = RecipeAuthor.objects.create(
            user=self.other_user,
            name="Other Author",
            slug="other-author",
        )
        self.moderator_user = user_model.objects.create_user(
            username="moderator",
            password="pass",
            is_staff=True,
        )
        self.moderator_author = RecipeAuthor.objects.create(
            user=self.moderator_user,
            name="Moderator Author",
            slug="moderator-author",
        )
        self.article = Article.objects.create(
            title="Original Article",
            slug="original-article",
            author=self.owner_author,
            excerpt="Original excerpt",
            body="Original body",
            published=date(2026, 5, 20),
            status=Article.Status.PENDING,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )

    def article_payload(self, **overrides):
        payload = {
            "title": "Updated Article",
            "excerpt": "Updated excerpt",
            "published": "2026-05-21",
            "related_recipe": "",
            "body": "Updated body",
            "image_rights_status": Article.ImageRightsStatus.NOT_APPLICABLE,
            "image_rights_note": "",
            "source_type": Article.SourceType.ORIGINAL,
            "source_title": "",
            "source_author": "",
            "source_url": "",
            "source_note": "",
            "confirm_own_work": "on",
            "confirm_image_rights": "on",
            "confirm_rules": "on",
        }
        payload.update(overrides)
        return payload

    def test_author_can_edit_own_article(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(),
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.title, "Updated Article")
        self.assertEqual(self.article.author, self.owner_author)

    def test_author_cannot_edit_another_authors_article(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(),
        )

        self.article.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.article.title, "Original Article")
        self.assertEqual(self.article.author, self.owner_author)

    def test_moderator_edit_does_not_reassign_article_author(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(),
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.title, "Updated Article")
        self.assertEqual(self.article.author, self.owner_author)
        self.assertNotEqual(self.article.author, self.moderator_author)

    def test_author_cannot_delete_another_authors_article(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse("articles:article_delete", kwargs={"slug": self.article.slug}),
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())

    def test_moderator_can_delete_any_article(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:article_delete", kwargs={"slug": self.article.slug}),
        )

        self.assertRedirects(response, reverse("articles:article_list"))
        self.assertFalse(Article.objects.filter(pk=self.article.pk).exists())
