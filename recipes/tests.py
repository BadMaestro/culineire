import importlib
import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from articles.models import Article
from .admin import RecipeAdminForm
from .allergens import build_present_allergen_items, parse_selected_allergen_keys, serialize_allergen_keys
from .forms import RecipeCommentForm
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
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        recipe = form.save(commit=False)

        self.assertEqual(recipe.allergens, "milk\ngluten")
        self.assertEqual(recipe.author_commentary, "Best served very hot.")


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

    def test_signup_creates_account_and_logs_user_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newcook",
                "password1": "KitchenTable123!",
                "password2": "KitchenTable123!",
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(get_user_model().objects.filter(username="newcook").exists())
        self.assertIn("_auth_user_id", self.client.session)

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
        self.assertContains(response, reverse("recipes:author_edit"))

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
                "slug": "ciaran-o-kitchen",
                "bio": "Modern Irish cooking notes.",
                "avatar": "",
            },
        )

        author.refresh_from_db()
        self.assertRedirects(response, author.get_absolute_url())
        self.assertEqual(author.name, "Ciaran O Kitchen")
        self.assertEqual(author.slug, "ciaran-o-kitchen")
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
            },
        )

        recipe = Recipe.objects.get(title="Test Kitchen Pie")
        self.assertRedirects(response, recipe.get_absolute_url())
        self.assertEqual(recipe.author, author)

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
            },
        )

        article = Article.objects.get(title="Kitchen Notes")
        self.assertRedirects(response, article.get_absolute_url())
        self.assertEqual(article.author, author)


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
        url = reverse("recipes:submit_recipe_comment", args=[self.recipe.slug])
        payload = {
            "name": "Niamh",
            "content": "This turned out beautifully.",
            "website": "",
        }

        first_response = self.client.post(url, payload)
        second_response = self.client.post(url, payload)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(RecipeComment.objects.filter(recipe=self.recipe).count(), 1)


class SecuritySettingsModuleTests(SimpleTestCase):
    def tearDown(self):
        importlib.reload(importlib.import_module("config.settings"))
        super().tearDown()

    def reload_project_settings(self, **env_overrides):
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
        self.assertFalse(project_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertFalse(project_settings.SECURE_HSTS_PRELOAD)
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
