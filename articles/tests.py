from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import inlineformset_factory
from django.http import QueryDict
from django.test import TestCase, override_settings
from django.urls import reverse
from messaging.models import Message
from PIL import Image

from recipes.models import Recipe, RecipeAuthor

from .admin import ArticleAdmin, ArticleAdminForm, ArticleImageInlineFormSet
from .models import Article, ArticleImage
from .views import ArticleDetailView, _gallery_alt_lines, _reading_time_minutes, _soft_delete_article


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

    @staticmethod
    def uploaded_invalid_image(name="broken.png"):
        return SimpleUploadedFile(name, b"not an image", content_type="image/png")

    def create_article(self, title, status, author=None, slug=None):
        return Article.objects.create(
            title=title,
            slug=slug or title.lower().replace(" ", "-"),
            author=author or self.owner_author,
            excerpt=f"{title} excerpt",
            body=f"{title} body",
            published=date(2026, 5, 20),
            status=status,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )

    def admin_payload(self, **overrides):
        payload = {
            "title": "Admin Article",
            "slug": "admin-article",
            "author": self.owner_author.pk,
            "excerpt": "Admin excerpt",
            "body": "Admin body",
            "published": "2026-05-21",
            "related_recipe": "",
            "hero_image": "",
            "status": Article.Status.PENDING,
            "image_rights_status": Article.ImageRightsStatus.NOT_APPLICABLE,
            "image_rights_note": "",
            "source_type": Article.SourceType.ORIGINAL,
            "source_title": "",
            "source_author": "",
            "source_url": "",
            "source_note": "",
            "confirmed_own_work": "on",
            "confirmed_image_rights": "on",
            "confirmed_rules": "on",
            "confirmation_timestamp": "",
        }
        payload.update(overrides)
        return payload

    def test_default_article_list_shows_only_approved_articles(self):
        self.article.title = "Pending Article"
        self.article.save(update_fields=["title"])
        self.create_article("Approved Article", Article.Status.APPROVED)
        self.create_article("Rejected Article", Article.Status.REJECTED)

        response = self.client.get(reverse("articles:article_list"))

        self.assertContains(response, "Approved Article")
        self.assertNotContains(response, "Pending Article")
        self.assertNotContains(response, "Rejected Article")
        self.assertFalse(response.context["can_manage_selected_author"])

    def test_default_article_list_does_not_hide_articles_after_first_50(self):
        for index in range(51):
            self.create_article(
                f"Approved Article {index:02d}",
                Article.Status.APPROVED,
                slug=f"approved-article-{index:02d}",
            )

        response = self.client.get(reverse("articles:article_list"))

        self.assertContains(response, "Approved Article 50")

    def test_article_list_marks_ai_generated_article_images(self):
        ai_article = self.create_article("AI Article", Article.Status.APPROVED)
        ai_article.image_rights_status = Article.ImageRightsStatus.AI_GENERATED
        ai_article.save(update_fields=["image_rights_status"])

        response = self.client.get(reverse("articles:article_list"))

        self.assertContains(response, 'aria-label="AI generated image"', html=False)

    def test_article_list_uses_first_gallery_image_when_article_image_is_missing(self):
        article = self.create_article("Gallery Card Article", Article.Status.APPROVED)
        gallery_image = ArticleImage.objects.create(
            article=article,
            image=self.uploaded_image("gallery-card.png"),
            sort_order=1,
        )

        response = self.client.get(reverse("articles:article_list"))

        self.assertContains(response, gallery_image.image.url, html=False)
        self.assertNotContains(response, "/static/images/hero.jpg", html=False)

    def test_public_author_article_list_shows_only_approved_without_management(self):
        self.article.title = "Pending Article"
        self.article.save(update_fields=["title"])
        self.create_article("Approved Article", Article.Status.APPROVED)
        self.create_article("Rejected Article", Article.Status.REJECTED)

        response = self.client.get(f"{reverse('articles:article_list')}?author={self.owner_author.slug}")

        self.assertContains(response, "Approved Article")
        self.assertNotContains(response, "Pending Article")
        self.assertNotContains(response, "Rejected Article")
        self.assertNotContains(response, "Edit Article")
        self.assertFalse(response.context["can_manage_selected_author"])

    def test_owner_author_article_list_shows_all_statuses_with_management(self):
        self.article.title = "Pending Article"
        self.article.save(update_fields=["title"])
        self.create_article("Approved Article", Article.Status.APPROVED)
        self.create_article("Rejected Article", Article.Status.REJECTED)
        self.client.force_login(self.owner_user)

        response = self.client.get(f"{reverse('articles:article_list')}?author={self.owner_author.slug}")

        self.assertContains(response, "Approved Article")
        self.assertContains(response, "Pending Article")
        self.assertContains(response, "Rejected Article")
        self.assertContains(response, "Pending Review")
        self.assertContains(response, "Rejected")
        self.assertContains(response, "Edit Article")
        self.assertTrue(response.context["can_manage_selected_author"])

    def test_moderator_author_article_list_shows_all_statuses_with_management(self):
        self.article.title = "Pending Article"
        self.article.save(update_fields=["title"])
        self.create_article("Approved Article", Article.Status.APPROVED)
        self.create_article("Rejected Article", Article.Status.REJECTED)
        self.client.force_login(self.moderator_user)

        response = self.client.get(f"{reverse('articles:article_list')}?author={self.owner_author.slug}")

        self.assertContains(response, "Approved Article")
        self.assertContains(response, "Pending Article")
        self.assertContains(response, "Rejected Article")
        self.assertContains(response, "Edit Article")
        self.assertTrue(response.context["can_manage_selected_author"])

    def test_article_admin_status_is_not_editable_from_changelist(self):
        self.assertNotIn("status", ArticleAdmin.list_editable)

    def test_article_admin_form_requires_credit_for_licensed_images(self):
        form = ArticleAdminForm(
            data=self.admin_payload(
                image_rights_status=Article.ImageRightsStatus.LICENSED,
                image_rights_note="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image_rights_note", form.errors)

    def test_article_admin_form_requires_source_title_for_adapted_articles(self):
        form = ArticleAdminForm(
            data=self.admin_payload(
                source_type=Article.SourceType.ADAPTED,
                source_title="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("source_title", form.errors)

    def test_article_admin_form_requires_source_detail_for_inspired_articles(self):
        form = ArticleAdminForm(
            data=self.admin_payload(
                source_type=Article.SourceType.INSPIRED,
                source_title="",
                source_author="",
                source_url="",
                source_note="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("source_note", form.errors)

    def test_article_admin_form_rejects_not_applicable_rights_with_existing_image(self):
        article = self.create_article("Hero Article", Article.Status.PENDING)
        article.hero_image = self.uploaded_image()
        form = ArticleAdminForm(
            data=self.admin_payload(
                slug=article.slug,
                image_rights_status=Article.ImageRightsStatus.NOT_APPLICABLE,
            ),
            instance=article,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image_rights_status", form.errors)

    def test_article_admin_form_rejects_not_applicable_rights_with_existing_gallery(self):
        article = self.create_article("Gallery Article", Article.Status.PENDING)
        ArticleImage.objects.create(
            article=article,
            image=self.uploaded_image("gallery.png"),
            sort_order=1,
        )
        form = ArticleAdminForm(
            data=self.admin_payload(
                slug=article.slug,
                image_rights_status=Article.ImageRightsStatus.NOT_APPLICABLE,
            ),
            instance=article,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image_rights_status", form.errors)

    def test_article_image_rights_status_includes_ai_generated_choice(self):
        self.assertIn(
            (Article.ImageRightsStatus.AI_GENERATED, "AI generated image"),
            Article.ImageRightsStatus.choices,
        )

    def test_article_admin_gallery_inline_rejects_not_applicable_rights(self):
        article = self.create_article("Inline Gallery Article", Article.Status.PENDING)
        article.image_rights_status = Article.ImageRightsStatus.NOT_APPLICABLE
        formset_class = inlineformset_factory(
            Article,
            ArticleImage,
            fields=("image", "alt_text", "caption", "sort_order", "is_active"),
            formset=ArticleImageInlineFormSet,
            extra=1,
            can_delete=True,
        )
        formset = formset_class(
            data={
                "gallery-TOTAL_FORMS": "1",
                "gallery-INITIAL_FORMS": "0",
                "gallery-MIN_NUM_FORMS": "0",
                "gallery-MAX_NUM_FORMS": "1000",
                "gallery-0-alt_text": "",
                "gallery-0-caption": "",
                "gallery-0-sort_order": "1",
                "gallery-0-is_active": "on",
            },
            files={
                "gallery-0-image": self.uploaded_image("inline-gallery.png"),
            },
            instance=article,
            prefix="gallery",
        )

        self.assertFalse(formset.is_valid())
        self.assertIn("Choose the correct image rights status", str(formset.non_form_errors()))

    def test_active_article_image_rejects_not_applicable_rights(self):
        article = self.create_article("Direct Gallery Article", Article.Status.PENDING)
        article.image_rights_status = Article.ImageRightsStatus.NOT_APPLICABLE
        gallery_image = ArticleImage(
            article=article,
            image=self.uploaded_image("direct-gallery.png"),
            sort_order=1,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            gallery_image.full_clean()

    def test_inactive_article_image_allows_not_applicable_rights(self):
        article = self.create_article("Inactive Gallery Article", Article.Status.PENDING)
        article.image_rights_status = Article.ImageRightsStatus.NOT_APPLICABLE
        gallery_image = ArticleImage(
            article=article,
            image=self.uploaded_image("inactive-gallery.png"),
            sort_order=1,
            is_active=False,
        )

        gallery_image.full_clean()

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

    def test_author_edit_of_approved_article_returns_to_pending_review(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(),
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.title, "Updated Article")
        self.assertEqual(self.article.status, Article.Status.PENDING)

    def test_author_edit_of_approved_article_mentions_review_in_message(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(),
            follow=True,
        )

        self.assertContains(response, "sent back to review")

    def test_author_edit_form_warns_live_article_returns_to_review(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )

        self.assertTrue(response.context["will_return_to_review"])
        self.assertContains(response, "Saving changes to a live article will move it back to Pending Review")

    def test_moderator_edit_form_does_not_warn_live_article_returns_to_review(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        self.client.force_login(self.moderator_user)

        response = self.client.get(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )

        self.assertFalse(response.context["will_return_to_review"])
        self.assertNotContains(response, "Saving changes to a live article will move it back to Pending Review")

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

    def test_moderator_edit_preserves_approved_article_status(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(),
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.APPROVED)

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

    def test_article_create_rejects_invalid_gallery_image_before_saving(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_create"),
            {
                **self.article_payload(
                    title="New Article",
                    image_rights_status=Article.ImageRightsStatus.OWN,
                ),
                "gallery_images": self.uploaded_invalid_image(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gallery image broken.png")
        self.assertFalse(Article.objects.filter(title="New Article").exists())
        self.assertFalse(ArticleImage.objects.exists())

    def test_article_create_rolls_back_if_gallery_save_fails(self):
        self.client.force_login(self.owner_user)
        self.client.raise_request_exception = False

        with patch(
            "articles.views.ArticleImage.objects.create",
            side_effect=RuntimeError("gallery save failed"),
        ):
            response = self.client.post(
                reverse("articles:article_create"),
                {
                    **self.article_payload(
                        title="Half Saved Article",
                        image_rights_status=Article.ImageRightsStatus.OWN,
                    ),
                    "gallery_images": self.uploaded_image("gallery.png"),
                },
            )

        self.assertEqual(response.status_code, 500)
        self.assertFalse(Article.objects.filter(title="Half Saved Article").exists())
        self.assertFalse(ArticleImage.objects.exists())

    def test_article_create_requires_credit_for_licensed_image_rights(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_create"),
            self.article_payload(
                title="Licensed Article",
                image_rights_status=Article.ImageRightsStatus.LICENSED,
                image_rights_note="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add the licence, credit line")
        self.assertFalse(Article.objects.filter(title="Licensed Article").exists())

    def test_article_create_requires_source_title_for_adapted_article(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_create"),
            self.article_payload(
                title="Adapted Article",
                source_type=Article.SourceType.ADAPTED,
                source_title="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add the source title")
        self.assertFalse(Article.objects.filter(title="Adapted Article").exists())

    def test_article_create_requires_source_detail_for_inspired_article(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_create"),
            self.article_payload(
                title="Inspired Article",
                source_type=Article.SourceType.INSPIRED,
                source_title="",
                source_author="",
                source_url="",
                source_note="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add at least one source detail")
        self.assertFalse(Article.objects.filter(title="Inspired Article").exists())

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

    def test_article_detail_gallery_alt_text_prefers_explicit_alt(self):
        ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("bread.png"),
            alt_text="Irish brown bread served with butter",
            caption="A sliced loaf on a board",
            sort_order=1,
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(
            response.context["gallery_items"][0]["alt"],
            "Irish brown bread served with butter",
        )
        self.assertContains(response, 'alt="Irish brown bread served with butter"', html=False)

    def test_article_detail_gallery_alt_text_falls_back_to_caption(self):
        ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("bread.png"),
            caption="A sliced loaf on a board",
            sort_order=1,
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(response.context["gallery_items"][0]["alt"], "A sliced loaf on a board")
        self.assertContains(response, 'alt="A sliced loaf on a board"', html=False)

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

    def test_article_detail_header_uses_article_image_as_hero_background(self):
        self.article.hero_image.save("cover.png", self.uploaded_image("cover.png"), save=True)
        ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("gallery.png"),
            sort_order=1,
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(response.context["article_hero_image"].url, self.article.hero_image.url)
        self.assertContains(
            response,
            f"--detail-hero-image: url('{self.article.hero_image.url}');",
            html=False,
        )

    def test_article_detail_shows_management_actions_for_owner(self):
        self.client.force_login(self.owner_user)

        response = self.client.get(self.article.get_absolute_url())

        self.assertContains(response, "Edit Article")
        self.assertContains(response, "Delete Article")
        self.assertNotContains(response, ">Save</span>")
        self.assertFalse(response.context["can_collect_article"])

    def test_article_detail_shows_collection_action_for_approved_article(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        self.client.force_login(self.other_user)

        response = self.client.get(self.article.get_absolute_url())

        self.assertContains(response, ">Save</span>")
        self.assertNotContains(response, "Edit Article")
        self.assertTrue(response.context["can_collect_article"])

    def test_article_detail_displays_source_metadata(self):
        self.article.status = Article.Status.APPROVED
        self.article.source_type = Article.SourceType.ADAPTED
        self.article.source_title = "Irish Pantry Notes"
        self.article.source_author = "CulinEire Archive"
        self.article.source_url = "https://example.com/source"
        self.article.source_note = "Adapted for home cooks."
        self.article.save(
            update_fields=[
                "status",
                "source_type",
                "source_title",
                "source_author",
                "source_url",
                "source_note",
            ]
        )

        response = self.client.get(self.article.get_absolute_url())

        self.assertContains(response, "Credits &amp; Source")
        self.assertContains(response, "Adapted from a source")
        self.assertContains(response, "Irish Pantry Notes")
        self.assertContains(response, "CulinEire Archive")
        self.assertContains(response, "https://example.com/source")
        self.assertContains(response, "Adapted for home cooks.")

    def test_article_detail_marks_ai_generated_article_images(self):
        self.article.status = Article.Status.APPROVED
        self.article.image_rights_status = Article.ImageRightsStatus.AI_GENERATED
        self.article.save(update_fields=["status", "image_rights_status"])

        response = self.client.get(self.article.get_absolute_url())

        self.assertContains(response, ">AI<", html=False)
        self.assertNotContains(response, "AI Generated")
        self.assertContains(response, 'aria-label="AI generated image"', html=False)

    def test_article_moderation_block_confirm_escapes_username_for_javascript(self):
        self.owner_user.username = "o'brien"
        self.owner_user.save(update_fields=["username"])
        self.client.force_login(self.moderator_user)

        response = self.client.get(self.article.get_absolute_url())

        self.assertContains(response, "o\\u0027brien", html=False)
        self.assertNotContains(response, "Block user o'brien?", html=False)

    def test_article_detail_escapes_json_ld_script_breakouts(self):
        self.article.status = Article.Status.APPROVED
        self.article.title = 'Safe title </script><script>alert("x")</script>'
        self.article.slug = "safe-title"
        self.article.save(update_fields=["status", "title", "slug"])

        response = self.client.get(self.article.get_absolute_url())

        self.assertContains(response, "\\u003C/script\\u003E", html=False)
        self.assertNotContains(response, '</script><script>alert("x")</script>', html=False)

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
                **self.article_payload(image_rights_status=Article.ImageRightsStatus.OWN),
                "gallery_images": self.uploaded_image("new.png", color=(120, 40, 40)),
            },
        )

        self.assertRedirects(response, self.article.get_absolute_url())
        new_image = ArticleImage.objects.get(article=self.article, sort_order=8)
        self.assertEqual(new_image.sort_order, 8)

    def test_article_gallery_image_replacement_changes_image_url(self):
        gallery_image = ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("gallery.png"),
            sort_order=1,
        )
        original_url = gallery_image.image.url

        gallery_image.image = self.uploaded_image("gallery.png", color=(120, 40, 40))
        gallery_image.save()
        gallery_image.refresh_from_db()

        self.assertNotEqual(gallery_image.image.url, original_url)
        self.assertIn("/img1-", gallery_image.image.url)

    def test_article_edit_rejects_invalid_gallery_image_before_saving(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            {
                **self.article_payload(
                    title="Should Not Save",
                    image_rights_status=Article.ImageRightsStatus.OWN,
                ),
                "gallery_images": self.uploaded_invalid_image(),
            },
        )

        self.article.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gallery image broken.png")
        self.assertEqual(self.article.title, "Original Article")
        self.assertFalse(ArticleImage.objects.filter(article=self.article).exists())

    def test_article_edit_rolls_back_if_gallery_save_fails(self):
        self.client.force_login(self.owner_user)
        self.client.raise_request_exception = False

        with patch(
            "articles.views.ArticleImage.objects.create",
            side_effect=RuntimeError("gallery save failed"),
        ):
            response = self.client.post(
                reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
                {
                    **self.article_payload(
                        title="Half Saved Edit",
                        image_rights_status=Article.ImageRightsStatus.OWN,
                    ),
                    "gallery_images": self.uploaded_image("gallery.png"),
                },
            )

        self.article.refresh_from_db()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.article.title, "Original Article")
        self.assertFalse(ArticleImage.objects.filter(article=self.article).exists())

    def test_article_edit_rejects_not_applicable_rights_with_gallery_upload(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            {
                **self.article_payload(
                    title="Should Not Save",
                    image_rights_status=Article.ImageRightsStatus.NOT_APPLICABLE,
                ),
                "gallery_images": self.uploaded_image("gallery.png"),
            },
        )

        self.article.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose the correct image rights status")
        self.assertEqual(self.article.title, "Original Article")
        self.assertFalse(ArticleImage.objects.filter(article=self.article).exists())

    def test_article_edit_rejects_not_applicable_rights_with_existing_gallery(self):
        ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("existing-gallery.png"),
            sort_order=1,
        )
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(
                title="Should Not Save",
                image_rights_status=Article.ImageRightsStatus.NOT_APPLICABLE,
            ),
        )

        self.article.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose the correct image rights status")
        self.assertEqual(self.article.title, "Original Article")

    def test_article_edit_rejects_not_applicable_rights_with_hero_image(self):
        self.article.hero_image.save("cover.png", self.uploaded_image("cover.png"), save=True)
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(
                title="Should Not Save",
                image_rights_status=Article.ImageRightsStatus.NOT_APPLICABLE,
            ),
        )

        self.article.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose the correct image rights status")
        self.assertEqual(self.article.title, "Original Article")

    def test_article_edit_replacing_hero_image_changes_card_image_url(self):
        self.article.hero_image.save("cover.png", self.uploaded_image("cover.png"), save=True)
        original_url = self.article.hero_image.url
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            {
                **self.article_payload(image_rights_status=Article.ImageRightsStatus.OWN),
                "hero_image": self.uploaded_image("cover.png", color=(120, 40, 40)),
            },
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertNotEqual(self.article.hero_image.url, original_url)
        self.assertIn("/cover-", self.article.hero_image.url)

    def test_article_edit_shows_delete_button_for_current_article_image(self):
        self.article.hero_image.save("cover.png", self.uploaded_image("cover.png"), save=True)
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )

        self.assertContains(
            response,
            reverse("articles:delete_hero_image", kwargs={"slug": self.article.slug}),
        )
        self.assertContains(response, 'id="delete-article-hero-image"', html=False)
        self.assertContains(response, 'form="delete-article-hero-image"', html=False)
        self.assertContains(response, 'aria-label="Delete current article image"', html=False)

    def test_author_can_delete_own_article_image(self):
        self.article.status = Article.Status.APPROVED
        self.article.hero_image.save("cover.png", self.uploaded_image("cover.png"), save=True)
        image_name = self.article.hero_image.name
        storage = self.article.hero_image.storage
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:delete_hero_image", kwargs={"slug": self.article.slug}),
        )

        self.article.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )
        self.assertFalse(self.article.hero_image)
        self.assertEqual(self.article.status, Article.Status.APPROVED)
        self.assertFalse(storage.exists(image_name))

    def test_author_cannot_delete_another_authors_article_image(self):
        self.article.hero_image.save("cover.png", self.uploaded_image("cover.png"), save=True)
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse("articles:delete_hero_image", kwargs={"slug": self.article.slug}),
        )

        self.article.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertTrue(self.article.hero_image)

    def test_article_edit_shows_delete_button_for_existing_gallery_images(self):
        gallery_image = ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("gallery.png"),
            sort_order=1,
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )

        self.assertContains(
            response,
            reverse("articles:delete_gallery_image", kwargs={"image_id": gallery_image.pk}),
        )
        self.assertContains(response, f'id="delete-gallery-image-{gallery_image.pk}"', html=False)
        self.assertContains(response, f'form="delete-gallery-image-{gallery_image.pk}"', html=False)
        self.assertContains(response, 'aria-label="Delete gallery image 1"', html=False)

    def test_author_can_delete_own_article_gallery_image(self):
        gallery_image = ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("gallery.png"),
            sort_order=1,
        )
        image_name = gallery_image.image.name
        storage = gallery_image.image.storage
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:delete_gallery_image", kwargs={"image_id": gallery_image.pk}),
        )

        self.assertRedirects(
            response,
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )
        self.assertFalse(ArticleImage.objects.filter(pk=gallery_image.pk).exists())
        self.assertFalse(storage.exists(image_name))

    def test_author_gallery_delete_keeps_live_article_approved(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        gallery_image = ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("gallery.png"),
            sort_order=1,
        )
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:delete_gallery_image", kwargs={"image_id": gallery_image.pk}),
        )

        self.article.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )
        self.assertEqual(self.article.status, Article.Status.APPROVED)
        self.assertFalse(ArticleImage.objects.filter(pk=gallery_image.pk).exists())

    def test_author_cannot_delete_another_authors_gallery_image(self):
        gallery_image = ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("gallery.png"),
            sort_order=1,
        )
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse("articles:delete_gallery_image", kwargs={"image_id": gallery_image.pk}),
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(ArticleImage.objects.filter(pk=gallery_image.pk).exists())

    def test_moderator_can_delete_gallery_image_without_returning_article_to_review(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        gallery_image = ArticleImage.objects.create(
            article=self.article,
            image=self.uploaded_image("gallery.png"),
            sort_order=1,
        )
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:delete_gallery_image", kwargs={"image_id": gallery_image.pk}),
        )

        self.article.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
        )
        self.assertEqual(self.article.status, Article.Status.APPROVED)
        self.assertFalse(ArticleImage.objects.filter(pk=gallery_image.pk).exists())

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
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_deleted)

    def test_article_delete_confirmation_uses_article_author_for_moderator(self):
        self.client.force_login(self.moderator_user)

        response = self.client.get(
            reverse("articles:article_delete", kwargs={"slug": self.article.slug}),
        )

        self.assertEqual(response.context["author"], self.owner_author)
        self.assertContains(response, self.owner_author.name)

    def test_article_delete_shows_success_message(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_delete", kwargs={"slug": self.article.slug}),
            follow=True,
        )

        self.assertContains(response, "Article deleted.")

    def test_non_moderator_cannot_moderate_article(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "approve"},
        )

        self.article.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.article.status, Article.Status.PENDING)

    def test_moderator_can_approve_article(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "approve"},
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.APPROVED)

    def test_moderator_can_reject_article(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "reject", "moderation_note": "Please revise the body."},
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.REJECTED)

    def test_article_status_includes_needs_changes(self):
        self.assertIn(Article.Status.NEEDS_CHANGES, Article.Status.values)
        self.assertEqual(Article.Status.NEEDS_CHANGES.label, "Needs changes")

    def test_article_status_includes_draft(self):
        self.assertIn(Article.Status.DRAFT, Article.Status.values)
        self.assertEqual(Article.Status.DRAFT.label, "Draft")

    def test_author_can_create_article_as_draft(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_create"),
            {**self.article_payload(title="Draft Article"), "action": "save_draft"},
        )

        article = Article.objects.get(title="Draft Article")
        self.assertRedirects(response, article.get_absolute_url())
        self.assertEqual(article.status, Article.Status.DRAFT)

    def test_author_can_submit_new_article_for_review(self):
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_create"),
            {**self.article_payload(title="Submitted Article"), "action": "submit_review"},
        )

        article = Article.objects.get(title="Submitted Article")
        self.assertRedirects(response, article.get_absolute_url())
        self.assertEqual(article.status, Article.Status.PENDING)

    def test_draft_article_is_hidden_from_public_list_and_direct_url(self):
        article = self.create_article("Draft Article", Article.Status.DRAFT)

        list_response = self.client.get(reverse("articles:article_list"))
        detail_response = self.client.get(article.get_absolute_url())

        self.assertNotContains(list_response, "Draft Article")
        self.assertEqual(detail_response.status_code, 404)

    def test_article_owner_and_moderator_can_view_draft_article(self):
        self.article.status = Article.Status.DRAFT
        self.article.save(update_fields=["status"])

        self.client.force_login(self.owner_user)
        owner_response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(owner_response.status_code, 200)

        self.client.force_login(self.moderator_user)
        moderator_response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(moderator_response.status_code, 200)

    def test_author_can_submit_draft_article_for_review(self):
        self.article.status = Article.Status.DRAFT
        self.article.save(update_fields=["status"])
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            {**self.article_payload(), "action": "submit_review"},
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.PENDING)

    def test_author_can_save_needs_changes_article_as_draft_and_keep_note(self):
        self.article.status = Article.Status.NEEDS_CHANGES
        self.article.moderation_note = "Clarify source."
        self.article.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.owner_user)

        self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            {**self.article_payload(), "action": "save_draft"},
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.DRAFT)
        self.assertEqual(self.article.moderation_note, "Clarify source.")

    def test_author_can_submit_rejected_article_for_review_and_keep_note(self):
        self.article.status = Article.Status.REJECTED
        self.article.moderation_note = "Rejected note."
        self.article.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.owner_user)

        self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            {**self.article_payload(), "action": "submit_review"},
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.PENDING)
        self.assertEqual(self.article.moderation_note, "Rejected note.")

    def test_approved_article_cannot_be_saved_as_draft_by_author(self):
        self.article.status = Article.Status.APPROVED
        self.article.save(update_fields=["status"])
        self.client.force_login(self.owner_user)

        self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            {**self.article_payload(), "action": "save_draft"},
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.PENDING)

    def test_moderator_can_request_article_changes_with_note(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "request_changes", "moderation_note": "Clarify the source attribution."},
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.NEEDS_CHANGES)
        self.assertEqual(self.article.moderation_note, "Clarify the source attribution.")
        self.assertEqual(self.article.moderated_by, self.moderator_user)
        self.assertIsNotNone(self.article.moderated_at)

    def test_article_request_changes_without_note_is_blocked(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "request_changes"},
            follow=True,
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.PENDING)
        self.assertIsNone(self.article.moderated_by)
        self.assertIsNone(self.article.moderated_at)
        self.assertContains(response, "moderation note is required")

    def test_needs_changes_article_is_hidden_from_public_list_and_direct_url(self):
        article = self.create_article("Needs Changes Article", Article.Status.NEEDS_CHANGES)

        list_response = self.client.get(reverse("articles:article_list"))
        detail_response = self.client.get(article.get_absolute_url())

        self.assertNotContains(list_response, "Needs Changes Article")
        self.assertEqual(detail_response.status_code, 404)

    def test_article_owner_and_moderator_can_view_needs_changes_article(self):
        self.article.status = Article.Status.NEEDS_CHANGES
        self.article.moderation_note = "Please add a clearer introduction."
        self.article.moderated_by = self.moderator_user
        self.article.save(update_fields=["status", "moderation_note", "moderated_by"])

        self.client.force_login(self.owner_user)
        owner_response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(owner_response.status_code, 200)
        self.assertContains(owner_response, "Please add a clearer introduction.")
        self.assertContains(owner_response, "Requested changes")

        self.client.force_login(self.moderator_user)
        moderator_response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(moderator_response.status_code, 200)
        self.assertContains(moderator_response, "Please add a clearer introduction.")

    def test_public_visitor_cannot_see_article_needs_changes_note(self):
        self.article.status = Article.Status.NEEDS_CHANGES
        self.article.moderation_note = "Private correction note."
        self.article.save(update_fields=["status", "moderation_note"])

        response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(response.status_code, 404)

    def test_author_edit_of_needs_changes_article_returns_to_pending_and_keeps_note(self):
        self.article.status = Article.Status.NEEDS_CHANGES
        self.article.moderation_note = "Clarify the source attribution."
        self.article.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("articles:article_edit", kwargs={"slug": self.article.slug}),
            self.article_payload(),
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.PENDING)
        self.assertEqual(self.article.moderation_note, "Clarify the source attribution.")

    def test_article_approve_after_needs_changes_clears_note(self):
        self.article.status = Article.Status.NEEDS_CHANGES
        self.article.moderation_note = "Clarify the source attribution."
        self.article.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.moderator_user)

        self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "approve"},
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.APPROVED)
        self.assertEqual(self.article.moderation_note, "")

    def test_moderator_can_delete_article_from_moderation_endpoint(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "delete"},
        )

        self.assertRedirects(response, reverse("recipes:moderation_panel"))
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_deleted)

    def test_article_moderation_rejects_unknown_actions(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "block"},
        )

        self.article.refresh_from_db()
        self.owner_user.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.article.status, Article.Status.PENDING)
        self.assertTrue(self.owner_user.is_active)

    def test_moderator_can_reject_article_and_message_author(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("messaging:send_message"),
            {
                "action": "reject_and_message",
                "recipient_id": self.owner_user.pk,
                "article_id": self.article.pk,
                "subject": f"Your article: {self.article.title}",
                "body": "Please revise this article.",
                "next": self.article.get_absolute_url(),
            },
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.REJECTED)
        self.assertTrue(
            Message.objects.filter(
                sender=self.moderator_user,
                recipient=self.owner_user,
                related_article=self.article,
                body="Please revise this article.",
            ).exists()
        )

    def test_article_reject_message_uses_article_author_as_recipient(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("messaging:send_message"),
            {
                "action": "reject_and_message",
                "recipient_id": self.other_user.pk,
                "article_id": self.article.pk,
                "subject": f"Your article: {self.article.title}",
                "body": "Please revise this article.",
                "next": self.article.get_absolute_url(),
            },
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.REJECTED)
        self.assertTrue(
            Message.objects.filter(
                sender=self.moderator_user,
                recipient=self.owner_user,
                related_article=self.article,
                body="Please revise this article.",
            ).exists()
        )
        self.assertFalse(
            Message.objects.filter(
                sender=self.moderator_user,
                recipient=self.other_user,
                related_article=self.article,
            ).exists()
        )

    def test_recipe_reject_message_uses_recipe_author_as_recipient(self):
        recipe = Recipe.objects.create(
            title="Original Recipe",
            slug="original-recipe",
            author=self.owner_author,
            short_description="Original recipe",
            ingredients="Potatoes",
            method="Cook.",
            status=Recipe.Status.PENDING,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("messaging:send_message"),
            {
                "action": "reject_and_message",
                "recipient_id": self.other_user.pk,
                "recipe_id": recipe.pk,
                "subject": f"Your recipe: {recipe.title}",
                "body": "Please revise this recipe.",
                "next": recipe.get_absolute_url(),
            },
        )

        recipe.refresh_from_db()
        self.assertRedirects(response, recipe.get_absolute_url())
        self.assertEqual(recipe.status, Recipe.Status.REJECTED)
        self.assertTrue(
            Message.objects.filter(
                sender=self.moderator_user,
                recipient=self.owner_user,
                related_recipe=recipe,
                body="Please revise this recipe.",
            ).exists()
        )
        self.assertFalse(
            Message.objects.filter(
                sender=self.moderator_user,
                recipient=self.other_user,
                related_recipe=recipe,
            ).exists()
        )

    def test_reject_message_rejects_ambiguous_recipe_and_article_targets(self):
        recipe = Recipe.objects.create(
            title="Original Recipe",
            slug="original-recipe",
            author=self.owner_author,
            short_description="Original recipe",
            ingredients="Potatoes",
            method="Cook.",
            status=Recipe.Status.PENDING,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("messaging:send_message"),
            {
                "action": "reject_and_message",
                "recipient_id": self.owner_user.pk,
                "recipe_id": recipe.pk,
                "article_id": self.article.pk,
                "subject": "Mixed target",
                "body": "Please revise this content.",
                "next": self.article.get_absolute_url(),
            },
        )

        self.article.refresh_from_db()
        recipe.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.PENDING)
        self.assertEqual(recipe.status, Recipe.Status.PENDING)
        self.assertFalse(Message.objects.filter(body="Please revise this content.").exists())

    def test_article_admin_form_rejects_profanity_in_title(self):
        form = ArticleAdminForm(data=self.admin_payload(title="bastard article"))

        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("bastard", str(form.errors["title"]))

    def test_article_admin_form_rejects_profanity_in_body(self):
        form = ArticleAdminForm(data=self.admin_payload(body="This article is bastard content."))

        self.assertFalse(form.is_valid())
        self.assertIn("body", form.errors)

    def test_article_admin_form_requires_image_rights_note_for_public_domain(self):
        form = ArticleAdminForm(
            data=self.admin_payload(
                image_rights_status=Article.ImageRightsStatus.PUBLIC_DOMAIN,
                image_rights_note="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image_rights_note", form.errors)

    # ── Phase 2: Moderation Tracking ─────────────────────────────────────────

    def test_article_reject_without_note_is_blocked(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "reject"},
            follow=True,
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.PENDING)
        self.assertContains(response, "rejection note is required")

    def test_article_reject_saves_tracking_fields(self):
        self.client.force_login(self.moderator_user)

        self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "reject", "moderation_note": "Needs more detail."},
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.REJECTED)
        self.assertEqual(self.article.moderation_note, "Needs more detail.")
        self.assertEqual(self.article.moderated_by, self.moderator_user)
        self.assertIsNotNone(self.article.moderated_at)

    def test_article_approve_clears_moderation_note(self):
        self.article.status = Article.Status.REJECTED
        self.article.moderation_note = "Old note."
        self.article.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.moderator_user)

        self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "approve"},
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.APPROVED)
        self.assertEqual(self.article.moderation_note, "")
        self.assertEqual(self.article.moderated_by, self.moderator_user)
        self.assertIsNotNone(self.article.moderated_at)

    def test_article_reject_and_message_saves_note(self):
        self.client.force_login(self.moderator_user)

        self.client.post(
            reverse("messaging:send_message"),
            {
                "action": "reject_and_message",
                "recipient_id": self.owner_user.pk,
                "article_id": self.article.pk,
                "subject": f"Your article: {self.article.title}",
                "body": "The images need proper rights documentation.",
                "next": self.article.get_absolute_url(),
            },
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.REJECTED)
        self.assertEqual(self.article.moderation_note, "The images need proper rights documentation.")
        self.assertEqual(self.article.moderated_by, self.moderator_user)
        self.assertIsNotNone(self.article.moderated_at)

    def test_article_rejection_note_shown_to_author(self):
        self.article.status = Article.Status.REJECTED
        self.article.moderation_note = "Please expand the introduction."
        self.article.moderated_by = self.moderator_user
        self.article.save(update_fields=["status", "moderation_note", "moderated_by"])
        self.client.force_login(self.owner_user)

        response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please expand the introduction.")
        self.assertContains(response, "Rejection note")

    def test_article_rejection_note_hidden_from_public(self):
        self.article.status = Article.Status.REJECTED
        self.article.moderation_note = "Please expand the introduction."
        self.article.save(update_fields=["status", "moderation_note"])

        response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(response.status_code, 404)


