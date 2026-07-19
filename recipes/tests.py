import importlib
import json
import os
import re
import tempfile
from datetime import date, timedelta
from io import BytesIO
from unittest import skip
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from PIL import Image

from articles.models import Article, ArticleImage
from collection.models import SavedRecipe
from config.release_journal import RELEASE_JOURNAL, build_git_journal
from .admin import RecipeAdmin, RecipeAdminForm
from .allergens import build_present_allergen_items, parse_selected_allergen_keys, serialize_allergen_keys
from .forms import RecipeAuthoringForm, RecipeCommentForm
from .models import Recipe, RecipeAdditionalCategory, RecipeAuthor, RecipeComment, RecipeGenerationTask, RecipeRating
from .services.screenshot_recipe_importer import ScreenshotExtractionError, normalise_extracted_recipe
from .validators import validate_image_upload
from .views import _build_context_paragraphs, _build_ingredient_items, _build_method_steps, _gallery_step_alt, _gallery_step_rows, _image_alt_text, _soft_delete_recipe, _split_text_lines, _update_recipe_gallery_order


class AuthoringCssTests(SimpleTestCase):
    def test_recipe_form_hero_uses_stable_height(self):
        css_path = os.path.join(settings.BASE_DIR, "static", "css", "authoring.css")
        with open(css_path, encoding="utf-8") as css_file:
            css = css_file.read()

        self.assertRegex(css, r"\.hero--recipe-tools\s*\{[^}]*height: 410px;[^}]*min-height: 410px;")
        self.assertRegex(css, r"@media \(max-width: 760px\)\s*\{[^{}]*\.hero--recipe-tools\s*\{[^}]*height: 440px;")
        self.assertRegex(css, r"@media \(max-width: 540px\)\s*\{[^{}]*\.hero--recipe-tools\s*\{[^}]*height: 460px;")


class HeaderCssTests(SimpleTestCase):
    def test_author_panel_constrains_long_names(self):
        css_path = os.path.join(settings.BASE_DIR, "static", "css", "header.css")
        with open(css_path, encoding="utf-8") as css_file:
            css = css_file.read()

        self.assertRegex(css, r"\.ce-nav\s*\{[^}]*min-width: 0;")
        self.assertRegex(
            css,
            r"\.ce-author-panel__copy\s*\{[^}]*min-width: 0;[^}]*width: 100%;[^}]*max-width: 100%;",
        )
        self.assertRegex(
            css,
            r"\.ce-author-panel__name\s*\{[^}]*display: block;[^}]*overflow: hidden;"
            r"[^}]*max-width: 100%;[^}]*text-overflow: ellipsis;[^}]*white-space: nowrap;",
        )
        self.assertRegex(css, r"\.ce-nav__auth--author\s*\{[^}]*max-width: clamp")


class ImageUploadValidatorTests(SimpleTestCase):
    @staticmethod
    def uploaded_image(name, image_format="PNG"):
        image_file = BytesIO()
        Image.new("RGB", (24, 24), (24, 76, 58)).save(image_file, format=image_format)
        image_file.seek(0)
        return SimpleUploadedFile(name, image_file.read(), content_type="image/png")

    def test_renames_valid_jpeg_with_png_extension(self):
        uploaded = self.uploaded_image("Gallery image 4.png", image_format="JPEG")

        validate_image_upload(uploaded)

        self.assertEqual(uploaded.name, "Gallery image 4.jpg")
        self.assertEqual(uploaded.content_type, "image/jpeg")

    def test_keeps_matching_png_name(self):
        uploaded = self.uploaded_image("step.png", image_format="PNG")

        validate_image_upload(uploaded)

        self.assertEqual(uploaded.name, "step.png")
        self.assertEqual(uploaded.content_type, "image/png")

    def test_rejects_corrupt_image_file(self):
        uploaded = SimpleUploadedFile("broken.png", b"not an image", content_type="image/png")

        with self.assertRaises(ValidationError):
            validate_image_upload(uploaded)


class RecipeTextHelperTests(SimpleTestCase):
    def test_image_alt_text_prefers_explicit_alt_then_caption_then_title(self):
        self.assertEqual(
            _image_alt_text("Irish Brown Bread", "Irish brown bread served with butter", "A sliced loaf"),
            "Irish brown bread served with butter",
        )
        self.assertEqual(
            _image_alt_text("Irish Brown Bread", "", "A sliced loaf served with butter"),
            "A sliced loaf served with butter",
        )
        self.assertEqual(_image_alt_text("Irish Brown Bread"), "Irish Brown Bread image")

    def test_split_text_lines_drops_blank_rows(self):
        value = " Potatoes \n\nCarrots\n  \nOnions "

        self.assertEqual(_split_text_lines(value), ["Potatoes", "Carrots", "Onions"])

    def test_build_method_steps_strips_numbered_prefixes_of_any_length(self):
        method = "1. Prep the veg\n10. Finish the stew"

        steps = _build_method_steps(method)

        self.assertEqual(
            steps,
            [
                {"number": 1, "text": "Prep the veg"},
                {"number": 2, "text": "Finish the stew"},
            ],
        )

    def test_build_method_steps_skips_empty_number_only_rows(self):
        method = "1. Prep the veg\n2. Finish the stew\n10."

        steps = _build_method_steps(method)

        self.assertEqual(
            steps,
            [
                {"number": 1, "text": "Prep the veg"},
                {"number": 2, "text": "Finish the stew"},
            ],
        )

    def test_build_context_paragraphs_keeps_explicit_paragraph_breaks(self):
        context = "First note about the dish.\n\nSecond note about how it is served."

        self.assertEqual(
            _build_context_paragraphs(context),
            [
                "First note about the dish.",
                "Second note about how it is served.",
            ],
        )

    def test_build_context_paragraphs_groups_long_single_block_into_pairs(self):
        context = (
            "Shepherd's pie and cottage pie are traditional comfort dishes. "
            "They are often served during colder months. "
            "Originally the dish was a practical way to use leftover meat. "
            "Today it remains a staple in Irish homes."
        )

        self.assertEqual(
            _build_context_paragraphs(context),
            [
                (
                    "Shepherd's pie and cottage pie are traditional comfort dishes. "
                    "They are often served during colder months."
                ),
                (
                    "Originally the dish was a practical way to use leftover meat. "
                    "Today it remains a staple in Irish homes."
                ),
            ],
        )

    def test_build_ingredient_items_splits_name_and_detail(self):
        ingredients = "Minced beef - 500g\nSalt - To taste"

        self.assertEqual(
            _build_ingredient_items(ingredients),
            [
                {
                    "name": "Minced beef",
                    "detail": "500g",
                    "detail_display": "500g.",
                },
                {
                    "name": "Salt",
                    "detail": "To taste",
                    "detail_display": "To taste.",
                },
            ],
        )

    def test_build_ingredient_items_keeps_single_value_without_detail(self):
        ingredients = "Fresh parsley"

        self.assertEqual(
            _build_ingredient_items(ingredients),
            [
                {
                    "name": "Fresh parsley",
                    "detail": "",
                    "detail_display": "",
                },
            ],
        )

    def test_parse_selected_allergen_keys_supports_legacy_text(self):
        self.assertEqual(
            parse_selected_allergen_keys("Milk Possible gluten depending on stock used"),
            ["gluten", "milk"],
        )

    def test_serialize_allergen_keys_keeps_known_values_only(self):
        self.assertEqual(
            serialize_allergen_keys(["milk", "gluten", "milk", "unknown"]),
            "milk\ngluten",
        )

    def test_build_present_allergen_items_returns_only_selected_items(self):
        allergen_items = build_present_allergen_items("milk\ngluten")

        self.assertEqual(
            allergen_items,
            [
                {"key": "gluten", "label": "Cereals containing gluten", "is_present": True},
                {"key": "milk", "label": "Milk", "is_present": True},
            ],
        )


class ModerationPanelRoleTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_superuser(
            username="greenbear",
            email="culineire@gmail.com",
            password="pass",
        )
        self.owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug="greenbear",
            defaults={
                "user": self.owner,
                "name": "GreenBear",
            },
        )
        self.second_superuser = user_model.objects.create_superuser(
            username="catwithtail",
            email="catwithtail.as@gmail.com",
            password="pass",
        )
        self.second_superuser_author = RecipeAuthor.objects.create(
            user=self.second_superuser,
            name="Alexey Senin",
            slug="catwithtail",
            has_bearseeker_privileges=True,
        )
        self.bearseeker_user = user_model.objects.create_user(
            username="bear-admin",
            email="bear-admin@example.com",
            password="pass",
        )
        self.bearseeker_author = RecipeAuthor.objects.create(
            user=self.bearseeker_user,
            name="Bear Admin",
            slug="bear-admin",
            has_bearseeker_privileges=True,
        )

    def test_panel_groups_django_superusers_above_bearseeker_admins(self):
        self.client.login(username="greenbear", password="pass")

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.context["bearseeker_super_users"].values_list("pk", flat=True)),
            {self.owner_author.pk, self.second_superuser_author.pk},
        )
        self.assertEqual(
            list(response.context["bearseeker_super_users"].values_list("slug", flat=True)),
            ["greenbear", "catwithtail"],
        )
        self.assertEqual(
            list(response.context["bearseeker_authors"].values_list("pk", flat=True)),
            [self.bearseeker_author.pk],
        )
        self.assertTrue(response.context["can_revoke_superuser_privileges"])
        self.assertContains(response, "@catwithtail")
        self.assertContains(response, "Revoke Superuser Privileges", count=1)
        self.assertContains(response, "Automation Progress")
        self.assertNotContains(response, "Pinch Roadmap")
        self.assertNotContains(response, "Month 1 Update Progress")

    @override_settings(TELEGRAM_BOT_TOKEN="token", TELEGRAM_CHANNEL_ID="@culineire", ANTHROPIC_API_KEY="anthropic-key")
    def test_automation_progress_marks_env_backed_steps_complete(self):
        self.client.login(username="greenbear", password="pass")

        response = self.client.get(reverse("recipes:automation_progress"))

        progress = response.context["automation_progress"]
        statuses = {item["label"]: item["status"] for item in progress["items"]}
        self.assertEqual(statuses["Telegram credentials"], "done")
        self.assertEqual(statuses["Anthropic credentials"], "done")
        self.assertGreater(progress["done_count"], 0)
        self.assertContains(response, "Copy for Claude Code")
        self.assertContains(response, "Show completed progress")

    def test_automation_progress_tracks_published_content_targets(self):
        for index in range(20):
            Recipe.objects.create(
                title=f"Approved Recipe {index}",
                slug=f"approved-recipe-{index}",
                author=self.owner_author,
                ingredients="Potatoes",
                method="Cook.",
                status=Recipe.Status.APPROVED,
            )
        for index in range(8):
            Article.objects.create(
                title=f"Approved Article {index}",
                slug=f"approved-article-{index}",
                author=self.owner_author,
                body="Story.",
                published=date(2026, 5, 26),
                status=Article.Status.APPROVED,
            )
        self.client.login(username="greenbear", password="pass")

        response = self.client.get(reverse("recipes:automation_progress"))

        statuses = {item["label"]: item["status"] for item in response.context["automation_progress"]["items"]}
        self.assertEqual(statuses["Recipe publishing target"], "done")
        self.assertEqual(statuses["Article publishing target"], "done")

    def test_automation_progress_hidden_from_non_moderators(self):
        response = self.client.get(reverse("recipes:automation_progress"))

        self.assertEqual(response.status_code, 404)

    def test_arena_master_console_plan_contains_every_copyable_yaml_section(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("recipes:arena_master_console_plan"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["plan_sections"]), 12)
        self.assertContains(response, "Arena Master Console Plan")
        self.assertContains(response, "phase_09_hardening_release.yaml")
        self.assertContains(response, 'data-copy-target="plan-source-p00"')
        self.assertContains(response, 'data-copy-target="plan-source-p09"')
        self.assertContains(response, 'phase_id: &quot;P00&quot;')

    def test_arena_master_console_plan_is_hidden_from_other_moderators(self):
        self.client.force_login(self.bearseeker_user)

        response = self.client.get(reverse("recipes:arena_master_console_plan"))

        self.assertEqual(response.status_code, 404)

    def test_owner_moderation_panel_links_to_arena_master_console_plan(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertContains(response, "Arena Console Plan")
        self.assertContains(response, reverse("recipes:arena_master_console_plan"))
        self.assertContains(response, "mod-tool-link--arena-plan")

    def test_owner_pending_recipe_counts_in_content_studio_not_moderation_header(self):
        Recipe.objects.create(
            title="Owner AI Draft",
            slug="owner-ai-draft",
            author=self.owner_author,
            ingredients="Flour",
            method="Draft.",
            status=Recipe.Status.PENDING,
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("recipes:moderation_panel"))

        actions = {action["label"]: action for action in response.context["header_author_actions"]}
        self.assertIsNone(actions["Moderation Panel"].get("badge"))
        self.assertEqual(actions["My Content Studio"]["badge"], 1)
        self.assertEqual(response.context["pending_recipes"], [])

    def test_other_author_pending_recipe_counts_in_moderation_header(self):
        Recipe.objects.create(
            title="Other Author Pending",
            slug="other-author-pending",
            author=self.bearseeker_author,
            ingredients="Flour",
            method="Review.",
            status=Recipe.Status.PENDING,
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("recipes:moderation_panel"))

        actions = {action["label"]: action for action in response.context["header_author_actions"]}
        self.assertEqual(actions["Moderation Panel"]["badge"], 1)
        self.assertIsNone(actions["My Content Studio"].get("badge"))
        self.assertEqual(len(response.context["pending_recipes"]), 1)

    def test_deployment_journal_hidden_from_anonymous_users(self):
        response = self.client.get(reverse("recipes:deployment_journal"))

        self.assertEqual(response.status_code, 404)

    def test_deployment_journal_hidden_from_non_moderator_users(self):
        regular_user = get_user_model().objects.create_user(
            username="regular-reader",
            email="regular@example.com",
            password="pass",
        )
        self.client.force_login(regular_user)

        response = self.client.get(reverse("recipes:deployment_journal"))

        self.assertEqual(response.status_code, 404)

    def test_staff_user_can_view_deployment_journal(self):
        staff_user = get_user_model().objects.create_user(
            username="journal-staff",
            email="journal-staff@example.com",
            password="pass",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse("recipes:deployment_journal"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deployment Journal")
        self.assertEqual(response.context["release_journal"], build_git_journal(settings.BASE_DIR))

    def test_moderation_panel_links_to_deployment_journal(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertContains(response, "Deployment Journal")
        self.assertContains(response, reverse("recipes:deployment_journal"))

    def test_panel_can_revoke_other_superuser_privileges(self):
        self.client.login(username="greenbear", password="pass")

        response = self.client.post(
            reverse("accounts:manage_author", kwargs={"slug": self.second_superuser_author.slug}),
            {"action": "revoke_superuser"},
        )

        self.assertEqual(response.status_code, 302)
        self.second_superuser.refresh_from_db()
        self.second_superuser_author.refresh_from_db()
        self.assertFalse(self.second_superuser.is_superuser)
        self.assertFalse(self.second_superuser.is_staff)
        self.assertTrue(self.second_superuser.is_active)
        self.assertFalse(self.second_superuser_author.has_bearseeker_privileges)

    def test_panel_cannot_revoke_current_superuser(self):
        self.client.login(username="greenbear", password="pass")

        response = self.client.post(
            reverse("accounts:manage_author", kwargs={"slug": self.owner_author.slug}),
            {"action": "revoke_superuser"},
        )

        self.assertEqual(response.status_code, 404)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_superuser)

    def test_other_superuser_cannot_revoke_owner_superuser(self):
        self.client.login(username="catwithtail", password="pass")

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_revoke_superuser_privileges"])
        self.assertNotContains(response, "Revoke Superuser Privileges")

        response = self.client.post(
            reverse("accounts:manage_author", kwargs={"slug": self.owner_author.slug}),
            {"action": "revoke_superuser"},
        )

        self.assertEqual(response.status_code, 404)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_superuser)


class RecipeCommentFormTests(SimpleTestCase):
    def test_valid_comment_form_passes_validation(self):
        form = RecipeCommentForm(
            data={
                "name": "Aoife",
                "content": "Lovely recipe and easy to follow.",
                "website": "",
            }
        )

        self.assertTrue(form.is_valid())

    def test_honeypot_field_blocks_spam_submissions(self):
        form = RecipeCommentForm(
            data={
                "name": "Aoife",
                "content": "Lovely recipe and easy to follow.",
                "website": "https://spam.example",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("website", form.errors)


class RecipeAdminFormTests(TestCase):
    def test_admin_form_populates_selected_allergens_from_instance(self):
        recipe = Recipe(
            title="Test pie",
            ingredients="Potatoes",
            method="Cook it",
            allergens="milk\ngluten",
        )

        form = RecipeAdminForm(instance=recipe)

        self.assertEqual(form.fields["selected_allergens"].initial, ["milk", "gluten"])

    def test_admin_form_saves_selected_allergens_and_author_commentary(self):
        form = RecipeAdminForm(
            data={
                "title": "Test pie",
                "short_description": "",
                "prep_time_minutes": 20,
                "cook_time_minutes": 40,
                "servings": 4,
                "calories": "",
                "difficulty": Recipe.Difficulty.EASY,
                "category": Recipe.Category.EVERYDAY_IRISH_COOKING,
                "ingredients": "Potatoes - 800g",
                "method": "1. Boil potatoes",
                "tips": "",
                "irish_context": "",
                "author_commentary": "Best served very hot.",
                "selected_allergens": ["milk", "gluten"],
                "source_type": Recipe.SourceType.ORIGINAL,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "image_rights_status": Recipe.ImageRightsStatus.OWN,
                "image_rights_note": "",
                "status": Recipe.Status.PENDING,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        recipe = form.save(commit=False)

        self.assertEqual(recipe.allergens, "milk\ngluten")
        self.assertEqual(recipe.author_commentary, "Best served very hot.")


class RecipeScreenshotImportTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="shot-author", password="pass")
        self.author = RecipeAuthor.objects.create(user=self.user, name="Shot Author", slug="shot-author")
        image = BytesIO()
        Image.new("RGB", (48, 48), (240, 240, 240)).save(image, format="PNG")
        self.upload = SimpleUploadedFile("screenshot.png", image.getvalue(), content_type="image/png")

    def valid_extraction(self, **overrides):
        data = {
            "title": "Screenshot Colcannon",
            "short_description": "A draft extracted from a screenshot.",
            "category": "Traditional Irish Dishes",
            "additional_categories": ["Everyday Irish Cooking"],
            "difficulty": "medium",
            "prep_time_minutes": 20,
            "cook_time_minutes": 25,
            "servings": 4,
            "allergens": ["milk"],
            "ingredients": "Potatoes\nCabbage\nButter",
            "method": "Boil the potatoes.\nFold in the cabbage.",
            "tips": "Serve immediately.",
            "irish_context": "A homely potato dish.",
            "commentary": "Seen in a screenshot.",
            "source": {
                "source_type": "website",
                "source_title": "Example Recipe",
                "source_author": "Example Author",
                "source_url": "https://example.com/recipe",
                "source_note": "Recipe information extracted from user-uploaded screenshot. Source requires manual review.",
            },
            "tags": ["colcannon", "potatoes"],
            "visual_description": {
                "dish_type": "colcannon",
                "main_visible_ingredients": ["potatoes", "cabbage", "butter"],
                "plating_style": "served in a bowl",
                "camera_angle": "three-quarter angle",
                "lighting": "natural light",
                "background": "simple kitchen table",
                "visual_mood": "warm and homely",
                "useful_context": "Irish potato dish",
            },
            "hero_image": {"alt_text": "colcannon in bowl", "prompt": "editorial food photo"},
            "gallery_images": [{"alt_text": "potatoes in pot", "prompt": "step photo"}],
            "confidence": {"overall": 0.9, "title": 0.9, "ingredients": 0.9, "method": 0.8, "source": 0.7},
            "warnings": [],
        }
        data.update(overrides)
        return data

    def test_upload_page_requires_login(self):
        response = self.client.get(reverse("recipes:recipe_create_from_screenshot"))
        self.assertEqual(response.status_code, 302)

    def test_upload_page_uses_recipe_creation_hero_for_staff_author(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("recipes:recipe_create_from_screenshot"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hero--recipe-form")
        self.assertContains(response, "hero--recipe-tools")
        self.assertContains(response, "images/hero-recipes")
        self.assertContains(response, "Create Recipe from Screenshot")
        self.assertContains(response, "Create New Recipe")
        self.assertContains(response, "Generate AI Recipe")
        self.assertContains(response, reverse("recipes:recipe_create"))
        self.assertContains(response, reverse("recipes:generate_recipe"))

    def test_invalid_file_type_is_rejected(self):
        self.client.force_login(self.user)
        bad = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
        response = self.client.post(reverse("recipes:recipe_create_from_screenshot"), {"screenshot": bad})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a JPG, PNG, or WebP screenshot.")

    def test_oversized_file_is_rejected(self):
        self.client.force_login(self.user)
        too_big = SimpleUploadedFile("screenshot.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
        response = self.client.post(reverse("recipes:recipe_create_from_screenshot"), {"screenshot": too_big})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "5 MB or smaller")

    @patch("recipes.views.extract_recipe_from_image", side_effect=ScreenshotExtractionError("Image quality is too poor to extract a recipe."))
    def test_poor_extraction_does_not_create_recipe(self, extractor):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("recipes:recipe_create_from_screenshot"),
            {"screenshot": self.upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Image quality is too poor to extract a recipe.")
        self.assertEqual(Recipe.objects.count(), 0)

    @patch("recipes.views.extract_recipe_from_image", side_effect=ScreenshotExtractionError("AI response was not valid JSON."))
    def test_invalid_ai_json_does_not_create_recipe(self, extractor):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("recipes:recipe_create_from_screenshot"),
            {"screenshot": self.upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI response was not valid JSON.")
        self.assertEqual(Recipe.objects.count(), 0)

    @patch("recipes.views.generate_reconstructed_hero_image", return_value={})
    @patch("recipes.views.extract_recipe_from_image")
    def test_valid_extraction_creates_pending_recipe_owned_by_user(self, extractor, image_generator):
        extractor.return_value = self.valid_extraction()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("recipes:recipe_create_from_screenshot"),
            {"screenshot": self.upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review Extracted Recipe")
        token = response.context["upload_token"]
        post_data = {
            "upload_token": token,
            "confirm_import": "1",
            "title": "Edited Screenshot Colcannon",
            "short_description": "Updated description.",
            "category": Recipe.Category.TRADITIONAL_IRISH_DISHES,
            "additional_categories": [Recipe.Category.EVERYDAY_IRISH_COOKING],
            "difficulty": Recipe.Difficulty.MEDIUM,
            "prep_time_minutes": "30",
            "cook_time_minutes": "25",
            "servings": "4",
            "ingredients": "Potatoes\nCabbage\nButter",
            "method": "Boil the potatoes.\nFold in the cabbage.",
            "tips": "Serve immediately.",
            "irish_context": "A homely potato dish.",
            "author_commentary": "Seen in a screenshot.",
            "source_type": Recipe.SourceType.WEBSITE,
            "source_title": "Example Recipe",
            "source_author": "Example Author",
            "source_url": "https://example.com/recipe",
            "source_note": "Manual review required.",
            "allergens": ["milk"],
            "hero_image_alt_text": "edited alt text",
            "image_rights_status": Recipe.ImageRightsStatus.NOT_APPLICABLE,
            "image_rights_note": "",
        }
        confirm = self.client.post(reverse("recipes:recipe_create_from_screenshot_confirm"), post_data)
        self.assertEqual(confirm.status_code, 302)
        recipe = Recipe.objects.get()
        self.assertEqual(recipe.title, "Edited Screenshot Colcannon")
        self.assertEqual(recipe.author, self.author)
        self.assertEqual(recipe.status, Recipe.Status.PENDING)
        self.assertEqual(recipe.source_type, Recipe.SourceType.WEBSITE)
        self.assertFalse(recipe.confirmed_own_work)
        self.assertFalse(recipe.confirmed_image_rights)
        self.assertFalse(recipe.confirmed_rules)
        self.assertEqual(recipe.allergens, "milk")

    @patch("recipes.views.generate_reconstructed_hero_image")
    @patch("recipes.views.extract_recipe_from_image")
    def test_generated_screenshot_image_is_attached_to_recipe(self, extractor, image_generator):
        extractor.return_value = self.valid_extraction()
        image = BytesIO()
        Image.new("RGB", (64, 64), (24, 76, 58)).save(image, format="PNG")
        temp_path = default_storage.save(
            "recipe_images/temp_screenshot_hero_test.png",
            ContentFile(image.getvalue()),
        )
        image_generator.return_value = {
            "generated_hero_image_path": temp_path,
            "generated_hero_image_url": default_storage.url(temp_path),
            "generated_hero_image_prompt": "High-quality realistic food photography of colcannon.",
        }

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("recipes:recipe_create_from_screenshot"),
            {"screenshot": self.upload},
        )
        token = response.context["upload_token"]
        post_data = {
            "upload_token": token,
            "confirm_import": "1",
            "title": "Generated Image Colcannon",
            "short_description": "Updated description.",
            "category": Recipe.Category.TRADITIONAL_IRISH_DISHES,
            "additional_categories": [Recipe.Category.EVERYDAY_IRISH_COOKING],
            "difficulty": Recipe.Difficulty.MEDIUM,
            "prep_time_minutes": "30",
            "cook_time_minutes": "25",
            "servings": "4",
            "ingredients": "Potatoes\nCabbage\nButter",
            "method": "Boil the potatoes.\nFold in the cabbage.",
            "tips": "Serve immediately.",
            "irish_context": "A homely potato dish.",
            "author_commentary": "Seen in a screenshot.",
            "source_type": Recipe.SourceType.WEBSITE,
            "source_title": "Example Recipe",
            "source_author": "Example Author",
            "source_url": "https://example.com/recipe",
            "source_note": "Manual review required.",
            "allergens": ["milk"],
            "hero_image_alt_text": "generated colcannon image",
            "image_rights_status": Recipe.ImageRightsStatus.NOT_APPLICABLE,
            "image_rights_note": "",
        }
        confirm = self.client.post(reverse("recipes:recipe_create_from_screenshot_confirm"), post_data)

        self.assertEqual(confirm.status_code, 302)
        recipe = Recipe.objects.get()
        self.assertTrue(recipe.hero_image.name)
        self.assertEqual(recipe.image_rights_status, Recipe.ImageRightsStatus.AI_GENERATED)
        self.assertIn("AI-generated image via", recipe.image_rights_note)
        self.assertFalse(default_storage.exists(temp_path))

    @patch("recipes.views.generate_reconstructed_hero_image", side_effect=RuntimeError("image generation failed"))
    @patch("recipes.views.extract_recipe_from_image")
    def test_image_generation_failure_keeps_text_import_flow(self, extractor, image_generator):
        extractor.return_value = self.valid_extraction()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("recipes:recipe_create_from_screenshot"),
            {"screenshot": self.upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review Extracted Recipe")
        self.assertContains(response, "replacement image could not be generated")
        self.assertEqual(Recipe.objects.count(), 0)

    def test_normalisation_marks_unclear_source_and_infers_allergens(self):
        payload = self.valid_extraction(source={"source_type": "original", "source_title": "", "source_author": "", "source_url": "", "source_note": ""}, ingredients="Flour\nMilk\nEggs")
        normalised = normalise_extracted_recipe(payload)
        self.assertNotEqual(normalised["source_type"], Recipe.SourceType.ORIGINAL)
        self.assertIn("milk", normalised["allergens"])
        self.assertIn("eggs", normalised["allergens"])

    def test_authoring_form_saves_additional_categories(self):
        form = RecipeAuthoringForm(
            data={
                "title": "Heritage Stew",
                "short_description": "Traditional but weeknight-friendly.",
                "category": Recipe.Category.IRISH_CULINARY_HERITAGE,
                "additional_categories": [
                    Recipe.Category.EVERYDAY_IRISH_COOKING,
                    Recipe.Category.SOUPS_AND_STEWS,
                ],
                "difficulty": Recipe.Difficulty.EASY,
                "prep_time_minutes": 20,
                "cook_time_minutes": 80,
                "servings": 4,
                "calories": "",
                "ingredients": "Potatoes - 800g",
                "method": "1. Simmer slowly",
                "tips": "",
                "irish_context": "",
                "author_commentary": "",
                "source_type": Recipe.SourceType.ORIGINAL,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "image_rights_status": Recipe.ImageRightsStatus.OWN,
                "image_rights_note": "",
                "confirm_own_work": "on",
                "confirm_image_rights": "on",
                "confirm_rules": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        recipe = form.save()

        self.assertEqual(
            recipe.get_additional_category_values(),
            [
                Recipe.Category.EVERYDAY_IRISH_COOKING,
                Recipe.Category.SOUPS_AND_STEWS,
            ],
        )

    def test_authoring_form_requires_credit_for_licensed_image_rights(self):
        form = RecipeAuthoringForm(
            data={
                "title": "Licensed Stew",
                "short_description": "Traditional but weeknight-friendly.",
                "category": Recipe.Category.IRISH_CULINARY_HERITAGE,
                "additional_categories": [],
                "difficulty": Recipe.Difficulty.EASY,
                "prep_time_minutes": 20,
                "cook_time_minutes": 80,
                "servings": 4,
                "calories": "",
                "ingredients": "Potatoes - 800g",
                "method": "1. Simmer slowly",
                "tips": "",
                "irish_context": "",
                "author_commentary": "",
                "source_type": Recipe.SourceType.ORIGINAL,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "image_rights_status": Recipe.ImageRightsStatus.LICENSED,
                "image_rights_note": "",
                "confirm_own_work": "on",
                "confirm_image_rights": "on",
                "confirm_rules": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image_rights_note", form.errors)

    def test_authoring_form_requires_source_detail_for_external_recipe_source(self):
        form = RecipeAuthoringForm(
            data={
                "title": "Cookbook Stew",
                "short_description": "Traditional but weeknight-friendly.",
                "category": Recipe.Category.IRISH_CULINARY_HERITAGE,
                "additional_categories": [],
                "difficulty": Recipe.Difficulty.EASY,
                "prep_time_minutes": 20,
                "cook_time_minutes": 80,
                "servings": 4,
                "calories": "",
                "ingredients": "Potatoes - 800g",
                "method": "1. Simmer slowly",
                "tips": "",
                "irish_context": "",
                "author_commentary": "",
                "source_type": Recipe.SourceType.COOKBOOK,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "image_rights_status": Recipe.ImageRightsStatus.OWN,
                "image_rights_note": "",
                "confirm_own_work": "on",
                "confirm_image_rights": "on",
                "confirm_rules": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("source_note", form.errors)

    def _recipe_admin_payload(self, **overrides):
        payload = {
            "title": "Test pie",
            "short_description": "",
            "prep_time_minutes": 20,
            "cook_time_minutes": 40,
            "servings": 4,
            "calories": "",
            "difficulty": Recipe.Difficulty.EASY,
            "category": Recipe.Category.EVERYDAY_IRISH_COOKING,
            "ingredients": "Potatoes - 800g",
            "method": "1. Boil potatoes",
            "tips": "",
            "irish_context": "",
            "author_commentary": "",
            "selected_allergens": [],
            "additional_categories": [],
            "source_type": Recipe.SourceType.ORIGINAL,
            "source_title": "",
            "source_author": "",
            "source_url": "",
            "source_note": "",
            "image_rights_status": Recipe.ImageRightsStatus.OWN,
            "image_rights_note": "",
            "status": Recipe.Status.PENDING,
        }
        payload.update(overrides)
        return payload

    def test_recipe_admin_does_not_have_status_in_list_editable(self):
        self.assertNotIn("status", RecipeAdmin.list_editable)

    def test_recipe_admin_form_rejects_profanity_in_title(self):
        form = RecipeAdminForm(data=self._recipe_admin_payload(title="bastard pie"))

        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("bastard", str(form.errors["title"]))

    def test_recipe_admin_form_rejects_profanity_in_method(self):
        form = RecipeAdminForm(data=self._recipe_admin_payload(method="1. bastard step"))

        self.assertFalse(form.is_valid())
        self.assertIn("method", form.errors)

    def test_recipe_admin_form_rejects_non_original_source_without_source_fields(self):
        form = RecipeAdminForm(
            data=self._recipe_admin_payload(
                source_type=Recipe.SourceType.COOKBOOK,
                source_title="",
                source_author="",
                source_url="",
                source_note="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("source_note", form.errors)

    def test_recipe_admin_form_requires_image_rights_note_for_licensed(self):
        form = RecipeAdminForm(
            data=self._recipe_admin_payload(
                image_rights_status=Recipe.ImageRightsStatus.LICENSED,
                image_rights_note="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image_rights_note", form.errors)

    def test_recipe_admin_form_requires_image_rights_note_for_public_domain(self):
        form = RecipeAdminForm(
            data=self._recipe_admin_payload(
                image_rights_status=Recipe.ImageRightsStatus.PUBLIC_DOMAIN,
                image_rights_note="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image_rights_note", form.errors)


class AuthenticationPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ciaran",
            password="StewPot123!",
        )

    def test_signup_page_renders(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/signup.html")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_login_authenticates_user_and_redirects_home(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "ciaran",
                "password": "StewPot123!",
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    @override_settings(
        SIGNUP_REQUIRE_EMAIL_CONFIRMATION=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_signup_creates_inactive_account_and_shows_activation_pending(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newcook",
                "default_avatar": RecipeAuthor.DefaultAvatar.NEUTRAL,
                "email": "newcook@example.com",
                "password1": "KitchenTable123!",
                "password2": "KitchenTable123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/activation_pending.html")
        user = get_user_model().objects.get(username="newcook")
        self.assertFalse(user.is_active)
        self.assertTrue(RecipeAuthor.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirm your CulinEire account", mail.outbox[0].subject)

    def test_anonymous_header_shows_sign_in_and_join_links(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("login"))
        self.assertContains(response, reverse("signup"))
        self.assertContains(response, "Sign In")
        self.assertContains(response, "Join")

    def test_authenticated_header_shows_username_and_sign_out(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "ciaran")
        self.assertContains(response, "Welcome Back")
        self.assertContains(response, "Sign Out")
        self.assertNotContains(response, "Hello, ciaran")
        self.assertNotContains(response, "Join")

    def test_authenticated_header_shows_staff_author_actions(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
            bio="Irish cooking notes.",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Ciaran")
        self.assertContains(response, "My Content Studio")
        self.assertContains(response, reverse("recipes:author_dashboard"))
        self.assertContains(response, "Messages")
        self.assertContains(response, reverse("messaging:inbox"))
        self.assertContains(response, "Moderation Panel")
        self.assertContains(response, reverse("recipes:moderation_panel"))
        self.assertNotContains(response, "My Recipes")
        self.assertNotContains(response, "My Pinch")
        self.assertNotContains(response, "My Articles")
        self.assertNotContains(response, "My Collection")
        self.assertNotContains(response, "Profile")
        self.assertNotContains(response, "(+ New)")
        self.assertNotContains(response, reverse("recipes:recipe_create"))
        self.assertNotContains(response, reverse("articles:article_create"))

    def test_author_dashboard_requires_login(self):
        response = self.client.get(reverse("recipes:author_dashboard"))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("recipes:author_dashboard")}',
        )

    def test_author_dashboard_requires_linked_author_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("recipes:author_dashboard"))

        self.assertRedirects(response, reverse("home"))

    def test_home_uses_article_gallery_image_when_article_image_is_missing(self):
        author = RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        article = Article.objects.create(
            title="Gallery Home Article",
            slug="gallery-home-article",
            author=author,
            body="Gallery home body",
            published="2026-05-21",
            status=Article.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )
        gallery_image = ArticleImage.objects.create(
            article=article,
            image="articles/gallery-home/gallery/img1-test.png",
            sort_order=1,
        )

        response = self.client.get(reverse("home"))

        self.assertContains(response, gallery_image.image.url, html=False)

    def test_authenticated_header_does_not_guess_author_by_slug(self):
        RecipeAuthor.objects.create(
            name="Ciaran",
            slug="ciaran",
            bio="Home kitchen notes.",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "ciaran")
        self.assertNotContains(response, reverse("recipes:author_detail", kwargs={"slug": "ciaran"}))
        self.assertNotContains(response, reverse("recipes:recipe_create"))

    def test_recipe_create_requires_linked_author_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("recipes:recipe_create"))

        self.assertRedirects(response, reverse("home"))

    def test_recipe_create_form_enables_autosave(self):
        RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("recipes:recipe_create"))

        self.assertContains(response, 'data-autosave="true"', html=False)
        self.assertContains(response, "recipe-authoring:/recipes/create/", html=False)

    def test_recipe_create_shows_generation_tools_to_staff_author(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("recipes:recipe_create"))

        self.assertContains(response, "hero--recipe-form")
        self.assertContains(response, "hero--recipe-tools")
        self.assertContains(response, "images/hero-recipes")
        self.assertContains(response, "Generate AI Recipe")
        self.assertContains(response, "Generate Screen Recipe")
        self.assertContains(response, reverse("recipes:generate_recipe"))
        self.assertContains(response, reverse("recipes:recipe_create_from_screenshot"))

    def test_recipe_create_hides_generation_tools_from_regular_author(self):
        RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("recipes:recipe_create"))

        self.assertNotContains(response, "Generate AI Recipe")
        self.assertNotContains(response, "Generate Screen Recipe")

    def test_login_form_does_not_enable_autosave(self):
        response = self.client.get(reverse("login"))

        self.assertNotContains(response, 'data-autosave="true"', html=False)

    def test_author_edit_requires_linked_author_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("recipes:author_edit"))

        self.assertRedirects(response, reverse("home"))

    def test_author_edit_updates_linked_author_profile(self):
        author = RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
            bio="Old author note.",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("recipes:author_edit"),
            {
                "name": "Ciaran O Kitchen",
                "default_avatar": RecipeAuthor.DefaultAvatar.NEUTRAL,
                "bio": "Modern Irish cooking notes.",
                "avatar": "",
            },
        )

        author.refresh_from_db()
        self.assertRedirects(response, author.get_absolute_url())
        self.assertEqual(author.name, "Ciaran O Kitchen")
        self.assertEqual(author.slug, "ciaran")
        self.assertEqual(author.bio, "Modern Irish cooking notes.")
        self.assertEqual(author.user, self.user)

    def test_recipe_create_assigns_linked_author(self):
        author = RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("recipes:recipe_create"),
            {
                "title": "Test Kitchen Pie",
                "short_description": "A practical pie for testing.",
                "category": Recipe.Category.EVERYDAY_IRISH_COOKING,
                "additional_categories": [Recipe.Category.IRISH_CULINARY_HERITAGE],
                "difficulty": Recipe.Difficulty.EASY,
                "prep_time_minutes": 20,
                "cook_time_minutes": 40,
                "servings": 4,
                "calories": "",
                "ingredients": "Potatoes\nBeef",
                "method": "Cook it slowly.",
                "tips": "",
                "irish_context": "",
                "author_commentary": "",
                "source_type": Recipe.SourceType.ORIGINAL,
                "source_title": "",
                "source_author": "",
                "source_url": "",
                "source_note": "",
                "image_rights_status": Recipe.ImageRightsStatus.OWN,
                "image_rights_note": "",
                "confirm_own_work": "on",
                "confirm_image_rights": "on",
                "confirm_rules": "on",
            },
        )

        recipe = Recipe.objects.get(title="Test Kitchen Pie")
        self.assertRedirects(response, recipe.get_absolute_url())
        self.assertEqual(recipe.author, author)
        self.assertEqual(
            recipe.get_additional_category_values(),
            [Recipe.Category.IRISH_CULINARY_HERITAGE],
        )

    def test_article_create_assigns_linked_author(self):
        author = RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("articles:article_create"),
            {
                "title": "Kitchen Notes",
                "excerpt": "Short notes from the kitchen.",
                "category": "baking",
                "published": "2026-04-29",
                "related_recipe": "",
                "body": "Useful notes for Irish cooking.",
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
            },
        )

        article = Article.objects.get(title="Kitchen Notes")
        self.assertRedirects(response, article.get_absolute_url())
        self.assertEqual(article.author, author)

    def test_public_author_profile_counts_only_approved_content(self):
        author = RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        Recipe.objects.create(
            title="Approved Recipe",
            slug="approved-recipe",
            author=author,
            ingredients="Potatoes",
            method="Boil",
            status=Recipe.Status.APPROVED,
        )
        Recipe.objects.create(
            title="Pending Recipe",
            slug="pending-recipe",
            author=author,
            ingredients="Carrots",
            method="Roast",
            status=Recipe.Status.PENDING,
        )
        Article.objects.create(
            title="Approved Article",
            slug="approved-article",
            author=author,
            body="Approved body",
            published="2026-05-20",
            status=Article.Status.APPROVED,
        )
        Article.objects.create(
            title="Pending Article",
            slug="pending-article",
            author=author,
            body="Pending body",
            published="2026-05-20",
            status=Article.Status.PENDING,
        )

        response = self.client.get(author.get_absolute_url())

        self.assertEqual(response.context["recipe_count"], 1)
        self.assertEqual(response.context["article_count"], 1)
        self.assertNotContains(response, "Awaiting Moderation")

    def test_owner_author_profile_counts_all_managed_content(self):
        author = RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        Recipe.objects.create(
            title="Approved Recipe",
            slug="approved-recipe",
            author=author,
            ingredients="Potatoes",
            method="Boil",
            status=Recipe.Status.APPROVED,
        )
        Recipe.objects.create(
            title="Rejected Recipe",
            slug="rejected-recipe",
            author=author,
            ingredients="Carrots",
            method="Roast",
            status=Recipe.Status.REJECTED,
        )
        Article.objects.create(
            title="Approved Article",
            slug="approved-article",
            author=author,
            body="Approved body",
            published="2026-05-20",
            status=Article.Status.APPROVED,
        )
        Article.objects.create(
            title="Pending Article",
            slug="pending-article",
            author=author,
            body="Pending body",
            published="2026-05-20",
            status=Article.Status.PENDING,
        )
        self.client.force_login(self.user)

        response = self.client.get(author.get_absolute_url())

        self.assertEqual(response.context["recipe_count"], 2)
        self.assertEqual(response.context["article_count"], 2)
        self.assertContains(response, "Content Dashboard")
        self.assertContains(response, "Rejected Recipe")
        self.assertContains(response, "Pending Article")

    def test_moderator_author_profile_counts_all_managed_content(self):
        author = RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
        )
        moderator = get_user_model().objects.create_user(
            username="moderator",
            password="pass",
            is_staff=True,
        )
        Recipe.objects.create(
            title="Approved Recipe",
            slug="approved-recipe",
            author=author,
            ingredients="Potatoes",
            method="Boil",
            status=Recipe.Status.APPROVED,
        )
        Recipe.objects.create(
            title="Pending Recipe",
            slug="pending-recipe",
            author=author,
            ingredients="Carrots",
            method="Roast",
            status=Recipe.Status.PENDING,
        )
        Article.objects.create(
            title="Approved Article",
            slug="approved-article",
            author=author,
            body="Approved body",
            published="2026-05-20",
            status=Article.Status.APPROVED,
        )
        Article.objects.create(
            title="Rejected Article",
            slug="rejected-article",
            author=author,
            body="Rejected body",
            published="2026-05-20",
            status=Article.Status.REJECTED,
        )
        self.client.force_login(moderator)

        response = self.client.get(author.get_absolute_url())

        self.assertEqual(response.context["recipe_count"], 2)
        self.assertEqual(response.context["article_count"], 2)
        self.assertContains(response, "Content Dashboard")
        self.assertContains(response, "Pending Recipe")
        self.assertContains(response, "Rejected Article")


class RecipeInteractionTests(TestCase):
    def setUp(self):
        self.recipe = Recipe.objects.create(
            title="Irish Stew",
            ingredients="2 potatoes\n1 onion",
            method="1. Chop everything\n2. Cook slowly",
            status=Recipe.Status.APPROVED,
        )

    def test_submit_recipe_rating_updates_existing_user_rating_without_duplicate(self):
        user = get_user_model().objects.create_user(username="rater", password="Kitchen123!")
        self.client.force_login(user)
        url = reverse("recipes:submit_recipe_rating", args=[self.recipe.slug])

        first_response = self.client.post(url, {"value": 5})
        second_response = self.client.post(url, {"value": 4})

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(RecipeRating.objects.filter(recipe=self.recipe).count(), 1)
        rating = RecipeRating.objects.get(recipe=self.recipe)
        self.assertEqual(rating.user, user)
        self.assertEqual(rating.value, 4)

    def test_submit_recipe_comment_blocks_duplicate_payloads_in_session(self):
        user = get_user_model().objects.create_user(username="niamh", password="Kitchen123!")
        self.client.force_login(user)

        url = reverse("recipes:submit_recipe_comment", args=[self.recipe.slug])
        payload = {
            "content": "This turned out beautifully.",
            "website": "",
        }

        first_response = self.client.post(url, payload)
        second_response = self.client.post(url, payload)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(RecipeComment.objects.filter(recipe=self.recipe).count(), 1)


class RecipeCategoryAssignmentTests(TestCase):
    def test_category_page_includes_recipe_from_additional_category(self):
        recipe = Recipe.objects.create(
            title="Irish Stew",
            category=Recipe.Category.EVERYDAY_IRISH_COOKING,
            ingredients="2 potatoes\n1 onion",
            method="1. Chop everything\n2. Cook slowly",
            status=Recipe.Status.APPROVED,
        )
        recipe.additional_category_links.create(category=Recipe.Category.IRISH_CULINARY_HERITAGE)

        response = self.client.get(
            reverse(
                "recipes:category_detail",
                kwargs={"category_slug": "irish-culinary-heritage"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Irish Stew")

    def test_category_page_deduplicates_primary_category_matches_with_extra_links(self):
        recipe = Recipe.objects.create(
            title="Duplicate Guard Stew",
            category=Recipe.Category.IRISH_CULINARY_HERITAGE,
            ingredients="2 potatoes\n1 onion",
            method="1. Chop everything\n2. Cook slowly",
            status=Recipe.Status.APPROVED,
        )
        recipe.additional_category_links.create(category=Recipe.Category.EVERYDAY_IRISH_COOKING)
        recipe.additional_category_links.create(category=Recipe.Category.SOUPS_AND_STEWS)

        response = self.client.get(
            reverse(
                "recipes:category_detail",
                kwargs={"category_slug": "irish-culinary-heritage"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["recipes"]), [recipe])


class SecuritySettingsModuleTests(SimpleTestCase):
    def tearDown(self):
        importlib.reload(importlib.import_module("config.settings"))
        super().tearDown()

    @staticmethod
    def reload_project_settings(**env_overrides):
        module = importlib.import_module("config.settings")
        base_env = {
            "DJANGO_SECRET_KEY": "x" * 64,
        }
        base_env.update(env_overrides)
        with patch.dict(os.environ, base_env, clear=False):
            managed_keys = {
                "DJANGO_ENV",
                "DJANGO_DEBUG",
                "DJANGO_ALLOWED_HOSTS",
                "DJANGO_CSRF_TRUSTED_ORIGINS",
                "DJANGO_SERVE_STATIC_LOCALLY",
                "DJANGO_SERVE_MEDIA_LOCALLY",
                "DJANGO_SECURE_SSL_REDIRECT",
                "DJANGO_SECURE_HSTS_SECONDS",
                "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
                "DJANGO_SECURE_HSTS_PRELOAD",
                "DJANGO_SESSION_COOKIE_SECURE",
                "DJANGO_CSRF_COOKIE_SECURE",
                "DJANGO_SECURE_PROXY_SSL_HEADER",
            }
            for key in managed_keys - set(base_env):
                os.environ.pop(key, None)
            with patch("dotenv.load_dotenv", return_value=False):
                return importlib.reload(module)

    def test_development_environment_defaults_to_http_friendly_security(self):
        project_settings = self.reload_project_settings(
            DJANGO_ENV="development",
            DJANGO_DEBUG="True",
            DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost,::1,culineire.localhost",
            DJANGO_CSRF_TRUSTED_ORIGINS=(
                "http://127.0.0.1:8000,"
                "http://localhost:8000,"
                "http://culineire.localhost:8000"
            ),
        )

        self.assertFalse(project_settings.SECURE_SSL_REDIRECT)
        self.assertEqual(project_settings.SECURE_HSTS_SECONDS, 0)
        self.assertTrue(project_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertTrue(project_settings.SECURE_HSTS_PRELOAD)
        self.assertFalse(project_settings.SESSION_COOKIE_SECURE)
        self.assertFalse(project_settings.CSRF_COOKIE_SECURE)
        self.assertTrue(project_settings.SERVE_STATIC_LOCALLY)
        self.assertTrue(project_settings.SERVE_MEDIA_LOCALLY)

    def test_production_environment_defaults_to_strict_https_security(self):
        project_settings = self.reload_project_settings(
            DJANGO_ENV="production",
            DJANGO_DEBUG="False",
            DJANGO_ALLOWED_HOSTS="culineire.ie,www.culineire.ie",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://culineire.ie,https://www.culineire.ie",
        )

        self.assertTrue(project_settings.SECURE_SSL_REDIRECT)
        self.assertEqual(project_settings.SECURE_HSTS_SECONDS, 31536000)
        self.assertTrue(project_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertTrue(project_settings.SECURE_HSTS_PRELOAD)
        self.assertTrue(project_settings.SESSION_COOKIE_SECURE)
        self.assertTrue(project_settings.CSRF_COOKIE_SECURE)
        self.assertFalse(project_settings.SERVE_STATIC_LOCALLY)
        self.assertFalse(project_settings.SERVE_MEDIA_LOCALLY)

    def test_standard_django_security_middleware_is_configured(self):
        self.assertIn("django.middleware.security.SecurityMiddleware", settings.MIDDLEWARE)
        self.assertNotIn("config.middleware.LocalhostAwareSecurityMiddleware", settings.MIDDLEWARE)


class SecurityMiddlewareEnvironmentTests(TestCase):
    @override_settings(
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=0,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        ALLOWED_HOSTS=["127.0.0.1", "localhost", "::1", "culineire.localhost", "culineire.ie"],
    )
    def test_development_localhost_does_not_redirect_to_https(self):
        response = self.client.get("/", SERVER_NAME="localhost", SERVER_PORT=8000)

        self.assertEqual(response.status_code, 200)

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=0,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        ALLOWED_HOSTS=["127.0.0.1", "localhost", "::1", "culineire.localhost", "culineire.ie"],
    )
    def test_development_loopback_does_not_redirect_to_https(self):
        response = self.client.get("/", SERVER_NAME="127.0.0.1", SERVER_PORT=8000)

        self.assertEqual(response.status_code, 200)

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=0,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        ALLOWED_HOSTS=["127.0.0.1", "localhost", "::1", "culineire.localhost", "culineire.ie"],
    )
    def test_development_culineire_localhost_does_not_redirect_to_https(self):
        response = self.client.get("/", SERVER_NAME="culineire.localhost", SERVER_PORT=8000)

        self.assertEqual(response.status_code, 200)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[],
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        ALLOWED_HOSTS=["127.0.0.1", "localhost", "::1", "culineire.localhost", "culineire.ie"],
    )
    def test_production_domain_redirects_to_https(self):
        response = self.client.get("/", SERVER_NAME="culineire.ie", SERVER_PORT=80)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "https://culineire.ie/")

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=0,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        ALLOWED_HOSTS=["127.0.0.1", "localhost", "::1", "culineire.localhost", "culineire.ie"],
    )
    def test_hsts_is_disabled_in_development(self):
        response = self.client.get("/", SERVER_NAME="localhost", SERVER_PORT=443, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Strict-Transport-Security", response.headers)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        ALLOWED_HOSTS=["127.0.0.1", "localhost", "::1", "culineire.localhost", "culineire.ie"],
    )
    def test_hsts_is_enabled_in_production(self):
        response = self.client.get("/", SERVER_NAME="culineire.ie", SERVER_PORT=443, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=31536000; includeSubDomains; preload",
        )


class SiteResearchProgressViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="reader", password="pass")
        self.moderator = user_model.objects.create_user(username="mod", password="pass", is_staff=True)
        self.greenbear_user = user_model.objects.create_user(username="greenbear", password="pass")
        RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={"user": self.greenbear_user, "name": "GreenBear"},
        )
        self.bearseeker_user = user_model.objects.create_user(username="bear-admin", password="pass")
        RecipeAuthor.objects.create(
            user=self.bearseeker_user,
            name="Bear Admin",
            slug="bear-admin",
            has_bearseeker_privileges=True,
        )

    def test_research_progress_requires_moderator(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("recipes:site_research_progress"))
        self.assertEqual(response.status_code, 404)

    def test_moderator_can_view_read_only_update_plan(self):
        self.client.force_login(self.moderator)
        response = self.client.get(reverse("recipes:site_research_progress"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Site Updates Plan")
        self.assertContains(response, "One-Year Plan")
        html = response.content.decode()
        research_section = html.split('class="page-section moderation-page automation-page research-page"', 1)[1]
        research_section = research_section.split("</main>", 1)[0]
        self.assertNotIn("<form", research_section)

    def test_greenbear_owner_can_view_update_plan_without_staff_flag(self):
        self.client.force_login(self.greenbear_user)
        response = self.client.get(reverse("recipes:site_research_progress"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Site Updates Plan")

    def test_bearseeker_privileges_do_not_grant_update_plan_access(self):
        self.client.force_login(self.bearseeker_user)
        response = self.client.get(reverse("recipes:site_research_progress"))
        self.assertEqual(response.status_code, 404)

        response = self.client.get(reverse("recipes:moderation_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("recipes:site_research_progress"))

    def test_moderation_panel_links_to_update_plan(self):
        self.client.force_login(self.moderator)
        response = self.client.get(reverse("recipes:moderation_panel"))
        self.assertContains(response, reverse("recipes:site_research_progress"))
        self.assertContains(response, "Site Updates Plan")


class RecipeDetailAccessibilityMarkupTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username="chef", password="pass")
        self.user = user
        self.author = RecipeAuthor.objects.create(user=user, name="Chef", slug="chef")

    def test_method_steps_use_css_counter_not_dom_step_number(self):
        recipe = Recipe.objects.create(
            title="Numbered Method Test",
            slug="numbered-method-test",
            author=self.author,
            short_description="A method numbering test.",
            category=Recipe.Category.EVERYDAY_IRISH_COOKING,
            ingredients="Potatoes",
            method="1. Wash the potatoes\n2. Bake until tender",
            status=Recipe.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
            image_rights_status=Recipe.ImageRightsStatus.NOT_APPLICABLE,
        )

        response = self.client.get(recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wash the potatoes")
        self.assertNotContains(response, "method-steps__number")
        self.assertNotContains(response, 'aria-label="Step 1"')

    def test_managed_recipe_hero_shows_author_actions_only(self):
        recipe = Recipe.objects.create(
            title="Managed Hero Test",
            slug="managed-hero-test",
            author=self.author,
            short_description="A managed recipe hero test.",
            category=Recipe.Category.EVERYDAY_IRISH_COOKING,
            ingredients="Potatoes",
            method="Bake until tender",
            status=Recipe.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
            image_rights_status=Recipe.ImageRightsStatus.NOT_APPLICABLE,
        )

        self.client.force_login(self.user)
        response = self.client.get(recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        # Author management controls now in .staff-bar below breadcrumb
        self.assertContains(response, "Edit Recipe")
        self.assertContains(response, "Delete Recipe")
        self.assertContains(response, "Generate Pinch")


class RecipeDetailStructuredDataTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username="schema-chef", password="pass")
        self.author = RecipeAuthor.objects.create(user=user, name="Schema Chef", slug="schema-chef")

    def test_recipe_detail_outputs_parseable_recipe_and_breadcrumb_json_ld(self):
        recipe = Recipe.objects.create(
            title="Structured Coddle",
            slug="structured-coddle",
            author=self.author,
            short_description="A structured data test recipe.",
            category=Recipe.Category.SOUPS_AND_STEWS,
            prep_time_minutes=10,
            cook_time_minutes=40,
            servings=4,
            calories=320,
            ingredients="Potatoes\nSausages\nOnions",
            method="1. Slice the onions\n2. Simmer everything gently",
            status=Recipe.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
            image_rights_status=Recipe.ImageRightsStatus.NOT_APPLICABLE,
        )

        response = self.client.get(recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        scripts = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            response.content.decode(),
            flags=re.S,
        )
        schemas = [json.loads(script) for script in scripts]
        recipe_schema = next(schema for schema in schemas if schema.get("@type") == "Recipe")
        breadcrumb_schema = next(schema for schema in schemas if schema.get("@type") == "BreadcrumbList")

        self.assertEqual(recipe_schema["name"], "Structured Coddle")
        self.assertEqual(recipe_schema["recipeCategory"], "Soups and Stews")
        self.assertEqual(recipe_schema["prepTime"], "PT10M")
        self.assertEqual(recipe_schema["cookTime"], "PT40M")
        self.assertEqual(recipe_schema["totalTime"], "PT50M")
        self.assertEqual(recipe_schema["recipeIngredient"], ["Potatoes", "Sausages", "Onions"])
        self.assertEqual(recipe_schema["recipeInstructions"][0]["@type"], "HowToStep")
        self.assertEqual(recipe_schema["recipeInstructions"][0]["text"], "Slice the onions")
        self.assertTrue(recipe_schema["recipeInstructions"][0]["url"].endswith("#step-1"))
        self.assertEqual(
            [item["position"] for item in breadcrumb_schema["itemListElement"]],
            [1, 2, 3],
        )

    def test_recipe_detail_uses_human_fallback_meta_description(self):
        recipe = Recipe.objects.create(
            title="Fallback Meta Bread",
            slug="fallback-meta-bread",
            author=self.author,
            category=Recipe.Category.BREAD_AND_BAKING,
            ingredients="Flour\nWater",
            method="1. Mix\n2. Bake",
            status=Recipe.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
            image_rights_status=Recipe.ImageRightsStatus.NOT_APPLICABLE,
        )

        response = self.client.get(recipe.get_absolute_url())

        self.assertContains(response, "A home-cooking recipe for Fallback Meta Bread on CulinEire.")
        self.assertNotContains(response, "Recipe detail page for")

    def test_recipe_detail_marks_hero_image_as_high_priority(self):
        recipe = Recipe.objects.create(
            title="Priority Hero Bread",
            slug="priority-hero-bread",
            author=self.author,
            category=Recipe.Category.BREAD_AND_BAKING,
            ingredients="Flour\nWater",
            method="1. Mix\n2. Bake",
            status=Recipe.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
            image_rights_status=Recipe.ImageRightsStatus.NOT_APPLICABLE,
        )

        response = self.client.get(recipe.get_absolute_url())

        self.assertContains(response, 'loading="eager"')
        self.assertContains(response, 'fetchpriority="high"')
        self.assertContains(response, 'decoding="async"')


class PublicImagePerformanceHintTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="performance-chef", password="pass")
        self.author = RecipeAuthor.objects.create(user=self.user, name="Performance Chef", slug="performance-chef")
        self.recipe = Recipe.objects.create(
            title="Lazy Card Stew",
            slug="lazy-card-stew",
            author=self.author,
            category=Recipe.Category.SOUPS_AND_STEWS,
            ingredients="Potatoes\nOnions",
            method="1. Chop\n2. Simmer",
            status=Recipe.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
            image_rights_status=Recipe.ImageRightsStatus.NOT_APPLICABLE,
        )
        self.article = Article.objects.create(
            title="Lazy Card Article",
            slug="lazy-card-article",
            author=self.author,
            body="Article body.",
            published=date(2026, 6, 3),
            status=Article.Status.APPROVED,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
            image_rights_status=Article.ImageRightsStatus.NOT_APPLICABLE,
        )

    def test_home_cards_use_eager_async_image_hints(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'loading="eager"')
        self.assertContains(response, 'decoding="async"')

    @override_settings(PINCH_PUBLIC=True)
    def test_home_pinch_carousel_orders_newest_first(self):
        from pinch.models import Pinch

        older_featured = Pinch.objects.create(
            author=self.author,
            title="Older Featured Bite",
            short_description="Older bite.",
            status=Pinch.Status.APPROVED,
            is_featured=True,
        )
        newest = Pinch.objects.create(
            author=self.author,
            title="Newest Bite",
            short_description="Newer bite.",
            status=Pinch.Status.APPROVED,
        )
        now = timezone.now()
        Pinch.objects.filter(pk=older_featured.pk).update(published_at=now - timedelta(days=2))
        Pinch.objects.filter(pk=newest.pk).update(published_at=now)

        response = self.client.get(reverse("home"))

        self.assertEqual(
            [item.title for item in response.context["latest_pinch"][:2]],
            ["Newest Bite", "Older Featured Bite"],
        )

    def test_recipe_list_cards_use_eager_async_image_hints(self):
        response = self.client.get(reverse("recipes:recipe_list"))

        self.assertContains(response, 'loading="eager"')
        self.assertContains(response, 'decoding="async"')

    def test_recipe_mood_categories_panel_removed(self):
        # Mood category panel removed (visual_consistency_polish Group 4)
        response = self.client.get(reverse("recipes:recipe_list"))

        self.assertNotContains(response, 'aria-label="Recipe mood categories"')
        self.assertNotContains(response, "recipe-mood-chip")
        self.assertNotContains(response, "What are you in the mood for today?")

    def test_author_recipe_mini_cards_show_management_actions(self):
        self.client.force_login(self.user)

        response = self.client.get(f'{reverse("recipes:recipe_list")}?author={self.author.slug}')

        self.assertContains(response, "recipe-grid--author-actions")
        self.assertContains(response, reverse("recipes:recipe_edit", kwargs={"slug": self.recipe.slug}))
        self.assertContains(response, reverse("recipes:recipe_delete", kwargs={"slug": self.recipe.slug}))

    def test_author_recipe_list_owner_sees_dashboard_back_link(self):
        self.client.force_login(self.user)

        response = self.client.get(f'{reverse("recipes:recipe_list")}?author={self.author.slug}')

        self.assertContains(response, "Back to My Dashboard")
        self.assertContains(response, reverse("recipes:author_dashboard"))

    def test_author_recipe_list_guest_does_not_see_dashboard_back_link(self):
        response = self.client.get(f'{reverse("recipes:recipe_list")}?author={self.author.slug}')

        self.assertNotContains(response, "Back to My Dashboard")
        self.assertNotContains(response, reverse("recipes:author_dashboard"))

    @override_settings(PINCH_PUBLIC=True)
    def test_public_main_sections_do_not_show_dashboard_back_button(self):
        self.client.force_login(self.user)
        urls = (
            reverse("recipes:recipe_list"),
            reverse("articles:article_list"),
            reverse("pinch:feed"),
            reverse("newsfeed:feed"),
            reverse("sponsors:puzzle"),
            reverse("messaging:contact"),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertNotContains(response, "Back to My Dashboard")
                self.assertNotContains(response, "author-dashboard-back-button")

    @override_settings(PINCH_PUBLIC=True)
    def test_public_section_heroes_hide_author_create_actions(self):
        self.client.force_login(self.user)

        recipe_response = self.client.get(reverse("recipes:recipe_list"))
        recipe_hero = recipe_response.content.decode().split('<div class="hero__actions">', 1)[1].split("</div>", 1)[0]
        self.assertIn("Create Recipe", recipe_hero)
        self.assertIn(reverse("recipes:recipe_create"), recipe_hero)
        self.assertNotIn("Back to My Dashboard", recipe_hero)
        self.assertIn("Pinch", recipe_hero)
        self.assertNotIn("Explore Recipes", recipe_hero)
        self.assertIn("Read Articles", recipe_hero)
        self.assertIn("Sponsors", recipe_hero)

        article_response = self.client.get(reverse("articles:article_list"))
        article_hero = article_response.content.decode().split('<div class="hero__actions">', 1)[1].split("</div>", 1)[0]
        self.assertIn("Create Article", article_hero)
        self.assertIn(reverse("articles:article_create"), article_hero)
        self.assertNotIn("Back to My Dashboard", article_hero)
        self.assertIn("Pinch", article_hero)
        self.assertIn("Explore Recipes", article_hero)
        self.assertNotIn("Read Articles", article_hero)
        self.assertIn("Sponsors", article_hero)

        pinch_response = self.client.get(reverse("pinch:feed"))
        pinch_hero = pinch_response.content.decode().split('<div class="hero__actions">', 1)[1].split("</div>", 1)[0]
        self.assertIn("Create Pinch", pinch_hero)
        self.assertIn(reverse("pinch:create"), pinch_hero)
        self.assertNotIn("Back to My Dashboard", pinch_hero)
        self.assertIn("Explore Recipes", pinch_hero)
        self.assertIn("Read Articles", pinch_hero)
        self.assertIn("Sponsors", pinch_hero)
        self.assertNotIn("Share a Bite +", pinch_hero)

    @override_settings(PINCH_PUBLIC=True)
    def test_author_filtered_heroes_show_page_create_action_only(self):
        self.client.force_login(self.user)

        cases = [
            (self.client.get(f'{reverse("recipes:recipe_list")}?author={self.author.slug}'), "Create Recipe"),
            (self.client.get(f'{reverse("articles:article_list")}?author={self.author.slug}'), "Create Article"),
            (self.client.get(f'{reverse("pinch:feed")}?author={self.author.slug}'), "Create Pinch"),
        ]

        for response, expected_label in cases:
            content = response.content.decode()
            hero = content.split("<section class=\"hero", 1)[1].split("</section>", 1)[0]
            self.assertNotIn("hero-author-cabinet", hero)
            self.assertIn(expected_label, hero)
            self.assertIn("Back to My Dashboard", hero)
            self.assertIn(reverse("recipes:author_dashboard"), hero)
            self.assertNotIn("Explore Recipes", hero)
            self.assertNotIn("Read Articles", hero)
            self.assertNotIn("author-recipes-add", content)
            self.assertNotIn("+ New Recipe", content)
            self.assertNotIn("+ New Article", content)

    def test_article_list_cards_use_eager_async_image_hints(self):
        response = self.client.get(reverse("articles:article_list"))

        self.assertContains(response, 'loading="eager"')
        self.assertContains(response, 'decoding="async"')


class RecipeModerationTrackingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="chef", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Chef",
            slug="chef",
        )
        self.moderator_user = user_model.objects.create_user(
            username="mod",
            password="pass",
            is_staff=True,
        )
        RecipeAuthor.objects.create(
            user=self.moderator_user,
            name="Moderator",
            slug="moderator",
        )
        self.greenbear_user = user_model.objects.create_user(username="greenbear", password="pass")
        self.greenbear_author, _ = RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={"user": self.greenbear_user, "name": "GreenBear"},
        )
        self.recipe = Recipe.objects.create(
            title="Test Recipe",
            slug="test-recipe",
            author=self.author,
            ingredients="Potatoes",
            method="Boil them.",
            status=Recipe.Status.PENDING,
        )

    def recipe_payload(self, **overrides):
        payload = {
            "title": "Updated Recipe",
            "short_description": "Updated description.",
            "category": Recipe.Category.EVERYDAY_IRISH_COOKING,
            "additional_categories": [],
            "difficulty": Recipe.Difficulty.EASY,
            "prep_time_minutes": 10,
            "cook_time_minutes": 20,
            "servings": 4,
            "calories": "",
            "ingredients": "Potatoes\nOnions",
            "method": "Cook slowly.",
            "tips": "",
            "irish_context": "",
            "author_commentary": "",
            "source_type": Recipe.SourceType.ORIGINAL,
            "source_title": "",
            "source_author": "",
            "source_url": "",
            "source_note": "",
            "image_rights_status": Recipe.ImageRightsStatus.NOT_APPLICABLE,
            "image_rights_note": "",
            "confirm_own_work": "on",
            "confirm_image_rights": "on",
            "confirm_rules": "on",
        }
        payload.update(overrides)
        return payload

    def test_recipe_status_includes_needs_changes(self):
        self.assertIn(Recipe.Status.NEEDS_CHANGES, Recipe.Status.values)
        self.assertEqual(Recipe.Status.NEEDS_CHANGES.label, "Needs changes")

    def test_recipe_status_includes_draft(self):
        self.assertIn(Recipe.Status.DRAFT, Recipe.Status.values)
        self.assertEqual(Recipe.Status.DRAFT.label, "Draft")

    def test_author_can_create_recipe_as_draft(self):
        self.client.force_login(self.author_user)

        response = self.client.post(
            reverse("recipes:recipe_create"),
            {**self.recipe_payload(title="Draft Recipe"), "action": "save_draft"},
        )

        recipe = Recipe.objects.get(title="Draft Recipe")
        self.assertRedirects(response, recipe.get_absolute_url())
        self.assertEqual(recipe.status, Recipe.Status.DRAFT)

    def test_author_can_submit_new_recipe_for_review(self):
        self.client.force_login(self.author_user)

        response = self.client.post(
            reverse("recipes:recipe_create"),
            {**self.recipe_payload(title="Submitted Recipe"), "action": "submit_review"},
        )

        recipe = Recipe.objects.get(title="Submitted Recipe")
        self.assertRedirects(response, recipe.get_absolute_url())
        self.assertEqual(recipe.status, Recipe.Status.PENDING)

    def test_greenbear_submit_new_recipe_publishes_without_review(self):
        self.client.force_login(self.greenbear_user)

        response = self.client.post(
            reverse("recipes:recipe_create"),
            {**self.recipe_payload(title="GreenBear Submitted Recipe"), "action": "submit_review"},
        )

        recipe = Recipe.objects.get(title="GreenBear Submitted Recipe")
        self.assertRedirects(response, recipe.get_absolute_url())
        self.assertEqual(recipe.author, self.greenbear_author)
        self.assertEqual(recipe.status, Recipe.Status.APPROVED)

    def test_draft_recipe_is_hidden_from_public_list_category_and_direct_url(self):
        self.recipe.status = Recipe.Status.DRAFT
        self.recipe.category = Recipe.Category.EVERYDAY_IRISH_COOKING
        self.recipe.save(update_fields=["status", "category"])

        list_response = self.client.get(reverse("recipes:recipe_list"))
        category_response = self.client.get(
            reverse("recipes:category_detail", kwargs={"category_slug": "everyday-irish-cooking"})
        )
        detail_response = self.client.get(self.recipe.get_absolute_url())

        self.assertNotContains(list_response, self.recipe.title)
        self.assertNotContains(category_response, self.recipe.title)
        self.assertEqual(detail_response.status_code, 404)

    def test_recipe_owner_and_moderator_can_view_draft_recipe(self):
        self.recipe.status = Recipe.Status.DRAFT
        self.recipe.save(update_fields=["status"])

        self.client.force_login(self.author_user)
        owner_response = self.client.get(self.recipe.get_absolute_url())
        self.assertEqual(owner_response.status_code, 200)

        self.client.force_login(self.moderator_user)
        moderator_response = self.client.get(self.recipe.get_absolute_url())
        self.assertEqual(moderator_response.status_code, 200)

    def test_draft_content_is_not_in_moderation_panel(self):
        self.recipe.status = Recipe.Status.DRAFT
        self.recipe.save(update_fields=["status"])
        Article.objects.create(
            title="Draft Panel Article",
            slug="draft-panel-article",
            author=self.author,
            body="Draft body.",
            published=date(2026, 5, 21),
            status=Article.Status.DRAFT,
        )
        self.client.force_login(self.moderator_user)

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.recipe.title)
        self.assertNotContains(response, "Draft Panel Article")

    def test_moderation_panel_excludes_greenbear_recipe_and_article_items(self):
        owner_recipe = Recipe.objects.create(
            title="Owner Pending Recipe",
            slug="owner-pending-recipe",
            author=self.greenbear_author,
            ingredients="Potatoes",
            method="Boil them.",
            status=Recipe.Status.PENDING,
        )
        owner_article = Article.objects.create(
            title="Owner Pending Article",
            slug="owner-pending-article",
            author=self.greenbear_author,
            body="Owner article.",
            published=date(2026, 5, 21),
            status=Article.Status.PENDING,
        )
        normal_article = Article.objects.create(
            title="Author Pending Article",
            slug="author-pending-article",
            author=self.author,
            body="Author article.",
            published=date(2026, 5, 21),
            status=Article.Status.PENDING,
        )
        self.client.force_login(self.moderator_user)

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertNotIn(owner_recipe, response.context["pending_recipes"])
        self.assertNotIn(owner_article, response.context["pending_articles"])
        self.assertIn(self.recipe, response.context["pending_recipes"])
        self.assertIn(normal_article, response.context["pending_articles"])

    def test_author_can_submit_draft_recipe_for_review(self):
        self.recipe.status = Recipe.Status.DRAFT
        self.recipe.save(update_fields=["status"])
        self.client.force_login(self.author_user)

        response = self.client.post(
            reverse("recipes:recipe_edit", kwargs={"slug": self.recipe.slug}),
            {**self.recipe_payload(), "action": "submit_review"},
        )

        self.recipe.refresh_from_db()
        self.assertRedirects(response, self.recipe.get_absolute_url())
        self.assertEqual(self.recipe.status, Recipe.Status.PENDING)

    def test_greenbear_submit_draft_recipe_publishes_without_review(self):
        owner_recipe = Recipe.objects.create(
            title="GreenBear Draft Recipe",
            slug="greenbear-draft-recipe",
            author=self.greenbear_author,
            ingredients="Potatoes",
            method="Boil them.",
            status=Recipe.Status.DRAFT,
        )
        self.client.force_login(self.greenbear_user)

        response = self.client.post(
            reverse("recipes:recipe_edit", kwargs={"slug": owner_recipe.slug}),
            {**self.recipe_payload(title="GreenBear Published Recipe"), "action": "submit_review"},
        )

        owner_recipe.refresh_from_db()
        self.assertRedirects(response, owner_recipe.get_absolute_url())
        self.assertEqual(owner_recipe.status, Recipe.Status.APPROVED)

    def test_author_can_save_needs_changes_recipe_as_draft_and_keep_note(self):
        self.recipe.status = Recipe.Status.NEEDS_CHANGES
        self.recipe.moderation_note = "Add more method detail."
        self.recipe.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.author_user)

        self.client.post(
            reverse("recipes:recipe_edit", kwargs={"slug": self.recipe.slug}),
            {**self.recipe_payload(), "action": "save_draft"},
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.DRAFT)
        self.assertEqual(self.recipe.moderation_note, "Add more method detail.")

    def test_author_can_submit_rejected_recipe_for_review_and_keep_note(self):
        self.recipe.status = Recipe.Status.REJECTED
        self.recipe.moderation_note = "Rejected note."
        self.recipe.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.author_user)

        self.client.post(
            reverse("recipes:recipe_edit", kwargs={"slug": self.recipe.slug}),
            {**self.recipe_payload(), "action": "submit_review"},
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.PENDING)
        self.assertEqual(self.recipe.moderation_note, "Rejected note.")

    def test_approved_recipe_cannot_be_saved_as_draft_by_author(self):
        self.recipe.status = Recipe.Status.APPROVED
        self.recipe.save(update_fields=["status"])
        self.client.force_login(self.author_user)

        self.client.post(
            reverse("recipes:recipe_edit", kwargs={"slug": self.recipe.slug}),
            {**self.recipe_payload(), "action": "save_draft"},
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.PENDING)

    def test_draft_recipe_cannot_be_rated_or_commented_by_public(self):
        self.recipe.status = Recipe.Status.DRAFT
        self.recipe.save(update_fields=["status"])
        reader = get_user_model().objects.create_user(username="draft-reader", password="pass")

        rating_response = self.client.post(
            reverse("recipes:submit_recipe_rating", args=[self.recipe.slug]),
            {"value": 5},
        )
        self.client.force_login(reader)
        comment_response = self.client.post(
            reverse("recipes:submit_recipe_comment", args=[self.recipe.slug]),
            {"content": "Looks good.", "website": ""},
        )

        self.assertEqual(rating_response.status_code, 404)
        self.assertEqual(comment_response.status_code, 404)

    def test_recipe_reject_without_note_is_blocked(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "reject"},
            follow=True,
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.PENDING)
        self.assertContains(response, "rejection note is required")

    def test_recipe_reject_saves_tracking_fields(self):
        self.client.force_login(self.moderator_user)

        self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "reject", "moderation_note": "Add more steps to the method."},
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.REJECTED)
        self.assertEqual(self.recipe.moderation_note, "Add more steps to the method.")
        self.assertEqual(self.recipe.moderated_by, self.moderator_user)
        self.assertIsNotNone(self.recipe.moderated_at)

    def test_recipe_request_changes_saves_tracking_fields(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "request_changes", "moderation_note": "Add clearer method steps."},
        )

        self.recipe.refresh_from_db()
        self.assertRedirects(response, self.recipe.get_absolute_url())
        self.assertEqual(self.recipe.status, Recipe.Status.NEEDS_CHANGES)
        self.assertEqual(self.recipe.moderation_note, "Add clearer method steps.")
        self.assertEqual(self.recipe.moderated_by, self.moderator_user)
        self.assertIsNotNone(self.recipe.moderated_at)

    def test_recipe_request_changes_without_note_is_blocked(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "request_changes"},
            follow=True,
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.PENDING)
        self.assertIsNone(self.recipe.moderated_by)
        self.assertIsNone(self.recipe.moderated_at)
        self.assertContains(response, "moderation note is required")

    def test_recipe_approve_clears_moderation_note(self):
        self.recipe.status = Recipe.Status.REJECTED
        self.recipe.moderation_note = "Old note."
        self.recipe.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.moderator_user)

        self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "approve"},
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.APPROVED)
        self.assertEqual(self.recipe.moderation_note, "")
        self.assertEqual(self.recipe.moderated_by, self.moderator_user)
        self.assertIsNotNone(self.recipe.moderated_at)

    def test_recipe_approve_after_needs_changes_clears_note(self):
        self.recipe.status = Recipe.Status.NEEDS_CHANGES
        self.recipe.moderation_note = "Add clearer method steps."
        self.recipe.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.moderator_user)

        self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "approve"},
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.APPROVED)
        self.assertEqual(self.recipe.moderation_note, "")

    def test_recipe_reject_and_message_saves_note(self):
        from messaging.models import Message
        self.client.force_login(self.moderator_user)

        self.client.post(
            reverse("messaging:send_message"),
            {
                "action": "reject_and_message",
                "recipient_id": self.author_user.pk,
                "recipe_id": self.recipe.pk,
                "subject": f"Your recipe: {self.recipe.title}",
                "body": "The method needs clearer steps.",
                "next": self.recipe.get_absolute_url(),
            },
        )

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.Status.REJECTED)
        self.assertEqual(self.recipe.moderation_note, "The method needs clearer steps.")
        self.assertEqual(self.recipe.moderated_by, self.moderator_user)
        self.assertIsNotNone(self.recipe.moderated_at)

    def test_recipe_rejection_note_shown_to_author(self):
        self.recipe.status = Recipe.Status.REJECTED
        self.recipe.moderation_note = "Please add serving suggestions."
        self.recipe.moderated_by = self.moderator_user
        self.recipe.save(update_fields=["status", "moderation_note", "moderated_by"])
        self.client.force_login(self.author_user)

        response = self.client.get(self.recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please add serving suggestions.")
        self.assertContains(response, "Rejection note")

    def test_recipe_rejection_note_hidden_from_public(self):
        self.recipe.status = Recipe.Status.REJECTED
        self.recipe.moderation_note = "Please add serving suggestions."
        self.recipe.save(update_fields=["status", "moderation_note"])

        response = self.client.get(self.recipe.get_absolute_url())

        self.assertEqual(response.status_code, 404)

    def test_needs_changes_recipe_is_hidden_from_public_list_and_direct_url(self):
        self.recipe.status = Recipe.Status.NEEDS_CHANGES
        self.recipe.save(update_fields=["status"])

        list_response = self.client.get(reverse("recipes:recipe_list"))
        detail_response = self.client.get(self.recipe.get_absolute_url())

        self.assertNotContains(list_response, self.recipe.title)
        self.assertEqual(detail_response.status_code, 404)

    def test_recipe_owner_and_moderator_can_view_needs_changes_recipe(self):
        self.recipe.status = Recipe.Status.NEEDS_CHANGES
        self.recipe.moderation_note = "Add serving notes."
        self.recipe.moderated_by = self.moderator_user
        self.recipe.save(update_fields=["status", "moderation_note", "moderated_by"])

        self.client.force_login(self.author_user)
        owner_response = self.client.get(self.recipe.get_absolute_url())
        self.assertEqual(owner_response.status_code, 200)
        self.assertContains(owner_response, "Add serving notes.")
        self.assertContains(owner_response, "Requested changes")

        self.client.force_login(self.moderator_user)
        moderator_response = self.client.get(self.recipe.get_absolute_url())
        self.assertEqual(moderator_response.status_code, 200)
        self.assertContains(moderator_response, "Add serving notes.")

    def test_author_edit_of_needs_changes_recipe_returns_to_pending_and_keeps_note(self):
        self.recipe.status = Recipe.Status.NEEDS_CHANGES
        self.recipe.moderation_note = "Add clearer method steps."
        self.recipe.save(update_fields=["status", "moderation_note"])
        self.client.force_login(self.author_user)

        response = self.client.post(
            reverse("recipes:recipe_edit", kwargs={"slug": self.recipe.slug}),
            self.recipe_payload(),
        )

        self.recipe.refresh_from_db()
        self.assertRedirects(response, self.recipe.get_absolute_url())
        self.assertEqual(self.recipe.status, Recipe.Status.PENDING)
        self.assertEqual(self.recipe.moderation_note, "Add clearer method steps.")

    def test_needs_changes_recipe_cannot_be_rated_or_commented_by_public(self):
        self.recipe.status = Recipe.Status.NEEDS_CHANGES
        self.recipe.save(update_fields=["status"])
        reader = get_user_model().objects.create_user(username="reader", password="pass")

        rating_response = self.client.post(
            reverse("recipes:submit_recipe_rating", args=[self.recipe.slug]),
            {"value": 5},
        )
        self.client.force_login(reader)
        comment_response = self.client.post(
            reverse("recipes:submit_recipe_comment", args=[self.recipe.slug]),
            {"content": "Looks good.", "website": ""},
        )

        self.assertEqual(rating_response.status_code, 404)
        self.assertEqual(comment_response.status_code, 404)

    def test_non_moderator_cannot_moderate_recipe(self):
        self.client.force_login(self.author_user)

        response = self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "approve"},
        )

        self.recipe.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.recipe.status, Recipe.Status.PENDING)

    def test_moderator_can_approve_recipe(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "approve"},
        )

        self.recipe.refresh_from_db()
        self.assertRedirects(response, self.recipe.get_absolute_url())
        self.assertEqual(self.recipe.status, Recipe.Status.APPROVED)

    def test_moderator_can_delete_recipe_from_moderation_endpoint(self):
        self.client.force_login(self.moderator_user)

        response = self.client.post(
            reverse("recipes:moderate_recipe", kwargs={"slug": self.recipe.slug}),
            {"action": "delete"},
        )

        self.assertRedirects(response, reverse("recipes:moderation_panel"))
        self.recipe.refresh_from_db()
        self.assertTrue(self.recipe.is_deleted)


