from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .forms import RecipeCommentForm
from .models import Recipe, RecipeComment, RecipeRating
from .views import _build_method_steps, _split_text_lines


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
