from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import inlineformset_factory
from django.test import TestCase, override_settings
from django.urls import reverse
from messaging.models import Message
from PIL import Image

from recipes.models import Recipe, RecipeAuthor

from .admin import ArticleAdmin, ArticleAdminForm, ArticleImageInlineFormSet
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

    def test_article_list_marks_ai_generated_article_images(self):
        ai_article = self.create_article("AI Article", Article.Status.APPROVED)
        ai_article.image_rights_status = Article.ImageRightsStatus.AI_GENERATED
        ai_article.save(update_fields=["image_rights_status"])

        response = self.client.get(reverse("articles:article_list"))

        self.assertContains(response, 'aria-label="AI generated image"', html=False)

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

        self.assertContains(response, "AI Generated")
        self.assertContains(response, 'aria-label="AI generated image"', html=False)

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

        self.assertContains(response, "Article Deleted Successfully.")

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
            {"action": "reject"},
        )

        self.article.refresh_from_db()
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(self.article.status, Article.Status.REJECTED)

    def test_moderator_can_delete_article_from_moderation_endpoint(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("articles:moderate_article", kwargs={"slug": self.article.slug}),
            {"action": "delete"},
        )

        self.assertRedirects(response, reverse("recipes:moderation_panel"))
        self.assertFalse(Article.objects.filter(pk=self.article.pk).exists())

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
