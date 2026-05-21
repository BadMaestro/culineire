import importlib
import os
from datetime import date
from unittest import skip
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from articles.models import Article, ArticleImage
from .admin import RecipeAdmin, RecipeAdminForm
from .allergens import build_present_allergen_items, parse_selected_allergen_keys, serialize_allergen_keys
from .forms import RecipeAuthoringForm, RecipeCommentForm
from .models import Recipe, RecipeAuthor, RecipeComment, RecipeRating
from .views import _build_context_paragraphs, _build_ingredient_items, _build_method_steps, _split_text_lines


class RecipeTextHelperTests(SimpleTestCase):
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

    def test_signup_creates_account_and_shows_success(self):
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
        self.assertTemplateUsed(response, "registration/signup_success.html")
        self.assertTrue(get_user_model().objects.filter(username="newcook").exists())

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
        author = RecipeAuthor.objects.create(
            user=self.user,
            name="Ciaran",
            slug="ciaran",
            bio="Irish cooking notes.",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Ciaran")
        self.assertContains(response, author.get_absolute_url())
        self.assertContains(response, reverse("recipes:recipe_create"))
        self.assertContains(response, reverse("articles:article_create"))
        self.assertContains(response, f'{reverse("recipes:recipe_list")}?author={author.slug}')
        self.assertContains(response, f'{reverse("articles:article_list")}?author={author.slug}')

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
        )

    def test_submit_recipe_rating_is_limited_to_one_per_session(self):
        url = reverse("recipes:submit_recipe_rating", args=[self.recipe.slug])

        first_response = self.client.post(url, {"value": 5})
        second_response = self.client.post(url, {"value": 4})

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(RecipeRating.objects.filter(recipe=self.recipe).count(), 1)
        self.assertEqual(RecipeRating.objects.get(recipe=self.recipe).value, 5)

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
        self.recipe = Recipe.objects.create(
            title="Test Recipe",
            slug="test-recipe",
            author=self.author,
            ingredients="Potatoes",
            method="Boil them.",
            status=Recipe.Status.PENDING,
        )

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
        self.assertFalse(Recipe.objects.filter(pk=self.recipe.pk).exists())


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
        self.approved_article = Article.objects.create(
            title="Approved Story",
            slug="approved-story",
            author=self.author,
            body="Published article body.",
            published=date(2026, 5, 21),
            status=Article.Status.APPROVED,
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
        self.url = reverse("recipes:author_detail", kwargs={"slug": self.author.slug})

    def test_owner_sees_all_content_in_dashboard(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertIn(self.pending_article, response.context["dashboard_articles"])
        self.assertIn(self.rejected_article, response.context["dashboard_articles"])

    def test_public_visitor_sees_approved_content_only(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.pending_article, response.context["dashboard_articles"])
        self.assertNotIn(self.rejected_article, response.context["dashboard_articles"])
        self.assertContains(response, "Approved Dish")
        self.assertContains(response, "Approved Story")
        self.assertNotContains(response, "Pending Dish")
        self.assertNotContains(response, "Rejected Dish")
        self.assertNotContains(response, "Pending Story")
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
        self.assertIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertIn(self.pending_article, response.context["dashboard_articles"])
        self.assertIn(self.rejected_article, response.context["dashboard_articles"])

    def test_rejection_note_visible_to_owner_in_dashboard(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url)

        self.assertContains(response, "Needs more detail in the method.")
        self.assertContains(response, "Article needs source attribution.")

    def test_rejection_note_not_visible_to_public(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, "Needs more detail in the method.")
        self.assertNotContains(response, "Article needs source attribution.")

    def test_status_filter_pending_returns_only_pending(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?status=pending")

        self.assertIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.pending_article, response.context["dashboard_articles"])
        self.assertNotIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.rejected_article, response.context["dashboard_articles"])

    def test_status_filter_approved_returns_only_approved(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?status=approved")

        self.assertIn(self.approved_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.pending_recipe, response.context["dashboard_recipes"])
        self.assertNotIn(self.rejected_recipe, response.context["dashboard_recipes"])
        self.assertIn(self.approved_article, response.context["dashboard_articles"])
        self.assertNotIn(self.pending_article, response.context["dashboard_articles"])
        self.assertNotIn(self.rejected_article, response.context["dashboard_articles"])

    def test_invalid_status_filter_is_ignored(self):
        self.client.force_login(self.author_user)

        response = self.client.get(self.url + "?status=bogus")

        self.assertEqual(response.context["status_filter"], "")
        self.assertEqual(len(response.context["dashboard_recipes"]), 3)
        self.assertEqual(len(response.context["dashboard_articles"]), 3)


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

    def test_approved_related_article_appears_in_context(self):
        response = self.client.get(self.recipe.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.approved_article, response.context["related_articles"])

    def test_pending_related_article_excluded_from_context(self):
        response = self.client.get(self.recipe.get_absolute_url())

        self.assertNotIn(self.pending_article, response.context["related_articles"])

    def test_related_articles_section_hidden_when_empty(self):
        self.approved_article.delete()

        response = self.client.get(self.recipe.get_absolute_url())

        self.assertEqual(response.context["related_articles"], [])
        self.assertNotContains(response, "Related Articles")


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