class ArticlePhase3ReadingTimeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        author_user = user_model.objects.create_user(username="rtauthor", password="pass")
        self.author = RecipeAuthor.objects.create(user=author_user, name="RT Author", slug="rt-author")

    def test_reading_time_helper_returns_one_for_short_text(self):
        self.assertEqual(_reading_time_minutes("short text"), 1)

    def test_reading_time_helper_calculates_correct_value(self):
        body = " ".join(["word"] * 400)

        self.assertEqual(_reading_time_minutes(body), 2)

    def test_reading_time_in_article_detail_context(self):
        article = Article.objects.create(
            title="RT Test Article",
            slug="rt-test-article",
            author=self.author,
            body=" ".join(["word"] * 600),
            published=date(2026, 5, 21),
            status=Article.Status.APPROVED,
        )

        response = self.client.get(article.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["reading_time"], 3)

    def test_reading_time_is_at_least_one_for_empty_body(self):
        self.assertEqual(_reading_time_minutes(""), 1)


class ArticlePhase32AltTextTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        author_user = user_model.objects.create_user(username="altwriter", password="pass")
        self.author = RecipeAuthor.objects.create(user=author_user, name="Alt Writer", slug="alt-writer")

    def test_hero_image_alt_text_field_saved_and_retrieved(self):
        article = Article.objects.create(
            title="Alt Text Article",
            slug="alt-text-article",
            author=self.author,
            body="Body text.",
            published=date(2026, 5, 21),
            hero_image_alt_text="A bowl of Irish stew on a stone table",
            status=Article.Status.APPROVED,
        )

        article.refresh_from_db()
        self.assertEqual(article.hero_image_alt_text, "A bowl of Irish stew on a stone table")

    def test_hero_image_alt_text_defaults_to_blank(self):
        article = Article.objects.create(
            title="No Alt Article",
            slug="no-alt-article",
            author=self.author,
            body="Body text.",
            published=date(2026, 5, 21),
            status=Article.Status.APPROVED,
        )

        self.assertEqual(article.hero_image_alt_text, "")

    def test_hero_image_alt_text_in_authoring_form_fields(self):
        from .forms import ArticleAuthoringForm

        self.assertIn("hero_image_alt_text", ArticleAuthoringForm.Meta.fields)

    def test_gallery_alt_lines_splits_on_newlines(self):
        post_data = {"gallery_alt_texts": "First image alt\nSecond image alt\n"}

        lines = _gallery_alt_lines(post_data)

        self.assertEqual(lines, ["First image alt", "Second image alt"])

    def test_gallery_alt_lines_reads_repeated_inputs(self):
        post_data = QueryDict("", mutable=True)
        post_data.update({"gallery_alt_texts": "First image alt"})
        post_data.update({"gallery_alt_texts": "Second image alt"})

        lines = _gallery_alt_lines(post_data)

        self.assertEqual(lines, ["First image alt", "Second image alt"])

    def test_gallery_alt_lines_returns_empty_list_when_missing(self):
        self.assertEqual(_gallery_alt_lines({}), [])

    def test_image_alt_text_helper_prefers_explicit_alt(self):
        class MockArticle:
            title = "Mock Article"

        self.assertEqual(
            ArticleDetailView._image_alt_text(MockArticle(), "Custom descriptive text"),
            "Custom descriptive text",
        )

    def test_image_alt_text_helper_falls_back_to_title(self):
        class MockArticle:
            title = "Mock Article"

        self.assertEqual(
            ArticleDetailView._image_alt_text(MockArticle()),
            "Mock Article image",
        )


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ArticleSoftDeleteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner_user = User.objects.create_user(username="sd_owner", password="pass")
        self.owner_author = RecipeAuthor.objects.create(
            user=self.owner_user, name="SD Owner", slug="sd-owner"
        )
        self.other_user = User.objects.create_user(username="sd_other", password="pass")
        self.other_author = RecipeAuthor.objects.create(
            user=self.other_user, name="SD Other", slug="sd-other"
        )
        self.moderator_user = User.objects.create_user(
            username="sd_mod", password="pass", is_staff=True
        )
        self.moderator_author = RecipeAuthor.objects.create(
            user=self.moderator_user, name="SD Mod", slug="sd-mod"
        )
        self.article = Article.objects.create(
            title="Soft Delete Article",
            slug="soft-delete-article",
            author=self.owner_author,
            body="Body content.",
            published=date(2026, 5, 20),
            status=Article.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )

    # ── Soft delete mechanics ────────────────────────────────────────────────

    def test_author_delete_view_soft_deletes(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse("articles:article_delete", kwargs={"slug": self.article.slug})
        )
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_deleted)
        self.assertIsNotNone(self.article.deleted_at)
        self.assertEqual(self.article.deleted_by, self.owner_user)

    def test_moderator_delete_view_soft_deletes(self):
        self.client.force_login(self.moderator_user)
        response = self.client.post(
            reverse("articles:article_delete", kwargs={"slug": self.article.slug})
        )
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_deleted)
        self.assertEqual(self.article.deleted_by, self.moderator_user)

    def test_soft_delete_helper_sets_all_fields(self):
        _soft_delete_article(self.article, self.owner_user)
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_deleted)
        self.assertIsNotNone(self.article.deleted_at)
        self.assertEqual(self.article.deleted_by, self.owner_user)

    def test_non_owner_cannot_delete_others_article(self):
        self.client.force_login(self.other_user)
        self.client.post(
            reverse("articles:article_delete", kwargs={"slug": self.article.slug})
        )
        self.article.refresh_from_db()
        self.assertFalse(self.article.is_deleted)

    # ── Public visibility ────────────────────────────────────────────────────

    def test_deleted_approved_article_hidden_from_list(self):
        _soft_delete_article(self.article, self.owner_user)
        response = self.client.get(reverse("articles:article_list"))
        self.assertNotIn(self.article, response.context["object_list"])

    def test_deleted_approved_article_direct_url_returns_404(self):
        _soft_delete_article(self.article, self.owner_user)
        response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_deleted_article_excluded_from_sitemap(self):
        _soft_delete_article(self.article, self.owner_user)
        response = self.client.get(reverse("sitemap_xml"))
        self.assertNotIn(self.article.slug, response.content.decode())

    def test_deleted_article_excluded_from_public_author_profile(self):
        _soft_delete_article(self.article, self.owner_user)
        response = self.client.get(
            reverse("recipes:author_detail", kwargs={"slug": self.owner_author.slug})
        )
        dashboard_articles = response.context.get("dashboard_articles", [])
        self.assertNotIn(self.article, dashboard_articles)

    def test_deleted_article_excluded_from_related_articles(self):
        recipe = Recipe.objects.create(
            title="Test Recipe",
            slug="test-recipe-sd",
            author=self.owner_author,
            status=Recipe.Status.APPROVED,
            ingredients="x",
            method="y",
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )
        self.article.related_recipe = recipe
        self.article.save(update_fields=["related_recipe"])
        _soft_delete_article(self.article, self.owner_user)
        response = self.client.get(recipe.get_absolute_url())
        related = response.context.get("related_articles", [])
        self.assertNotIn(self.article, related)

    def test_deleted_article_cannot_be_saved_to_collection(self):
        _soft_delete_article(self.article, self.owner_user)
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse("collection:add_article", kwargs={"slug": self.article.slug}),
            {"next": "/"},
        )
        self.assertEqual(response.status_code, 404)

    # ── Non-deleted content unaffected ───────────────────────────────────────

    def test_approved_not_deleted_article_still_public(self):
        response = self.client.get(reverse("articles:article_list"))
        self.assertIn(self.article, response.context["object_list"])

    def test_approved_not_deleted_article_detail_accessible(self):
        response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 200)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 5 — editorial_format filter unit tests
