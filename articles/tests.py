from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from recipes.models import Recipe, RecipeAuthor

from .models import Article, ArticleImage


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.InMemoryStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    },
)
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

    @staticmethod
    def uploaded_image(name="article-image.png", color=(24, 76, 58)):
        image_file = BytesIO()
        Image.new("RGB", (24, 24), color).save(image_file, format="PNG")
        image_file.seek(0)
        return SimpleUploadedFile(name, image_file.read(), content_type="image/png")

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

    def test_moderator_edit_preserves_article_status(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(),
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.PENDING)

    def test_moderator_edit_uses_article_author_recipes_for_related_recipe_choices(self):
        owner_recipe = Recipe.objects.create(
            title="Owner Recipe",
            slug="owner-recipe",
            author=self.owner_author,
            ingredients="Potatoes",
            method="Boil",
        )
        moderator_recipe = Recipe.objects.create(
            title="Moderator Recipe",
            slug="moderator-recipe",
            author=self.moderator_author,
            ingredients="Carrots",
            method="Roast",
        )
        self.client.force_login(self.moderator_user)

        response = self.client.get(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )

        related_recipe_ids = set(response.context["form"].fields["related_recipe"].queryset.values_list("pk", flat=True))
        self.assertIn(owner_recipe.pk, related_recipe_ids)
        self.assertNotIn(moderator_recipe.pk, related_recipe_ids)

    @override_settings(TURNSTILE_SITE_KEY="test-site-key")
    def test_article_create_shows_turnstile_when_configured(self):
        self.client.force_login(self.owner_user)

        response = self.client.get(reverse("articles:article_create"))

        self.assertContains(response, "cf-turnstile")
        self.assertContains(response, "test-site-key")

    @override_settings(TURNSTILE_SITE_KEY="test-site-key")
    def test_article_edit_does_not_show_unverified_turnstile_widget(self):
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )

        self.assertNotContains(response, "cf-turnstile")
        self.assertNotContains(response, "test-site-key")

    def test_article_detail_uses_only_active_gallery_images_in_sort_order(self):
        ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("inactive.png"),
            sort_order=1,
            is_active=False,
        )
        second = ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("second.png"),
            sort_order=2,
        )
        first = ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("first.png"),
            sort_order=1,
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(self.article.get_absolute_url())

        gallery_sources = [item["src"] for item in response.context["gallery_items"]]
        self.assertEqual(gallery_sources, [first.image.url, second.image.url])
        self.assertTrue(response.context["has_gallery"])

    def test_article_detail_falls_back_to_hero_when_gallery_has_no_active_images(self):
        self.article.hero_image.save("cover.png", self.uploaded_image("cover.png"), save=True)
        ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("inactive.png"),
            sort_order=1,
            is_active=False,
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(len(response.context["gallery_items"]), 1)
        self.assertEqual(response.context["gallery_items"][0]["src"], self.article.hero_image.url)
        self.assertFalse(response.context["has_gallery"])

    def test_article_edit_appends_gallery_images_after_highest_existing_sort_order(self):
        ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("inactive.png"),
            sort_order=7,
            is_active=False,
        )
        ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("active.png"),
            sort_order=2,
        )
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            {
                **self.article_payload(),
                "gallery_images": self.uploaded_image("new.png", color=(120, 40, 40)),
            },
        )

        self.assertRedirects(response, self.article.get_absolute_url())
        new_image = ArticleImage.objects.get(article=self.article, sort_order=8)
        self.assertEqual(new_image.sort_order, 8)

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