class RecipePhase3AuthorDashboardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="dashchef", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Dash Chef",
            slug="dash-chef",
        )
        self.moderator_user = user_model.objects.create_user(
            username="dashmod",
            password="pass",
            is_staff=True,
        )
        RecipeAuthor.objects.create(user=self.moderator_user, name="Dash Mod", slug="dash-mod")
        self.approved_recipe = Recipe.objects.create(
            title="Approved Dish",
            slug="approved-dish",
            author=self.author,
            ingredients="Flour",
            method="Mix.",
            status=Recipe.Status.APPROVED,
        )
        self.draft_recipe = Recipe.objects.create(
            title="Draft Dish",
            slug="draft-dish",
            author=self.author,
            ingredients="Flour",
            method="Plan.",
            status=Recipe.Status.DRAFT,
        )
        self.pending_recipe = Recipe.objects.create(
            title="Pending Dish",
            slug="pending-dish",
            author=self.author,
            ingredients="Flour",
            method="Wait.",
            status=Recipe.Status.PENDING,
        )
        self.rejected_recipe = Recipe.objects.create(
            title="Rejected Dish",
            slug="rejected-dish",
            author=self.author,
            ingredients="Flour",
            method="Fix.",
            status=Recipe.Status.REJECTED,
            moderation_note="Needs more detail in the method.",
        )
        self.needs_changes_recipe = Recipe.objects.create(
            title="Needs Changes Dish",
            slug="needs-changes-dish",
            author=self.author,
            ingredients="Flour",
            method="Fix.",
            status=Recipe.Status.NEEDS_CHANGES,
            moderation_note="Needs clearer method steps.",
        )
        self.approved_article = Article.objects.create(
            title="Approved Story",
            slug="approved-story",
            author=self.author,
            body="Published article body.",
            published=date(2026, 5, 21),
            status=Article.Status.APPROVED,
        )
        self.draft_article = Article.objects.create(
            title="Draft Story",
            slug="draft-story",
            author=self.author,
            body="Draft article body.",
            published=date(2026, 5, 21),
            status=Article.Status.DRAFT,
        )
        self.pending_article = Article.objects.create(
            title="Pending Story",
            slug="pending-story",
            author=self.author,
            body="Pending article body.",
            published=date(2026, 5, 21),
            status=Article.Status.PENDING,
        )
        self.rejected_article = Article.objects.create(
            title="Rejected Story",
            slug="rejected-story",
            author=self.author,
            body="Rejected article body.",
            published=date(2026, 5, 21),
            status=Article.Status.REJECTED,
            moderation_note="Article needs source attribution.",
        )
        self.needs_changes_article = Article.objects.create(
            title="Needs Changes Story",
            slug="needs-changes-story",
            author=self.author,
            body="Needs changes article body.",
            published=date(2026, 5, 21),
            status=Article.Status.NEEDS_CHANGES,
            moderation_note="Article needs clearer source attribution.",
        )
        from pinch.models import Pinch

        self.approved_bite = Pinch.objects.create(
            title="Approved Bite",
            author=self.author,
            short_description="Published pinch.",
            status=Pinch.Status.APPROVED,
        )
        self.draft_bite = Pinch.objects.create(
            title="Draft Bite",
            author=self.author,
            short_description="Draft pinch.",
            status=Pinch.Status.DRAFT,
        )
        self.pending_bite = Pinch.objects.create(
            title="Pending Bite",
            author=self.author,
            short_description="Pending pinch.",
            status=Pinch.Status.PENDING,
        )
        self.rejected_bite = Pinch.objects.create(
            title="Rejected Bite",
            author=self.author,
            short_description="Rejected pinch.",
            status=Pinch.Status.REJECTED,
            moderation_note="Bite needs clearer attribution.",
        )
        self.needs_changes_bite = Pinch.objects.create(
            title="Needs Changes Bite",
            author=self.author,
            short_description="Needs changes pinch.",
            status=Pinch.Status.NEEDS_CHANGES,
            moderation_note="Bite needs clearer source note.",
        )
        self.url = reverse("recipes:author_detail", kwargs={"slug": self.author.slug})

    def test_owner_sees_all_content_in_dashboard(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.needs_changes_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertIn(self.draft_article, response.context["dashboard_articles"])
        self.assertIn(self.pending_article, response.context["dashboard_articles"])
        self.assertIn(self.needs_changes_article, response.context["dashboard_articles"])
        self.assertIn(self.rejected_article, response.context["dashboard_articles"])
        self.assertIn(self.approved_bite, response.context["dashboard_pinch"])
        self.assertIn(self.draft_bite, response.context["dashboard_pinch"])
        self.assertIn(self.pending_bite, response.context["dashboard_pinch"])
        self.assertIn(self.needs_changes_bite, response.context["dashboard_pinch"])
        self.assertIn(self.rejected_bite, response.context["dashboard_pinch"])

    def test_recipe_card_shows_author_workspace_attention_count(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url)

        self.assertEqual(response.context["recipe_workspace_attention_count"], 4)
        self.assertContains(response, "4 needs attention")

    def test_dashboard_content_filters_render_for_private_dashboard(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url)
        filter_nav = response.content.decode().split('aria-label="Dashboard filters"', 1)[1].split("</nav>", 1)[0]

        self.assertContains(response, 'aria-label="Dashboard filters"')
        self.assertContains(response, "category-nav author-studio-filter-row")
        self.assertContains(response, "category-nav__item category-nav__link")
        self.assertNotIn("All Types", filter_nav)
        self.assertIn("Pinch", filter_nav)
        self.assertIn("Recipes", filter_nav)
        self.assertIn("Articles", filter_nav)
        self.assertIn("Draft", filter_nav)
        self.assertIn("Published", filter_nav)
        self.assertNotIn(">AB<", filter_nav)
        self.assertNotContains(response, 'aria-label="Filter by status"')
        self.assertNotIn("All Statuses", filter_nav)
        self.assertNotIn("Waiting for review", filter_nav)
        self.assertNotIn("Needs changes", filter_nav)
        self.assertNotIn("Rejected", filter_nav)
        self.assertNotContains(response, "author-studio-filters")

    def test_dashboard_content_filter_recipes_returns_only_recipes(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?content=recipes")

        self.assertEqual(response.context["content_filter"], "recipes")
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertEqual(response.context["dashboard_articles"], [])
        self.assertEqual(response.context["dashboard_pinch"], [])
        self.assertContains(response, "content=recipes&amp;status=draft")

    def test_dashboard_content_filter_articles_returns_only_articles(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?content=articles")

        self.assertEqual(response.context["content_filter"], "articles")
        self.assertEqual(response.context["dashboard_recipes"], [])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertIn(self.draft_article, response.context["dashboard_articles"])
        self.assertEqual(response.context["dashboard_pinch"], [])

    def test_dashboard_content_filter_ab_returns_only_pinch(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?content=ab")

        self.assertEqual(response.context["content_filter"], "ab")
        self.assertEqual(response.context["dashboard_recipes"], [])
        self.assertEqual(response.context["dashboard_articles"], [])
        self.assertIn(self.approved_bite, response.context["dashboard_pinch"])
        self.assertIn(self.draft_bite, response.context["dashboard_pinch"])

    def test_dashboard_content_filter_preserves_status_filter(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?content=recipes&status=draft")

        self.assertEqual(response.context["content_filter"], "recipes")
        self.assertEqual(response.context["status_filter"], "draft")
        self.assertIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertEqual(response.context["dashboard_articles"], [])
        self.assertEqual(response.context["dashboard_pinch"], [])
        self.assertContains(response, "content=articles&amp;status=draft")
        self.assertContains(response, "content=recipes")

    def test_public_content_filter_is_ignored(self):
        response = self.client.get(self.url + "?content=recipes")

        self.assertEqual(response.context["content_filter"], "")
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotContains(response, "author-studio-filters")

    def test_author_dashboard_url_renders_owner_cabinet(self):
        self.client.force_login(self.author_user)

        response = self.client.get(reverse("recipes:author_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["author"], self.author)
        self.assertTrue(response.context["private_dashboard"])
        self.assertContains(response, "Author Dashboard")
        self.assertContains(response, reverse("recipes:recipe_create"))
        self.assertContains(response, reverse("articles:article_create"))
        self.assertContains(response, reverse("pinch:create"))
        hero = response.content.decode().split("<section class=\"hero", 1)[1].split("</section>", 1)[0]
        self.assertNotIn("hero-author-cabinet", hero)
        self.assertIn("Create Recipe", hero)
        self.assertIn("Create Article", hero)
        self.assertIn("Create Pinch", hero)
        self.assertIn("Edit Profile", hero)
        self.assertLess(hero.index("Create Pinch"), hero.index("Create Recipe"))
        self.assertLess(hero.index("Create Recipe"), hero.index("Create Article"))
        self.assertLess(hero.index("Create Article"), hero.index("Edit Profile"))
        self.assertNotIn("Explore Recipes", hero)
        self.assertNotIn("Read Articles", hero)

    def test_author_dashboard_links_to_my_collection(self):
        SavedRecipe.objects.create(user=self.author_user, recipe=self.approved_recipe)
        self.client.force_login(self.author_user)

        response = self.client.get(reverse("recipes:author_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["collection_count"], 1)
        self.assertContains(response, "My Collection")
        self.assertContains(response, reverse("collection:my_collection"))

    def test_dashboard_uses_author_facing_status_labels_and_view_links(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url)

        self.assertContains(response, ">Waiting for review</span>", html=False)
        self.assertContains(response, ">Published</span>", html=False)
        self.assertContains(response, self.approved_recipe.get_absolute_url())
        self.assertContains(response, self.approved_article.get_absolute_url())

    def test_greenbear_dashboard_hides_moderation_only_status_filters(self):
        greenbear_user = get_user_model().objects.create_user(username="greenbear", password="pass")
        greenbear_author, _created = RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={"user": greenbear_user, "name": "GreenBear"},
        )
        greenbear_url = reverse("recipes:author_detail", kwargs={"slug": greenbear_author.slug})
        self.client.force_login(greenbear_user)

        response = self.client.get(greenbear_url)

        self.assertEqual(
            tuple(filter_key for filter_key, _status_value, _label in response.context["dashboard_status_filters"]),
            ("draft", "approved"),
        )
        self.assertContains(response, "Content Dashboard")
        self.assertContains(response, "All")
        self.assertContains(response, "Draft")
        self.assertContains(response, "Published")
        self.assertNotContains(response, "Waiting for review")
        self.assertNotContains(response, "Needs changes")
        self.assertNotContains(response, "Rejected")

        filtered_response = self.client.get(greenbear_url + "?status=pending")
        self.assertEqual(filtered_response.context["status_filter"], "")

    def test_dashboard_recipe_rows_include_edit_and_delete_actions(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url)

        for recipe in (
            self.approved_recipe,
            self.draft_recipe,
            self.pending_recipe,
            self.needs_changes_recipe,
            self.rejected_recipe,
        ):
            self.assertContains(response, reverse("recipes:recipe_edit", kwargs={"slug": recipe.slug}))
            self.assertContains(response, reverse("recipes:recipe_delete", kwargs={"slug": recipe.slug}))

    def test_public_visitor_sees_approved_content_only(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.needs_changes_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.draft_article, response.context["dashboard_articles"])
        self.assertNotIn(self.pending_article, response.context["dashboard_articles"])
        self.assertNotIn(self.needs_changes_article, response.context["dashboard_articles"])
        self.assertNotIn(self.rejected_article, response.context["dashboard_articles"])
        self.assertContains(response, "Approved Dish")
        self.assertContains(response, "Approved Story")
        self.assertNotContains(response, "Draft Dish")
        self.assertNotContains(response, "Draft Story")
        self.assertNotContains(response, "Pending Dish")
        self.assertNotContains(response, "Needs Changes Dish")
        self.assertNotContains(response, "Rejected Dish")
        self.assertNotContains(response, "Pending Story")
        self.assertNotContains(response, "Needs Changes Story")
        self.assertNotContains(response, "Rejected Story")
        self.assertNotContains(response, "Content Dashboard")
        self.assertNotContains(response, "author-studio-filters")
        self.assertNotContains(response, reverse("recipes:recipe_edit", kwargs={"slug": self.approved_recipe.slug}))
        self.assertNotContains(response, reverse("articles:article_edit", kwargs={"slug": self.approved_article.slug}))

    def test_moderator_sees_all_content_in_dashboard(self):
        self.client.force_login(self.moderator_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.needs_changes_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertIn(self.draft_article, response.context["dashboard_articles"])
        self.assertIn(self.pending_article, response.context["dashboard_articles"])
        self.assertIn(self.needs_changes_article, response.context["dashboard_articles"])
        self.assertIn(self.rejected_article, response.context["dashboard_articles"])

    def test_rejection_note_visible_to_owner_in_dashboard(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url)

        self.assertContains(response, "Needs more detail in the method.")
        self.assertContains(response, "Needs clearer method steps.")
        self.assertContains(response, "Article needs source attribution.")
        self.assertContains(response, "Article needs clearer source attribution.")

    def test_rejection_note_not_visible_to_public(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, "Needs more detail in the method.")
        self.assertNotContains(response, "Needs clearer method steps.")
        self.assertNotContains(response, "Article needs source attribution.")
        self.assertNotContains(response, "Article needs clearer source attribution.")

    def test_status_filter_pending_returns_only_pending(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?status=pending")

        self.assertIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.needs_changes_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.pending_article, response.context["dashboard_articles"])
        self.assertNotIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.draft_article, response.context["dashboard_articles"])
        self.assertNotIn(self.needs_changes_article, response.context["dashboard_articles"])
        self.assertNotIn(self.rejected_article, response.context["dashboard_articles"])
        self.assertIn(self.pending_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.approved_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.draft_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.needs_changes_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.rejected_bite, response.context["dashboard_pinch"])

    def test_status_filter_needs_changes_returns_only_needs_changes(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?status=needs_changes")

        self.assertIn(self.needs_changes_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.needs_changes_article, response.context["dashboard_articles"])
        self.assertNotIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.draft_article, response.context["dashboard_articles"])
        self.assertNotIn(self.pending_article, response.context["dashboard_articles"])
        self.assertNotIn(self.rejected_article, response.context["dashboard_articles"])
        self.assertIn(self.needs_changes_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.approved_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.draft_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.pending_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.rejected_bite, response.context["dashboard_pinch"])

    def test_public_status_filter_cannot_reveal_needs_changes_content(self):
        response = self.client.get(self.url + "?status=needs_changes")

        self.assertEqual(response.context["status_filter"], "")
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.needs_changes_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.needs_changes_article, response.context["dashboard_articles"])
        self.assertNotContains(response, "Needs Changes Dish")
        self.assertNotContains(response, "Needs Changes Story")

    def test_status_filter_draft_returns_only_draft(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?status=draft")

        self.assertIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.draft_article, response.context["dashboard_articles"])
        self.assertNotIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.pending_article, response.context["dashboard_articles"])
        self.assertNotIn(self.rejected_article, response.context["dashboard_articles"])
        self.assertIn(self.draft_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.approved_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.pending_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.rejected_bite, response.context["dashboard_pinch"])

    def test_public_status_filter_cannot_reveal_draft_content(self):
        response = self.client.get(self.url + "?status=draft")

        self.assertEqual(response.context["status_filter"], "")
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.draft_article, response.context["dashboard_articles"])
        self.assertNotContains(response, "Draft Dish")
        self.assertNotContains(response, "Draft Story")

    def test_status_filter_approved_returns_only_approved(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?status=approved")

        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.draft_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.pending_article, response.context["dashboard_articles"])
        self.assertNotIn(self.draft_article, response.context["dashboard_articles"])
        self.assertNotIn(self.rejected_article, response.context["dashboard_articles"])
        self.assertIn(self.approved_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.pending_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.draft_bite, response.context["dashboard_pinch"])
        self.assertNotIn(self.rejected_bite, response.context["dashboard_pinch"])

    def test_invalid_status_filter_is_ignored(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?status=bogus")

        self.assertEqual(response.context["status_filter"], "")
        self.assertEqual(len(response.context["dashboard_recipes"]), 5)
        self.assertEqual(len(response.context["dashboard_articles"]), 5)
        self.assertEqual(len(response.context["dashboard_pinch"]), 5)


class RecipePhase3RelatedArticlesTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        author_user = user_model.objects.create_user(username="artchef", password="pass")
        self.author = RecipeAuthor.objects.create(user=author_user, name="Art Chef", slug="art-chef")
        self.recipe = Recipe.objects.create(
            title="Base Recipe",
            slug="base-recipe",
            author=self.author,
            ingredients="Oats",
            method="Cook.",
            status=Recipe.Status.APPROVED,
        )
        self.approved_article = Article.objects.create(
            title="Related Article",
            slug="related-article",
            author=self.author,
            body="Some content.",
            published=date(2026, 5, 21),
            related_recipe=self.recipe,
            status=Article.Status.APPROVED,
        )
        self.pending_article = Article.objects.create(
            title="Pending Article",
            slug="pending-related-article",
            author=self.author,
            body="Pending content.",
            published=date(2026, 5, 21),
            related_recipe=self.recipe,
            status=Article.Status.PENDING,
        )
        self.draft_article = Article.objects.create(
            title="Draft Article",
            slug="draft-related-article",
            author=self.author,
            body="Draft content.",
            published=date(2026, 5, 21),
            related_recipe=self.recipe,
            status=Article.Status.DRAFT,
        )
        self.needs_changes_article = Article.objects.create(
            title="Needs Changes Article",
            slug="needs-changes-related-article",
            author=self.author,
            body="Needs changes content.",
            published=date(2026, 5, 21),
            related_recipe=self.recipe,
            status=Article.Status.NEEDS_CHANGES,
        )

    def test_approved_related_article_appears_in_context(self):
        response = self.client.get(self.recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.approved_article, response.context["related_articles"])

    def test_pending_related_article_excluded_from_context(self):
        response = self.client.get(self.recipe.get_absolute_url())

        self.assertNotIn(self.pending_article, response.context["related_articles"])
        self.assertNotIn(self.draft_article, response.context["related_articles"])
        self.assertNotIn(self.needs_changes_article, response.context["related_articles"])

    def test_related_articles_section_hidden_when_empty(self):
        self.approved_article.delete()

        response = self.client.get(self.recipe.get_absolute_url())

        self.assertEqual(response.context["related_articles"], [])
        self.assertNotContains(response, "Related Articles")


class RecipeMonth1RelatedRecipesTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        author_user = user_model.objects.create_user(username="relatedchef", password="pass")
        self.author = RecipeAuthor.objects.create(user=author_user, name="Related Chef", slug="related-chef")
        self.recipe = Recipe.objects.create(
            title="Base Boxty",
            slug="base-boxty",
            author=self.author,
            ingredients="Potatoes",
            method="Cook.",
            category=Recipe.Category.TRADITIONAL_IRISH_DISHES,
            status=Recipe.Status.APPROVED,
        )

    def test_related_recipes_include_shared_primary_category(self):
        related = Recipe.objects.create(
            title="Related Colcannon",
            slug="related-colcannon",
            author=self.author,
            ingredients="Potatoes",
            method="Mash.",
            category=Recipe.Category.TRADITIONAL_IRISH_DISHES,
            status=Recipe.Status.APPROVED,
        )

        response = self.client.get(self.recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        related_recipe_objs = [item["recipe"] for item in response.context["related_recipes"]]
        self.assertIn(related, related_recipe_objs)
        self.assertContains(response, "You Might Also Like")
        self.assertContains(response, "Related Colcannon")

    def test_related_recipes_include_shared_additional_category(self):
        related = Recipe.objects.create(
            title="Related Soda Bread",
            slug="related-soda-bread",
            author=self.author,
            ingredients="Flour",
            method="Bake.",
            category=Recipe.Category.BREAD_AND_BAKING,
            status=Recipe.Status.APPROVED,
        )
        RecipeAdditionalCategory.objects.create(
            recipe=related,
            category=Recipe.Category.TRADITIONAL_IRISH_DISHES,
        )

        response = self.client.get(self.recipe.get_absolute_url())

        related_recipe_objs = [item["recipe"] for item in response.context["related_recipes"]]
        self.assertIn(related, related_recipe_objs)

    def test_related_recipes_exclude_self_draft_pending_and_deleted(self):
        draft = Recipe.objects.create(
            title="Draft Match",
            slug="draft-match",
            author=self.author,
            ingredients="Potatoes",
            method="Cook.",
            category=Recipe.Category.TRADITIONAL_IRISH_DISHES,
            status=Recipe.Status.DRAFT,
        )
        pending = Recipe.objects.create(
            title="Pending Match",
            slug="pending-match",
            author=self.author,
            ingredients="Potatoes",
            method="Cook.",
            category=Recipe.Category.TRADITIONAL_IRISH_DISHES,
            status=Recipe.Status.PENDING,
        )
        deleted = Recipe.objects.create(
            title="Deleted Match",
            slug="deleted-match",
            author=self.author,
            ingredients="Potatoes",
            method="Cook.",
            category=Recipe.Category.TRADITIONAL_IRISH_DISHES,
            status=Recipe.Status.APPROVED,
            is_deleted=True,
        )

        response = self.client.get(self.recipe.get_absolute_url())

        related_recipes = response.context["related_recipes"]
        self.assertNotIn(self.recipe, related_recipes)
        self.assertNotIn(draft, related_recipes)
        self.assertNotIn(pending, related_recipes)
        self.assertNotIn(deleted, related_recipes)
        self.assertNotContains(response, "Related Recipes")


class RecipePhase32AltTextTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        author_user = user_model.objects.create_user(username="altchef", password="pass")
        self.author = RecipeAuthor.objects.create(user=author_user, name="Alt Chef", slug="alt-chef")

    def test_hero_image_alt_text_field_saved_and_retrieved(self):
        recipe = Recipe.objects.create(
            title="Alt Text Recipe",
            slug="alt-text-recipe",
            author=self.author,
            ingredients="Flour",
            method="Mix.",
            hero_image_alt_text="A freshly baked loaf on a wooden board",
            status=Recipe.Status.APPROVED,
        )

        recipe.refresh_from_db()
        self.assertEqual(recipe.hero_image_alt_text, "A freshly baked loaf on a wooden board")

    def test_hero_image_alt_text_defaults_to_blank(self):
        recipe = Recipe.objects.create(
            title="No Alt Recipe",
            slug="no-alt-recipe",
            author=self.author,
            ingredients="Flour",
            method="Mix.",
            status=Recipe.Status.APPROVED,
        )

        self.assertEqual(recipe.hero_image_alt_text, "")

    def test_hero_image_alt_text_in_authoring_form_fields(self):
        self.assertIn("hero_image_alt_text", RecipeAuthoringForm.Meta.fields)

    def test_gallery_step_alt_returns_value_for_matching_step(self):
        post_data = {"gallery_step_1_alt": "Step 1 alt", "gallery_step_2_alt": "Step 2 alt"}

        self.assertEqual(_gallery_step_alt(post_data, 1), "Step 1 alt")
        self.assertEqual(_gallery_step_alt(post_data, 2), "Step 2 alt")

    def test_gallery_step_alt_returns_empty_for_missing_step(self):
        self.assertEqual(_gallery_step_alt({}, 5), "")

    def test_gallery_step_rows_returns_at_least_three_rows_with_no_recipe(self):
        rows = _gallery_step_rows()

        self.assertGreaterEqual(len(rows), 3)
        self.assertEqual(rows[0]["step"], 1)
        self.assertIsNone(rows[0]["image"])

    def test_gallery_step_rows_includes_existing_images_at_correct_step(self):
        recipe = Recipe.objects.create(
            title="Gallery Recipe",
            slug="gallery-recipe",
            author=self.author,
            ingredients="Oats",
            method="Cook.",
            status=Recipe.Status.APPROVED,
        )
        from .models import RecipeImage
        img = RecipeImage.objects.create(
            recipe=recipe,
            sort_order=2,
            alt_text="Step 2 photo",
        )

        rows = _gallery_step_rows(recipe)

        step2 = next(r for r in rows if r["step"] == 2)
        self.assertEqual(step2["image"].pk, img.pk)

    def test_update_recipe_gallery_order_saves_dragged_order(self):
        from .models import RecipeImage

        recipe = Recipe.objects.create(
            title="Dragged Gallery Recipe",
            slug="dragged-gallery-recipe",
            author=self.author,
            ingredients="Oats",
            method="Cook.",
            status=Recipe.Status.APPROVED,
        )
        first = RecipeImage.objects.create(recipe=recipe, sort_order=1)
        second = RecipeImage.objects.create(recipe=recipe, sort_order=2)
        third = RecipeImage.objects.create(recipe=recipe, sort_order=3)
        post_data = QueryDict("", mutable=True)
        post_data.update({"recipe_gallery_image_order": str(third.pk)})
        post_data.update({"recipe_gallery_image_order": str(first.pk)})
        post_data.update({"recipe_gallery_image_order": str(second.pk)})

        _update_recipe_gallery_order(recipe, post_data)

        ordered_ids = list(
            recipe.gallery_images.order_by("sort_order", "id").values_list("pk", flat=True)
        )
        self.assertEqual(ordered_ids, [third.pk, first.pk, second.pk])


@skip("Dev-only tests: static and media serving via culineire.localhost is not available on the production server")
class DevelopmentMediaServingTests(TestCase):
    def test_development_static_is_served_locally(self):
        response = self.client.get(
            "/static/images/hero.jpg",
            HTTP_HOST="culineire.localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "image/jpeg")

    def test_development_homepage_media_is_served_locally(self):
        response = self.client.get(
            "/media/recipes/GreenBear/Farmhouse%20Farls/cover.png",
            HTTP_HOST="culineire.localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "image/png")


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class RecipeSoftDeleteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner_user = User.objects.create_user(username="rsd_owner", password="pass")
        self.owner_author = RecipeAuthor.objects.create(
            user=self.owner_user, name="RSD Owner", slug="rsd-owner"
        )
        self.other_user = User.objects.create_user(username="rsd_other", password="pass")
        self.other_author = RecipeAuthor.objects.create(
            user=self.other_user, name="RSD Other", slug="rsd-other"
        )
        self.moderator_user = User.objects.create_user(
            username="rsd_mod", password="pass", is_staff=True
        )
        self.moderator_author = RecipeAuthor.objects.create(
            user=self.moderator_user, name="RSD Mod", slug="rsd-mod"
        )
        self.recipe = Recipe.objects.create(
            title="Soft Delete Recipe",
            slug="soft-delete-recipe",
            author=self.owner_author,
            status=Recipe.Status.APPROVED,
            ingredients="x",
            method="y",
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
        )

    # ── Soft delete mechanics ────────────────────────────────────────────────

    def test_author_delete_view_soft_deletes(self):
        self.client.force_login(self.owner_user)
        self.client.post(
            reverse("recipes:recipe_delete", kwargs={"slug": self.recipe.slug})
        )
        self.recipe.refresh_from_db()
        self.assertTrue(self.recipe.is_deleted)
        self.assertIsNotNone(self.recipe.deleted_at)
        self.assertEqual(self.recipe.deleted_by, self.owner_user)

    def test_moderator_delete_view_soft_deletes(self):
        self.client.force_login(self.moderator_user)
        self.client.post(
            reverse("recipes:recipe_delete", kwargs={"slug": self.recipe.slug})
        )
        self.recipe.refresh_from_db()
        self.assertTrue(self.recipe.is_deleted)
        self.assertEqual(self.recipe.deleted_by, self.moderator_user)

    def test_soft_delete_helper_sets_all_fields(self):
        _soft_delete_recipe(self.recipe, self.owner_user)
        self.recipe.refresh_from_db()
        self.assertTrue(self.recipe.is_deleted)
        self.assertIsNotNone(self.recipe.deleted_at)
        self.assertEqual(self.recipe.deleted_by, self.owner_user)

    def test_non_owner_cannot_delete_others_recipe(self):
        self.client.force_login(self.other_user)
        self.client.post(
            reverse("recipes:recipe_delete", kwargs={"slug": self.recipe.slug})
        )
        self.recipe.refresh_from_db()
        self.assertFalse(self.recipe.is_deleted)

    # ── Public visibility ────────────────────────────────────────────────────

    def test_deleted_approved_recipe_hidden_from_list(self):
        _soft_delete_recipe(self.recipe, self.owner_user)
        response = self.client.get(reverse("recipes:recipe_list"))
        recipe_slugs = [r.slug for r in response.context.get("default_recent_recipes", [])]
        self.assertNotIn(self.recipe.slug, recipe_slugs)

    def test_deleted_approved_recipe_direct_url_returns_410(self):
        _soft_delete_recipe(self.recipe, self.owner_user)
        response = self.client.get(self.recipe.get_absolute_url())
        self.assertEqual(response.status_code, 410)

    def test_deleted_recipe_hidden_from_category_page(self):
        self.recipe.category = Recipe.Category.DINNER
        self.recipe.save(update_fields=["category"])
        _soft_delete_recipe(self.recipe, self.owner_user)
        response = self.client.get(
            reverse("recipes:category_detail", kwargs={"category_slug": "dinner"})
        )
        recipe_slugs = [r.slug for r in response.context.get("recipes", [])]
        self.assertNotIn(self.recipe.slug, recipe_slugs)

    def test_deleted_recipe_excluded_from_sitemap(self):
        _soft_delete_recipe(self.recipe, self.owner_user)
        response = self.client.get(reverse("sitemap_xml"))
        self.assertNotIn(self.recipe.slug, response.content.decode())

    def test_deleted_recipe_excluded_from_public_author_profile(self):
        _soft_delete_recipe(self.recipe, self.owner_user)
        response = self.client.get(
            reverse("recipes:author_detail", kwargs={"slug": self.owner_author.slug})
        )
        dashboard_recipes = response.context.get("dashboard_recipes", [])
        self.assertNotIn(self.recipe, dashboard_recipes)

    def test_deleted_recipe_cannot_be_rated(self):
        _soft_delete_recipe(self.recipe, self.owner_user)
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse("recipes:submit_recipe_rating", kwargs={"slug": self.recipe.slug}),
            {"value": 5},
        )
        self.assertEqual(response.status_code, 404)

    def test_deleted_recipe_cannot_be_commented_on(self):
        _soft_delete_recipe(self.recipe, self.owner_user)
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse("recipes:submit_recipe_comment", kwargs={"slug": self.recipe.slug}),
            {"body": "Great recipe!"},
        )
        self.assertEqual(response.status_code, 404)

    def test_deleted_recipe_cannot_be_saved_to_collection(self):
        _soft_delete_recipe(self.recipe, self.owner_user)
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse("collection:add_recipe", kwargs={"slug": self.recipe.slug}),
            {"next": "/"},
        )
        self.assertEqual(response.status_code, 404)

    # ── Non-deleted content unaffected ───────────────────────────────────────

    def test_approved_not_deleted_recipe_still_public(self):
        response = self.client.get(self.recipe.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_approved_not_deleted_recipe_in_list(self):
        response = self.client.get(reverse("recipes:recipe_list"))
        slugs = [r.slug for r in response.context.get("default_recent_recipes", [])]
        self.assertIn(self.recipe.slug, slugs)


class RecipeSourceDisplayTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        author_user = user_model.objects.create_user(username="sourcechef", password="pass")
        self.author = RecipeAuthor.objects.create(user=author_user, name="Source Chef", slug="source-chef")

    def test_ai_assisted_recipe_does_not_show_original_source_link(self):
        recipe = Recipe.objects.create(
            title="AI Stew",
            slug="ai-stew",
            author=self.author,
            ingredients="Potatoes",
            method="Simmer.",
            status=Recipe.Status.APPROVED,
            source_type=Recipe.SourceType.AI_ASSISTED,
            source_title="Created specially for CulinEire",
            source_author="CulinEire Creative Studio",
            source_url="https://www.culineire.ie/",
            source_note="An original CulinEire recipe.",
        )

        response = self.client.get(recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Created specially for CulinEire")
        self.assertContains(response, "Enjoyed it?")
        self.assertContains(response, "Buy a coffee")
        self.assertContains(response, "https://buymeacoffee.com/bearcave")
        self.assertNotContains(response, "View original source")

    def test_external_recipe_source_still_shows_original_source_link(self):
        recipe = Recipe.objects.create(
            title="Cookbook Stew",
            slug="cookbook-stew",
            author=self.author,
            ingredients="Potatoes",
            method="Simmer.",
            status=Recipe.Status.APPROVED,
            source_type=Recipe.SourceType.WEBSITE,
            source_title="Original Stew",
            source_url="https://example.com/original-stew",
            source_note="Adapted with credit.",
        )

        response = self.client.get(recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View original source")
        self.assertContains(response, "https://example.com/original-stew")
        self.assertNotContains(response, "Buy a coffee")


class GenerateRecipeCommandTests(TestCase):
    def setUp(self):
        self.author_user = get_user_model().objects.create_user(username="ai-author", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="AI Author",
            slug="ai-author",
        )

    @staticmethod
    def generated_payload(**overrides):
        payload = {
            "title": "Irish Colcannon",
            "short_description": "A buttery potato and cabbage draft.",
            "category": "Traditional Irish Dishes",
            "difficulty": "medium",
            "prep_time_minutes": 15,
            "cook_time_minutes": 25,
            "servings": 4,
            "calories": None,
            "ingredients": ["500g potatoes", "Cabbage", "Butter"],
            "method": ["Boil the potatoes.", "Fold in cabbage and butter."],
            "tips": "Serve hot.",
            "irish_context": "A home-style Irish potato dish.",
            "author_commentary": "Draft for review.",
            "allergens": ["milk", "unknown"],
            "source_note": "",
        }
        payload.update(overrides)
        return payload

    @patch("recipes.management.commands.generate_recipe._call_anthropic")
    def test_generate_recipe_creates_draft_only_with_safety_fields(self, call_anthropic):
        call_anthropic.return_value = self.generated_payload()

        call_command("generate_recipe", "Irish", "Colcannon", author_slug=self.author.slug, no_image=True)

        recipe = Recipe.objects.get(title="Irish Colcannon")
        self.assertEqual(recipe.status, Recipe.Status.DRAFT)
        self.assertEqual(recipe.category, Recipe.Category.TRADITIONAL_IRISH_DISHES)
        # Without a generated image the command must not claim any image rights
        # (CLAUDE.md content automation rule); AI_GENERATED is set only after a
        # hero/step image is actually produced.
        self.assertEqual(recipe.image_rights_status, Recipe.ImageRightsStatus.NOT_APPLICABLE)
        self.assertFalse(recipe.hero_image)
        self.assertEqual(recipe.source_type, Recipe.SourceType.AI_ASSISTED)
        self.assertEqual(recipe.source_title, "Created specially for CulinEire")
        self.assertEqual(recipe.source_author, "CulinEire Creative Studio")
        self.assertEqual(recipe.source_url, "https://www.culineire.ie/")
        self.assertIn("An original CulinEire recipe", recipe.source_note)
        self.assertIn("crafted with AI", recipe.source_note)
        self.assertIn("reviewed by our editorial team", recipe.source_note)
        self.assertIn("Free to cook and enjoy at home", recipe.source_note)
        self.assertNotIn("a rating or a kind comment", recipe.source_note)
        self.assertNotIn("Draft", recipe.source_title)
        self.assertNotIn("draft", recipe.source_note.lower())
        self.assertFalse(recipe.confirmed_own_work)
        self.assertEqual(recipe.allergens, "milk")
        self.assertIn("500g potatoes", recipe.ingredients)
        self.assertIn("Boil the potatoes.", recipe.method)

    @patch("recipes.management.commands.generate_recipe._call_anthropic")
    def test_generate_recipe_batch_respects_limit(self, call_anthropic):
        call_anthropic.side_effect = [
            self.generated_payload(title="First Draft"),
            self.generated_payload(title="Second Draft"),
        ]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as batch_file:
            batch_file.write("First Draft\nSecond Draft\nThird Draft\n")
            batch_path = batch_file.name
        try:
            call_command("generate_recipe", batch=batch_path, limit=2, author_slug=self.author.slug)
        finally:
            os.unlink(batch_path)

        self.assertEqual(Recipe.objects.filter(author=self.author).count(), 2)
        self.assertEqual(call_anthropic.call_count, 2)

    @patch("recipes.management.commands.generate_recipe._call_anthropic")
    def test_generate_recipe_can_save_pending_but_never_approved(self, call_anthropic):
        call_anthropic.return_value = self.generated_payload(title="Pending AI Draft")

        call_command("generate_recipe", "Pending AI Draft", author_slug=self.author.slug, status=Recipe.Status.PENDING)

        recipe = Recipe.objects.get(title="Pending AI Draft")
        self.assertEqual(recipe.status, Recipe.Status.PENDING)

    @patch("recipes.management.commands.generate_recipe._call_anthropic")
    def test_generate_recipe_updates_task_with_created_recipe(self, call_anthropic):
        call_anthropic.return_value = self.generated_payload(title="Task Linked Draft")
        task = RecipeGenerationTask.objects.create(
            dish_name="Task Linked Draft",
            author=self.author,
            requested_by=self.author_user,
        )

        call_command(
            "generate_recipe",
            "Task Linked Draft",
            author_slug=self.author.slug,
            task_id=str(task.task_id),
        )

        task.refresh_from_db()
        self.assertEqual(task.status, RecipeGenerationTask.Status.DONE)
        self.assertEqual(task.result_recipe.title, "Task Linked Draft")


class RecipeGenerationTaskViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.moderator_user = user_model.objects.create_user(
            username="task-mod",
            password="pass",
            is_staff=True,
        )
        self.author_user = user_model.objects.create_user(username="task-author", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Task Author",
            slug="task-author",
        )
        RecipeAuthor.objects.create(
            user=self.moderator_user,
            name="Task Moderator",
            slug="task-mod",
        )
        self.client.force_login(self.moderator_user)

    def test_generate_recipe_page_uses_recipe_creation_hero(self):
        response = self.client.get(reverse("recipes:generate_recipe"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hero--recipe-form")
        self.assertContains(response, "hero--recipe-tools")
        self.assertContains(response, "images/hero-recipes")
        self.assertContains(response, "Generate AI Recipe")
        self.assertContains(response, "Create New Recipe")
        self.assertContains(response, "Generate Screen Recipe")
        self.assertContains(response, reverse("recipes:recipe_create"))
        self.assertContains(response, reverse("recipes:recipe_create_from_screenshot"))

    @override_settings(ANTHROPIC_API_KEY="test-key")
    @patch("threading.Thread")
    def test_generate_recipe_ajax_returns_task_id(self, thread_cls):
        response = self.client.post(
            reverse("recipes:generate_recipe"),
            {
                "dish_name": "Task Stew",
                "author_slug": self.author.slug,
                "status": Recipe.Status.PENDING,
                "no_image": "1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["started"])
        self.assertTrue(data["task_id"])
        self.assertTrue(
            RecipeGenerationTask.objects.filter(
                task_id=data["task_id"],
                dish_name="Task Stew",
                author=self.author,
                requested_by=self.moderator_user,
                status=RecipeGenerationTask.Status.RUNNING,
            ).exists()
        )
        thread_cls.assert_called_once()

    def test_generate_recipe_poll_returns_done_task_result(self):
        recipe = Recipe.objects.create(
            title="Generated Stew",
            slug="generated-stew",
            author=self.author,
            ingredients="Potatoes",
            method="Simmer.",
            status=Recipe.Status.PENDING,
        )
        task = RecipeGenerationTask.objects.create(
            dish_name="Generated Stew",
            author=self.author,
            requested_by=self.moderator_user,
            status=RecipeGenerationTask.Status.DONE,
            result_recipe=recipe,
        )

        response = self.client.get(
            reverse("recipes:generate_recipe_poll"),
            {"task_id": str(task.task_id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], recipe.slug)
        self.assertTrue(response.json()["ready"])

    def test_generate_recipe_poll_returns_failed_task_error(self):
        task = RecipeGenerationTask.objects.create(
            dish_name="Broken Stew",
            author=self.author,
            requested_by=self.moderator_user,
            status=RecipeGenerationTask.Status.FAILED,
            error_message="Anthropic API request failed",
        )

        response = self.client.get(
            reverse("recipes:generate_recipe_poll"),
            {"task_id": str(task.task_id)},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["ready"])
        self.assertTrue(data["failed"])
        self.assertEqual(data["error"], "Anthropic API request failed")

    def test_generate_recipe_poll_rejects_other_users_task(self):
        other_user = get_user_model().objects.create_user(
            username="other-mod",
            password="pass",
            is_staff=True,
        )
        task = RecipeGenerationTask.objects.create(
            dish_name="Private Stew",
            author=self.author,
            requested_by=other_user,
            status=RecipeGenerationTask.Status.RUNNING,
        )

        response = self.client.get(
            reverse("recipes:generate_recipe_poll"),
            {"task_id": str(task.task_id)},
        )

        self.assertEqual(response.status_code, 404)

    def test_generate_recipe_poll_marks_stale_running_task_failed(self):
        task = RecipeGenerationTask.objects.create(
            dish_name="Stale Stew",
            author=self.author,
            requested_by=self.moderator_user,
            status=RecipeGenerationTask.Status.RUNNING,
        )
        RecipeGenerationTask.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(minutes=21)
        )

        response = self.client.get(
            reverse("recipes:generate_recipe_poll"),
            {"task_id": str(task.task_id)},
        )

        task.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["failed"])
        self.assertEqual(task.status, RecipeGenerationTask.Status.FAILED)


class RecipeStudioModeratorAccessTests(TestCase):
    """AI recipe tools (Studio + AI Fill) are available to all moderators,
    not only Django staff/superusers (v2.5.174)."""

    def setUp(self):
        user_model = get_user_model()
        # Non-staff, non-superuser author who IS a moderator via bearseeker.
        self.mod_user = user_model.objects.create_user(
            username="mod-bearseeker", email="mod@example.com", password="pass",
        )
        RecipeAuthor.objects.create(
            user=self.mod_user, name="Mod Bearseeker", slug="mod-bearseeker",
            has_bearseeker_privileges=True,
        )
        # Regular author with no moderator privileges.
        self.plain_user = user_model.objects.create_user(
            username="plain-author", email="plain@example.com", password="pass",
        )
        RecipeAuthor.objects.create(
            user=self.plain_user, name="Plain Author", slug="plain-author",
        )

    def test_moderator_can_open_recipe_studio(self):
        self.client.login(username="mod-bearseeker", password="pass")
        resp = self.client.get(reverse("recipes:recipe_studio"))
        self.assertEqual(resp.status_code, 200)

    def test_regular_author_cannot_open_recipe_studio(self):
        self.client.login(username="plain-author", password="pass")
        resp = self.client.get(reverse("recipes:recipe_studio"))
        self.assertEqual(resp.status_code, 404)

    def test_moderator_ai_fill_is_authorized(self):
        # Not 403 (authorization passes); may 400/502 on missing API key,
        # but must not be the 403 "Not authorized" gate.
        self.client.login(username="mod-bearseeker", password="pass")
        resp = self.client.post(
            reverse("recipes:recipe_studio_ai_fill"),
            data=json.dumps({"dish_name": "Test"}),
            content_type="application/json",
        )
        self.assertNotEqual(resp.status_code, 403)

    def test_regular_author_ai_fill_is_forbidden(self):
        self.client.login(username="plain-author", password="pass")
        resp = self.client.post(
            reverse("recipes:recipe_studio_ai_fill"),
            data=json.dumps({"dish_name": "Test"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(SECURE_SSL_REDIRECT=False)
class ArenaBuildPlanTests(TestCase):
    """Owner-gated arena build board + the START signal to both agents."""

    def setUp(self):
        User = get_user_model()
        self.boss = User.objects.create_user(username="abp-boss", password="pw", is_superuser=True, is_staff=True)

    def test_anonymous_gets_404(self):
        self.assertEqual(self.client.get(reverse("recipes:arena_build_plan")).status_code, 404)

    def test_board_renders_two_lanes_and_start(self):
        self.client.login(username="abp-boss", password="pw")
        resp = self.client.get(reverse("recipes:arena_build_plan"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Arena Build Plan")
        self.assertContains(resp, "Backend")
        self.assertContains(resp, "Frontend")
        self.assertContains(resp, "готово 100%")
        self.assertContains(resp, "START")
        self.assertContains(resp, "Зависимость")

    def test_start_signals_both_agents(self):
        from coworking.models import CoworkingMessage
        self.client.login(username="abp-boss", password="pw")
        resp = self.client.post(reverse("recipes:arena_build_start"), {"stage": "perspective"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(sorted(data["signalled"]), ["bolt", "greenbear"])
        for agent in ("bolt", "greenbear"):
            self.assertTrue(
                CoworkingMessage.objects.filter(
                    to_agent__agent_id=agent, subject__startswith="START stage 8"
                ).exists()
            )

    def test_start_unknown_stage_400(self):
        self.client.login(username="abp-boss", password="pw")
        resp = self.client.post(reverse("recipes:arena_build_start"), {"stage": "nope"})
        self.assertEqual(resp.status_code, 400)