# ══════════════════════════════════════════════════════════════════════════════

class EditorialFormatFilterTests(TestCase):
    """Unit tests for articles.templatetags.article_filters.editorial_format."""

    def _render(self, text):
        from articles.templatetags.article_filters import editorial_format
        return editorial_format(text)

    # ── Basic paragraph rendering ─────────────────────────────────────────────

    def test_plain_text_renders_as_lead_paragraph(self):
        result = self._render("A plain paragraph of text.")
        self.assertIn('<p class="lead">', result)
        self.assertIn("A plain paragraph of text.", result)

    def test_two_paragraphs_first_is_lead(self):
        result = self._render("First paragraph.\n\nSecond paragraph.")
        self.assertIn('<p class="lead">First paragraph.</p>', result)
        self.assertIn('<p>Second paragraph.</p>', result)

    def test_empty_string_returns_empty(self):
        result = self._render("")
        self.assertEqual(result, "")

    def test_none_returns_empty(self):
        result = self._render(None)
        self.assertEqual(result, "")

    def test_single_newlines_within_para_become_br(self):
        result = self._render("Line one\nLine two")
        self.assertIn("<br>", result)
        self.assertIn("Line one", result)
        self.assertIn("Line two", result)

    # ── Headings ──────────────────────────────────────────────────────────────

    def test_h2_heading_rendered(self):
        result = self._render("## My Section")
        self.assertIn("<h2>My Section</h2>", result)
        self.assertNotIn("<p", result)

    def test_h3_heading_rendered(self):
        result = self._render("### My Sub-Section")
        self.assertIn("<h3>My Sub-Section</h3>", result)
        self.assertNotIn("<p", result)

    def test_h2_followed_by_paragraph(self):
        result = self._render("## Intro\n\nSome text here.")
        self.assertIn("<h2>Intro</h2>", result)
        self.assertIn("<p", result)
        self.assertIn("Some text here.", result)

    def test_first_para_after_heading_is_lead(self):
        result = self._render("## Section\n\nFirst real paragraph.")
        self.assertIn('<p class="lead">First real paragraph.</p>', result)

    # ── Blockquote ────────────────────────────────────────────────────────────

    def test_blockquote_rendered(self):
        result = self._render("> A wise observation.")
        self.assertIn("<blockquote>", result)
        self.assertIn("<p>A wise observation.</p>", result)

    def test_multiline_blockquote(self):
        result = self._render("> Line one\n> Line two")
        self.assertIn("<blockquote>", result)
        self.assertIn("Line one", result)
        self.assertIn("Line two", result)

    # ── Lists ─────────────────────────────────────────────────────────────────

    def test_dash_list_rendered_as_ul(self):
        result = self._render("- First item\n- Second item")
        self.assertIn("<ul>", result)
        self.assertIn("<li>First item</li>", result)
        self.assertIn("<li>Second item</li>", result)

    def test_asterisk_list_rendered_as_ul(self):
        result = self._render("* Alpha\n* Beta")
        self.assertIn("<ul>", result)
        self.assertIn("<li>Alpha</li>", result)

    # ── XSS safety ───────────────────────────────────────────────────────────

    def test_script_tag_in_body_is_escaped(self):
        result = self._render("<script>alert('xss')</script>")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_html_in_heading_is_escaped(self):
        result = self._render("## <b>Bold</b> Title")
        self.assertNotIn("<b>", result)
        self.assertIn("&lt;b&gt;", result)

    def test_html_in_list_item_is_escaped(self):
        result = self._render('- <img src=x onerror="alert(1)">')
        self.assertNotIn("<img", result)
        self.assertIn("&lt;img", result)

    def test_html_in_blockquote_is_escaped(self):
        result = self._render('> <strong>Bold</strong>')
        self.assertNotIn("<strong>", result)
        self.assertIn("&lt;strong&gt;", result)

    def test_ampersand_escaped(self):
        result = self._render("Fish & chips.")
        self.assertIn("Fish &amp; chips.", result)

    # ── Output is mark_safe ───────────────────────────────────────────────────

    def test_output_is_mark_safe(self):
        from django.utils.safestring import SafeString
        result = self._render("Some text.")
        self.assertIsInstance(result, SafeString)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 5 — article detail integration tests (editorial renderer + checklist)
