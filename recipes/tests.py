from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .admin import RecipeAdminForm
from .allergens import build_present_allergen_items, parse_selected_allergen_keys, serialize_allergen_keys
from .forms import RecipeCommentForm
from .models import Recipe, RecipeComment, RecipeRating
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


class RecipeAdminFormTests(SimpleTestCase):
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
    def test_signup_page_renders(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/signup.html")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")


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
