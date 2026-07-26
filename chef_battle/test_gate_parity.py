from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings

from chef_battle.access import is_battle_visible
from config.context_processors import battle_widget_context
from recipes.models import RecipeAuthor


@override_settings(CHEF_BATTLE_ENABLED=False)
class ChefBattleGateParityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.request_factory = RequestFactory()

        self.plain_author_user = user_model.objects.create_user(
            username="gate-parity-plain-author",
        )
        RecipeAuthor.objects.create(
            user=self.plain_author_user,
            name="Gate Parity Plain Author",
            slug="gate-parity-plain-author",
        )

        self.bearseeker_user = user_model.objects.create_user(
            username="gate-parity-bearseeker",
        )
        RecipeAuthor.objects.create(
            user=self.bearseeker_user,
            name="Gate Parity Bearseeker",
            slug="gate-parity-bearseeker",
            has_bearseeker_privileges=True,
        )

        self.staff_user = user_model.objects.create_user(
            username="gate-parity-staff",
            is_staff=True,
        )

    def test_widget_visibility_matches_page_access(self):
        users = {
            "anonymous": (AnonymousUser(), False),
            "author without privileges": (self.plain_author_user, False),
            "author with has_bearseeker_privileges": (self.bearseeker_user, True),
            "staff": (self.staff_user, True),
        }

        for label, (user, expected) in users.items():
            with self.subTest(user=label):
                request = self.request_factory.get("/")
                request.user = user

                shown = bool(battle_widget_context(request))
                allowed_in = is_battle_visible(request)
                if shown and not allowed_in:
                    direction = "shown the entrance but denied access"
                elif allowed_in and not shown:
                    direction = "allowed access but entrance hidden"
                else:
                    direction = "gates agree"

                self.assertEqual(
                    shown,
                    allowed_in,
                    f"{label}: {direction}",
                )
                self.assertEqual(
                    shown,
                    expected,
                    f"{label}: both gates returned {shown}, expected {expected}",
                )