# ══════════════════════════════════════════════════════════════════════════════

@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ArticleEditorialDetailTests(TestCase):
    """Integration tests for editorial_format rendering on the article detail page."""

    def setUp(self):
        User = get_user_model()
        self.author_user = User.objects.create_user(username="ed_author", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user, name="Ed Author", slug="ed-author"
        )
        self.article = Article.objects.create(
            title="Editorial Test Article",
            slug="editorial-test-article",
            author=self.author,
            excerpt="Test excerpt",
            body=(
                "## Opening Section\n\n"
                "First paragraph with enough text to be the lead.\n\n"
                "> An editorial quote from someone.\n\n"
                "- Bullet one\n"
                "- Bullet two\n\n"
                "### Sub-section\n\n"
                "Another paragraph of body text."
            ),
            published=date(2026, 5, 1),
            status=Article.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )

    def _get(self):
        return self.client.get(self.article.get_absolute_url())

    def test_article_detail_returns_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_h2_rendered_on_detail_page(self):
        response = self._get()
        self.assertContains(response, "<h2>Opening Section</h2>")

    def test_h3_rendered_on_detail_page(self):
        response = self._get()
        self.assertContains(response, "<h3>Sub-section</h3>")

    def test_blockquote_rendered_on_detail_page(self):
        response = self._get()
        self.assertContains(response, "<blockquote>")
        self.assertContains(response, "An editorial quote from someone.")

    def test_list_rendered_on_detail_page(self):
        response = self._get()
        self.assertContains(response, "<ul>")
        self.assertContains(response, "<li>Bullet one</li>")

    def test_lead_paragraph_class_present(self):
        response = self._get()
        self.assertContains(response, 'class="lead"')

    def test_no_raw_linebreaks_filter_output(self):
        # The old |linebreaks filter wraps every double-newline in </p><p>
        # The new filter produces proper semantic elements.
        # Verify the body block-level element order makes structural sense.
        response = self._get()
        content = response.content.decode()
        # h2 should appear before the lead paragraph
        self.assertLess(content.index("<h2>"), content.index('class="lead"'))

    def test_xss_body_is_safe_on_detail_page(self):
        self.article.body = "<script>alert('xss')</script>"
        self.article.save(update_fields=["body"])
        response = self._get()
        self.assertNotContains(response, "<script>alert")
        self.assertContains(response, "&lt;script&gt;")

    def test_editorial_checklist_visible_to_author(self):
        self.client.force_login(self.author_user)
        response = self._get()
        self.assertContains(response, "Editorial checklist")

    def test_editorial_checklist_hidden_from_public(self):
        response = self._get()
        self.assertNotContains(response, "Editorial checklist")

    def test_editorial_hints_in_context(self):
        self.client.force_login(self.author_user)
        response = self._get()
        self.assertIn("editorial_hints", response.context)
        hints = response.context["editorial_hints"]
        self.assertIn("has_excerpt", hints)
        self.assertIn("has_section_headings", hints)

    def test_editorial_hints_detects_section_headings(self):
        self.client.force_login(self.author_user)
        response = self._get()
        self.assertTrue(response.context["editorial_hints"]["has_section_headings"])

    def test_editorial_hints_detects_missing_headings(self):
        self.article.body = "Just a plain paragraph with no headings at all."
        self.article.save(update_fields=["body"])
        self.client.force_login(self.author_user)
        response = self._get()
        self.assertFalse(response.context["editorial_hints"]["has_section_headings"])


# ── Part H: Editorial Automation Toolkit Tests ────────────────────────────────

import json as _json

from articles.services.editorial_tools import (
    _clean_list_field,
    _clean_method_field,
    _clean_plain_field,
    _FALLBACK_HEADINGS,
    _has_h2,
    _normalize_body,
    _score_para_theme,
    _SECTION_THEMES,
    _split_long_blocks,
    render_article_preview,
    render_recipe_preview,
    suggest_article_body,
    suggest_recipe_fields,
)


class SuggestArticleBodyTests(TestCase):
    """Unit tests for articles.services.editorial_tools.suggest_article_body."""

    def test_returns_empty_for_empty_body(self):
        self.assertEqual(suggest_article_body("T", "E", ""), "")

    def test_returns_body_unchanged_if_already_has_headings(self):
        body = "## Intro\n\nSome text here that is already structured."
        result = suggest_article_body("T", "E", body)
        self.assertIn("## Intro", result)
        # Should still be returned (cleaned/unchanged)
        self.assertIn("Some text", result)

    def test_short_body_returned_unchanged(self):
        body = "Short text."
        result = suggest_article_body("T", "E", body)
        self.assertEqual(result, "Short text.")

    def test_long_body_gets_headings_inserted(self):
        # Build a body > 300 words with no ## headings
        para = "This is a paragraph about Irish food culture and tradition. " * 10
        body = "\n\n".join([para] * 6)
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertIn("##", result)

    def test_inserted_headings_come_from_allowed_list(self):
        all_allowed = {t["heading"] for t in _SECTION_THEMES} | set(_FALLBACK_HEADINGS)
        para = "This is a paragraph about Irish food culture and tradition. " * 10
        body = "\n\n".join([para] * 6)
        result = suggest_article_body("Title", "Excerpt", body)
        inserted = [ln[3:] for ln in result.splitlines() if ln.startswith("## ")]
        self.assertTrue(inserted, "Expected at least one heading to be inserted")
        for heading in inserted:
            self.assertIn(heading, all_allowed, f"Unexpected heading in output: {heading!r}")

    # ── Editorial quality tests (task spec) ──────────────────────────────────

    def test_no_bare_introduction_heading(self):
        para = "This is a paragraph about Irish food culture and tradition. " * 15
        body = "\n\n".join([para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertNotIn("## Introduction", result)

    def test_no_background_heading(self):
        para = "This is a paragraph about Irish food culture and tradition. " * 15
        body = "\n\n".join([para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertNotIn("## Background", result)

    def test_no_modern_revival_heading(self):
        para = "This is a paragraph about Irish food culture and tradition. " * 15
        body = "\n\n".join([para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertNotIn("## Modern Revival", result)

    def test_first_paragraph_is_lead_before_first_heading(self):
        para = "This is a paragraph about Irish food culture and tradition. " * 15
        body = "\n\n".join([para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        lines = result.splitlines()
        first_para_idx = next(
            (i for i, ln in enumerate(lines) if ln.strip() and not ln.startswith("#")),
            None,
        )
        first_h2_idx = next(
            (i for i, ln in enumerate(lines) if ln.startswith("## ")),
            None,
        )
        if first_h2_idx is not None:
            self.assertIsNotNone(first_para_idx)
            self.assertLess(
                first_para_idx,
                first_h2_idx,
                "First paragraph must appear before the first ## heading",
            )

    def test_blank_lines_around_headings(self):
        para = "This is a paragraph about Irish food culture and tradition. " * 15
        body = "\n\n".join([para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        if "## " not in result:
            return
        lines = result.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("## ") and i > 0:
                self.assertEqual(
                    lines[i - 1].strip(),
                    "",
                    f"Expected blank line before heading at line {i}: {line!r}",
                )

    def test_short_article_not_over_formatted(self):
        # ~400 words, single dominant theme: algorithm should produce only 1 heading
        # (one theme group after the lead), well within the 4-heading ceiling.
        para = "This is a paragraph about Irish food culture and tradition. " * 10
        body = "\n\n".join([para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        heading_count = sum(1 for ln in result.splitlines() if ln.startswith("## "))
        self.assertLessEqual(heading_count, 4, "Single-theme article must not exceed heading ceiling")

    def test_contextual_heading_land_rural_season(self):
        rural_para = (
            "The rural landscape of Ireland, shaped by seasonal harvests and "
            "countryside farming traditions, has defined food culture for centuries. " * 5
        )
        body = "\n\n".join([rural_para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertIn("Food Rooted in the Land", result)

    def test_contextual_heading_baking_griddle_oats(self):
        baking_para = (
            "Traditional Irish baking relied on oats, griddle bread, and soda loaves "
            "made in the country kitchen and passed down through generations. " * 5
        )
        body = "\n\n".join([baking_para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertIn("Baking, Griddles and the Country Kitchen", result)

    def test_contextual_heading_mills_grain_flour(self):
        mill_para = (
            "The old mills along river valleys ground grain and produced the flour "
            "that sustained rural communities throughout the centuries of Irish history. " * 5
        )
        body = "\n\n".join([mill_para] * 4)
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertIn("Mills, Grain and Rural Memory", result)

    def test_existing_headings_are_preserved(self):
        body = "## A Custom Heading\n\nSome paragraph text here.\n\n## Another Heading\n\nMore paragraph text."
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertIn("## A Custom Heading", result)
        self.assertIn("## Another Heading", result)
        # No extra headings should be injected
        injected = [ln for ln in result.splitlines() if ln.startswith("## ") and ln not in ("## A Custom Heading", "## Another Heading")]
        self.assertEqual(injected, [])

    def test_normalise_collapses_multiple_blank_lines(self):
        body = "Para one.\n\n\n\nPara two."
        result = _normalize_body(body)
        self.assertNotIn("\n\n\n", result)

    def test_has_h2_detects_heading(self):
        self.assertTrue(_has_h2("## Heading\n\nText."))
        self.assertFalse(_has_h2("Just text."))

    def test_body_with_list_blocks_not_broken(self):
        para = "This is a paragraph about Irish food culture. " * 15
        body = para + "\n\n- item one\n- item two\n\n" + para
        result = suggest_article_body("Title", "Excerpt", body)
        # List items must be preserved in output
        self.assertIn("- item one", result)
        self.assertIn("- item two", result)
        # A ## heading must never appear immediately before a list item line
        non_empty = [ln for ln in result.splitlines() if ln.strip()]
        for i, line in enumerate(non_empty):
            if line.startswith("- "):
                if i > 0:
                    prev = non_empty[i - 1].strip()
                    self.assertFalse(
                        prev.startswith("## "),
                        f"Heading was inserted directly before list item: {prev!r}",
                    )

    def test_preserves_blockquotes(self):
        para = "This is a paragraph about Irish food culture. " * 15
        body = para + "\n\n> A blockquote line.\n\n" + para
        result = suggest_article_body("Title", "Excerpt", body)
        self.assertIn("> A blockquote line.", result)

    # ── New algorithm tests (content-aware grouping) ──────────────────────────

    def test_generates_3_to_4_headings_for_multitheme_article(self):
        """300-600 word article with multiple distinct themes gets 3-4 headings."""
        # ~80 words each × 6 paragraphs = ~480 words
        lead1 = "Irish food tells a rich story of place and community tied to the land and to its people. " * 5
        lead2 = "The countryside shaped generations of cooks who relied on what the seasons and the soil provided. " * 5
        mills = "Watermills and windmills once ground grain and flour for rural communities all across Ireland. " * 5
        baking = "Traditional Irish baking relied on griddle bread and oats baked fresh over open fires each day. " * 5
        land = "The rural countryside and seasonal farming harvest shaped local food traditions for many centuries. " * 5
        modern = "Modern restaurants and bistros in Dublin and Belfast have revived Irish culinary traditions today. " * 5
        body = "\n\n".join([lead1, lead2, mills, baking, land, modern])
        result = suggest_article_body("Title", "Excerpt", body)
        heading_count = sum(1 for ln in result.splitlines() if ln.startswith("## "))
        self.assertGreaterEqual(heading_count, 3, "Multi-theme 300-600 word article should have at least 3 headings")
        self.assertLessEqual(heading_count, 4, "Article should not exceed 4 headings for this word count")

    def test_headings_follow_article_order_not_dictionary_order(self):
        """Heading order matches paragraph order, not _SECTION_THEMES dict order.

        In _SECTION_THEMES, 'baking' (index 4) appears before 'mills' (index 5).
        If a mills paragraph comes first in the article, its heading must appear
        before the baking heading in the output.
        """
        # ~100 words each × 3 paragraphs = ~300 words
        filler = "Irish food has a long story connected to rural farming and seasonal traditions for many centuries. " * 8
        mills = "Watermills and windmills ground grain and flour for communities across rural Ireland for generations. " * 8
        baking = "Griddle bread and soda loaves were baked using local oats in Irish farmhouse kitchens every day. " * 8
        body = "\n\n".join([filler, mills, baking])
        result = suggest_article_body("Title", "Excerpt", body)
        lines = [ln for ln in result.splitlines() if ln.startswith("## ")]
        if len(lines) >= 2:
            mills_pos = next((i for i, l in enumerate(lines) if "Mills" in l), None)
            baking_pos = next((i for i, l in enumerate(lines) if "Baking" in l), None)
            if mills_pos is not None and baking_pos is not None:
                self.assertLess(
                    mills_pos, baking_pos,
                    "Mills heading must precede Baking heading because the mills "
                    "paragraph appears first in the article",
                )

    def test_split_long_blocks_splits_at_sentence_boundary(self):
        """_split_long_blocks splits a paragraph over the threshold into two parts."""
        sentences = [
            "Traditional Irish baking has always been tied to the rhythm of rural life.",
            "Griddle breads were made over open fires in farmhouse kitchens across Ireland.",
            "The soda bread tradition developed as a practical response to local available ingredients.",
            "Oats were ground at local mills and used in both porridge and daily baked goods.",
            "Buttermilk and bicarbonate of soda replaced yeast in many traditional Irish recipes.",
            "These simple methods produced loaves that were nourishing and well suited to the climate.",
            "The griddle remained central to Irish home baking for many subsequent generations.",
            "Families passed their best recipes down through oral tradition and practical demonstration.",
            "Simple ingredients combined with careful technique produced a lasting food heritage.",
            "Today these baking traditions are celebrated in cookery schools and heritage centres.",
            "The revival of traditional baking continues to inspire a new generation of Irish cooks.",
        ]
        long_para = " ".join(sentences)  # ~155 words — over threshold
        result = _split_long_blocks([long_para])
        self.assertEqual(len(result), 2, f"Expected 2 blocks after split, got {len(result)}")
        self.assertTrue(result[0].strip(), "First half must not be empty")
        self.assertTrue(result[1].strip(), "Second half must not be empty")
        # Wording must be preserved (split only removes whitespace at the boundary)
        combined_words = result[0].split() + result[1].split()
        self.assertEqual(combined_words, long_para.split(), "Split must not alter any wording")

    def test_split_long_blocks_does_not_split_short_blocks(self):
        """Blocks under the threshold are returned unchanged."""
        short = "A short paragraph about Irish food."
        result = _split_long_blocks([short])
        self.assertEqual(result, [short])

    def test_split_long_blocks_does_not_split_list_blocks(self):
        """List blocks are never split regardless of length."""
        long_list = "- " + ("item " * 200)
        result = _split_long_blocks([long_list])
        self.assertEqual(result, [long_list])

    def test_preserves_original_wording(self):
        """suggest_article_body never changes the wording of any paragraph."""
        p1 = "Irish food has a remarkable story rooted in simplicity and rural heritage. " * 10
        p2 = "Butter and cream have long been central ingredients in traditional Irish cooking. " * 10
        p3 = "The griddle was essential to Irish baking traditions across many generations. " * 10
        p4 = "Rural milling provided grain and flour for communities throughout Ireland. " * 10
        body = "\n\n".join([p1, p2, p3, p4])
        result = suggest_article_body("Title", "Excerpt", body)
        result_paras = [" ".join(b.split()) for b in result.split("\n\n") if not b.strip().startswith("## ")]
        for original in [p1.strip(), p2.strip(), p3.strip(), p4.strip()]:
            self.assertIn(
                " ".join(original.split()),
                result_paras,
                f"Original paragraph wording was altered: {original[:50]!r}…",
            )

    def test_score_para_theme_returns_correct_theme(self):
        """_score_para_theme picks the theme with the highest keyword count."""
        baking_text = "baking griddle bread soda oats loaf bannocks — many baking references here"
        theme = _score_para_theme(baking_text)
        self.assertIsNotNone(theme)
        self.assertEqual(theme["name"], "baking")

    def test_score_para_theme_returns_none_for_unmatched_text(self):
        """_score_para_theme returns None when no theme keywords appear."""
        theme = _score_para_theme("the sky is blue and the weather is mild today")
        self.assertIsNone(theme)

    def test_score_para_theme_article_order_wins_on_tie(self):
        """When two themes tie, the first theme in _SECTION_THEMES wins."""
        # familiar_icons (index 0) and land_and_rural (index 1) each get exactly 1 hit
        text = "butter and seasonal cooking"  # 'butter' → familiar_icons(1), 'seasonal' → land_and_rural(1)
        theme = _score_para_theme(text)
        self.assertIsNotNone(theme)
        # familiar_icons appears at index 0, land_and_rural at index 1 → familiar_icons wins
        self.assertEqual(theme["name"], "familiar_icons", "First theme in list should win on tie")


class RenderArticlePreviewTests(TestCase):
    """Unit tests for render_article_preview."""

    def test_empty_body_returns_empty_string(self):
        result = render_article_preview("")
        self.assertEqual(result, "")

    def test_h2_rendered_as_h2_tag(self):
        result = render_article_preview("## Section\n\nSome text.")
        self.assertIn("<h2>", result)
        self.assertIn("Section", result)

    def test_plain_text_rendered_as_p(self):
        result = render_article_preview("Hello world.")
        self.assertIn("<p", result)
        self.assertIn("Hello world.", result)

    def test_xss_escaped(self):
        result = render_article_preview("<script>alert(1)</script>")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_output_is_string(self):
        result = render_article_preview("Simple text.")
        self.assertIsInstance(result, str)

    def test_suggested_body_renders_h2_not_raw_hash(self):
        """Full pipeline: suggest → preview produces <h2> tags, no raw ## markers."""
        # Build a multi-theme body > 300 words (use * 8 to stay well above threshold)
        lead = "Irish food tells a rich story of place and community connected to land and season. " * 8
        mills = "Watermills and windmills ground grain and flour for rural Irish communities. " * 8
        baking = "Griddle breads and soda loaves were baked fresh using local oats and wheat flour. " * 8
        land = "The rural countryside of Ireland and seasonal farming shaped local culinary traditions. " * 8
        body = "\n\n".join([lead, mills, baking, land])
        suggested = suggest_article_body("Irish Food Heritage", "An introduction.", body)
        rendered = render_article_preview(suggested)
        self.assertIn("<h2>", rendered, "Rendered HTML must contain <h2> tags")
        self.assertNotIn("##", rendered, "Rendered HTML must not contain raw ## markers")

    def test_preview_matches_editorial_format_filter(self):
        """render_article_preview uses the identical filter as the article detail template."""
        from articles.templatetags.article_filters import editorial_format
        body = "## A Section\n\nA paragraph of editorial text about Irish food."
        self.assertEqual(render_article_preview(body), editorial_format(body))


class SuggestRecipeFieldsTests(TestCase):
    """Unit tests for suggest_recipe_fields."""

    def test_ingredients_removes_bullet_dashes(self):
        data = {"ingredients": "- 200g flour\n- 1 egg\n- 100ml milk"}
        result = suggest_recipe_fields(data)
        self.assertNotIn("- ", result["ingredients"])
        self.assertIn("200g flour", result["ingredients"])
        self.assertIn("1 egg", result["ingredients"])

    def test_ingredients_removes_bullet_stars(self):
        data = {"ingredients": "* 200g flour\n* 1 egg"}
        result = suggest_recipe_fields(data)
        self.assertNotIn("* ", result["ingredients"])

    def test_ingredients_removes_blank_lines(self):
        data = {"ingredients": "200g flour\n\n1 egg\n\n100ml milk"}
        result = suggest_recipe_fields(data)
        self.assertNotIn("\n\n", result["ingredients"])

    def test_method_removes_step_prefixes(self):
        data = {"method": "1. Preheat oven\n2. Mix ingredients\n3. Bake for 20 minutes"}
        result = suggest_recipe_fields(data)
        method = result["method"]
        self.assertNotIn("1.", method)
        self.assertIn("Preheat oven", method)
        self.assertIn("Mix ingredients", method)

    def test_method_removes_step_word_prefix(self):
        data = {"method": "Step 1: Preheat oven\nStep 2: Mix"}
        result = suggest_recipe_fields(data)
        self.assertNotIn("Step 1:", result["method"])
        self.assertIn("Preheat oven", result["method"])

    def test_method_removes_blank_lines(self):
        data = {"method": "Preheat oven\n\nMix ingredients"}
        result = suggest_recipe_fields(data)
        self.assertNotIn("\n\n", result["method"])

    def test_tips_cleaned(self):
        data = {"tips": "  Use fresh eggs.  \n\n\nSeason well."}
        result = suggest_recipe_fields(data)
        self.assertIn("Use fresh eggs.", result["tips"])
        self.assertNotIn("\n\n\n", result["tips"])

    def test_other_fields_unchanged(self):
        data = {
            "title": "Colcannon",
            "servings": "4",
            "ingredients": "- 500g potatoes",
        }
        result = suggest_recipe_fields(data)
        self.assertEqual(result["title"], "Colcannon")
        self.assertEqual(result["servings"], "4")

    def test_returns_copy_not_mutate(self):
        data = {"ingredients": "- flour"}
        original = data.copy()
        suggest_recipe_fields(data)
        self.assertEqual(data, original)

    def test_empty_ingredients_unchanged(self):
        data = {"ingredients": ""}
        result = suggest_recipe_fields(data)
        self.assertEqual(result["ingredients"], "")

    def test_clean_list_helper_with_bullets(self):
        text = "- flour\n* sugar\n• butter"
        result = _clean_list_field(text)
        self.assertIn("flour", result)
        self.assertNotIn("-", result)
        self.assertNotIn("*", result)
        self.assertNotIn("•", result)

    def test_clean_method_removes_numbered_prefix(self):
        result = _clean_method_field("1. Preheat\n2. Mix\n3. Bake")
        self.assertNotIn("1.", result)
        self.assertIn("Preheat", result)

    def test_clean_plain_field_strips_trailing_whitespace(self):
        result = _clean_plain_field("Line one.   \nLine two.   ")
        self.assertNotIn("   ", result)


class RenderRecipePreviewTests(TestCase):
    """Unit tests for render_recipe_preview."""

    def test_empty_data_returns_placeholder(self):
        result = render_recipe_preview({})
        self.assertIn("Nothing to preview", result)

    def test_title_rendered(self):
        result = render_recipe_preview({"title": "Colcannon"})
        self.assertIn("Colcannon", result)
        self.assertIn("recipe-preview__title", result)

    def test_ingredients_rendered_as_list(self):
        result = render_recipe_preview({"ingredients": "500g potatoes\n100ml milk"})
        self.assertIn("<ul", result)
        self.assertIn("500g potatoes", result)
        self.assertIn("100ml milk", result)

    def test_method_rendered_as_ordered_list(self):
        result = render_recipe_preview({"method": "Boil potatoes\nMash well"})
        self.assertIn("<ol", result)
        self.assertIn("Boil potatoes", result)

    def test_xss_escaped_in_title(self):
        result = render_recipe_preview({"title": "<script>alert(1)</script>"})
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_xss_escaped_in_ingredients(self):
        result = render_recipe_preview({"ingredients": '<b>not bold</b>'})
        self.assertNotIn("<b>", result)

    def test_output_is_string(self):
        result = render_recipe_preview({"title": "Test"})
        self.assertIsInstance(result, str)

    def test_meta_row_rendered(self):
        result = render_recipe_preview({
            "prep_time_minutes": "15",
            "cook_time_minutes": "30",
            "servings": "4",
        })
        self.assertIn("recipe-preview__meta", result)
        self.assertIn("Prep", result)
        self.assertIn("Cook", result)
        self.assertIn("Serves", result)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class EditorialSuggestEndpointTests(TestCase):
    """Integration tests for the editorial_suggest JSON endpoint."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="edituser", password="pass")
        self.url = reverse("articles:editorial_suggest")

    def _post(self, data, as_json=True):
        if as_json:
            return self.client.post(
                self.url,
                data=_json.dumps(data),
                content_type="application/json",
            )
        return self.client.post(self.url, data=data)

    def test_login_required(self):
        response = self._post({"body": "Some text."})
        self.assertIn(response.status_code, [302, 403])

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_returns_json_with_suggested_body(self):
        self.client.force_login(self.user)
        response = self._post({"title": "T", "excerpt": "E", "body": "Short body."})
        self.assertEqual(response.status_code, 200)
        data = _json.loads(response.content)
        self.assertIn("suggested_body", data)

    def test_suggested_body_is_string(self):
        self.client.force_login(self.user)
        response = self._post({"body": "Short text."})
        data = _json.loads(response.content)
        self.assertIsInstance(data["suggested_body"], str)

    def test_empty_body_returns_empty_suggestion(self):
        self.client.force_login(self.user)
        response = self._post({"body": ""})
        data = _json.loads(response.content)
        self.assertEqual(data["suggested_body"], "")

    def test_accepts_form_post_fallback(self):
        self.client.force_login(self.user)
        response = self._post({"body": "A test."}, as_json=False)
        self.assertEqual(response.status_code, 200)
        data = _json.loads(response.content)
        self.assertIn("suggested_body", data)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class EditorialPreviewEndpointTests(TestCase):
    """Integration tests for the editorial_preview JSON endpoint."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="prevuser", password="pass")
        self.url = reverse("articles:editorial_preview")

    def _post(self, data, as_json=True):
        if as_json:
            return self.client.post(
                self.url,
                data=_json.dumps(data),
                content_type="application/json",
            )
        return self.client.post(self.url, data=data)

    def test_login_required(self):
        response = self._post({"body": "Text."})
        self.assertIn(response.status_code, [302, 403])

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_returns_preview_html(self):
        self.client.force_login(self.user)
        response = self._post({"body": "## Heading\n\nParagraph text."})
        self.assertEqual(response.status_code, 200)
        data = _json.loads(response.content)
        self.assertIn("preview_html", data)
        self.assertIn("<h2>", data["preview_html"])

    def test_preview_html_escapes_xss(self):
        self.client.force_login(self.user)
        response = self._post({"body": "<script>alert(1)</script>"})
        data = _json.loads(response.content)
        self.assertNotIn("<script>", data["preview_html"])

    def test_empty_body_returns_empty_html(self):
        self.client.force_login(self.user)
        response = self._post({"body": ""})
        data = _json.loads(response.content)
        self.assertEqual(data["preview_html"], "")


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class RecipeFormatSuggestEndpointTests(TestCase):
    """Integration tests for recipes:recipe_format_suggest."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="rfuser", password="pass")
        self.url = reverse("recipes:recipe_format_suggest")

    def _post(self, data, as_json=True):
        if as_json:
            return self.client.post(
                self.url,
                data=_json.dumps(data),
                content_type="application/json",
            )
        return self.client.post(self.url, data=data)

    def test_login_required(self):
        response = self._post({"ingredients": "flour"})
        self.assertIn(response.status_code, [302, 403])

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_returns_cleaned_ingredients(self):
        self.client.force_login(self.user)
        response = self._post({"ingredients": "- 200g flour\n- 1 egg"})
        self.assertEqual(response.status_code, 200)
        data = _json.loads(response.content)
        self.assertIn("ingredients", data)
        self.assertNotIn("- ", data["ingredients"])
        self.assertIn("200g flour", data["ingredients"])

    def test_returns_cleaned_method(self):
        self.client.force_login(self.user)
        response = self._post({"method": "1. Preheat oven\n2. Bake"})
        data = _json.loads(response.content)
        self.assertIn("method", data)
        self.assertNotIn("1.", data["method"])
        self.assertIn("Preheat oven", data["method"])

    def test_all_expected_keys_in_response(self):
        self.client.force_login(self.user)
        response = self._post({})
        data = _json.loads(response.content)
        for key in ("ingredients", "method", "tips", "irish_context", "author_commentary"):
            self.assertIn(key, data)

    def test_empty_inputs_return_empty_strings(self):
        self.client.force_login(self.user)
        response = self._post({
            "ingredients": "",
            "method": "",
            "tips": "",
        })
        data = _json.loads(response.content)
        self.assertEqual(data["ingredients"], "")
        self.assertEqual(data["method"], "")
        self.assertEqual(data["tips"], "")


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class RecipeFormatPreviewEndpointTests(TestCase):
    """Integration tests for recipes:recipe_format_preview."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="rfprev", password="pass")
        self.url = reverse("recipes:recipe_format_preview")

    def _post(self, data, as_json=True):
        if as_json:
            return self.client.post(
                self.url,
                data=_json.dumps(data),
                content_type="application/json",
            )
        return self.client.post(self.url, data=data)

    def test_login_required(self):
        response = self._post({"title": "Test"})
        self.assertIn(response.status_code, [302, 403])

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_returns_preview_html(self):
        self.client.force_login(self.user)
        response = self._post({
            "title": "Boxty",
            "ingredients": "500g potatoes\n2 eggs",
            "method": "Grate potatoes\nMix with eggs",
        })
        self.assertEqual(response.status_code, 200)
        data = _json.loads(response.content)
        self.assertIn("preview_html", data)
        self.assertIn("Boxty", data["preview_html"])
        self.assertIn("<ul", data["preview_html"])
        self.assertIn("<ol", data["preview_html"])

    def test_xss_escaped_in_preview(self):
        self.client.force_login(self.user)
        response = self._post({"title": "<script>xss()</script>"})
        data = _json.loads(response.content)
        self.assertNotIn("<script>", data["preview_html"])

    def test_empty_data_returns_placeholder(self):
        self.client.force_login(self.user)
        response = self._post({})
        data = _json.loads(response.content)
        self.assertIn("preview_html", data)
        self.assertIn("Nothing to preview", data["preview_html"])


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class SuggestArticleEditorialFormatCommandTests(TestCase):
    """Tests for the suggest_article_editorial_format management command."""

    def setUp(self):
        user_model = get_user_model()
        self.owner_user = user_model.objects.create_user(
            username="cmdowner", password="pass"
        )
        self.author = RecipeAuthor.objects.create(
            user=self.owner_user,
            name="CMD Author",
            slug="cmd-author",
        )
        self.article = Article.objects.create(
            title="Colcannon History",
            slug="colcannon-history",
            author=self.author,
            excerpt="About colcannon.",
            body="A short body.",
            published=date(2026, 1, 1),
            status=Article.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_rules=True,
            source_type="original",
        )

    def _call_command(self, *args, **kwargs):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        err = StringIO()
        call_command(
            "suggest_article_editorial_format",
            *args,
            stdout=out,
            stderr=err,
            **kwargs,
        )
        return out.getvalue(), err.getvalue()

    def test_command_runs_without_error(self):
        out, _ = self._call_command("--slug", "colcannon-history")
        # Short body -> "already well-formatted" or dry-run output
        self.assertIsInstance(out, str)

    def test_command_reports_already_formatted(self):
        # Short body without headings should report "already well-formatted"
        out, _ = self._call_command("--slug", "colcannon-history")
        self.assertIn("well-formatted", out)

    def test_command_raises_for_unknown_slug(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self._call_command("--slug", "does-not-exist-xyz")

    def test_apply_flag_writes_to_db(self):
        para = "This is a paragraph about Irish food culture and tradition. " * 15
        long_body = "\n\n".join([para] * 6)
        self.article.body = long_body
        self.article.save(update_fields=["body"])

        self._call_command("--slug", "colcannon-history", "--apply")
        self.article.refresh_from_db()
        # Headings should now be present
        self.assertIn("##", self.article.body)

    def test_dry_run_does_not_write_to_db(self):
        para = "This is a paragraph about Irish food culture and tradition. " * 15
        long_body = "\n\n".join([para] * 6)
        self.article.body = long_body
        self.article.save(update_fields=["body"])
        original_body = self.article.body

        self._call_command("--slug", "colcannon-history")  # no --apply
        self.article.refresh_from_db()
        self.assertEqual(self.article.body, original_body)
